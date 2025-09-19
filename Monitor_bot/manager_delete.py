import sqlite3
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states import user_states

DB_FILE = "db.sqlite"
PAGE_SIZE = 100    # максимум товаров за раз при удалении
MAX_CHARS = 4000   # ограничение символов в одном сообщении

# список кнопок главного меню, которые прерывают режим удаления
EXIT_DELETE_BUTTONS = [
    "🔍 Проверить цены",
    "➕ Добавить товар",
    "❌ Удалить товар",
    "📋 Мои товары",
    "📊 Запустить мониторинг цен на 7 дней",
    "📥 Импорт избранного Ozon (локально)"
]

def fetch_products(user_id: str):
    """Получаем все товары пользователя из базы"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT product_name, product_url
        FROM products
        WHERE user_id=?
    """, (user_id,))
    products = cursor.fetchall()
    conn.close()
    return products


def format_products_chunk(products, start_idx=0):
    """
    Форматируем блок товаров для удаления
    Возвращает текст и индекс последнего включённого товара
    """
    text = ""
    last_idx = start_idx
    for idx, (name, url) in enumerate(products[start_idx:], start=start_idx + 1):
        display_name = name or "(Без названия)"
        block = f"{idx}. 📦 {display_name}\n<a href='{url}'>ссылка</a>\n"
        if len(text) + len(block) > MAX_CHARS:
            break
        text += block
        last_idx = idx
    return text, last_idx


# --------------------- Шаг 1: запуск удаления ---------------------
async def delete_product_handler(message: types.Message):
    user_id = str(message.from_user.id)
    products = fetch_products(user_id)

    if not products:
        await message.answer("У вас нет добавленных товаров для удаления.")
        return

    # Сохраняем список в состоянии
    user_states[user_id] = {"mode": "deleting_product", "products": products}

    # Отправляем первую страницу
    text, last_idx = format_products_chunk(products, start_idx=0)
    total = len(products)
    text = f"📦 Выберите товар для удаления (введите номер) или напишите 'удалить все':\n\n{text}"

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if last_idx < total:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="⏭ Показать ещё", callback_data=f"del_more:{last_idx}")
        ])
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"📋 Показать все ({total})", callback_data="del_all")
        ])

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


# --------------------- Шаг 2: пагинация ---------------------
async def show_more_delete_products(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    state = user_states.get(user_id)
    if not state or state.get("mode") != "deleting_product":
        await callback.answer("❌ Режим удаления не активен.")
        return

    products = state["products"]
    start_idx = int(callback.data.split(":")[1])
    text, last_idx = format_products_chunk(products, start_idx=start_idx)
    total = len(products)
    text = f"📦 Выберите товар для удаления (введите номер) или напишите 'удалить все':\n\n{text}"

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if last_idx < total:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="⏭ Показать ещё", callback_data=f"del_more:{last_idx}")
        ])
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"📋 Показать все ({total})", callback_data="del_all")
        ])

    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# --------------------- Шаг 3: показать все ---------------------
async def show_all_delete_products(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    state = user_states.get(user_id)
    if not state or state.get("mode") != "deleting_product":
        await callback.answer("❌ Режим удаления не активен.")
        return

    products = state["products"]
    total = len(products)
    start_idx = 0
    while start_idx < total:
        text, last_idx = format_products_chunk(products, start_idx=start_idx)
        text = f"📦 Выберите товар для удаления (введите номер) или напишите 'удалить все':\n\n{text}"
        await callback.message.answer(text, parse_mode="HTML")
        start_idx = last_idx

    await callback.answer()


# --------------------- Шаг 4: обработка выбора ---------------------
async def process_delete_product(message: types.Message):
    user_id = str(message.from_user.id)

    # --- Прерываем режим удаления, если нажата кнопка главного меню ---
    if message.text in EXIT_DELETE_BUTTONS:
        state = user_states.get(user_id)
        if isinstance(state, dict) and state.get("mode") == "deleting_product":
            user_states.pop(user_id, None)
        return  # сообщение пойдёт в основной обработчик кнопок

    state = user_states.get(user_id)
    if not state or state.get("mode") != "deleting_product":
        return  # пользователь не в режиме удаления

    products = state["products"]
    text = message.text.strip().lower()

    # Удаление всех товаров
    if text == "удалить все":
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        user_states[user_id] = None
        await message.answer(f"✅ Все {len(products)} товаров удалены.")
        return

    selected_index = None
    selected_url = None

    if text.isdigit():
        index = int(text) - 1
        if 0 <= index < len(products):
            selected_index = index
            selected_url = products[index][1]

    if selected_index is None:
        await message.answer("❌ Не удалось найти товар. Попробуйте ещё раз.")
        return

    # Удаляем выбранный товар
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE user_id=? AND product_url=?", (user_id, selected_url))
    conn.commit()
    conn.close()

    await message.answer(f"✅ Товар '{products[selected_index][0] or selected_url}' удалён.")

    # Обновляем состояние списка
    updated_products = products[:selected_index] + products[selected_index+1:]
    if updated_products:
        user_states[user_id]["products"] = updated_products
    else:
        user_states[user_id] = None
