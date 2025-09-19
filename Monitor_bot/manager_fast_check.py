# manager_parsing_fast_v4.py
import os
import json
import sqlite3
import re
import time
import asyncio
from pathlib import Path
from datetime import datetime, date, timedelta

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

DB_FILE = "db.sqlite"
PRODUCTS_FOLDER = "Products"
MAX_CONCURRENT_PARSE = 10  # количество одновременных парсингов

# --------------------- Логирование ---------------------
def log(msg: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")

# --------------------- Браузер ---------------------
def create_browser(cookies_file: str = None, headless=True):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    if cookies_file and os.path.exists(cookies_file):
        driver.get("https://www.ozon.ru/")
        with open(cookies_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)
            for cookie in cookies:
                try:
                    driver.add_cookie({"name": cookie["name"], "value": cookie["value"], "domain": ".ozon.ru"})
                except Exception as e:
                    log(f"Ошибка добавления куки: {e}")
        log("✅ Куки пользователя применены")

    return driver

# --------------------- Скачивание HTML ---------------------
def download_html(user_id: str, urls: list, cookies_file: str):
    user_folder = Path(PRODUCTS_FOLDER) / str(user_id)
    user_folder.mkdir(parents=True, exist_ok=True)

    driver = create_browser(cookies_file=cookies_file, headless=True)
    html_mapping = {}  # filepath -> original URL

    try:
        for idx, url in enumerate(urls, start=1):
            log(f"Скачиваем {idx}/{len(urls)}: {url}")
            driver.get(url)
            time.sleep(3)

            page_source = driver.page_source
            if "<title>Доступ ограничен</title>" in page_source:
                log(f"❌ Доступ к {url} ограничен. Пропускаем товар.")
                continue

            # безопасное имя файла
            file_name_raw = url.rstrip("/").split("/")[-1]
            file_name_safe = re.sub(r'[<>:"/\\|?*]', '_', file_name_raw) + ".html"
            filepath = user_folder / file_name_safe

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(page_source)

            html_mapping[filepath] = url
            log(f"✅ HTML сохранён для {url}")

    finally:
        driver.quit()

    return html_mapping

# --------------------- Парсинг HTML ---------------------
def parse_html_file(filepath: Path):
    with open(filepath, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # Цена с картой
    card_tag = (
        soup.select_one("span.tsHeadline600Large")
        or soup.select_one("span.tsHeadline700Large")
        or soup.select_one("span.tsHeadline550Medium")
        or soup.select_one("span.tsHeadline500Medium")
    )

    # Цена без карты
    no_card_tag = (
        soup.select_one("span.pdp_bf2.tsHeadline500Medium")
        or soup.select_one("span.tsHeadline500Medium")
        or soup.select_one("div.pdp_f3b > span")
    )

    def clean_price(tag):
        if not tag:
            return None
        text = tag.get_text(strip=True)
        digits = re.sub(r"\D", "", text)
        return int(digits) if digits else None

    price_card = clean_price(card_tag)
    price_no_card = clean_price(no_card_tag)

    h1_tag = soup.select_one("h1.tsHeadline550Medium")
    product_name = h1_tag.get_text(strip=True) if h1_tag else filepath.stem

    return product_name, price_card, price_no_card

# --------------------- Сохранение в БД ---------------------
def save_product_to_db(user_id: str, product_url: str, product_name: str, price_card, price_no_card, html_file: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Проверяем, есть ли запись
    cursor.execute("SELECT last_check_time, last_price_card, last_price_no_card, day_start_time, week_start_time FROM products WHERE user_id=? AND product_url=?", (user_id, product_url))
    row = cursor.fetchone()
    now = datetime.now()
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    if row:
        # повторная проверка
        last_check_time, last_price_card, last_price_no_card, day_start_time, week_start_time = row
        # обновляем last_price
        cursor.execute("""
            UPDATE products
            SET product_name=?, last_price_card=?, last_price_no_card=?, html_file=?, last_check_time=?
            WHERE user_id=? AND product_url=?
        """, (product_name, price_card, price_no_card, html_file, now, user_id, product_url))

        # Обновляем day_price если новый день
        if not day_start_time or datetime.strptime(day_start_time, "%Y-%m-%d %H:%M:%S").date() < today:
            cursor.execute("""
                UPDATE products
                SET day_start_time=?, day_price_card=?, day_price_no_card=?
                WHERE user_id=? AND product_url=?
            """, (now, price_card, price_no_card, user_id, product_url))

        # Обновляем week_price если новая неделя
        if not week_start_time or datetime.strptime(week_start_time, "%Y-%m-%d %H:%M:%S").date() < week_start:
            cursor.execute("""
                UPDATE products
                SET week_start_time=?, week_price_card=?, week_price_no_card=?
                WHERE user_id=? AND product_url=?
            """, (now, price_card, price_no_card, user_id, product_url))

    else:
        # первая проверка
        cursor.execute("""
            INSERT INTO products (
                user_id, product_url, product_name, last_check_time,
                last_price_card, last_price_no_card,
                day_start_time, day_price_card, day_price_no_card,
                week_start_time, week_price_card, week_price_no_card,
                html_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, product_url, product_name, now,
              price_card, price_no_card,
              now, price_card, price_no_card,
              now, price_card, price_no_card,
              html_file))

    conn.commit()
    conn.close()

# --------------------- Асинхронный парсинг ---------------------
async def parse_html_files_async(user_id: str, html_mapping: dict, max_concurrent: int = MAX_CONCURRENT_PARSE):
    sem = asyncio.Semaphore(max_concurrent)

    async def parse_file(file_path, original_url):
        async with sem:
            loop = asyncio.get_running_loop()
            name, price_card, price_no_card = await loop.run_in_executor(None, parse_html_file, file_path)
            save_product_to_db(user_id, original_url, name, price_card, price_no_card, html_file=file_path.name)
            log(f"{name} 💳 {price_card} ₽ | 🏷️ {price_no_card} ₽")

    tasks = [parse_file(f, url) for f, url in html_mapping.items()]
    await asyncio.gather(*tasks)

# --------------------- Основная функция ---------------------
async def fast_check_products(message):
    user_id = str(message.from_user.id)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT product_url FROM products WHERE user_id=?", (user_id,))
    products = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not products:
        await message.answer("У вас нет добавленных товаров.")
        return

    cookies_file = f"user_cookies/cookies_{user_id}.json"

    await message.answer(f"⚡ Скачиваем HTML для {len(products)} товаров...")
    log(f"Старт скачивания HTML для {len(products)} товаров.")

    html_mapping = download_html(user_id, products, cookies_file)

    if not html_mapping:
        await message.answer("❌ Не удалось скачать ни одного товара (доступ ограничен).")
        return

    await message.answer(f"⚡ Парсим HTML для {len(html_mapping)} товаров...")
    await parse_html_files_async(user_id, html_mapping)

    await message.answer(f"✅ Проверка завершена для {len(html_mapping)} товаров.")
