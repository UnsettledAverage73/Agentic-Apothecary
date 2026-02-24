import sqlite3
import pandas as pd
import os

DB_PATH = "pharmacy.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Products Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        pzn TEXT,
        price REAL,
        package_size TEXT,
        prescription_required TEXT,
        stock_level INTEGER DEFAULT 100
    )
    """)

    # 2. Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT,
        product_name TEXT,
        purchase_date TEXT,
        quantity INTEGER,
        dosage_frequency TEXT,
        FOREIGN KEY (product_name) REFERENCES products (name)
    )
    """)

    # 3. Refill Predictions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS refill_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT,
        product_name TEXT,
        predicted_date TEXT,
        action TEXT,
        FOREIGN KEY (product_name) REFERENCES products (name)
    )
    """)

    conn.commit()
    return conn

def migrate_data():
    conn = init_db()
    
    # Load raw data from Excel/CSV
    products_df = pd.read_excel('db/products-export.xlsx')
    history_df = pd.read_excel('db/Consumer Order History 1.xlsx', header=4)
    
    # Clean and Insert Products
    # Map 'prescription_required' from the history file or default to No
    # For simplicity, we merge to get the Rx flag for each product
    rx_map = history_df[['Product Name', 'Prescription Required']].drop_duplicates()
    
    for _, row in products_df.iterrows():
        rx_req = rx_map[rx_map['Product Name'] == row['product name']]['Prescription Required'].values
        rx_val = rx_req[0] if len(rx_req) > 0 else 'No'
        
        try:
            conn.execute("""
            INSERT INTO products (name, pzn, price, package_size, prescription_required)
            VALUES (?, ?, ?, ?, ?)
            """, (row['product name'], row['pzn'], row['price rec'], row['package size'], rx_val))
        except sqlite3.IntegrityError:
            pass

    # Insert Orders
    for _, row in history_df.iterrows():
        conn.execute("""
        INSERT INTO orders (patient_id, product_name, purchase_date, quantity, dosage_frequency)
        VALUES (?, ?, ?, ?, ?)
        """, (row['Patient ID'], row['Product Name'], str(row['Purchase Date']), row['Quantity'], row['Dosage Frequency']))

    conn.commit()
    print(f"Migration complete. Database created at {DB_PATH}")
    conn.close()

if __name__ == "__main__":
    migrate_data()
