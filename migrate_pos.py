import sqlite3
import os

db_path = 'instance/erp.sqlite'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # Add new columns to OrderTicket
        cursor.execute("ALTER TABLE order_ticket ADD COLUMN payment_method VARCHAR(20) DEFAULT 'card'")
        cursor.execute("ALTER TABLE order_ticket ADD COLUMN total_in_zar FLOAT DEFAULT 0")
        cursor.execute("ALTER TABLE order_ticket ADD COLUMN amount_tendered FLOAT")
        cursor.execute("ALTER TABLE order_ticket ADD COLUMN currency_at_sale VARCHAR(10) DEFAULT 'ZAR'")
        conn.commit()
        print("Migration: Added payment columns to 'order_ticket' table successfully.")
    except sqlite3.OperationalError as e:
        print(f"Migration Notice/Error: {e}")
    finally:
        conn.close()
else:
    print("DB file not found.")
