import asyncio
import logging
from app.services.population import calculator
from app.services.django_client import django_client


logger = logging.getLogger(__name__)


async def process_calculation(application_id: int, territory_area: float, orders: list) -> None:
    """Фоновая задача расчета"""
    try:
        logger.info(f"Starting calculation for application {application_id}")
        
        # Имитируем задержку
        await calculator.simulate_calculation()
        
        # Выполняем расчет
        population = await calculator.calculate_total_population(territory_area, orders)
        
        logger.info(f"Calculated population for app {application_id}: {population}")
        
        # Пытаемся отправить результат
        success = await django_client.send_result(application_id, population)
        
        if success:
            logger.info(f"Successfully processed application {application_id}")
        else:
            logger.error(f"Failed to send result for application {application_id}")
            
    except Exception as e:
        logger.error(f"Error processing application {application_id}: {e}")