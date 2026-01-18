import os
import logging

logger = logging.getLogger(__name__)


class Settings:
    """Настройки приложения"""
    
    def __init__(self):
        # Читаем из .env или используем значения по умолчанию
        self.django_url = os.getenv("DJANGO_URL", "http://127.0.0.1:8000")
        self.async_service_token = os.getenv("ASYNC_SERVICE_TOKEN", "my-secret-token-12345")
        self.django_auth_token = os.getenv("DJANGO_AUTH_TOKEN", "django-secret-token-67890")
        
        self.host = os.getenv("HOST", "127.0.0.1")
        self.port = int(os.getenv("PORT", "8081"))
        
        self.delay_min = int(os.getenv("DELAY_MIN", "5"))
        self.delay_max = int(os.getenv("DELAY_MAX", "10"))
        
        self.frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:3000")
        
        logger.info(f"Configuration loaded: Django={self.django_url}, Port={self.port}")
    
    @property
    def django_async_result_url(self) -> str:
        return f"{self.django_url}/api/density_calculations"


# Создаем экземпляр настроек
settings = Settings()