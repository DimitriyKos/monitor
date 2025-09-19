import sqlite3

DB_FILE = "db.sqlite"
USER_ID = 186699497  # укажи нужного пользователя

def delete_some_products(user_id, limit=200):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Получаем ID товаров, которые хотим удалить
    cursor.execute(
        "SELECT id FROM products WHERE user_id=? LIMIT ?",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    if not rows:
        print("Нет товаров для удаления.")
        conn.close()
        return

    ids_to_delete = [row[0] for row in rows]
    cursor.execute(
        f"DELETE FROM products WHERE id IN ({','.join('?' for _ in ids_to_delete)})",
        ids_to_delete
    )
    conn.commit()
    conn.close()
    print(f"Удалено {len(ids_to_delete)} товаров для пользователя {user_id}.")

if __name__ == "__main__":
    delete_some_products(USER_ID, limit=200)
