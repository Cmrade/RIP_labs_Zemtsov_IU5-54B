# bmstu_lab/management/commands/redis_operations.py
from django.core.management.base import BaseCommand, CommandError
from bmstu_lab.redis_service import RedisService
from django.contrib.auth.models import User
import json
import re


class Command(BaseCommand):
    help = 'Операции с Redis через Lua скрипты'

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-keys',
            action='store_true',
            dest='show_keys',
            help='Показать все ключи Redis'
        )
        parser.add_argument(
            '--show-sessions',
            action='store_true',
            dest='show_sessions',
            help='Показать активные сессии'
        )
        parser.add_argument(
            '--show-carts',
            action='store_true',
            dest='show_carts',
            help='Показать статистику корзин'
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            dest='clear_cache',
            help='Очистить кэш'
        )
        parser.add_argument(
            '--search',
            type=str,
            dest='search',
            help='Поиск услуг по тексту'
        )

    def handle(self, *args, **options):
        redis_service = RedisService()

        if not redis_service.redis:
            self.stdout.write(self.style.ERROR('Redis не доступен!'))
            return

        self.stdout.write(self.style.SUCCESS('=== Redis Operations ==='))

        if options['show_keys']:
            self.show_keys(redis_service)

        if options['show_sessions']:
            self.show_sessions(redis_service)

        if options['show_carts']:
            self.show_carts(redis_service)

        if options['clear_cache']:
            self.clear_cache(redis_service)

        if options['search']:
            self.search_orders(redis_service, options['search'])

        # Если не указаны аргументы, показываем справку
        if not any([options['show_keys'], options['show_sessions'],
                    options['show_carts'], options['clear_cache'],
                    options['search']]):
            self.stdout.write(self.style.WARNING('Используйте аргументы:'))
            self.stdout.write('  --show-keys     - показать все ключи Redis')
            self.stdout.write('  --show-sessions - показать активные сессии')
            self.stdout.write('  --show-carts    - показать статистику корзин')
            self.stdout.write('  --clear-cache   - очистить кэш')
            self.stdout.write('  --search текст  - поиск услуг')

    def show_keys(self, redis_service):
        """Показать все ключи через Lua"""
        self.stdout.write(self.style.SUCCESS('=== Все ключи Redis ==='))

        try:
            # Простой Lua скрипт для получения всех ключей с их типами
            lua_script = """
            local keys = redis.call('KEYS', '*')
            local result = {}
            for i, key in ipairs(keys) do
                local key_type = redis.call('TYPE', key)['ok']
                local ttl = redis.call('TTL', key)
                table.insert(result, {key, key_type, ttl})
            end
            return result
            """

            keys = redis_service.redis.eval(lua_script, 0)

            if not keys:
                self.stdout.write('Ключей нет')
                return

            for key_info in keys:
                key_name = key_info[0]
                key_type = key_info[1]
                ttl = key_info[2]

                if ttl == -1:
                    ttl_str = 'нет'
                elif ttl == -2:
                    ttl_str = 'истек'
                else:
                    ttl_str = f'{ttl} сек'

                self.stdout.write(f'{self.style.HTTP_INFO(key_name)} | Тип: {key_type} | TTL: {ttl_str}')

            self.stdout.write(self.style.SUCCESS(f'Всего ключей: {len(keys)}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка: {str(e)}'))

    def show_sessions(self, redis_service):
        """Показать активные сессии через Lua"""
        self.stdout.write(self.style.SUCCESS('=== Активные сессии ==='))

        try:
            # Lua скрипт для поиска сессий Django
            lua_script = """
            -- Получаем все ключи сессий (формат может отличаться)
            local session_patterns = {
                '*session*',
                'django.contrib.sessions.*',
                ':1:django.contrib.sessions.*'
            }

            local all_sessions = {}

            for _, pattern in ipairs(session_patterns) do
                local keys = redis.call('KEYS', pattern)
                for _, key in ipairs(keys) do
                    table.insert(all_sessions, key)
                end
            end

            -- Удаляем дубликаты
            local unique_sessions = {}
            for _, session_key in ipairs(all_sessions) do
                unique_sessions[session_key] = true
            end

            local result = {}
            for session_key, _ in pairs(unique_sessions) do
                table.insert(result, session_key)
            end

            return result
            """

            sessions = redis_service.redis.eval(lua_script, 0)

            if not sessions:
                self.stdout.write('Нет активных сессий')
                return

            session_count = 0
            for session_key in sessions:
                try:
                    # Получаем данные сессии
                    session_data = redis_service.redis.get(session_key)
                    if session_data:
                        # Пытаемся найти user_id в данных сессии
                        # Django хранит сессии в формате: "user_id:123:_auth_user_hash:..."
                        match = re.search(r'user_id:(\d+):', session_data.decode('utf-8', errors='ignore'))
                        if match:
                            user_id = match.group(1)
                            try:
                                user = User.objects.get(id=int(user_id))
                                username = user.username
                            except:
                                username = f'Пользователь ID:{user_id}'
                        else:
                            username = 'Анонимная сессия'

                        self.stdout.write(f'Сессия: {session_key[:50]}...')
                        self.stdout.write(f'  Пользователь: {username}')
                        self.stdout.write(f'  Размер данных: {len(session_data)} байт')
                        session_count += 1

                except Exception as e:
                    self.stdout.write(f'Сессия: {session_key[:50]}... (ошибка чтения: {e})')

            self.stdout.write(self.style.SUCCESS(f'Всего активных сессий: {session_count}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка: {str(e)}'))

    def show_carts(self, redis_service):
        """Показать статистику корзин"""
        self.stdout.write(self.style.SUCCESS('=== Статистика корзин ==='))

        try:
            # Lua скрипт для получения статистики корзин
            lua_script = """
            local cart_keys = redis.call('KEYS', '*cart*')
            local total_items = 0
            local carts = {}

            for _, key in ipairs(cart_keys) do
                local value = redis.call('GET', key)
                if value then
                    local items = tonumber(value) or 0
                    total_items = total_items + items
                    table.insert(carts, {key, items})
                end
            end

            return {#cart_keys, total_items, carts}
            """

            result = redis_service.redis.eval(lua_script, 0)

            if not result:
                self.stdout.write('Нет данных о корзинах')
                return

            total_carts = result[0]
            total_items = result[1]
            carts = result[2]

            self.stdout.write(f'Всего корзин: {total_carts}')
            self.stdout.write(f'Всего товаров: {total_items}')

            if carts:
                self.stdout.write(self.style.SUCCESS('Детали по корзинам:'))
                for cart_info in carts:
                    key = cart_info[0]
                    items = cart_info[1]
                    # Извлекаем user_id из ключа
                    match = re.search(r'user_(\d+)_cart', key)
                    if match:
                        user_id = match.group(1)
                        try:
                            user = User.objects.get(id=int(user_id))
                            username = user.username
                        except:
                            username = f'ID:{user_id}'
                    else:
                        username = 'Неизвестный'

                    self.stdout.write(f'  {username}: {items} товаров')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка: {str(e)}'))

    def clear_cache(self, redis_service):
        """Очистить кэш через Lua"""
        self.stdout.write(self.style.WARNING('Очистка кэша...'))

        try:
            # Lua скрипт для очистки кэша
            lua_script = """
            -- Паттерны для поиска ключей кэша
            local patterns = {
                'orders*',
                'application*',
                '*cart*',
                'user_*'
            }

            local deleted = 0
            local preserved = 0

            for _, pattern in ipairs(patterns) do
                local keys = redis.call('KEYS', pattern)
                for _, key in ipairs(keys) do
                    -- Не удаляем сессии
                    if not string.find(key, 'session') and 
                       not string.find(key, 'django.contrib.sessions') then
                        redis.call('DEL', key)
                        deleted = deleted + 1
                    else
                        preserved = preserved + 1
                    end
                end
            end

            return {deleted, preserved}
            """

            result = redis_service.redis.eval(lua_script, 0)
            deleted = result[0]
            preserved = result[1]

            self.stdout.write(self.style.SUCCESS(f'Удалено ключей: {deleted}'))
            self.stdout.write(self.style.WARNING(f'Сохранено (сессии): {preserved}'))

            # Пересоздаем кэш заказов
            self.stdout.write('Пересоздание кэша заказов...')
            redis_service.cache_orders_list()
            self.stdout.write(self.style.SUCCESS('Кэш пересоздан'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка: {str(e)}'))

    def search_orders(self, redis_service, search_term):
        """Поиск услуг"""
        self.stdout.write(self.style.SUCCESS(f'=== Поиск: "{search_term}" ==='))

        try:
            # Lua скрипт для поиска в кэше
            lua_script = f"""
            local search_term = '{search_term.lower()}'
            local orders_key = 'orders_list'
            local orders_json = redis.call('GET', orders_key)

            if not orders_json then
                return {{}}
            end

            local orders = cjson.decode(orders_json)
            local results = {{}}

            for i, order in ipairs(orders) do
                local title = string.lower(order.title or '')
                local info = string.lower(order.main_information or '')

                if string.find(title, search_term) or string.find(info, search_term) then
                    table.insert(results, order)
                end
            end

            return results
            """

            results = redis_service.redis.eval(lua_script, 0)

            if not results:
                self.stdout.write('Ничего не найдено')
                return

            self.stdout.write(self.style.SUCCESS(f'Найдено записей: {len(results)}'))

            for order in results:
                self.stdout.write(f'\nУслуга: {self.style.HTTP_INFO(order.get("title", "Без названия"))}')
                self.stdout.write(f'  Описание: {order.get("main_information", "")[:100]}...')
                if order.get("building_density"):
                    self.stdout.write(f'  Плотность застройки: {order.get("building_density")}')
                if order.get("people_per_building"):
                    self.stdout.write(f'  Людей в постройке: {order.get("people_per_building")}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка поиска: {str(e)}'))