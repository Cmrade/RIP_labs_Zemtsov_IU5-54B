from django.db import models
from django.contrib.auth.models import User

class Orders(models.Model):
    title = models.CharField(max_length=30)
    main_information = models.CharField(max_length=255)
    image = models.CharField(max_length=255)
    more_information = models.CharField(max_length=600)
    app_flag = models.BooleanField(default=False)

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

    creation_datetime = models.DateTimeField(auto_now_add=True)
    formation_datetime = models.DateTimeField(blank=True, null=True)
    completion_datetime = models.DateTimeField(blank=True, null=True)
    client = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='created_orders', null=True, blank=True)
    manager = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='managed_orders', blank=True, null=True)

    def __str__(self):
        return f"Заказ № {self.id}"

class OrderInApplication(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    order = models.ForeignKey(Orders, on_delete=models.CASCADE)
    comment = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.application_id}-{self.order_id}"

    class Meta:
        unique_together = ('application', 'order'),