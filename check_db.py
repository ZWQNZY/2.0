import sqlite3
import os

db_path = os.path.join('instance', 'data.db')
if not os.path.exists(db_path):
    print("Database not found at", db_path)
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(crawler_rule)")
        columns = cursor.fetchall()
        print("Columns in crawler_rule:")
        for col in columns:
            print(col)
    except Exception as e:
        print("Error:", e)
    finally:
        conn.close()
