# fastapi_app.py
from fastapi import FastAPI, HTTPException, Request
import httpx
import asyncio
import logging

logger = logging.getLogger(__name__)

app = FastAPI()

DJANGO_BASE_URL = "http://localhost:8000"

@app.post("/calculate_population")
async def calculate_population(request: Request):
    """
    Эндпоинт для расчета населения БЕЗ проверки авторизации
    Проверяется только сервисный токен
    """
    
    try:
        # Получаем данные
        data = await request.json()
        application_id = data.get('application_id')
        service_token = data.get('token')
        
        logger.info(f"📥 Получен запрос на расчет: application_id={application_id}")
        
        # Проверяем только сервисный токен
        if service_token != "my-secret-token-12345":
            logger.error(f"❌ Неверный сервисный токен: {service_token}")
            raise HTTPException(status_code=401, detail="Invalid service token")
        
        logger.info(f"✅ Сервисный токен валиден, запуск расчета для application_id={application_id}")
        
        # Имитируем асинхронный расчет
        async def background_calculation():
            await asyncio.sleep(5)
            
            territory_area = data.get('territory_area', 0)
            orders = data.get('orders', [])
            
            total = 0
            for order in orders:
                building_density = order.get('building_density', 0)
                people_per_building = order.get('people_per_building', 0)
                total += territory_area * building_density * people_per_building
            
            final_population = int(total * 1.05)
            
            logger.info(f"✅ Расчет завершен: {final_population}")
            
            # Отправляем результат в Django
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{DJANGO_BASE_URL}/api/density_calculations/{application_id}/async_result/",
                        json={
                            'async_population': final_population,
                            'auth_token': 'my-secret-token-12345'
                        },
                        timeout=10
                    )
                    logger.info(f"✅ Результат отправлен в Django")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки результата: {e}")
        
        # Запускаем расчет в фоне
        asyncio.create_task(background_calculation())
        
        return {
            "status": "processing",
            "message": "Расчет запущен",
            "application_id": application_id,
            "estimated_time": "5 секунд"
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка в calculate_population: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/test_endpoint")
async def test_endpoint(request: Request):
    """Тестовый эндпоинт без проверок"""
    data = await request.json()
    return {
        "message": "Endpoint works without authentication",
        "received_data": data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8081, log_level="info")