# bmstu_lab/middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class DisableCSRFForAPI(MiddlewareMixin):
    """Отключает CSRF для всех API запросов"""

    def process_request(self, request):
        # Отключаем CSRF для всех запросов, начинающихся с /api/
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
            logger.debug(f"🔐 [DisableCSRFForAPI] CSRF отключен для: {request.path}")


class StrictSessionMiddleware(MiddlewareMixin):
    """Middleware для строгой проверки сессий"""

    def __call__(self, request):
        # Проверяем только API запросы
        if request.path.startswith('/api/'):
            session_key = request.COOKIES.get('sessionid')

            if session_key:
                try:
                    # Ищем сессию в базе данных
                    session = Session.objects.get(
                        session_key=session_key,
                        expire_date__gt=timezone.now()
                    )

                    # Получаем пользователя из сессии
                    session_data = session.get_decoded()
                    user_id = session_data.get('_auth_user_id')

                    if user_id:
                        try:
                            user = User.objects.get(id=user_id)
                            request.user = user  # Устанавливаем пользователя
                            logger.info(f"✅ [StrictSession] Установлен пользователь: {user.username}")
                        except User.DoesNotExist:
                            logger.warning(f"⚠️ [StrictSession] Пользователь с ID {user_id} не найден")
                            request.user = AnonymousUser()
                    else:
                        logger.warning(f"⚠️ [StrictSession] В сессии нет user_id")
                        request.user = AnonymousUser()

                except Session.DoesNotExist:
                    logger.warning(f"⚠️ [StrictSession] Сессия не найдена или истекла: {session_key}")
                    request.user = AnonymousUser()
            else:
                logger.warning("⚠️ [StrictSession] Нет sessionid в cookies")
                request.user = AnonymousUser()

        response = self.get_response(request)
        return response


class DebugSessionMiddleware(MiddlewareMixin):
    """Middleware для отладки сессий и аутентификации"""

    def process_request(self, request):
        # Логируем информацию об аутентификации
        logger.info(f"🔐 [DebugSession] Путь: {request.path}")
        logger.info(f"🔐 [DebugSession] Session key: {request.session.session_key}")
        logger.info(f"🔐 [DebugSession] User: {request.user.username if request.user.is_authenticated else 'Anonymous'}")
        logger.info(f"🔐 [DebugSession] Authenticated: {request.user.is_authenticated}")
        logger.info(f"🔐 [DebugSession] User ID: {request.user.id if request.user.is_authenticated else 'None'}")

        return None