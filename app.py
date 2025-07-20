import os
import pandas as pd
import sqlite3
from datetime import datetime
from flask import Flask, request, redirect, render_template, send_file, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'xlsx'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Initialize SQLite database for logging uploads and customers
conn = sqlite3.connect('upload_logs.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        timestamp TEXT,
        transactions_rows INTEGER,
        customers_rows INTEGER,
        products_rows INTEGER
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS customers (
        customer_id TEXT PRIMARY KEY,
        name TEXT,
        email TEXT,
        dob TEXT,
        address TEXT,
        created_date TEXT,
        upload_id INTEGER,
        FOREIGN KEY(upload_id) REFERENCES uploads(id)
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS address_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id TEXT,
        old_address TEXT,
        new_address TEXT,
        change_timestamp TEXT,
        upload_id INTEGER,
        FOREIGN KEY(upload_id) REFERENCES uploads(id)
    )
''')
conn.commit()

# Check if the file is an allowed Excel file
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

                # Log upload metadata
                timestamp = datetime.now().isoformat()
                cursor.execute('''
                    INSERT INTO uploads (filename, timestamp, transactions_rows, customers_rows, products_rows)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    filename,
                    timestamp,
                    len(transactions) - 1,
                    len(customers_raw) - 1,
                    len(products) - 1
                ))
                upload_id = cursor.lastrowid
                conn.commit()

                # Process Customers sheet
                converted_lines = []
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

                customers = pd.DataFrame(converted_lines, columns=['customer_id', 'name', 'email', 'dob', 'address', 'created_date'])
                customers.columns = customers.columns.str.lower()

                # Save customers to DB and track address changes
                for _, row in customers.iterrows():
                    existing = cursor.execute('SELECT address FROM customers WHERE customer_id = ?', (row['customer_id'],)).fetchone()
                    if existing and existing[0] != row['address']:
                        cursor.execute('''
                            INSERT INTO address_changes (customer_id, old_address, new_address, change_timestamp, upload_id)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (row['customer_id'], existing[0], row['address'], timestamp, upload_id))
                    cursor.execute('''
                        INSERT OR REPLACE INTO customers (customer_id, name, email, dob, address, created_date, upload_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['customer_id'], row['name'], row['email'], row['dob'], row['address'], row['created_date'], upload_id
                    ))
                conn.commit()

                # Normalize and merge data
                transactions.columns = transactions.iloc[0].str.lower()
                transactions = transactions.iloc[1:]
                products.columns = products.iloc[0].str.lower()
                products = products.iloc[1:]

                merged = transactions.merge(products, on='product_code')
                merged = merged.merge(customers, on='customer_id')
                merged['amount'] = pd.to_numeric(merged['amount'], errors='coerce')

                # Total transaction per customer per category
                category_totals = merged.groupby(['customer_id', 'name', 'category'])['amount'].sum().reset_index()

                # Summary for ranking
                category_totals_summary = category_totals.groupby(['customer_id', 'name'])['amount'].sum().reset_index()
                category_totals_summary['amount'] = category_totals_summary['amount'].round(2)
                category_totals_summary['rank'] = category_totals_summary['amount'].rank(method='dense', ascending=False).astype(int)
                category_totals_summary = category_totals_summary.sort_values(by='rank')

                # Top spenders per category
                top_spenders = category_totals.loc[category_totals.groupby('category')['amount'].idxmax()].reset_index(drop=True)
                top_spenders['amount'] = top_spenders['amount'].round(2)

                # Category detail dict per customer
                category_totals_grouped = category_totals.copy()
                category_totals_grouped['amount'] = category_totals_grouped['amount'].round(2)
                category_totals_grouped = category_totals_grouped.groupby('customer_id').apply(lambda df: df.to_dict(orient='records')).to_dict()

                return render_template('results.html',
                    category_totals=category_totals_summary.to_dict(orient='records'),
                    top_spenders=top_spenders.to_dict(orient='records'),
                    category_totals_grouped=category_totals_grouped,
                    upload_id=upload_id)

            except Exception as e:
                flash(f'Error processing file: {e}')
                return redirect('/')
        else:
            flash('Invalid file type. Please upload an Excel file.')
            return redirect('/')
    return render_template('upload.html')

@app.route('/uploads')
def view_uploads():
    cursor.execute('SELECT * FROM uploads ORDER BY timestamp DESC')
    uploads = cursor.fetchall()
    return render_template('uploads.html', uploads=uploads)

@app.route('/address-changes')
def view_address_changes():
    cursor.execute('SELECT * FROM address_changes ORDER BY change_timestamp DESC')
    changes = cursor.fetchall()
    return render_template('address_changes.html', changes=changes)

if __name__ == '__main__':
    app.run(debug=True)
