from django.contrib import admin
from django.urls import path, include
from bmstu_lab import views
from bmstu_lab.api_views import AsyncResultView

from rest_framework.routers import DefaultRouter
from bmstu_lab.api_views import *

from django.conf import settings
from django.conf.urls.static import static

# Импорты для drf-spectacular
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from bmstu_lab.api_views import CSRFTokenView

router = DefaultRouter()
router.register(r'populations', PopulationsViewSet)
router.register(r'density_calculations', ApplicationViewSet, basename='density_calculation')
router.register(r'population-in-density-calculation', PopulationInDensityCalculationViewSet)
router.register(r'users', UserViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.get_populations_list_page),
    path('information_about_object/<int:id>/', views.get_population_page, name='population_url'),
    path('archaeologic_objects', views.get_populations_list_page, name='populations_url'),
    path('calculate_of_population/<int:id>', views.GetDensityCalculation, name='density_calculation_url'),
    path('archaeologic_objects/search', views.sendText, name='populations_search_url'),
    path('add_to_density_calculation/<int:population_id>/', views.add_to_density_calculation,
         name='add_to_density_calculation_url'),
    path('delete_density_calculation/<int:density_calculation_id>/', views.delete_density_calculation,
         name='delete_density_calculation_url'),
    path('update_comment/<int:population_in_density_calculation_id>/', views.update_comment, name='update_comment_url'),
    path('api/', include(router.urls)),
    path('api/cart/', CartView.as_view(), name='cart'),
    path('api/density_calculations/add_population/<int:population_id>/',
         AddPopulationToDensityCalculationView.as_view(),
         name='add_population_to_density_calculation'),
    path('api/users/update_profile/', UserViewSet.as_view({'put': 'update_profile'}), name='update_profile'),
    path('api/users/login/', UserViewSet.as_view({'post': 'login'}), name='login'),
    path('api/users/logout/', UserViewSet.as_view({'post': 'logout'}), name='logout'),

    # DRF Spectacular URLs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/csrf-token/', CSRFTokenView.as_view(), name='csrf_token'),
    # path('api/redis/info/', RedisInfoView.as_view(), name='redis_info'),
    # path('api/redis/clear-cache/', ClearCacheView.as_view(), name='redis_clear_cache'),
    path('api/auth/', include('rest_framework.urls')),
    path('api/density_calculations/<int:pk>/async_calculate/',
         AsyncCalculateView.as_view(),
         name='async_calculate'),

    path('api/density_calculations/<int:pk>/async_simple/',
         SimpleAsyncView.as_view(),
         name='async_simple'),

    path('api/density_calculations/<int:pk>/async_result/',
         AsyncResultView.as_view(),
         name='async_result'),
    path('api/density_calculations/<int:pk>/direct_update/', DirectUpdateView.as_view(), name='direct_update'),

    # Явные пути для кастомных действий ApplicationViewSet
    path('api/density_calculations/<int:pk>/complete/',
         ApplicationViewSet.as_view({'put': 'complete'}),
         name='density_calculation-complete'),

    path('api/density_calculations/<int:pk>/form/',
         ApplicationViewSet.as_view({'put': 'form'}),
         name='density_calculation-form'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)