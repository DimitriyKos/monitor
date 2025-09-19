# validate_ozon_url.py
from urllib.parse import urlparse, urlunparse

def validate_ozon_url(url: str):
    """
    Проверяет, что ссылка на Ozon корректная:
    - Содержит 'ozon.ru'
    - Содержит хотя бы одно из: 'product', '/t/', '/s/'
    - Отрезает всё после '?'

    Возвращает:
    - Чистый URL, если валидно
    - (False, сообщение), если не валидно
    """
    url = url.strip()

    # Парсим URL
    parsed = urlparse(url)
    if 'ozon.ru' not in parsed.netloc:
        return False, "Ссылка не содержит домен ozon.ru"

    # Проверка типа ссылки
    path = parsed.path.lower()
    if not ('product' in path or '/t/' in path or '/s/' in path):
        return False, "Ссылка не похожа на товар на Ozon. Используйте ссылку с 'product', '/t/' или '/s/'"

    # Убираем GET-параметры
    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))

    return clean_url
