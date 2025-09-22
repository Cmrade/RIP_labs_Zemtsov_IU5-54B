from django.contrib import admin
from .models import Service, Order, ServiceInOrder

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'population_density')
    list_filter = ('is_active',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'client', 'creation_date')
    list_filter = ('status', 'creation_date')

@admin.register(ServiceInOrder)
class ServiceInOrderAdmin(admin.ModelAdmin):
    list_display = ('order', 'service', 'quantity', 'is_main')