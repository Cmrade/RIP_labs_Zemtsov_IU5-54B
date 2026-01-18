# bmstu_lab/authentication.py
from rest_framework.authentication import SessionAuthentication
import logging

logger = logging.getLogger(__name__)


class SessionAuthenticationWithoutCSRF(SessionAuthentication):
    """Session authentication без проверки CSRF"""

    def authenticate(self, request):
        # Вызываем родительский метод для получения пользователя из сессии
        user_auth_tuple = super().authenticate(request)

        if user_auth_tuple is None:
            # Если не удалось аутентифицировать через родительский метод,
            # проверяем сессию вручную
            logger.info(f"🔐 [SessionAuth] Пытаемся аутентифицировать вручную")

            # Проверяем сессию через стандартный механизм Django
            if hasattr(request, 'user') and request.user.is_authenticated:
                logger.info(f"✅ [SessionAuth] Пользователь уже аутентифицирован: {request.user.username}")
                return (request.user, None)

            logger.warning("❌ [SessionAuth] Не удалось аутентифицировать пользователя")
            return None

        user, auth = user_auth_tuple
        logger.info(f"✅ [SessionAuth] Аутентификация успешна: {user.username}")
        return user_auth_tuple

    def enforce_csrf(self, request):
        """Отключаем проверку CSRF"""
        return  # Ничего не делаем, пропускаем проверку CSRF