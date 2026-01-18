from fastapi import Header, HTTPException
from app.config import settings


async def verify_token(x_token: str = Header(None)) -> str:
    """Проверка токена авторизации"""
    if not x_token or x_token != settings.async_service_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing token"
        )
    return x_token