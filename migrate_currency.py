import sqlite3
import os

db_path = 'instance/erp.sqlite'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # Add the currency column to the users table
        cursor.execute("ALTER TABLE users ADD COLUMN currency VARCHAR(10) DEFAULT 'ZAR'")
        conn.commit()
        print("Migration: Added 'currency' column to 'users' table successfully.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Migration: 'currency' column already exists.")
        else:
            print(f"Migration Error: {e}")
    finally:
        conn.close()
else:
    print("DB file not found. Database will be created on next app run.")
