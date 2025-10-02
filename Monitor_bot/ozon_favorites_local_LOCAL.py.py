import os
import time
import json
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from manager_write_db import write_or_update_products_bulk

URL_BASE = "https://www.ozon.ru"
URL_FAVORITES = f"{URL_BASE}/my/favorites"

SCROLL_COUNT = 15
SCROLL_STEP = 3000
SCROLL_PAUSE = 1
FINAL_PAUSE = 10

USER_COOKIES_DIR = "user_cookies"
os.makedirs(USER_COOKIES_DIR, exist_ok=True)

# ================= Состояния пользователей =================
user_states = {}

# ================= Утилиты =================
def safe_prefix_link(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urllib.parse.urljoin(URL_BASE, href)

def get_cookie_file_path(user_id: int) -> str:
    return os.path.join(USER_COOKIES_DIR, f"cookies_{user_id}.json")

def save_cookies(driver, user_id: int):
    cookies = driver.get_cookies()
    path = get_cookie_file_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"✅ Cookies сохранены в {path}")

def load_cookies(user_id: int):
    path = get_cookie_file_path(user_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

# ----------------- Парсинг -----------------
def parse_products_from_html(html: str, delim_text: str = "Подобрано для вас"):
    soup = BeautifulSoup(html, "html.parser")
    pos_delim = html.find(delim_text)
    anchors = [a for a in soup.find_all("a", href=True) if "/product/" in a['href']]
    products = []
    for a in anchors:
        a_html = str(a)
        pos = html.find(a_html)
        if pos == -1:
            href = a['href']
            pos = html.find(href) if href else -1
        if pos == -1:
            continue
        if pos_delim != -1 and pos >= pos_delim:
            continue
        title_tag = a.select_one("span.tsBody500Medium")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        if not title:
            continue
        link = safe_prefix_link(a['href'])
        products.append({"title": title, "link": link})
    return products

def parse_products_from_fav_block(html: str):
    soup = BeautifulSoup(html, "html.parser")
    fav_block = soup.find("div", {"data-widget": "favoriteItems"})
    products = []
    if not fav_block:
        return products
    anchors = fav_block.find_all("a", href=True)
    for a in anchors:
        href = a.get("href", "")
        if "/product/" not in href:
            continue
        title_tag = a.select_one("span.tsBody500Medium")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        if not title:
            continue
        link = safe_prefix_link(href)
        products.append({"title": title, "link": link})
    return products

# ================= Ручной вход =================
async def manual_login_and_save_cookies(user_id: int, bot):
    """
    Запускает браузер для ручного входа через Selenium.
    Открывает страницу Ozon и сохраняет драйвер в user_states.
    Отправляет пользователю сообщение с инструкцией.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    )

    # Создаём новый драйвер
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    # Обязательно открываем Ozon
    driver.get("https://www.ozon.ru")

    # Сохраняем драйвер в состояние пользователя
    user_states[user_id] = {"mode": "manual_login", "driver": driver}

    # Отправляем пользователю сообщение с инструкцией
    await bot.send_message(
        user_id,
        "❗ Куки устарели или отсутствуют. Пожалуйста, войдите в аккаунт Ozon вручную в открывшемся браузере.\n"
        "После входа нажмите кнопку 'Готово' здесь, чтобы сохранить куки и продолжить..."
    )

def finalize_manual_login(user_id: int):
    state = user_states.get(user_id)
    if not state or state.get("mode") != "manual_login":
        return False, "Нет активного ручного входа."
    driver = state.get("driver")
    if not driver:
        return False, "Драйвер не найден."
    try:
        save_cookies(driver, user_id)
        driver.quit()
        user_states.pop(user_id, None)
        return True, "✅ Куки успешно сохранены."
    except Exception as e:
        return False, f"❌ Ошибка при сохранении куки: {e}"

# ================= Импорт через куки =================
def try_import_with_cookies(user_id: int, cookies: list) -> dict:
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
    )
    try:
        driver.get(URL_BASE)
        time.sleep(2)
        if cookies:
            for c in cookies:
                cookie = {k: v for k, v in c.items() if k in ("name", "value", "domain", "path", "secure", "expiry", "httpOnly")}
                if "domain" in cookie and cookie["domain"].startswith("www."):
                    cookie["domain"] = cookie["domain"].lstrip("www.")
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    pass
            driver.get(URL_FAVORITES)
            time.sleep(3)
            try:
                profile_span = driver.find_element("css selector", "div.bq03_0_2-a span.tsCompact300XSmall")
                if profile_span.text.strip().lower() == "войти":
                    return {"ok": False, "msg": "❌ Куки устарели."}
            except Exception:
                return {"ok": False, "msg": "❌ Не удалось проверить авторизацию."}

        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        for i in range(SCROLL_COUNT):
            driver.execute_script(f"window.scrollBy(0, {SCROLL_STEP});")
            time.sleep(SCROLL_PAUSE if i < SCROLL_COUNT - 1 else FINAL_PAUSE)
        html = driver.page_source
    finally:
        driver.quit()

    products = parse_products_from_fav_block(html)
    if not products:
        products = parse_products_from_html(html)

    for p in products:
        p.setdefault("last_price_card", None)
        p.setdefault("last_price_no_card", None)
    write_or_update_products_bulk(str(user_id), products)
    return {"ok": True, "count": len(products), "msg": f"Найдено {len(products)} товаров"}

def import_favorites_for_user(user_id: int) -> dict:
    cookies = load_cookies(user_id)
    if cookies:
        result = try_import_with_cookies(user_id, cookies)
        if result["ok"]:
            return result
    return {"ok": False, "msg": "❌ Куки устарели или отсутствуют. Требуется ручной вход."}
