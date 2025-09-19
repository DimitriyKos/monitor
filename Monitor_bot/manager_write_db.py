# manager_write_db.py
import sqlite3
from datetime import datetime, timedelta

DB_FILE = "db.sqlite"

def write_or_update_products_bulk(user_id: str, products: list):
    """
    Массовое добавление или обновление товаров в БД.
    products: список словарей с ключами title, link, last_price_card, last_price_no_card
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Подготавливаем данные с правильными ключами для колонок в БД
    data_to_insert = [
        (
            user_id,
            p["title"],
            p["link"],
            p.get("last_price_card"),
            p.get("last_price_no_card")
        )
        for p in products
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO products
        (user_id, product_name, product_url, last_price_card, last_price_no_card)
        VALUES (?, ?, ?, ?, ?)
    """, data_to_insert)

    conn.commit()
    conn.close()


def write_or_update_product(user_id: str, product_url: str, product_name: str, price_card: int, price_no_card: int):
    """
    Записывает или обновляет данные товара в базе.
    - При первой проверке: заполняем last_price_card и last_price_no_card
    - При повторных проверках: обновляем last_price_card / last_price_no_card
    - Если прошёл день/неделя: обновляем day_price_* / week_price_*
    """
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=today_start.weekday())

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Получаем текущие значения для обновления
    cursor.execute("""
        SELECT last_price_card, last_price_no_card,
               day_start_time, day_price_card, day_price_no_card,
               week_start_time, week_price_card, week_price_no_card
        FROM products
        WHERE user_id=? AND product_url=?
    """, (user_id, product_url))
    row = cursor.fetchone()

    if not row:
        # Первый запуск: записываем всё
        cursor.execute("""
            INSERT INTO products (
                user_id, product_name, product_url,
                last_check_time, last_price_card, last_price_no_card,
                day_start_time, day_price_card, day_price_no_card,
                week_start_time, week_price_card, week_price_no_card
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, product_name, product_url,
            now, price_card, price_no_card,
            today_start, price_card, price_no_card,
            week_start, price_card, price_no_card
        ))
    else:
        last_card, last_no_card, day_start_str, day_price_card, day_price_no_card, week_start_str, week_price_card, week_price_no_card = row

        # Преобразуем строки времени в datetime
        day_start_time = datetime.strptime(day_start_str, "%Y-%m-%d %H:%M:%S") if day_start_str else today_start
        week_start_time = datetime.strptime(week_start_str, "%Y-%m-%d %H:%M:%S") if week_start_str else week_start

        # Обновляем дневные цены при смене дня
        if now.date() != day_start_time.date():
            day_start_time = today_start
            day_price_card = price_card
            day_price_no_card = price_no_card

        # Обновляем недельные цены при смене недели
        if now.isocalendar()[1] != week_start_time.isocalendar()[1]:
            week_start_time = week_start
            week_price_card = price_card
            week_price_no_card = price_no_card

        # Если дневные/недельные цены пустые, заполняем текущей ценой
        day_price_card = day_price_card if day_price_card is not None else price_card
        day_price_no_card = day_price_no_card if day_price_no_card is not None else price_no_card
        week_price_card = week_price_card if week_price_card is not None else price_card
        week_price_no_card = week_price_no_card if week_price_no_card is not None else price_no_card

        # Обновляем last_price_card и last_price_no_card
        cursor.execute("""
            UPDATE products SET
                product_name=?,
                last_check_time=?,
                last_price_card=?,
                last_price_no_card=?,
                day_start_time=?, day_price_card=?, day_price_no_card=?,
                week_start_time=?, week_price_card=?, week_price_no_card=?
            WHERE user_id=? AND product_url=?
        """, (
            product_name,
            now,
            price_card,
            price_no_card,
            day_start_time, day_price_card, day_price_no_card,
            week_start_time, week_price_card, week_price_no_card,
            user_id, product_url
        ))

    conn.commit()
    conn.close()
