import sqlite3
import os

db_path = 'instance/erp.sqlite'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(sales_records)")
        columns = cursor.fetchall()
        print("Columns in sales_records:")
        for col in columns:
            print(col[1])
            
        cursor.execute("PRAGMA table_info(users)")
        print("\nUsers table exists.")
    except Exception as e:
        print(f"Error or table missing: {e}")
    finally:
        conn.close()
else:
    print("DB file not found.")
