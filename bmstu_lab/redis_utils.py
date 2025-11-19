# redis_utils.py - улучшенная версия
import redis
from django.conf import settings
import time

def get_redis_connection(max_retries=3, retry_delay=1):
    """Получение соединения с Redis с повторными попытками"""
    for attempt in range(max_retries):
        try:
            r = redis.Redis(
                host='localhost',
                port=6379,
                db=1,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            r.ping()
            print("Redis подключен успешно!")
            return r
        except redis.ConnectionError as e:
            print(f"Попытка {attempt + 1}/{max_retries}: Ошибка подключения к Redis: {e}")
            if attempt < max_retries - 1:
                print(f"Повторная попытка через {retry_delay} секунд...")
                time.sleep(retry_delay)
            else:
                print("Не удалось подключиться к Redis после всех попыток")
                return None
        except Exception as e:
            print(f"Неожиданная ошибка при подключении к Redis: {e}")
            return None

def test_redis_connection():
    """Тестирование подключения к Redis"""
    r = get_redis_connection()
    if r:
        try:
            r.set('test_key', 'test_value', ex=10)  # ex=10 - expire через 10 сек
            value = r.get('test_key')
            print(f"Redis тест: записано и прочитано значение: '{value}'")
            return True
        except Exception as e:
            print(f"Ошибка работы с Redis: {e}")
            return False
    return False