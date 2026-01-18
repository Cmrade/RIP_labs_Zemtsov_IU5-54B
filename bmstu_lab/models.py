from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

class Orders(models.Model):
    title = models.CharField(max_length=30)
    main_information = models.CharField(max_length=255)
    image = models.CharField(max_length=255, blank=True, null=True)
    more_information = models.CharField(max_length=600, blank=True, null=True)
    app_flag = models.BooleanField(default=False)

    building_density = models.IntegerField(
        verbose_name='Плотность застройки (домов/га)',
        null=True,
        blank=True,
        help_text='Количество домов на гектар'
    )

    people_per_building = models.IntegerField(
        verbose_name='Количество человек в постройке',
        null=True,
        blank=True,
        help_text='Среднее количество людей в одном доме'
    )

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Тип населения'
        verbose_name_plural = 'Типы населения'
        db_table = 'bmstu_lab_orders'  # Добавляем явное имя таблицы


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
    client = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='created_density_calculations', null=True, blank=True)
    manager = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='managed_density_calculations', blank=True, null=True)

    # Пользовательские поля
    title = models.CharField(max_length=100, blank=True, null=True, verbose_name="Название расчета плотности")
    description = models.TextField(blank=True, null=True, verbose_name="Описание расчета плотности")

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
        return f"Расчет плотности № {self.id}"

    def save(self, *args, **kwargs):
        if not self.client_id and hasattr(self, '_current_user'):
            self.client = self._current_user
        super().save(*args, **kwargs)

    def calculate_population(self):
        """Расчет численности населения на основе выбранных типов населения"""
        if not self.territory_area or self.territory_area <= 0:
            return 0

        total_population = Decimal('0')

        for population_in_calc in self.orderinapplication_set.all():
            population = population_in_calc.order

            if population.building_density and population.people_per_building:
                # Преобразуем все значения в Decimal для точности
                population_calc = Decimal(str(self.territory_area)) * \
                             Decimal(str(population.building_density)) * \
                             Decimal(str(population.people_per_building))
                total_population += population_calc

        self.calculated_population = round(total_population, 2)
        self.save()

        return total_population

    def get_status_display(self):
        """Возвращает человеко-читаемое название статуса"""
        status_map = {
            'DRAFT': 'Черновик',
            'DELETED': 'Удален',
            'FORMED': 'Сформирован',
            'COMPLETED': 'Завершен',
            'REJECTED': 'Отклонен'
        }
        return status_map.get(self.status, self.status)

    def __str__(self):
        return f"Расчет плотности №{self.id} - {self.get_status_display()}"

    class Meta:
        verbose_name = 'Расчет плотности'
        verbose_name_plural = 'Расчеты плотности'
        db_table = 'bmstu_lab_application'  # Добавляем явное имя таблицы


class OrderInApplication(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    order = models.ForeignKey(Orders, on_delete=models.CASCADE)
    comment = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.application_id}-{self.order_id}"

    class Meta:
        unique_together = ('application', 'order')
        verbose_name = 'Население в расчете плотности'
        verbose_name_plural = 'Населения в расчетах плотности'
        db_table = 'bmstu_lab_orderindensitycalculation'  # Критически важно! Используем правильное имя таблицы


# Добавим после существующих моделей

class Media(models.Model):
    """Модель для хранения медиа-файлов (фото и видео) к типам населения"""

    class MediaType(models.TextChoices):
        IMAGE = 'image', 'Изображение'
        VIDEO = 'video', 'Видео'

    population = models.ForeignKey(
        Orders,
        on_delete=models.CASCADE,
        related_name='media_files',
        verbose_name='Тип населения'
    )

    file_url = models.CharField(
        max_length=500,
        verbose_name='URL файла в Minio'
    )

    file_type = models.CharField(
        max_length=10,
        choices=MediaType.choices,
        verbose_name='Тип файла'
    )

    upload_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата и время загрузки'
    )

    clip_embedding = models.BinaryField(
        null=True,
        blank=True,
        verbose_name='Векторное представление CLIP'
    )

    class Meta:
        verbose_name = 'Медиа-файл'
        verbose_name_plural = 'Медиа-файлы'
        ordering = ['id']  # Сортировка по умолчанию по ID
        db_table = 'bmstu_lab_media'  # Добавляем явное имя таблицы

    def __str__(self):
        return f"Медиа #{self.id} ({self.get_file_type_display()}) для {self.population.title}"

    def is_image(self):
        return self.file_type == self.MediaType.IMAGE

    def is_video(self):
        return self.file_type == self.MediaType.VIDEO