from django.db import models
from django.contrib.auth.models import User


class Orders(models.Model):
    title = models.CharField(max_length=30)
    main_information = models.CharField(max_length=255)
    image = models.CharField(max_length=255, blank=True, null=True)
    more_information = models.CharField(max_length=600, blank=True, null=True)
    app_flag = models.BooleanField(default=False)

    # НОВЫЕ ПОЛЯ ДЛЯ РАСЧЕТА
    building_density = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Плотность застройки [домов/га]"
    )
    people_per_building = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        blank=True,
        null=True,
        verbose_name="Плотность человек в постройке [чел/дом]"
    )

    def __str__(self):
        return self.title


class Application(models.Model):
    class ApplicationStatus(models.TextChoices):
        DRAFT = "DRAFT"
        DELETED = "DELETED"
        FORMED = "FORMED"
        COMPLETED = "COMPLETED"
        REJECTED = "REJECTED"

    status = models.CharField(
        max_length=10,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.DRAFT,
    )

    # Системные поля
    creation_datetime = models.DateTimeField(auto_now_add=True)
    formation_datetime = models.DateTimeField(blank=True, null=True)
    completion_datetime = models.DateTimeField(blank=True, null=True)
    client = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='created_orders', null=True, blank=True)
    manager = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='managed_orders', blank=True, null=True)

    # Пользовательские поля
    title = models.CharField(max_length=100, blank=True, null=True, verbose_name="Название заявки")
    description = models.TextField(blank=True, null=True, verbose_name="Описание заявки")

    # ПОЛЕ ПЛОЩАДИ ТЕРРИТОРИИ
    territory_area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Площадь территории (га)"
    )

    # ВЫЧИСЛЯЕМОЕ ПОЛЕ
    calculated_population = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Расчетная численность населения"
    )

    def __str__(self):
        return f"Заказ № {self.id}"

    def save(self, *args, **kwargs):
        # Автоматическое заполнение client при создании
        if not self.client_id and hasattr(self, '_current_user'):
            self.client = self._current_user
        super().save(*args, **kwargs)

    def calculate_population(self):
        """
        Расчет численности населения по формуле: N = П × P_д × P_ч
        где:
        П – площадь территории [га]
        P_д – плотность застройки [домов/га]
        P_ч – плотность человек в одной постройке [чел/дом]
        """
        if not self.territory_area:
            return 0

        # Получаем все услуги в заявке
        order_applications = self.orderinapplication_set.all()
        if not order_applications:
            return 0

        # Вычисляем средневзвешенные значения P_д и P_ч
        total_building_density = 0
        total_people_per_building = 0
        valid_orders = 0

        for order_app in order_applications:
            order = order_app.order
            if order.building_density and order.people_per_building:
                total_building_density += order.building_density
                total_people_per_building += order.people_per_building
                valid_orders += 1

        if valid_orders == 0:
            return 0

        # Средние значения
        avg_building_density = total_building_density / valid_orders
        avg_people_per_building = total_people_per_building / valid_orders

        # Применяем формулу: N = П × P_д × P_ч
        calculated_population = self.territory_area * avg_building_density * avg_people_per_building

        # Сохраняем вычисленное значение
        self.calculated_population = calculated_population
        self.save(update_fields=['calculated_population'])

        return calculated_population



class OrderInApplication(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    order = models.ForeignKey(Orders, on_delete=models.CASCADE)
    comment = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.application_id}-{self.order_id}"

    class Meta:
        unique_together = ('application', 'order'),