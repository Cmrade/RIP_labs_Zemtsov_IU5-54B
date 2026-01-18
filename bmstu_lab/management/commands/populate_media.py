import os
from django.core.management.base import BaseCommand
from django.conf import settings
from bmstu_lab.models import Orders, Media
import requests


class Command(BaseCommand):
    help = 'Заполняет таблицу Media тестовыми данными из Minio'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minio-url',
            type=str,
            default='http://localhost:9000',
            help='URL Minio сервера'
        )

    def handle(self, *args, **options):
        minio_url = options['minio_url']

        # Тестовые данные: предполагаем, что у каждого типа населения есть файлы в Minio
        test_media = {
            1: [  # Древний город
                {'file_url': f'{minio_url}/media/population_1_photo1.jpg', 'file_type': 'image'},
                {'file_url': f'{minio_url}/media/population_1_photo2.jpg', 'file_type': 'image'},
                {'file_url': f'{minio_url}/media/population_1_video.mp4', 'file_type': 'video'},
            ],
            2: [  # Крепость
                {'file_url': f'{minio_url}/media/population_2_photo1.jpg', 'file_type': 'image'},
                {'file_url': f'{minio_url}/media/population_2_photo2.jpg', 'file_type': 'image'},
                {'file_url': f'{minio_url}/media/population_2_photo3.jpg', 'file_type': 'image'},
            ],
            3: [  # Село
                {'file_url': f'{minio_url}/media/population_3_photo1.jpg', 'file_type': 'image'},
                {'file_url': f'{minio_url}/media/population_3_video1.mp4', 'file_type': 'video'},
                {'file_url': f'{minio_url}/media/population_3_video2.mp4', 'file_type': 'video'},
            ]
        }

        created_count = 0

        for population_id, media_list in test_media.items():
            try:
                population = Orders.objects.get(id=population_id)

                for media_data in media_list:
                    # Проверяем существование файла в Minio (опционально)
                    try:
                        # Можно сделать HEAD запрос для проверки существования файла
                        # response = requests.head(media_data['file_url'])
                        # if response.status_code == 200:

                        # Создаем запись в базе данных
                        Media.objects.create(
                            population=population,
                            file_url=media_data['file_url'],
                            file_type=media_data['file_type']
                        )
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Создана запись для типа населения {population_id}: {media_data["file_url"]}'
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Ошибка при создании записи {media_data["file_url"]}: {str(e)}'
                            )
                        )

            except Orders.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Тип населения с ID {population_id} не найден')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Создано {created_count} записей в таблице Media')
        )