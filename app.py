import os
import pandas as pd
from flask import Flask, request, redirect, render_template, send_file, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'xlsx'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# This function checks if the uploaded file has a valid Excel extension (e.g., .xlsx)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            try:
                xl = pd.read_excel(filepath, sheet_name=None, header=None)
                required_sheets = {'Transactions', 'Customers', 'Products'}
                if not required_sheets.issubset(xl.keys()):
                    flash('File must contain Transactions, Customers, and Products sheets.')
                    return redirect('/')

                transactions = xl['Transactions']
                customers_raw = xl['Customers']
                products = xl['Products']

                # Process Customers sheet
                converted_lines = []
                # This loop skips the header (row 0) and processes customer data from the first column
                for raw_line in customers_raw.iloc[1:, 0]:
                    try:
                        line = str(raw_line).strip()
                        if line.startswith("{") and line.endswith("}"):
                            content = line[1:-1]
                            parts = content.split("_", 5)
                            if len(parts) == 6:
                                converted = "|".join(parts)
                                converted_lines.append(converted.split('|'))
                    except Exception as e:
                        print(f"Error processing line: {raw_line} - {e}")

                # Convert the cleaned list of customer data into a DataFrame with named columns
                customers = pd.DataFrame(converted_lines, columns=['customer_id', 'name', 'email', 'dob', 'address', 'created_date'])

                # Normalize and merge
                transactions.columns = transactions.iloc[0].str.lower()
                transactions = transactions.iloc[1:]
                products.columns = products.iloc[0].str.lower()
                products = products.iloc[1:]
                customers.columns = customers.columns.str.lower()

                # Extract and standardize column headers for transactions and products
                merged = transactions.merge(products, on='product_code')
                merged = merged.merge(customers, left_on='customer_id', right_on='customer_id')
                merged['amount'] = pd.to_numeric(merged['amount'], errors='coerce')

                # Total transaction per customer per category
                category_totals = merged.groupby(['customer_id', 'name', 'category'])['amount'].sum().reset_index()

                # Summarize category_totals to match customer ranking
                category_totals_summary = category_totals.groupby(['customer_id', 'name'])['amount'].sum().reset_index()
                category_totals_summary['rank'] = category_totals_summary['amount'].rank(method='dense', ascending=False).astype(int)
                category_totals_summary = category_totals_summary.sort_values(by='rank')

                # Top spender per category
                top_spenders = category_totals.loc[category_totals.groupby('category')['amount'].idxmax()].reset_index(drop=True)

                # Ranking customers
                customer_ranking = merged.groupby('customer_id').agg({
                    'amount': 'sum',
                    'name': 'first'
                }).reset_index()
                customer_ranking['rank'] = customer_ranking['amount'].rank(method='dense', ascending=False).astype(int)
                customer_ranking = customer_ranking.sort_values(by='rank')

                # Convert category totals into a dict grouped by customer_id
                category_totals_grouped = category_totals.groupby('customer_id').apply(lambda df: df.to_dict(orient='records')).to_dict()

                return render_template('results.html',
                    category_totals=category_totals_summary.to_dict(orient='records'),
                    top_spenders=top_spenders.to_dict(orient='records'),
                    customer_ranking=customer_ranking.to_dict(orient='records'),
                    category_totals_grouped=category_totals_grouped)

            except Exception as e:
                flash(f'Error processing file: {e}')
                return redirect('/')
        else:
            flash('Invalid file type. Please upload an Excel file.')
            return redirect('/')
    return render_template('upload.html')

if __name__ == '__main__':
    app.run(debug=True)
