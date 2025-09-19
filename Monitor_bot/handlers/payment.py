from aiogram.types import LabeledPrice, Message, PreCheckoutQuery
from aiogram import Bot
from keyboards.payment_keyboard import payment_keyboard
from manager_monitor import start_monitoring_handler

# --------------------- Настройки ---------------------
# Включает или отключает платность услуги мониторинга
MONITORING_IS_PAID = False

# Список пользователей, у которых мониторинг бесплатный независимо от флага
FREE_USERS = {186699497}

# --------------------- Выставление счёта или запуск бесплатно ---------------------
async def send_invoice_handler(message: Message, bot: Bot):
    user_id = message.from_user.id

    # Если услуга бесплатная по флагу или пользователь в списке исключений
    if not MONITORING_IS_PAID or user_id in FREE_USERS:
        await message.answer("✅ Мониторинг запущен без оплаты.")
        await start_monitoring_handler(message, bot)
        return

    # Иначе выставляем счёт на оплату
    prices = [LabeledPrice(label="XTR", amount=50)]  # 100 ⭐️
    await message.answer_invoice(
        title="Мониторинг цен на 7 дней",
        description="Полный доступ к функции мониторинга цен на 7 дней",
        prices=prices,
        provider_token="",  # Для Stars
        payload="monitoring_7_days",
        currency="XTR",
        reply_markup=payment_keyboard()
    )

# --------------------- Предпродажная проверка ---------------------
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

# --------------------- Успешная оплата ---------------------
async def success_payment_handler(message: Message, bot: Bot):
    await message.answer("🥳 Оплата прошла успешно! Мониторинг запущен.")
    await start_monitoring_handler(message, bot)

# --------------------- Команда поддержки ---------------------
async def pay_support_handler(message: Message):
    await message.answer(
        "Добровольные пожертвования не подразумевают возврат средств, "
        "но если хотите вернуть — свяжитесь с нами."
    )
