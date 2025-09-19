import os
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# ================= Настройки =================
USER_ID = 186699497
URL_BASE = "https://www.ozon.ru"
URL_FAVORITES = f"{URL_BASE}/my/favorites"
USER_COOKIES_DIR = "user_cookies"

# ================= Утилиты =================
def get_cookie_file_path(user_id: int) -> str:
    return os.path.join(USER_COOKIES_DIR, f"cookies_{user_id}.json")

def load_cookies(user_id: int):
    path = get_cookie_file_path(user_id)
    if not os.path.exists(path):
        print("⚠️ Файл куки не найден")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ================= Основной код =================
def test_cookies(user_id: int):
    cookies = load_cookies(user_id)
    if not cookies:
        return False

    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    # visible браузер
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        driver.get(URL_BASE)
        time.sleep(2)

        print("🍪 Применяем куки...")
        for c in cookies:
            cookie = {k: v for k, v in c.items() if k in ("name", "value", "domain", "path", "secure", "expiry", "httpOnly")}
            if "domain" in cookie and cookie["domain"].startswith("www."):
                cookie["domain"] = cookie["domain"].lstrip("www.")
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"⚠️ Не удалось добавить куку {cookie['name']}: {e}")

        driver.get(URL_FAVORITES)
        time.sleep(5)  # ждём подгрузку страницы

        # проверка по имени профиля
        try:
            profile_span = driver.find_element(By.CSS_SELECTOR, "div.bq03_0_2-a span.tsCompact300XSmall")
            profile_name = profile_span.text.strip()
            if profile_name.lower() == "войти":
                print("❌ Куки устарели или отсутствуют. Требуется ручной вход.")
                return False
            else:
                print(f"✅ Куки действительны, пользователь: {profile_name}")
        except Exception as e:
            print(f"⚠️ Не удалось определить имя профиля: {e}")
            return False

        # можно дополнительно вывести заголовки товаров
        try:
            products = driver.find_elements(By.CSS_SELECTOR, "span.tsBody500Medium")
            print(f"🔹 Найдено товаров на странице: {len(products)}")
            for p in products[:10]:
                print("-", p.text)
        except Exception:
            pass

        input("Нажмите Enter, чтобы закрыть браузер...")
        return True
    finally:
        driver.quit()

if __name__ == "__main__":
    valid = test_cookies(USER_ID)
    if not valid:
        print("❌ Куки недействительны, необходимо войти заново.")
