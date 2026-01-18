from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.dependencies import verify_token
from app.core.background import process_calculation


router = APIRouter()


@router.post("/calculate_population")
async def calculate_population(
    data: dict,
    background_tasks: BackgroundTasks,
    token: str = verify_token
):
    """Запуск расчета населения"""
    # Проверяем обязательные поля
    required_fields = ["application_id", "token", "territory_area", "orders"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")
    
    # Проверяем токен (простая проверка)
    if data["token"] != "my-secret-token-12345":
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Запускаем фоновую задачу
    background_tasks.add_task(
        process_calculation,
        data["application_id"],
        data["territory_area"],
        data["orders"]
    )
    
    return {
        "message": "Population calculation initiated",
        "application_id": data["application_id"],
        "status": "processing",
        "estimated_delay": "5-10 seconds"
    }


@router.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "ok",
        "service": "async-population-calculator",
        "version": "1.0.0"
    }


@router.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "Async Population Service",
        "docs": "/docs",
        "health": "/health"
    }