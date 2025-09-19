# manager_monitor.py
import asyncio
import sqlite3

DB_FILE = "db.sqlite"

async def start_monitoring_handler(message, bot):
    """
    Запуск мониторинга цен на 7 дней.
    Каждые 1 час проверяем изменения цен относительно начала дня и недели.
    Если цена изменилась >10%, уведомляем пользователя.
    """
    await message.answer("🚀 Мониторинг цен на 7 дней запущен!")

    user_id = str(message.from_user.id)

    async def monitor():
        for _ in range(7 * 24):  # 7 дней * 24 часа
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT product_name, product_url, last_price_card, last_price_no_card,
                       day_price_card, day_price_no_card,
                       week_price_card, week_price_no_card
                FROM products
                WHERE user_id=?
            """, (user_id,))
            products = cursor.fetchall()
            conn.close()

            for product in products:
                name, url, last_card, last_no_card, day_card, day_no_card, week_card, week_no_card = product

                # Проверка с начала дня
                if day_card and last_card and abs(last_card - day_card)/day_card > 0.1:
                    await bot.send_message(message.chat.id,
                        f"⚠️ Цена на '{name}' изменилась более чем на 10% с начала дня! "
                        f"💳 {day_card} -> {last_card}"
                    )
                if day_no_card and last_no_card and abs(last_no_card - day_no_card)/day_no_card > 0.1:
                    await bot.send_message(message.chat.id,
                        f"⚠️ Цена без карты на '{name}' изменилась более чем на 10% с начала дня! "
                        f"🏷 {day_no_card} -> {last_no_card}"
                    )

                # Проверка с начала недели
                if week_card and last_card and abs(last_card - week_card)/week_card > 0.1:
                    await bot.send_message(message.chat.id,
                        f"📈 Цена на '{name}' изменилась более чем на 10% с начала недели! "
                        f"💳 {week_card} -> {last_card}"
                    )
                if week_no_card and last_no_card and abs(last_no_card - week_no_card)/week_no_card > 0.1:
                    await bot.send_message(message.chat.id,
                        f"📈 Цена без карты на '{name}' изменилась более чем на 10% с начала недели! "
                        f"🏷 {week_no_card} -> {last_no_card}"
                    )

            await asyncio.sleep(3600)  # проверка каждый час

    asyncio.create_task(monitor())
