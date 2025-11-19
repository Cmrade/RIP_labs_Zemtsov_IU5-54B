from django.core.management.base import BaseCommand
from bmstu_lab.redis_service import RedisService
from bmstu_lab.redis_utils import test_redis_connection


class Command(BaseCommand):
    help = 'Операции с Redis'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            help='Действие: test, cache_orders, cache_applications, clear_cache'
        )

    def handle(self, *args, **options):
        action = options.get('action', 'test')
        redis_service = RedisService()

        if action == 'test':
            if test_redis_connection():
                self.stdout.write(
                    self.style.SUCCESS('Redis подключен успешно!')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Ошибка подключения к Redis!')
                )

        elif action == 'cache_orders':
            if redis_service.cache_orders_list():
                self.stdout.write(
                    self.style.SUCCESS('Услуги закэшированы в Redis')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Ошибка кэширования услуг')
                )

        elif action == 'clear_cache':
            if redis_service.clear_cache_pattern('*'):
                self.stdout.write(
                    self.style.SUCCESS('Кэш очищен')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Ошибка очистки кэша')
                )