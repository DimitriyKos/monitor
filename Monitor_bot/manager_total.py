# manager_total.py
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3

DB_FILE = "db.sqlite"
PAGE_SIZE = 50
MAX_CHARS = 3500


def fetch_products(user_id: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT product_name, product_url, last_price_card, last_price_no_card,
               week_price_card, week_price_no_card
        FROM products
        WHERE user_id=?
    """, (user_id,))
    products = cursor.fetchall()
    conn.close()
    return products


def format_products_chunk(products, start_idx=0):
    text = ""
    last_idx = start_idx
    for idx, row in enumerate(products[start_idx:], start=start_idx + 1):
        name, url, last_card, last_no_card, week_card, week_no_card = row
        change_card = f"{((last_card - week_card) / week_card * 100):+.1f}%" if last_card and week_card else "N/A"
        change_no_card = f"{((last_no_card - week_no_card) / week_no_card * 100):+.1f}%" if last_no_card and week_no_card else "N/A"
        link_html = f'<a href="{url}">ссылка</a>'

        block = (
            f"{idx}️⃣ 📦 {name} ({link_html})\n"
            f"💳 {last_card or 'N/A'} ₽ | 🏷 {last_no_card or 'N/A'} ₽\n"
            f"📈 Изменение: 💳 {change_card} | 🏷 {change_no_card}\n"
            f"──────────────────────────────\n"
        )

        if len(text) + len(block) > MAX_CHARS:
            break

        text += block
        last_idx = idx

    return text, last_idx


async def show_user_products(message: types.Message):
    user_id = str(message.from_user.id)
    products = fetch_products(user_id)

    if not products:
        await message.answer("У вас нет добавленных товаров.")
        return

    total = len(products)
    text, last_idx = format_products_chunk(products, start_idx=0)
    text = f"📋 Ваши товары (показаны 1-{last_idx} из {total}):\n\n{text}"

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if last_idx < total:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="⏭ Показать ещё", callback_data=f"more:{last_idx}")
        ])
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"📋 Показать все ({total})", callback_data="all")
        ])

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


async def show_more_products(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    products = fetch_products(user_id)

    if not products:
        await callback.answer("У вас нет товаров.")
        return

    total = len(products)
    start_idx = int(callback.data.split(":")[1])
    text, last_idx = format_products_chunk(products, start_idx=start_idx)
    text = f"📋 Ваши товары (показаны {start_idx+1}-{last_idx} из {total}):\n\n{text}"

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if last_idx < total:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="⏭ Показать ещё", callback_data=f"more:{last_idx}")
        ])
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"📋 Показать все ({total})", callback_data="all")
        ])

    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


async def show_all_products(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    products = fetch_products(user_id)

    if not products:
        await callback.answer("У вас нет товаров.")
        return

    total = len(products)
    start_idx = 0
    while start_idx < total:
        text, last_idx = format_products_chunk(products, start_idx=start_idx)
        text = f"📋 Все товары ({start_idx+1}-{last_idx} из {total}):\n\n{text}"
        await callback.message.answer(text, parse_mode="HTML")
        start_idx = last_idx

    await callback.answer()
