from django.utils.deprecation import MiddlewareMixin

class DisableCSRFForAPI(MiddlewareMixin):
    """
    Middleware для отключения CSRF проверки для API запросов
    """
    def process_request(self, request):
        # Отключаем CSRF для всех API запросов
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)