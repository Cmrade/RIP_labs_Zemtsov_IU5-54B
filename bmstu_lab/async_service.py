import requests
from django.conf import settings
import logging
from decimal import Decimal
import json
from .utils import decimal_to_float, DecimalEncoder
from .models import Orders

logger = logging.getLogger(__name__)


class AsyncPopulationService:
    """Сервис для асинхронного расчета численности населения"""

    @staticmethod
    def send_calculation_request(density_calculation):
        """
        Отправляет расчет плотности на асинхронный расчет в Go-сервис
        """
        try:
            # Подготавливаем данные для отправки
            orders_data = []

            for population_in_calc in density_calculation.orderinapplication_set.all():
                population = population_in_calc.order

                # Убедимся, что значения целочисленные и преобразуем в int
                building_density = int(population.building_density) if population.building_density else 0
                people_per_building = int(population.people_per_building) if population.people_per_building else 0

                orders_data.append({
                    'building_density': building_density,
                    'people_per_building': people_per_building,
                })

            # Преобразуем Decimal в float для сериализации JSON
            territory_area = float(density_calculation.territory_area) if density_calculation.territory_area else 0.0

            # Формируем запрос
            payload = {
                'application_id': density_calculation.id,
                'territory_area': territory_area,
                'orders': orders_data,
                'token': settings.ASYNC_SERVICE_TOKEN,
            }

            # Рекурсивно преобразуем все Decimal во float
            payload = decimal_to_float(payload)

            # Логируем данные для отладки
            logger.info(f"Sending async calculation request for density calculation {density_calculation.id}")
            logger.info(f"Payload: {json.dumps(payload, indent=2, cls=DecimalEncoder)}")
            logger.info(f"Go service URL: {settings.ASYNC_SERVICE_URL}/calculate_population")

            # Отладочная информация о типах данных
            for i, order in enumerate(orders_data):
                logger.info(
                    f"Order {i}: building_density={order['building_density']} (type: {type(order['building_density'])}), "
                    f"people_per_building={order['people_per_building']} (type: {type(order['people_per_building'])})")

            # Явно сериализуем с помощью нашего энкодера
            json_data = json.dumps(payload, cls=DecimalEncoder)

            # Отправляем запрос в Go-сервис
            response = requests.post(
                f"{settings.ASYNC_SERVICE_URL}/calculate_population",
                data=json_data,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )

            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response content: {response.text}")

            if response.status_code == 202:  # Accepted
                logger.info(f"Async calculation started for density calculation {density_calculation.id}")
                return {
                    'status': 'processing',
                    'message': 'Расчет запущен в асинхронном режиме',
                    'response': response.json() if response.content else None
                }
            else:
                logger.error(f"Async service error: {response.status_code}, Response: {response.text}")
                return {
                    'status': 'error',
                    'message': f'Ошибка сервиса: {response.status_code}',
                    'response': response.text
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Async service connection error: {e}")
            return {
                'status': 'error',
                'message': f'Ошибка подключения к Go-сервису: {str(e)}',
            }
        except Exception as e:
            logger.error(f"Unexpected error in async service: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': f'Неожиданная ошибка: {str(e)}',
            }