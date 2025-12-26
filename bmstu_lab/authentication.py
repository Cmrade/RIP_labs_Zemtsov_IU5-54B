# bmstu_lab/authentication.py
from rest_framework.authentication import SessionAuthentication as BaseSessionAuthentication

class SessionAuthenticationWithoutCSRF(BaseSessionAuthentication):
    def enforce_csrf(self, request):
        return  # Отключаем проверку CSRF для API