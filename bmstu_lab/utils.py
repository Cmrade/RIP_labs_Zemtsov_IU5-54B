from django.contrib.auth.models import User

def get_fixed_user():
    """Функция-singleton для получения фиксированного пользователя"""
    user, created = User.objects.get_or_create(
        username='Admin1',
        defaults={
            'email': 'admin1@example.com',
            'is_staff': True
        }
    )
    if created:
        user.set_password('admin')
        user.save()
    return user