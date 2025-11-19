import json
import pickle
from .redis_utils import get_redis_connection
from .models import Orders, Application


class RedisService:
    def __init__(self):
        self.redis = get_redis_connection()

    def cache_orders_list(self, timeout=3600):
        """Кэширование списка услуг"""
        if not self.redis:
            return False

        try:
            orders = Orders.objects.all()
            orders_data = []

            for order in orders:
                orders_data.append({
                    'id': order.id,
                    'title': order.title,
                    'main_information': order.main_information,
                    'image': order.image,
                    'more_information': order.more_information,
                    'building_density': str(order.building_density) if order.building_density else None,
                    'people_per_building': str(order.people_per_building) if order.people_per_building else None
                })

            # Сохраняем в Redis в формате JSON
            self.redis.setex(
                'orders_list',
                timeout,
                json.dumps(orders_data, ensure_ascii=False)
            )
            print(f"Кэшировано {len(orders_data)} услуг в Redis")
            return True

        except Exception as e:
            print(f"Ошибка кэширования услуг: {e}")
            return False

    def get_cached_orders(self):
        """Получение кэшированного списка услуг"""
        if not self.redis:
            return None

        try:
            cached_data = self.redis.get('orders_list')
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            print(f"Ошибка получения кэшированных данных: {e}")
            return None

    def cache_application_data(self, application_id, timeout=1800):
        """Кэширование данных заявки"""
        if not self.redis:
            return False

        try:
            application = Application.objects.get(id=application_id)
            application_data = {
                'id': application.id,
                'status': application.status,
                'title': application.title,
                'territory_area': str(application.territory_area) if application.territory_area else None,
                'calculated_population': str(
                    application.calculated_population) if application.calculated_population else None,
                'creation_datetime': application.creation_datetime.isoformat() if application.creation_datetime else None,
            }

            key = f'application_{application_id}'
            self.redis.setex(key, timeout, json.dumps(application_data, ensure_ascii=False))
            print(f"Кэширована заявка {application_id} в Redis")
            return True

        except Exception as e:
            print(f"Ошибка кэширования заявки: {e}")
            return False

    def get_cached_application(self, application_id):
        """Получение кэшированной заявки"""
        if not self.redis:
            return None

        try:
            key = f'application_{application_id}'
            cached_data = self.redis.get(key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            print(f"Ошибка получения кэшированной заявки: {e}")
            return None

    def cache_cart_count(self, user_id, count, timeout=3600):
        """Кэширование количества товаров в корзине"""
        if not self.redis:
            return False

        try:
            key = f'user_{user_id}_cart_count'
            self.redis.setex(key, timeout, count)
            return True
        except Exception as e:
            print(f"Ошибка кэширования корзины: {e}")
            return False

    def get_cached_cart_count(self, user_id):
        """Получение кэшированного количества товаров в корзине"""
        if not self.redis:
            return None

        try:
            key = f'user_{user_id}_cart_count'
            count = self.redis.get(key)
            return int(count) if count else None
        except Exception as e:
            print(f"Ошибка получения кэшированной корзины: {e}")
            return None

    def clear_cache_pattern(self, pattern):
        """Очистка кэша по паттерну"""
        if not self.redis:
            return False

        try:
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
                print(f"Удалено ключей: {len(keys)}")
            return True
        except Exception as e:
            print(f"Ошибка очистки кэша: {e}")
            return False