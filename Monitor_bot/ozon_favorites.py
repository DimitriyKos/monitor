# ozon_favorites.py
import os
import json
import time
import asyncio
import urllib.parse
from typing import List, Dict, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# попытка импортировать массовую запись, если её нет — fallback на по-штучную запись
try:
    from manager_write_db import write_or_update_products_bulk
except Exception:
    write_or_update_products_bulk = None
from manager_write_db import write_or_update_product

# =========================
# КОНСТАНТЫ / НАСТРОЙКИ
# =========================
COOKIES_DIR = "user_cookies"
USER_HTML_DIR = "user_data"
os.makedirs(COOKIES_DIR, exist_ok=True)
os.makedirs(USER_HTML_DIR, exist_ok=True)

URL_BASE = "https://www.ozon.ru"
URL_FAVORITES = "https://www.ozon.ru/my/favorites"

SCROLL_COUNT = 15
SCROLL_STEP = 3000
SCROLL_PAUSE = 2
FINAL_PAUSE = 15

HEADLESS = False  # True = без окна, False = видимый браузер

active_drivers: Dict[str, webdriver.Chrome] = {}

# =========================
# УТИЛИТЫ
# =========================
def _make_chrome_options(headless: bool) -> webdriver.ChromeOptions:
    opts = webdriver.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--remote-allow-origins=*")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )
    if not headless:
        opts.add_argument("--start-maximized")
    return opts

def _safe_prefix_link(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urllib.parse.urljoin(URL_BASE, href)

def _apply_cookies_sync(driver: webdriver.Chrome, cookies: List[dict]) -> None:
    driver.delete_all_cookies()
    for c in cookies:
        cookie = {k: c[k] for k in c.keys() if k in ("name", "value", "domain", "path", "expiry", "secure", "httpOnly")}
        if "domain" in cookie and isinstance(cookie["domain"], str) and cookie["domain"].startswith("www."):
            cookie["domain"] = cookie["domain"].lstrip("www.")
        try:
            driver.add_cookie(cookie)
        except Exception:
            pass

def _save_cookies_list_to_file_sync(cookies: List[dict], filepath: str) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)

# =========================
# ПАРСИНГ
# =========================
def parse_products_from_fav_block(html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    fav_block = soup.find("div", {"data-widget": "favoriteItems"})
    products: List[Dict[str, str]] = []
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
        link = _safe_prefix_link(href)
        products.append({"title": title, "link": link})
    return products

def parse_products_from_html(html: str, delim_text: str = "Подобрано для вас") -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    pos_delim = html.find(delim_text)
    anchors = [a for a in soup.find_all("a", href=True) if "/product/" in a['href']]
    products: List[Dict[str, str]] = []
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
        link = _safe_prefix_link(a['href'])
        products.append({"title": title, "link": link})
    return products

# =========================
# ПРОВЕРКА COOKIE
# =========================
def _verify_cookies_and_login_sync(cookies_path: str, headless: bool = True, timeout: int = 10) -> bool:
    opts = _make_chrome_options(headless)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    try:
        driver.get(URL_BASE)
        time.sleep(1)
        with open(cookies_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        _apply_cookies_sync(driver, cookies)
        driver.refresh()
        time.sleep(1)
        driver.get(URL_FAVORITES)
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-widget="favoriteItems"]'))
            )
            print("[INFO] _verify: найден блок favoriteItems — куки рабочие.")
            return True
        except Exception:
            return False
    finally:
        try:
            driver.quit()
        except Exception:
            pass

async def check_if_user_logged(user_id: int) -> dict:
    uid = str(user_id)
    filepath = os.path.join(COOKIES_DIR, f"cookies_{uid}.json")
    if not os.path.exists(filepath):
        return {"ok": False, "msg": "Куки не найдены."}
    ok = await asyncio.to_thread(_verify_cookies_and_login_sync, filepath, HEADLESS, 10)
    if ok:
        return {"ok": True, "msg": "Куки валидны."}
    return {"ok": False, "msg": "Куки есть, но невалидны — требуется новый вход."}

# =========================
# РУЧНОЙ ЛОГИН
# =========================
def _launch_login_browser_sync() -> webdriver.Chrome:
    opts = _make_chrome_options(False)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.get(URL_BASE)
    return driver

