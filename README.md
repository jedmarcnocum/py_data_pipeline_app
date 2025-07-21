## 🛠️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/jedmarcnocum/py_data_pipeline_app.git
cd py_data_pipeline_app
```

### 2. (Optional) Create and Activate Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # For Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```
---

## ▶️ Run the App Locally

```bash
python app.py
```

Then open your browser and go to:  
[http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 📁 Directory Structure

```
.
├── app.py
├── requirements.txt
├── upload_logs.db              # SQLite database
├── uploads/                    # Uploaded Excel files
├── processed/                  # Generated Excel exports
├── templates/
│   ├── upload.html
│   ├── results.html
│   ├── uploads.html
│   └── address_changes.html
└── README.md
```

---

## 📦 Dependencies

- Flask
- pandas
- openpyxl
- xlsxwriter
- sqlite3

---


## 📤 Excel Format Expectations

### Customers Sheet (raw format):
Each cell in the first column should look like:
```
{C0001_Allison Hill_jillrhodes@miller.com_1975-05-15_908 Jennifer Squares, Sydney NSW 71927_43899.6575694444}
```

### Required Sheets:
- **Transactions**
- **Customers**
- **Products**

---