from django.contrib import admin
from django.urls import path, include
from bmstu_lab import views

from rest_framework.routers import DefaultRouter
from bmstu_lab.api_views import *

from django.conf import settings
from django.conf.urls.static import static

# Импорты для drf-spectacular
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from bmstu_lab.api_views import CSRFTokenView
router = DefaultRouter()
router.register(r'orders', OrdersViewSet)
router.register(r'applications', ApplicationViewSet)
router.register(r'order-in-application', OrderInApplicationViewSet)
router.register(r'users', UserViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.get_orders_list_page),
    path('information_about_object/<int:id>/', views.get_order_page, name='order_url'),
    path('archaeologic_objects', views.get_orders_list_page, name='orders_url'),
    path('calculate_of_population/<int:id>', views.GetApplication, name='application_url'),
    path('archaeologic_objects/search', views.sendText, name='orders_search_url'),
    path('add_to_application/<int:order_id>/', views.add_to_application, name='add_to_application_url'),
    path('delete_application/<int:application_id>/', views.delete_application, name='delete_application_url'),
    path('update_comment/<int:order_in_app_id>/', views.update_comment, name='update_comment_url'),
    path('api/', include(router.urls)),
    path('api/cart/', CartView.as_view(), name='cart'),
    path('api/applications/add_order/<int:order_id>/',
         AddOrderToApplicationView.as_view(),
         name='add_order_to_application'),
    path('api/users/update_profile/', UserViewSet.as_view({'put': 'update_profile'}), name='update_profile'),
    path('api/users/login/', UserViewSet.as_view({'post': 'login'}), name='login'),
    path('api/users/logout/', UserViewSet.as_view({'post': 'logout'}), name='logout'),

    # DRF Spectacular URLs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/csrf-token/', CSRFTokenView.as_view(), name='csrf_token'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)