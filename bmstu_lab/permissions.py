from rest_framework import permissions

class IsOwner(permissions.BasePermission):
    """
    Разрешение только для владельца объекта
    """
    def has_object_permission(self, request, view, obj):
        return obj.client == request.user

class IsModerator(permissions.BasePermission):
    """
    Разрешение только для модераторов
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_staff

class IsOwnerOrModerator(permissions.BasePermission):
    """
    Разрешение для владельца или модератора
    """
    def has_object_permission(self, request, view, obj):
        return obj.client == request.user or request.user.is_staff

class IsAuthenticatedOrReadOnlyForNonModerator(permissions.BasePermission):
    """
    Разрешение: чтение для всех, запись только для аутентифицированных,
    определенные действия только для модераторов
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated