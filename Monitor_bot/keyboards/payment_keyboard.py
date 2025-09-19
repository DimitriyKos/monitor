from aiogram.utils.keyboard import InlineKeyboardBuilder

def payment_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Запустить мониторинг 50 ⭐️", pay=True)
    return builder.as_markup()
