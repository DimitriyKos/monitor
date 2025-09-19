import json
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

COOKIES_FILE = "cookies.json"
LOGIN_URL = "https://www.ozon.ru/"
USERNAME = "твоя_почта_или_телефон"  # сюда свои данные
PASSWORD = "твой_пароль"  # сюда свой пароль

def save_cookies(driver):
    cookies = driver.get_cookies()
    cookies_dict = {}
    for c in cookies:
        cookies_dict[c["name"]] = c["value"]
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies_dict, f, indent=2)
    print("🍪 Куки обновлены!")

def update_cookies():
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
        driver.get(LOGIN_URL)
        time.sleep(5)

        # Кнопка входа (если нужно)
        login_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Войти')]")
        login_button.click()
        time.sleep(2)

        # Ввод логина
        login_input = driver.find_element(By.NAME, "login")
        login_input.send_keys(USERNAME)

        # Ввод пароля
        password_input = driver.find_element(By.NAME, "password")
        password_input.send_keys(PASSWORD)

        # Кнопка подтверждения
        submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Войти')]")
        submit_btn.click()

        time.sleep(10)  # ждём загрузки после авторизации

        save_cookies(driver)
    finally:
        driver.quit()

# ----------------- Автоматический запуск раз в день в 00:01 -----------------
if __name__ == "__main__":
    while True:
        now = datetime.now()
        if now.hour == 0 and now.minute == 1:
            print("🔄 Обновляем куки...")
            try:
                update_cookies()
            except Exception as e:
                print("❌ Ошибка при обновлении куки:", e)
            time.sleep(60)  # ждём минуту, чтобы не сработало дважды
        time.sleep(20)  # проверяем каждые 20 секунд
