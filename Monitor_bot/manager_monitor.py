# manager_monitor.py
import asyncio
import sqlite3
import shutil
import os
from datetime import datetime, timedelta

from manager_parsing import check_prices_for_user

DB_FILE = "db.sqlite"
PRODUCTS_FOLDER = "Products"


async def start_monitoring_handler(message, bot):
    """
    Запуск мониторинга цен на 7 дней.
    Каждые 1 час: чистим папку пользователя, скачиваем новые HTML,
    обновляем базу и проверяем изменения цен относительно начала дня и недели.
    """
    await message.answer("🚀 Мониторинг цен на 7 дней запущен!")
    print("🚀 Мониторинг цен запущен для пользователя:", message.from_user.id)

    user_id = str(message.from_user.id)

    async def monitor():
        for hour in range(7 * 24):  # 7 дней * 24 часа
            print(f"\n🕒 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Запуск проверки №{hour+1}")

            # 1. Чистим папку с HTML пользователя
            user_folder = os.path.join(PRODUCTS_FOLDER, user_id)
            if os.path.exists(user_folder):
                shutil.rmtree(user_folder)
                print(f"🗑 Папка {user_folder} очищена")

            # 2. Скачиваем новые HTML и обновляем last_price_* в базе
            print("⬇️ Скачиваем свежие страницы товаров...")
            await check_prices_for_user(message)
            print("📦 База данных обновлена свежими ценами")

            # 3. Загружаем актуальные данные из БД
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, product_name, product_url,
                       last_price_card, last_price_no_card,
                       day_price_card, day_price_no_card, day_start_time,
                       week_price_card, week_price_no_card, week_start_time
                FROM products
                WHERE user_id=?
            """, (user_id,))
            products = cursor.fetchall()

            today = datetime.now().date()
            changed_products = []

            print(f"🔍 Найдено товаров для проверки: {len(products)}")

            # 4. Обновляем day/week при необходимости + проверка изменений
            for product in products:
                (pid, name, url,
                 last_card, last_no_card,
                 day_card, day_no_card, day_start,
                 week_card, week_no_card, week_start) = product

                print(f"   ▶ {name} | 💳 {last_card} | 🏷 {last_no_card}")

                # --- Проверка и обновление дневных цен ---
                if not day_start or datetime.fromisoformat(day_start).date() < today:
                    cursor.execute("""
                        UPDATE products
                        SET day_price_card=?, day_price_no_card=?, day_start_time=?
                        WHERE id=?
                    """, (last_card, last_no_card, today.isoformat(), pid))
                    print(f"   🔄 Обновлены дневные цены для {name}")

                # --- Проверка и обновление недельных цен ---
                if not week_start or datetime.fromisoformat(week_start).date() <= today - timedelta(days=7):
                    cursor.execute("""
                        UPDATE products
                        SET week_price_card=?, week_price_no_card=?, week_start_time=?
                        WHERE id=?
                    """, (last_card, last_no_card, today.isoformat(), pid))
                    print(f"   🔄 Обновлены недельные цены для {name}")

                # --- Проверка изменений относительно day/week ---
                if day_card and last_card and abs(last_card - day_card) / day_card > 0.1:
                    msg = (f"⚠️ Цена на '{name}' изменилась более чем на 10% с начала дня!\n"
                           f"💳 {day_card} → {last_card}")
                    await bot.send_message(message.chat.id, msg)
                    changed_products.append(msg)

                if day_no_card and last_no_card and abs(last_no_card - day_no_card) / day_no_card > 0.1:
                    msg = (f"⚠️ Цена без карты на '{name}' изменилась более чем на 10% с начала дня!\n"
                           f"🏷 {day_no_card} → {last_no_card}")
                    await bot.send_message(message.chat.id, msg)
                    changed_products.append(msg)

                if week_card and last_card and abs(last_card - week_card) / week_card > 0.1:
                    msg = (f"📈 Цена на '{name}' изменилась более чем на 10% с начала недели!\n"
                           f"💳 {week_card} → {last_card}")
                    await bot.send_message(message.chat.id, msg)
                    changed_products.append(msg)

                if week_no_card and last_no_card and abs(last_no_card - week_no_card) / week_no_card > 0.1:
                    msg = (f"📈 Цена без карты на '{name}' изменилась более чем на 10% с начала недели!\n"
                           f"🏷 {week_no_card} → {last_no_card}")
                    await bot.send_message(message.chat.id, msg)
                    changed_products.append(msg)

            conn.commit()
            conn.close()

            # 5. Лог итогов
            print(f"✅ Проверка завершена. Обработано товаров: {len(products)}")
            if changed_products:
                print("⚡ Изменения обнаружены:")
                for msg in changed_products:
                    print("   -", msg.replace("\n", " "))
            else:
                print("ℹ️ Изменений цен не найдено.")

            # 6. Ждём 1 час
            await asyncio.sleep(3600)

    asyncio.create_task(monitor())
