# manager_add.py
import sqlite3
from datetime import datetime
from aiogram import types
from states import user_states  # общий словарь состояний
from typing import Optional
from html import escape
from manager_parsing import download_ozon_html, parse_html_file
from manager_write_db import write_or_update_product

DB_FILE = "db.sqlite"


# --------------------- Функция валидации ссылки ---------------------
def validate_ozon_url(url: str) -> Optional[str]:
    """
    Проверяет, что ссылка корректная для Ozon:
    - должна содержать 'ozon'
    - должна содержать 'product' или сокращённые варианты '/t/' или '/s/'
    Возвращает обрезанную ссылку без параметров после '?' или None если некорректная.
    """
    url = url.strip()
    if not url:
        return None
    url_base = url.split("?")[0]  # убираем все GET-параметры
    if "ozon" not in url_base.lower():
        return None
    if not any(x in url_base.lower() for x in ["product", "/t/", "/s/"]):
        return None
    return url_base


# --------------------- Обработчик кнопки "➕ Добавить товар" ---------------------
async def add_product_handler(message: types.Message):
    """
    Переводит пользователя в режим ожидания ссылки
    """
    user_id = str(message.from_user.id)
    user_states[user_id] = "adding_product"
    await message.answer("📎 Отправьте ссылку на товар, который хотите добавить:")


# --------------------- Обработка полученной ссылки ---------------------
async def process_product_link(message: types.Message):
    """
    Получает ссылку товара от пользователя, сохраняет её в БД,
    сразу парсит и показывает название и цену.
    Поддержка нескольких ссылок сразу.
    """
    user_id = str(message.from_user.id)
    if user_states.get(user_id) != "adding_product":
        return  # Игнорируем, если пользователь не в режиме добавления

    raw_urls = message.text.strip().split()  # поддержка множества ссылок через пробел/новую строку
    if not raw_urls:
        await message.answer("❌ Ссылок не обнаружено. Пожалуйста, отправьте хотя бы одну ссылку.")
        return

    # --- Мгновенный фидбэк пользователю ---
    await message.answer(f"⏳ Получено {len(raw_urls)} ссылок! Начинаем добавление товаров...")

    added_products = []

    for raw_url in raw_urls:
        product_url = validate_ozon_url(raw_url)

        if not product_url:
            await message.answer(f"❌ Некорректная ссылка: {raw_url}")
            continue

        check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # ------------------- Добавляем пользователя -------------------
        cursor.execute("""
            INSERT OR REPLACE INTO users(user_id, chat_id, first_name, last_name, username)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            message.chat.id,
            message.from_user.first_name,
            message.from_user.last_name,
            message.from_user.username
        ))

        # ------------------- Создаем таблицу products -------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                user_id TEXT NOT NULL,
                product_url TEXT NOT NULL,
                product_name TEXT,
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
                PRIMARY KEY(user_id, product_url),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        # ------------------- Проверяем наличие товара -------------------
        cursor.execute("SELECT 1 FROM products WHERE user_id=? AND product_url=?", (user_id, product_url))
        if cursor.fetchone():
            await message.answer(f"⚠️ Товар уже добавлен: {product_url}")
            conn.close()
            continue

        # ------------------- Вставляем новый товар -------------------
        cursor.execute("""
            INSERT INTO products(
                user_id, product_url, product_name, last_check_time,
                last_price_card, last_price_no_card,
                day_start_time, day_price_card, day_price_no_card,
                week_start_time, week_price_card, week_price_no_card,
                html_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            product_url,
            "",  # product_name пока пустой
            check_time,
            None, None,  # last_price_card, last_price_no_card
            check_time, None, None,  # day_start_time, day_price_card, day_price_no_card
            check_time, None, None,  # week_start_time, week_price_card, week_price_no_card
            ""  # html_file
        ))
        conn.commit()
        conn.close()

        # ------------------- Сразу качаем HTML и парсим -------------------
        try:
            html_file = download_ozon_html(product_url, user_id)
            product_name, price_card, price_no_card = parse_html_file(html_file)

            # Записываем в БД
            write_or_update_product(user_id, product_url, product_name, price_card, price_no_card)

            # Запоминаем для ответа пользователю
            added_products.append((product_name, price_card, price_no_card, product_url))

        except Exception as e:
            await message.answer(f"⚠️ Ошибка при обработке {product_url}: {e}")

    # Формируем итоговый ответ
    if added_products:
        response = "✅ Добавлены товары:\n\n"
        for name, price_card, price_no_card, url in added_products:
            safe_name = escape(name) if name else "Без названия"
            pc_text = f"{price_card} ₽ (с картой)" if price_card else "—"
            pnc_text = f"{price_no_card} ₽ (без карты)" if price_no_card else "—"

            response += (
                f"📦 {safe_name}\n"
                f"💳 {pc_text}\n"
                f"🏷 {pnc_text}\n"
                f"🔗 <a href=\"{escape(url)}\">ссылка</a>\n\n"
            )

        # Отправляем в HTML-режиме — это удобно для простых ссылок и не требует экранирования Markdown
        await message.answer(response, parse_mode="HTML")

    # Сбрасываем состояние пользователя
    user_states[user_id] = None
