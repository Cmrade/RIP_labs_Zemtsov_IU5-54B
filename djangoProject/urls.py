"""djangoProject URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from bmstu_lab import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.get_orders_list_page),
    path('order_information_page/<int:id>/', views.get_order_page, name='order_url'),
    #path('sendText', views.sendText, name='sendText'),
    path('orders_page', views.get_orders_list_page, name='orders_url'),
    path('application_page/<int:id>', views.GetApplication, name='application_url'),
    path('orders_page/search', views.sendText, name='orders_search_url'),
    path('add_to_application/<int:order_id>/', views.add_to_application, name='add_to_application_url'),
    path('delete_application/<int:application_id>/', views.delete_application, name='delete_application_url'),
    #path('orders_page', views.status_to_true, name='add_to_application'),
]