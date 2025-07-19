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
                xl = pd.read_excel(filepath, sheet_name=None)
                required_sheets = {'Transactions', 'Customers', 'Products'}
                if not required_sheets.issubset(xl.keys()):
                    flash('File must contain Transactions, Customers, and Products sheets.')
                    return redirect('/')

                transactions = xl['Transactions']
                customers_raw = xl['Customers']
                products = xl['Products']

                # Update: use sample string-based rows with {} braces and extract content
                col_name = customers_raw.columns[0]
                cleaned = customers_raw[col_name].astype(str).str.extract(r'\{(.+?)\}')[0]
                parsed = cleaned.str.extract(
                    r'(?P<CustomerID>C\d+)\|(?P<Name>[^|]+)\|(?P<Email>[^|]+@[^|]+\.[^|]+)\|(?P<DOB>\d{4}-\d{2}-\d{2})\|(?P<Address>[^|]+)\|(?P<CreatedDate>\d+\.\d+)'
                )

                if parsed.isnull().any().any():
                    flash('Customer data format incorrect. Check delimiter and fields.')
                    return redirect('/')

                # Convert CreatedDate from Excel float to date
                parsed['CreatedDate'] = pd.to_datetime(parsed['CreatedDate'].astype(float), unit='d', origin='1899-12-30').dt.strftime('%Y-%m-%d')

                customers = parsed

                # Total transaction per customer per product category
                transactions.columns = transactions.columns.str.lower()
                products.columns = products.columns.str.lower()
                customers.columns = customers.columns.str.lower()

                merged = transactions.merge(products, left_on='product_code', right_on='product_code')
                merged = merged.merge(customers, left_on='customer_id', right_on='customerid')
                category_totals = merged.groupby(['customer_id', 'category'])['amount'].sum().reset_index()

                # Top spender per category
                top_spenders = category_totals.loc[category_totals.groupby('category')['amount'].idxmax()].reset_index(drop=True)

                # Ranking customers
                customer_ranking = merged.groupby('customer_id')['amount'].sum().reset_index()
                customer_ranking['rank'] = customer_ranking['amount'].rank(method='dense', ascending=False).astype(int)
                customer_ranking = customer_ranking.sort_values(by='rank')

                return render_template('results.html',
                                       category_totals=category_totals.to_dict(orient='records'),
                                       top_spenders=top_spenders.to_dict(orient='records'),
                                       customer_ranking=customer_ranking.to_dict(orient='records'))

            except Exception as e:
                flash(f'Error processing file: {e}')
                return redirect('/')
        else:
            flash('Invalid file type. Please upload an Excel file.')
            return redirect('/')
    return render_template('upload.html')

if __name__ == '__main__':
    app.run(debug=True)
