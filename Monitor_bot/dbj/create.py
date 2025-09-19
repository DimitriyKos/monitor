# create_db.py
import sqlite3

DB_FILE = "../db.sqlite"

def create_products_table():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            user_id TEXT NOT NULL,
            chat_id TEXT,
            product_name TEXT,
            product_url TEXT,
            last_check_time TEXT,
            last_price_card INTEGER,
            last_price_no_card INTEGER,
            day_start_time TEXT,
            day_price_card INTEGER,
            day_price_no_card INTEGER,
            week_start_time TEXT,
            week_price_card INTEGER,
            week_price_no_card INTEGER,
            html_file TEXT,
            PRIMARY KEY(user_id, html_file)
        )
    """)

    conn.commit()
    conn.close()
    print("Таблица products успешно создана (если её не было)")

if __name__ == "__main__":
    create_products_table()
