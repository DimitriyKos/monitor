import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from ozon_favorites_local import manual_login_and_save_cookies, import_favorites_for_user, finalize_manual_login
from manager_add import add_product_handler, process_product_link, user_states
from manager_parsing import check_prices_for_user
from manager_total import show_user_products, show_more_products, show_all_products
from manager_delete import delete_product_handler, process_delete_product, show_more_delete_products, show_all_delete_products
from handlers import payment
from manager_fast_check import fast_check_products

API_TOKEN = "8479990520:AAE0UaNSzf-E3x5i-m0l7pJ67TtJI4bwe3k"

# --------------------- Основная клавиатура ---------------------
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔍 Проверить цены")],
        [KeyboardButton(text="⚡ Быстрая проверка цен")],
        [KeyboardButton(text="➕ Добавить товар")],
        [KeyboardButton(text="❌ Удалить товар")],
        [KeyboardButton(text="📋 Мои товары")],
        [KeyboardButton(text="📊 Запустить мониторинг цен на 7 дней")],
        [KeyboardButton(text="📥 Импорт избранного Ozon (локально)")]
    ],
    resize_keyboard=True
)

# Клавиатура для ручного входа (добавляется динамически)
manual_login_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Готово")]
    ],
    resize_keyboard=True
)

# --------------------- Обработчики ---------------------
async def start_handler(message: types.Message):
    await message.answer(
        "Привет! 👋 Я бот для отслеживания цен на маркетплейсе Ozon. "
        "Ты можешь выгрузить все товары из избранного или добавить товары вручную.\n\nВыбери действие ниже:",
        reply_markup=main_kb
    )

# Состояние ожидания ручного входа
manual_login_waiting = {}

# --------------------- Импорт избранного ---------------------
async def import_favorites_local_handler(message: types.Message):
    user_id = message.from_user.id
    bot = message.bot

    await message.answer("🚀 Пытаемся импортировать ваши товары из Ozon...", reply_markup=main_kb)

    # Пробуем импорт через куки
    result = await asyncio.to_thread(import_favorites_for_user, user_id)

    if result["ok"]:
        await message.answer(f"✅ Импорт завершён: добавлено {result['count']} товаров.", reply_markup=main_kb)
    else:
        # Куки недействительны — запускаем ручной вход
        await manual_login_and_save_cookies(user_id, bot)
        await message.answer(
            "❗После входа нажмите кнопку «Готово» ниже, чтобы сохранить куки и продолжить...",
            reply_markup=manual_login_kb
        )
        manual_login_waiting[user_id] = True

# --------------------- Обработчик кнопки "Готово" ---------------------
async def manual_login_done_handler(message: types.Message):
    user_id = message.from_user.id
    if manual_login_waiting.get(user_id):
        success, msg = await asyncio.to_thread(finalize_manual_login, user_id)
        await message.answer(msg, reply_markup=main_kb)
        if success:
            # После успешного сохранения куки импортируем избранное
            result = await asyncio.to_thread(import_favorites_for_user, user_id)
            if result["ok"]:
                await message.answer(f"✅ Импорт завершён: добавлено {result['count']} товаров.", reply_markup=main_kb)
            else:
                await message.answer(f"⚠️ Не удалось импортировать избранное: {result['msg']}", reply_markup=main_kb)
        manual_login_waiting[user_id] = False

# --------------------- Основная функция ---------------------
async def main():
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()

    # Команда /start
    dp.message.register(start_handler, Command("start"))

    # Кнопки меню
    dp.message.register(check_prices_for_user, lambda msg: msg.text == "🔍 Проверить цены")
    dp.message.register(delete_product_handler, lambda msg: msg.text == "❌ Удалить товар")
    dp.message.register(show_user_products, lambda msg: msg.text == "📋 Мои товары")
    dp.message.register(add_product_handler, lambda msg: msg.text == "➕ Добавить товар")
    dp.message.register(import_favorites_local_handler, lambda msg: msg.text == "📥 Импорт избранного Ozon (локально)")
    dp.message.register(fast_check_products, lambda msg: msg.text == "⚡ Быстрая проверка цен")

    # Кнопка "Готово"
    dp.message.register(manual_login_done_handler, lambda msg: msg.text == "✅ Готово")

    # --------------------- Callback для inline-кнопок ---------------------
    dp.callback_query.register(show_more_products, lambda c: c.data.startswith("more:"))
    dp.callback_query.register(show_all_products, lambda c: c.data == "all")
    dp.callback_query.register(show_more_delete_products, lambda c: c.data.startswith("del_more:"))
    dp.callback_query.register(show_all_delete_products, lambda c: c.data == "del_all")

    # Мониторинг через оплату
    async def start_monitoring_wrapper(message: types.Message):
        await payment.send_invoice_handler(message, bot)
    dp.message.register(start_monitoring_wrapper, lambda msg: msg.text == "📊 Запустить мониторинг цен на 7 дней")

    # Обработка сообщений в режиме добавления/удаления
    async def handle_message(message: types.Message):
        user_id = str(message.from_user.id)
        if user_states.get(user_id) == "adding_product":
            await process_product_link(message)
            return
        state = user_states.get(user_id)
        if isinstance(state, dict) and state.get("mode") == "deleting_product":
            await process_delete_product(message)
            return
    dp.message.register(handle_message, lambda msg: True)

    # Обработчики платежей
    dp.message.register(lambda msg: payment.send_invoice_handler(msg, bot), Command("donate"))
    dp.pre_checkout_query.register(payment.pre_checkout_handler)
    dp.message.register(lambda msg: payment.success_payment_handler(msg, bot), F.successful_payment)
    dp.message.register(payment.pay_support_handler, Command("paysupport"))

    print("Бот запущен ✅")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
