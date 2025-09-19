# manager_parsing.py
import os
import time
import json
from urllib.parse import urlparse
from datetime import datetime, date
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from aiogram import types
import sqlite3
import asyncio
import concurrent.futures
import re

from manager_write_db import write_or_update_product

DB_FILE = "db.sqlite"
PRODUCTS_FOLDER = "Products"
COOKIES_FILE = "cookies.json"
COOKIES_LAST_UPDATE_FILE = "cookies_last_update.txt"
MAX_CONCURRENT = 20  # Количество одновременных проверок

# --------------------- Куки ---------------------
def update_cookies_if_needed():
    today = date.today()
    last_update = None
    if os.path.exists(COOKIES_LAST_UPDATE_FILE):
        with open(COOKIES_LAST_UPDATE_FILE, "r", encoding="utf-8") as f:
            try:
                last_update = datetime.strptime(f.read().strip(), "%Y-%m-%d").date()
            except:
                last_update = None
    if last_update != today:
        with open(COOKIES_LAST_UPDATE_FILE, "w", encoding="utf-8") as f:
            f.write(today.strftime("%Y-%m-%d"))

def load_cookies():
    if not os.path.exists(COOKIES_FILE):
        raise FileNotFoundError(f"{COOKIES_FILE} не найден")
    with open(COOKIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# --------------------- HTML ---------------------
def download_ozon_html(product_url: str, user_id: str):
    update_cookies_if_needed()
    cookies = load_cookies()

    user_folder = os.path.join(PRODUCTS_FOLDER, str(user_id))
    os.makedirs(user_folder, exist_ok=True)

    path_part = urlparse(product_url).path.strip("/").split("/")[-1]
    filename = f"{path_part}.html"
    filepath = os.path.join(user_folder, filename)

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    try:
        driver.get("https://www.ozon.ru/")
        for name, value in cookies.items():
            driver.add_cookie({"name": name, "value": value, "domain": ".ozon.ru", "path": "/"})
        driver.get(product_url)
        time.sleep(5)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        return filepath
    finally:
        driver.quit()

# --------------------- Парсинг ---------------------

def parse_html_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # Попытки найти цену "с картой" (несколько шаблонов, если OZON меняет классы)
    card_tag = (
        soup.select_one("span.tsHeadline600Large")
        or soup.select_one("span.tsHeadline700Large")
        or soup.select_one("span.tsHeadline550Medium")
        or soup.select_one("span.tsHeadline500Medium")
    )

    # Цена без карты — сначала пробуем конкретный класс из твоего примера,
    # затем более общий вариант
    no_card_tag = (
        soup.select_one("span.pdp_bf2.tsHeadline500Medium")
        or soup.select_one("span.tsHeadline500Medium")
        or soup.select_one("div.pdp_f3b > span")
    )

    def clean_price(tag):
        if not tag:
            return None
        text = tag.get_text(strip=True)
        digits = re.sub(r"\D", "", text)  # оставляем только цифры
        return int(digits) if digits else None

    price_card = clean_price(card_tag)
    price_no_card = clean_price(no_card_tag)

    # Название товара — ищем по классу, который стабильно содержит tsHeadline550Medium
    h1_tag = soup.select_one("h1.tsHeadline550Medium")
    product_name = (
        h1_tag.get_text(strip=True) if h1_tag else os.path.basename(filepath).replace(".html", "")
    )

    return product_name, price_card, price_no_card

# --------------------- Основная функция проверки цен ---------------------
async def check_prices_for_user(message: types.Message):
    user_id = str(message.from_user.id)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT product_url FROM products WHERE user_id=?", (user_id,))
    products = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not products:
        await message.answer("У вас нет добавленных товаров.")
        return

    await message.answer(f"🚀 Запускаем проверку цен для {len(products)} товаров...")

    loop = asyncio.get_running_loop()
    result_lines = []

    def process_product(idx, product_url):
        try:
            html_file = download_ozon_html(product_url, user_id)
            product_name, price_card, price_no_card = parse_html_file(html_file)
            write_or_update_product(user_id, product_url, product_name, price_card, price_no_card)
            return f"{idx}. {product_name} 💳 {price_card} ₽ | 🏷️ {price_no_card} ₽"
        except Exception as e:
            return f"{idx}. Ошибка при обработке {product_url}: {e}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
        futures = [
            loop.run_in_executor(executor, process_product, idx, product_url)
            for idx, product_url in enumerate(products, start=1)
        ]
        for completed in asyncio.as_completed(futures):
            result = await completed
            result_lines.append(result)

    await message.answer(f"✅ Проверка завершена: {len(result_lines)} товаров обновлено")

