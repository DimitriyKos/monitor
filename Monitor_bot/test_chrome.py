# test_runet_sites_selenium.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

# -------------------- Настройки --------------------
CHROMEDRIVER_PATH = CHROMEDRIVER_PATH = r".\drivers\chromedriver.exe" # путь к драйверу в проекте
PROXY_USERNAME = "a51ac6f0312da844d7f83-zone-custom-region-ru-st-moscow-city-moscow-session-6a5v1oyqj-sessTime-15"
PROXY_PASSWORD = "fe40637f85cf4433"
PROXY_HOST = "p1.mangoproxy.com"
PROXY_PORT = "2334"

# 10 популярных сайтов Рунета
SITES = [
    "https://www.yandex.ru",
    "https://www.mail.ru",
    "https://www.vk.com",
    "https://www.ozon.ru",
    "https://www.tinkoff.ru",
    "https://www.rambler.ru",
    "https://www.lenta.ru",
    "https://www.kinopoisk.ru",
    "https://www.gismeteo.ru",
    "https://www.sberbank.ru"
]

# -------------------- Настройка браузера --------------------
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--start-maximized")  # обычный браузер, не хедлесс

# Прокси для Selenium
proxy = f"http://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}"
chrome_options.add_argument(f"--proxy-server={proxy}")

service = Service(CHROMEDRIVER_PATH)

# -------------------- Основной цикл --------------------
print("⚡ Начинаем тест подключений через прокси...")

driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    for site in SITES:
        print(f"\n🌐 Подключаемся к: {site}")
        driver.get(site)
        time.sleep(3)

        # Выводим первый <h1>, если есть
        h1_list = driver.find_elements(By.TAG_NAME, "h1")
        if h1_list:
            print("Первый <h1>:", h1_list[0].text)
        else:
            print("На странице нет <h1>")

        # Проверка текущего IP через ip-api.com
        driver.get("http://ip-api.com/json")
        time.sleep(2)
        pre = driver.find_element(By.TAG_NAME, "pre")
        print("IP по прокси:", pre.text)

finally:
    driver.quit()
    print("\n✅ Тест завершён")
