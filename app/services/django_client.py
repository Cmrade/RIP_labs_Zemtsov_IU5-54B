import asyncio
import httpx
import logging
from app.config import settings


logger = logging.getLogger(__name__)


class DjangoClient:
    """Клиент для взаимодействия с Django"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def send_result(self, application_id: int, population: int) -> bool:
        """Отправка результата в Django"""
        url = f"{settings.django_url}/api/density_calculations/{application_id}/async_result/"
        
        data = {
            "async_population": population,
            "calculation_status": "completed",
            "calculation_method": "async_refined",
            "auth_token": settings.django_auth_token,
        }
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Sending result to Django (attempt {attempt}): {url}")
                
                response = await self.client.post(url, json=data)
                
                if response.status_code == 200:
                    logger.info(f"Successfully sent result for application {application_id}")
                    return True
                else:
                    logger.error(f"Django returned error {response.status_code}: {response.text}")
                    
            except Exception as e:
                logger.error(f"Error sending result (attempt {attempt}): {e}")
            
            if attempt < max_retries:
                await asyncio.sleep(attempt * 2)
        
        return False
    
    async def close(self):
        """Закрытие клиента"""
        await self.client.aclose()


django_client = DjangoClient()