async def start_login_for_user(user_id: int) -> dict:
    uid = str(user_id)
    if uid in active_drivers:
        return {"ok": False, "msg": "Браузер для логина уже открыт."}
    driver = await asyncio.to_thread(_launch_login_browser_sync)
    active_drivers[uid] = driver
    return {"ok": True, "msg": "Откройте браузер и войдите в Ozon. После входа нажмите 'Готово'."}

async def finalize_login_and_save_cookies(user_id: int) -> dict:
    uid = str(user_id)
    driver = active_drivers.get(uid)
    if not driver:
        return {"ok": False, "msg": "Браузер для логина не найден."}
    cookies = await asyncio.to_thread(driver.get_cookies)
    filepath = os.path.join(COOKIES_DIR, f"cookies_{uid}.json")
    await asyncio.to_thread(_save_cookies_list_to_file_sync, cookies, filepath)
    try:
        await asyncio.to_thread(driver.quit)
    except Exception:
        pass
    active_drivers.pop(uid, None)
    # проверяем наличие маркеров авторизации
    names = {c.get("name") for c in cookies}
    logged = any(k in names for k in ("__Secure-user-id", "ozonIdAuthResponseToken", "__Secure-access-token"))
    if logged:
        return {"ok": True, "msg": "Куки сохранены. Теперь можно импортировать избранное."}
    return {"ok": False, "msg": "Куки сохранены, но маркеры входа не найдены."}

# =========================
# ИМПОРТ ИЗБРАННОГО
# =========================
def _fetch_favorites_and_products_sync(uid: str, cookies_path: str, headless: bool, max_items: int = 500) -> Tuple[List[Dict], str]:
    opts = _make_chrome_options(headless)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    html_path = os.path.join(USER_HTML_DIR, f"{uid}_favorites.html")
    try:
        driver.get(URL_BASE)
        time.sleep(1)
        with open(cookies_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        _apply_cookies_sync(driver, cookies)
        driver.refresh()
        time.sleep(2)
        driver.get(URL_FAVORITES)
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-widget="favoriteItems"]'))
            )
        except Exception:
            print("[WARN] favoriteItems не найден — возможно куки устарели.")

        driver.execute_script("window.scrollTo(0, 0);")
        for i in range(SCROLL_COUNT):
            driver.execute_script(f"window.scrollBy(0, {SCROLL_STEP});")
            if i < SCROLL_COUNT - 1:
                time.sleep(SCROLL_PAUSE)
            else:
                time.sleep(FINAL_PAUSE)

        html = driver.page_source
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        products = parse_products_from_fav_block(html)
        if not products:
            products = parse_products_from_html(html)
        return products[:max_items], html_path
    finally:
        try:
            driver.quit()
        except Exception:
            pass

async def import_favorites_for_user(user_id: int, max_items: int = 500) -> dict:
    uid = str(user_id)
    cookie_path = os.path.join(COOKIES_DIR, f"cookies_{uid}.json")
    if not os.path.exists(cookie_path):
        return {"ok": False, "msg": "Куки не найдены. Сначала выполните вход."}
    ok_check = await check_if_user_logged(user_id)
    if not ok_check["ok"]:
        return {"ok": False, "msg": f"Куки невалидны: {ok_check['msg']}"}
    try:
        products, html_path = await asyncio.to_thread(
            _fetch_favorites_and_products_sync, uid, cookie_path, HEADLESS, max_items
        )
    except Exception as e:
        return {"ok": False, "msg": f"Ошибка парсинга избранного: {e}"}

    added = 0
    try:
        if write_or_update_products_bulk:
            try:
                res = write_or_update_products_bulk(uid, products)
                added = res if isinstance(res, int) else len(products)
            except Exception:
                for p in products:
                    try:
                        write_or_update_product(uid, p["link"], p["title"], None, None)
                        added += 1
                    except Exception:
                        pass
        else:
            for p in products:
                try:
                    write_or_update_product(uid, p["link"], p["title"], None, None)
                    added += 1
                except Exception:
                    pass
    finally:
        try:
            if os.path.exists(html_path):
                os.remove(html_path)
        except Exception:
            pass
    return {"ok": True, "added": added, "msg": f"Импорт завершён: добавлено {added} товаров."}
