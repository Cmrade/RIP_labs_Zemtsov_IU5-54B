from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Service(models.Model):
    """Модель услуг"""
    name = models.CharField(max_length=255, verbose_name='Наименование')
    description = models.TextField(verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Действует')
    image_url = models.URLField(null=True, blank=True, verbose_name='URL изображения')
    # Добавьте дополнительные поля по вашей предметной области
    population_density = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Плотность населения')
    area = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Площадь территории')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуги'


class Order(models.Model):
    """Модель заявок"""

    class OrderStatus(models.TextChoices):
        DRAFT = "DRAFT", "Черновик"
        DELETED = "DELETED", "Удалён"
        FORMED = "FORMED", "Сформирован"
        COMPLETED = "COMPLETED", "Завершён"
        REJECTED = "REJECTED", "Отклонён"

    status = models.CharField(
        max_length=10,
        choices=OrderStatus.choices,
        default=OrderStatus.DRAFT,
        verbose_name='Статус'
    )
    creation_date = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    formation_date = models.DateTimeField(null=True, blank=True, verbose_name='Дата формирования')
    completion_date = models.DateTimeField(null=True, blank=True, verbose_name='Дата завершения')
    client = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='orders', verbose_name='Создатель')
    moderator = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='moderated_orders',
        verbose_name='Модератор'
    )
    # Дополнительные поля по предметной области
    calculated_population = models.IntegerField(null=True, blank=True, verbose_name='Рассчитанная численность')
    client_comment = models.TextField(blank=True, verbose_name='Комментарий клиента')

    def clean(self):
        """Проверка: у пользователя не более одной заявки в статусе черновик"""
        if self.status == Order.OrderStatus.DRAFT:
            if Order.objects.filter(client=self.client, status=Order.OrderStatus.DRAFT).exclude(id=self.id).exists():
                raise ValidationError('У пользователя может быть только одна заявка в статусе черновик')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Заявка №{self.id} - {self.client.username}"

    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'


class ServiceInOrder(models.Model):
    """Модель связи многие-ко-многим (заявки-услуги)"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name='Заявка')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, verbose_name='Услуга')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Количество')
    order_index = models.IntegerField(default=0, verbose_name='Порядок')
    is_main = models.BooleanField(default=False, verbose_name='Главная услуга')

    # Поле, рассчитываемое при завершении заявки
    calculated_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
                                           verbose_name='Рассчитанное значение')

    def __str__(self):
        return f"{self.order} - {self.service}"

    class Meta:
        verbose_name = 'Услуга в заявке'
        verbose_name_plural = 'Услуги в заявках'
        unique_together = ('order', 'service')  # Составной уникальный ключ