# check_db_full.py
import sqlite3
from tabulate import tabulate

DB_FILE = "db.sqlite"

def print_all_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Получаем список всех таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    if not tables:
        print("В базе нет таблиц.")
        return

    for table in tables:
        table_name = table[0]
        # Пропускаем системные таблицы
        if table_name.startswith("sqlite_"):
            continue

        print(f"\n=== Таблица: {table_name} ===")
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        if rows:
            headers = [description[0] for description in cursor.description]
            print(tabulate(rows, headers=headers, tablefmt="grid"))
        else:
            print("Таблица пустая.")

    conn.close()

if __name__ == "__main__":
    print_all_tables()
