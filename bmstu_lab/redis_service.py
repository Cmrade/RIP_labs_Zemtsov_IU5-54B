import json
import redis
from django.conf import settings
from .models import Orders  # Модель осталась с тем же именем
from .serializers import PopulationsSerializer  # Изменено с OrdersSerializer на PopulationsSerializer
from django.core.cache import cache


class RedisService:
    def __init__(self):
        # Пытаемся подключиться к Redis
        try:
            self.redis_client = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0),
                decode_responses=True
            )
            self.redis_client.ping()  # Проверяем подключение
            print("✅ Redis подключен успешно")
        except redis.ConnectionError:
            print("❌ Не удалось подключиться к Redis, используется Django cache")
            self.redis_client = None

    def get_cached_populations(self):  # Изменено get_cached_orders -> get_cached_populations
        """Получить закэшированные типы населения"""
        cache_key = 'populations_list'  # Изменено 'orders_list' -> 'populations_list'

        # Пробуем получить из Redis
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    print("📦 Используются кэшированные данные популяций из Redis")
                    return json.loads(cached_data)
            except Exception as e:
                print(f"❌ Ошибка при получении популяций из Redis: {e}")

        # Пробуем получить из Django cache
        cached_data = cache.get(cache_key)
        if cached_data:
            print("📦 Используются кэшированные данные популяций из Django cache")
            return cached_data

        return None

    def cache_populations_list(self):  # Изменено cache_orders_list -> cache_populations_list
        """Кэшировать список типов населения"""
        cache_key = 'populations_list'  # Изменено 'orders_list' -> 'populations_list'

        try:
            # Получаем данные из базы
            populations = Orders.objects.all()  # Модель все еще Orders
            serializer = PopulationsSerializer(populations, many=True)  # Изменено OrdersSerializer на PopulationsSerializer
            data = serializer.data

            # Кэшируем в Redis
            if self.redis_client:
                try:
                    self.redis_client.setex(
                        cache_key,
                        3600,  # Время жизни кэша в секундах (1 час)
                        json.dumps(data)
                    )
                    print("✅ Данные популяций успешно закэшированы в Redis")
                except Exception as e:
                    print(f"❌ Ошибка при кэшировании популяций в Redis: {e}")

            # Кэшируем в Django cache
            cache.set(cache_key, data, 3600)
            print("✅ Данные популяций успешно закэшированы в Django cache")

        except Exception as e:
            print(f"❌ Ошибка при кэшировании типов населения: {e}")

    def invalidate_populations_cache(self):  # Изменено invalidate_orders_cache -> invalidate_populations_cache
        """Инвалидировать кэш типов населения"""
        cache_key = 'populations_list'  # Изменено 'orders_list' -> 'populations_list'

        # Удаляем из Redis
        if self.redis_client:
            try:
                self.redis_client.delete(cache_key)
                print("🗑️ Кэш популяций Redis очищен")
            except Exception as e:
                print(f"❌ Ошибка при очистке кэша популяций Redis: {e}")

        # Удаляем из Django cache
        cache.delete(cache_key)
        print("🗑️ Django cache популяций очищен")

    def get_cached_cart_count(self, user_id):
        """Получить количество товаров в корзине из кэша"""
        cache_key = f'cart_count_{user_id}'

        if self.redis_client:
            try:
                count = self.redis_client.get(cache_key)
                if count:
                    return int(count)
            except Exception as e:
                print(f"❌ Ошибка при получении количества корзины из Redis: {e}")

        return cache.get(cache_key)

    def cache_cart_count(self, user_id, count):
        """Кэшировать количество товаров в корзине"""
        cache_key = f'cart_count_{user_id}'

        if self.redis_client:
            try:
                self.redis_client.setex(cache_key, 300, count)  # 5 минут
            except Exception as e:
                print(f"❌ Ошибка при кэшировании количества корзины в Redis: {e}")

        cache.set(cache_key, count, 300)

    def invalidate_cart_cache(self, user_id):
        """Инвалидировать кэш корзины"""
        cache_key = f'cart_count_{user_id}'

        if self.redis_client:
            try:
                self.redis_client.delete(cache_key)
            except Exception as e:
                print(f"❌ Ошибка при очистке кэша корзины Redis: {e}")

        cache.delete(cache_key)

    # Методы для обратной совместимости (опционально, можно удалить позже)
    def get_cached_orders(self):
        """Устаревший метод для обратной совместимости"""
        print("⚠️ Используется устаревший метод get_cached_orders(), используйте get_cached_populations()")
        return self.get_cached_populations()

    def cache_orders_list(self):
        """Устаревший метод для обратной совместимости"""
        print("⚠️ Используется устаревший метод cache_orders_list(), используйте cache_populations_list()")
        self.cache_populations_list()

    def invalidate_orders_cache(self):
        """Устаревший метод для обратной совместимости"""
        print("⚠️ Используется устаревший метод invalidate_orders_cache(), используйте invalidate_populations_cache()")
        self.invalidate_populations_cache()