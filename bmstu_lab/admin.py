from django.contrib import admin

# Register your models here.
from django.contrib import admin

from bmstu_lab.models import Orders, Application, OrderInApplication

admin.site.register(Orders)
admin.site.register(Application)
admin.site.register(OrderInApplication)