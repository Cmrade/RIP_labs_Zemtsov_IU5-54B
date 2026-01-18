# async_service.py
import requests
import logging

logger = logging.getLogger(__name__)


class AsyncPopulationService:
    def __init__(self):
        self.base_url = 'http://localhost:8081'
        self.token = 'my-secret-token-12345'
        self.timeout = 10

    def send_calculation_request(self, application, session_key=None):
        """Отправляет запрос на расчет в FastAPI сервис (без проверки сессии)"""

        try:
            # Формируем данные для расчета
            orders_data = []
            for order_in_app in application.orderinapplication_set.all():
                order = order_in_app.order
                orders_data.append({
                    "building_density": float(order.building_density or 0),
                    "people_per_building": float(order.people_per_building or 0)
                })

            # Данные для отправки
            payload = {
                "application_id": application.id,
                "token": self.token,
                "territory_area": float(application.territory_area or 0),
                "orders": orders_data
            }

            headers = {
                "Content-Type": "application/json",
                "X-Token": self.token
            }

            logger.info(f"📤 Отправка запроса в FastAPI: {self.base_url}/calculate_population")

            # Отправляем запрос без cookies (сессия не нужна)
            response = requests.post(
                f"{self.base_url}/calculate_population",
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            logger.info(f"📥 Ответ от FastAPI: статус {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'processing':
                    logger.info(f"✅ Расчет запущен для заявки {application.id}")
                    return {
                        "status": "processing",
                        "message": "Расчет запущен успешно",
                        "response": result
                    }
                else:
                    logger.error(f"❌ Ошибка от сервиса: {result}")
                    return {
                        "status": "error",
                        "message": result.get('detail', 'Неизвестная ошибка'),
                        "response": result
                    }
            elif response.status_code == 401:
                logger.error(f"❌ Неавторизован: Неверный сервисный токен")
                return {
                    "status": "error",
                    "message": "Неверный сервисный токен",
                    "response": response.text
                }
            else:
                logger.error(f"❌ Ошибка от сервиса: {response.status_code}")
                return {
                    "status": "error",
                    "message": f"Ошибка от сервиса: {response.status_code}",
                    "response": response.text
                }

        except requests.exceptions.ConnectionError:
            logger.error(f"❌ FastAPI сервис недоступен: {self.base_url}")
            return {
                "status": "error",
                "message": "Асинхронный сервис недоступен",
                "response": None
            }
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке запроса: {e}")
            return {
                "status": "error",
                "message": f"Ошибка: {str(e)}",
                "response": None
            }


async_population_service = AsyncPopulationService()