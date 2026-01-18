from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, permission_classes
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone
from .models import Orders, Application, OrderInApplication
from .permissions import IsOwner, IsModerator, IsOwnerOrModerator, IsAuthenticatedOrReadOnlyForNonModerator
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from rest_framework.authtoken.models import Token
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from django.middleware.csrf import get_token
from .redis_service import RedisService
from django.core.files.storage import default_storage
import uuid
import os
import threading
import time
import logging
from django.conf import settings
import concurrent.futures
import random
from django.db import transaction
from decimal import Decimal
import json
from .models import Media
from .serializers import MediaSerializer, MediaDetailSerializer
from .serializers import (
    UserSerializer, UserLoginSerializer, UserRegisterSerializer,
    PopulationsSerializer,
    ApplicationSerializer, ApplicationListSerializer,
    PopulationInDensityCalculationSerializer,
    ApplicationDetailSerializer
)
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .authentication import SessionAuthenticationWithoutCSRF

logger = logging.getLogger(__name__)

class DecimalEncoder(json.JSONEncoder):
    """Кастомный JSON encoder для обработки Decimal"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

class CSRFTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = get_token(request)
        return Response({'csrfToken': token})


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get_serializer_class(self):
        if self.action == 'login':
            return UserLoginSerializer
        elif self.action == 'register':
            return UserRegisterSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ['login', 'register', 'profile', 'logout']:  # Добавили logout
            return [permissions.AllowAny()]
        elif self.action in ['update_profile']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def logout(self, request):
        """
        Эндпоинт для выхода из системы.
        Доступен без аутентификации.
        """
        try:
            # Пытаемся найти и удалить токен, если пользователь аутентифицирован
            if request.user.is_authenticated:
                try:
                    Token.objects.filter(user=request.user).delete()
                    logger.info(f"🗑️ Токен удален для пользователя: {request.user.username}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось удалить токен: {e}")

            # Выход из системы (работает даже для анонимных пользователей)
            logout(request)

            return Response({
                'message': 'Деавторизация успешна',
                'note': 'Сессия очищена, токен удален'
            })

        except Exception as e:
            logger.error(f"❌ Ошибка при выходе: {e}")
            return Response({
                'error': 'Ошибка при выходе из системы',
                'details': str(e)
            })

class OrdersViewSet(viewsets.ModelViewSet):
    queryset = Orders.objects.all()
    serializer_class = PopulationsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['title']
    permission_classes = [IsAuthenticatedOrReadOnlyForNonModerator]
    authentication_classes = [TokenAuthentication]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'])
    def upload_image(self, request, pk=None):
        order = self.get_object()
        image_file = request.FILES.get('image')

        if not image_file:
            return Response({'error': 'No image provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            file_extension = os.path.splitext(image_file.name)[1]
            filename = f"order_{order.id}_{uuid.uuid4().hex}{file_extension}"

            if order.image and default_storage.exists(order.image):
                default_storage.delete(order.image)

            file_path = default_storage.save(filename, image_file)
            image_url = f"/media/{file_path}"

            order.image = image_url
            order.save()

            return Response({
                'image_url': order.image,
                'message': 'Image uploaded successfully'
            })

        except Exception as e:
            return Response({
                'error': f'Upload failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def list(self, request, *args, **kwargs):
        redis_service = RedisService()
        cached_orders = redis_service.get_cached_orders()
        if cached_orders:
            print("Используются кэшированные данные услуг")
            return Response(cached_orders)

        response = super().list(request, *args, **kwargs)
        redis_service.cache_orders_list()
        return response

class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationListSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Application.objects.exclude(status='DELETED')

        if self.request.user.is_authenticated and not self.request.user.is_staff:
            queryset = queryset.filter(client=self.request.user)

        if self.action == 'list':
            queryset = queryset.exclude(status=Application.ApplicationStatus.DRAFT)

        if self.action == 'retrieve':
            queryset = queryset.select_related('client', 'manager').prefetch_related(
                'orderinapplication_set__order'
            )

        formation_date_start = self.request.query_params.get('formation_date_start')
        formation_date_end = self.request.query_params.get('formation_date_end')

        if formation_date_start:
            queryset = queryset.filter(formation_datetime__date__gte=formation_date_start)
        if formation_date_end:
            queryset = queryset.filter(formation_datetime__date__lte=formation_date_end)

        return queryset

    def create(self, request, *args, **kwargs):
        """Создание нового расчета плотности"""
        # Автоматически устанавливаем текущего пользователя как клиента
        request.data._mutable = True
        request.data['client'] = request.user.id
        request.data._mutable = False

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Сохраняем с текущим пользователем
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = ApplicationDetailSerializer(
                instance,
                context={'request': request}
            )
            return Response(serializer.data)

        except Application.DoesNotExist:
            return Response(
                {'error': 'Расчет плотности не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ApplicationDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ApplicationSerializer
        return ApplicationListSerializer

    @action(detail=True, methods=['post'], url_path='populations')
    def add_population_to_density_calculation(self, request, pk=None):
        """
        Добавление типа населения в расчет плотности-черновик
        POST /api/density_calculations/{id}/populations/
        """
        try:
            density_calculation = Application.objects.get(id=pk)
        except Application.DoesNotExist:
            return Response(
                {
                    'error': f'Расчет плотности с ID {pk} не найден',
                    'available_density_calculations': list(Application.objects.filter(
                        client=request.user,
                        status=Application.ApplicationStatus.DRAFT
                    ).values('id', 'status'))
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if density_calculation.client != request.user and not request.user.is_staff:
            return Response(
                {
                    'error': f'Расчет плотности принадлежит другому пользователю',
                    'density_calculation_owner': density_calculation.client.username if density_calculation.client else 'None',
                    'current_user': request.user.username
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if density_calculation.status != Application.ApplicationStatus.DRAFT:
            return Response(
                {
                    'error': f'Можно добавлять типы населения только в расчет плотности-черновик. Текущий статус: {density_calculation.status}',
                    'current_status': density_calculation.status,
                    'required_status': Application.ApplicationStatus.DRAFT
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        population_id = request.data.get('population_id')
        if not population_id:
            return Response(
                {'error': 'population_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            population = Orders.objects.get(id=population_id)
        except Orders.DoesNotExist:
            return Response(
                {
                    'error': f'Тип населения с ID {population_id} не найден',
                    'available_populations': list(Orders.objects.values('id', 'title'))
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if OrderInApplication.objects.filter(application=density_calculation, order=population).exists():
            return Response(
                {'error': 'Этот тип населения уже добавлен в расчет плотности'},
                status=status.HTTP_400_BAD_REQUEST
            )

        OrderInApplication.objects.create(
            application=density_calculation,
            order=population,
            comment=request.data.get('comment', '')
        )

        density_calculation.refresh_from_db()
        serializer = ApplicationDetailSerializer(density_calculation, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='populations/(?P<population_id>[^/.]+)')
    def remove_population_from_density_calculation(self, request, pk=None, population_id=None):
        try:
            density_calculation = self.get_object()
        except Application.DoesNotExist:
            return Response(
                {'error': 'Расчет плотности не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        if density_calculation.status != Application.ApplicationStatus.DRAFT:
            return Response(
                {'error': 'Можно удалять типы населения только из расчета плотности-черновика'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            population = Orders.objects.get(id=population_id)
        except Orders.DoesNotExist:
            return Response(
                {'error': 'Тип населения не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            population_in_calc = OrderInApplication.objects.get(
                application=density_calculation,
                order=population
            )
            population_in_calc.delete()
        except OrderInApplication.DoesNotExist:
            return Response(
                {'error': 'Тип населения не найден в расчете плотности'},
                status=status.HTTP_404_NOT_FOUND
            )

        density_calculation.refresh_from_db()
        serializer = ApplicationDetailSerializer(density_calculation, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['put'], url_path='populations/(?P<population_id>[^/.]+)')
    def update_population_in_density_calculation(self, request, pk=None, population_id=None):
        try:
            population_in_calc = OrderInApplication.objects.get(
                application_id=pk,
                order_id=population_id
            )
        except OrderInApplication.DoesNotExist:
            return Response(
                {'error': 'Связь между расчетом плотности и типом населения не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        new_comment = request.data.get('comment', '')
        population_in_calc.comment = new_comment
        population_in_calc.save()

        serializer = PopulationInDensityCalculationSerializer(population_in_calc)
        return Response(serializer.data)

    @action(detail=True, methods=['put'], permission_classes=[IsModerator])
    def complete(self, request, pk=None):
        density_calculation = self.get_object()
        action_type = request.data.get('action')

        if density_calculation.status != Application.ApplicationStatus.FORMED:
            return Response(
                {'error': 'Расчет плотности должен быть в статусе FORMED'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if action_type == 'complete':
            density_calculation.status = Application.ApplicationStatus.COMPLETED
            density_calculation.calculated_population = None

        elif action_type == 'reject':
            density_calculation.status = Application.ApplicationStatus.REJECTED
        else:
            return Response(
                {'error': 'Неверное действие'},
                status=status.HTTP_400_BAD_REQUEST
            )

        density_calculation.completion_datetime = timezone.now()
        density_calculation.manager = request.user
        density_calculation.save()

        return Response({
            **ApplicationSerializer(density_calculation).data,
            'note': 'Для расчета численности вызовите /api/density_calculations/{id}/async_calculate/'
        })

    @action(detail=True, methods=['put'])
    def form(self, request, pk=None):
        density_calculation = self.get_object()

        if density_calculation.status != Application.ApplicationStatus.DRAFT:
            return Response(
                {'error': 'Расчет плотности уже сформирован или имеет другой статус'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверяем, что расчет плотности принадлежит текущему пользователю
        if density_calculation.client != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Расчет плотности принадлежит другому пользователю'},
                status=status.HTTP_403_FORBIDDEN
            )

        territory_area = request.data.get('territory_area')
        required_fields = []
        if not territory_area:
            required_fields.append('territory_area')

        if required_fields:
            return Response(
                {
                    'error': 'Не заполнены обязательные поля расчета плотности',
                    'missing_fields': required_fields,
                    'message': f'Заполните следующие поля: {", ".join(required_fields)}'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not density_calculation.orderinapplication_set.exists():
            return Response(
                {'error': 'Добавьте хотя бы один тип населения в расчет плотности'},
                status=status.HTTP_400_BAD_REQUEST
            )

        populations_with_missing_data = []
        for population_in_calc in density_calculation.orderinapplication_set.all():
            population = population_in_calc.order
            if not population.building_density or not population.people_per_building:
                populations_with_missing_data.append({
                    'population_id': population.id,
                    'population_title': population.title,
                    'missing_building_density': not population.building_density,
                    'missing_people_per_building': not population.people_per_building
                })

        if populations_with_missing_data:
            return Response(
                {
                    'error': 'Некоторые типы населения не имеют данных для расчета',
                    'populations_with_missing_data': populations_with_missing_data,
                    'message': 'Заполните плотность застройки и количество человек в постройке для всех типов населения'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        density_calculation.territory_area = territory_area

        # Устанавливаем клиента, если он не установлен
        if not density_calculation.client:
            density_calculation.client = request.user

        density_calculation.status = Application.ApplicationStatus.FORMED
        density_calculation.formation_datetime = timezone.now()
        density_calculation.save()
        #density_calculation.calculate_population()

        serializer = ApplicationSerializer(density_calculation)
        return Response(serializer.data)

class OrderInApplicationViewSet(viewsets.ModelViewSet):
    queryset = OrderInApplication.objects.all()
    serializer_class = PopulationInDensityCalculationSerializer
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        application_id = instance.application.id
        instance.delete()

        application = Application.objects.get(id=application_id)
        serializer = ApplicationSerializer(application)
        return Response(serializer.data)
'''
class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get(self, request):
        user = request.user

        density_calculation, created = Application.objects.get_or_create(
            client=user,
            status=Application.ApplicationStatus.DRAFT,
            defaults={
                'client': user,
                'status': Application.ApplicationStatus.DRAFT,
                'title': f'Черновик расчета от {timezone.now().strftime("%d.%m.%Y %H:%M")}',
            }
        )

        populations_count = density_calculation.orderinapplication_set.count()

        return Response({
            'density_calculation_id': density_calculation.id,
            'populations_count': populations_count,
            'created': created,
            'status': density_calculation.status,
            'populations': PopulationInDensityCalculationSerializer(
                density_calculation.orderinapplication_set.all(),
                many=True,
                context={'request': request}
            ).data
        })'''

class PopulationsViewSet(viewsets.ModelViewSet):
    queryset = Orders.objects.all()
    serializer_class = PopulationsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['title']
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Требуется аутентификация для создания типа населения'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'])
    def upload_image(self, request, pk=None):
        population = self.get_object()
        image_file = request.FILES.get('image')

        if not image_file:
            return Response({'error': 'No image provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            file_extension = os.path.splitext(image_file.name)[1]
            filename = f"population_{population.id}_{uuid.uuid4().hex}{file_extension}"

            if population.image and default_storage.exists(population.image):
                default_storage.delete(population.image)

            file_path = default_storage.save(filename, image_file)
            image_url = f"/media/{file_path}"

            population.image = image_url
            population.save()

            return Response({
                'image_url': population.image,
                'message': 'Image uploaded successfully'
            })

        except Exception as e:
            return Response({
                'error': f'Upload failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def list(self, request, *args, **kwargs):
        redis_service = RedisService()
        cached_populations = redis_service.get_cached_populations()
        if cached_populations:
            print("Используются кэшированные данные популяций")
            return Response(cached_populations)

        response = super().list(request, *args, **kwargs)
        redis_service.cache_populations_list()
        return response

class PopulationInDensityCalculationViewSet(viewsets.ModelViewSet):
    queryset = OrderInApplication.objects.all()
    serializer_class = PopulationInDensityCalculationSerializer
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        density_calculation_id = instance.application.id
        instance.delete()

        density_calculation = Application.objects.get(id=density_calculation_id)
        serializer = ApplicationSerializer(density_calculation)
        return Response(serializer.data)
'''
class AsyncCalculateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        try:
            application = Application.objects.get(id=pk)

            if application.status != Application.ApplicationStatus.COMPLETED:
                return Response(
                    {'error': 'Расчет плотности должен быть завершен (статус COMPLETED)'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not application.territory_area or application.territory_area <= 0:
                return Response(
                    {'error': 'Не указана площадь территории для расчета'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not application.orderinapplication_set.exists():
                return Response(
                    {'error': 'В расчете плотности нет типов населения'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            from .async_service import async_population_service
            result = async_population_service.send_calculation_request(application)

            if result['status'] == 'processing':
                logger.info(f"✅ Асинхронный расчет запущен для расчета {application.id}")
                return Response({
                    'message': '✅ Асинхронный расчет запущен в FastAPI сервисе!',
                    'application_id': application.id,
                    'status': 'processing',
                    'estimated_time': '5-10 секунд',
                    'note': 'Поле calculated_population будет обновлено автоматически',
                    **result.get('response', {})
                }, status=status.HTTP_202_ACCEPTED)
            else:
                logger.error(f"❌ Ошибка запуска расчета для {application.id}: {result['message']}")
                return Response({
                    'error': result['message'],
                    'details': result.get('response')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Application.DoesNotExist:
            logger.error(f"❌ Расчет плотности {pk} не найден")
            return Response(
                {'error': 'Расчет плотности не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

class AsyncResultView(APIView):
    permission_classes = [permissions.AllowAny]

    def put(self, request, pk=None):
        return self.handle_request(request, pk)

    def post(self, request, pk=None):
        return self.handle_request(request, pk)

    def handle_request(self, request, pk=None):
        logger.info(f"📥 Получен результат для расчета {pk}")
        logger.info(f"📦 Данные: {request.data}")

        auth_token = request.data.get('auth_token')
        expected_token = settings.ASYNC_RESULT_TOKEN

        if auth_token != expected_token:
            logger.error(f"❌ Неверный токен. Получен: {auth_token}, Ожидался: {expected_token}")
            return Response(
                {'error': 'Invalid authentication token'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            application = Application.objects.get(id=pk)
            logger.info(f"✅ Найден расчет плотности {pk}")
        except Application.DoesNotExist:
            logger.error(f"❌ Расчет плотности {pk} не найден")
            return Response(
                {'error': 'Расчет плотности не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        async_population = request.data.get('async_population')

        if async_population is not None:
            application.calculated_population = async_population
            application.save(update_fields=['calculated_population'])

            logger.info(f"✅ Расчет {pk} обновлен: население = {async_population}")
            return Response({
                'message': 'Population updated successfully',
                'application_id': pk,
                'calculated_population': async_population,
            })
        else:
            logger.error("❌ Отсутствует поле async_population в запросе")
            return Response(
                {'error': 'async_population field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )'''

class SimpleAsyncView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        import threading
        import time

        def update_in_background(app_id):
            try:
                time.sleep(5)

                from django.db import connections
                for conn in connections.all():
                    conn.close()

                from django.db import connection
                connection.connect()

                from .models import Application
                app = Application.objects.get(id=app_id)

                if app.territory_area and app.territory_area > 0:
                    total = 0
                    for order_in_app in app.orderinapplication_set.all():
                        order = order_in_app.order
                        if order.building_density and order.people_per_building:
                            total += float(app.territory_area) * order.building_density * order.people_per_building

                    Application.objects.filter(id=app_id).update(
                        calculated_population=int(total * 1.05)
                    )

                    print(f"✅ [SimpleAsyncView] Заявка {app_id} обновлена: {int(total * 1.05)}")

            except Exception as e:
                print(f"❌ [SimpleAsyncView] Ошибка: {e}")

        thread = threading.Thread(target=update_in_background, args=(pk,))
        thread.daemon = True
        thread.start()

        return Response({
            'message': '✅ Простой асинхронный расчет запущен!',
            'application_id': pk,
            'status': 'processing',
            'note': 'Обновите страницу через 5 секунд'
        }, status=202)

class DirectUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        from django.db import connection
        import threading
        import time

        def direct_sql_update(app_id):
            try:
                time.sleep(5)
                connection.close()
                connection.connect()

                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT territory_area FROM bmstu_lab_application WHERE id = %s",
                        [app_id]
                    )
                    row = cursor.fetchone()

                    if row and row[0]:
                        territory_area = float(row[0])

                        cursor.execute("""
                            SELECT o.building_density, o.people_per_building 
                            FROM bmstu_lab_orderinapplication oia
                            JOIN bmstu_lab_orders o ON oia.order_id = o.id
                            WHERE oia.application_id = %s
                        """, [app_id])

                        rows = cursor.fetchall()
                        total = 0

                        for density, people in rows:
                            if density and people:
                                total += territory_area * density * people

                        new_value = int(total * 1.05)
                        cursor.execute(
                            "UPDATE bmstu_lab_application SET calculated_population = %s WHERE id = %s",
                            [new_value, app_id]
                        )

                        print(f"✅ [DirectUpdate] Заявка {app_id} обновлена через SQL: {new_value}")

            except Exception as e:
                print(f"❌ [DirectUpdate] Ошибка: {e}")

        thread = threading.Thread(target=direct_sql_update, args=(pk,))
        thread.daemon = True
        thread.start()

        return Response({
            'message': 'Прямое обновление запущено!',
            'status': 'success'
        }, status=202)

class MediaViewSet(viewsets.ModelViewSet):
    queryset = Media.objects.all()
    serializer_class = MediaSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return MediaDetailSerializer
        return MediaSerializer

    def get_queryset(self):
        queryset = Media.objects.all()

        population_id = self.request.query_params.get('population_id')
        if population_id:
            queryset = queryset.filter(population_id=population_id)

        file_type = self.request.query_params.get('file_type')
        if file_type in ['image', 'video']:
            queryset = queryset.filter(file_type=file_type)

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        population_id = request.data.get('population')
        try:
            population = Orders.objects.get(id=population_id)
        except Orders.DoesNotExist:
            return Response(
                {'error': f'Тип населения с ID {population_id} не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        media = serializer.save(population=population)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        data = request.data if isinstance(request.data, list) else [request.data]
        created_media = []

        for item in data:
            serializer = self.get_serializer(data=item)
            if serializer.is_valid():
                population_id = item.get('population')
                try:
                    population = Orders.objects.get(id=population_id)
                    media = serializer.save(population=population)
                    created_media.append(serializer.data)
                except Orders.DoesNotExist:
                    created_media.append({
                        'error': f'Тип населения с ID {population_id} не найден',
                        'data': item
                    })
            else:
                created_media.append({
                    'error': serializer.errors,
                    'data': item
                })

        return Response(created_media, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        try:
            media = self.get_object()
            media_id = media.id
            media.delete()

            return Response({
                'success': True,
                'message': f'Медиа-файл с ID {media_id} успешно удален',
                'deleted_id': media_id
            }, status=status.HTTP_200_OK)

        except Media.DoesNotExist:
            return Response({
                'success': False,
                'error': f'Медиа-файл с ID {kwargs.get("pk")} не найден'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при удалении медиа-файла: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['delete'])
    def delete_by_population(self, request, pk=None):
        try:
            population = Orders.objects.get(id=pk)
            media_count = Media.objects.filter(population=population).count()

            if media_count == 0:
                return Response({
                    'success': False,
                    'message': f'Для типа населения с ID {pk} нет медиа-файлов'
                }, status=status.HTTP_404_NOT_FOUND)

            deleted_count, _ = Media.objects.filter(population=population).delete()

            return Response({
                'success': True,
                'message': f'Удалено {deleted_count} медиа-файлов для типа населения "{population.title}"',
                'deleted_count': deleted_count,
                'population_id': pk,
                'population_title': population.title
            }, status=status.HTTP_200_OK)

        except Orders.DoesNotExist:
            return Response({
                'success': False,
                'error': f'Тип населения с ID {pk} не найден'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при удалении медиа-файлов: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        media_ids = request.data.get('media_ids', [])

        if not media_ids:
            return Response({
                'success': False,
                'error': 'Не указаны ID медиа-файлов для удаления'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            existing_media = Media.objects.filter(id__in=media_ids)
            existing_ids = list(existing_media.values_list('id', flat=True))

            non_existing_ids = [id for id in media_ids if id not in existing_ids]

            if non_existing_ids:
                return Response({
                    'success': False,
                    'error': f'Некоторые медиа-файлы не найдены: {non_existing_ids}',
                    'existing_ids': existing_ids,
                    'non_existing_ids': non_existing_ids
                }, status=status.HTTP_404_NOT_FOUND)

            deleted_count, _ = existing_media.delete()

            return Response({
                'success': True,
                'message': f'Удалено {deleted_count} медиа-файлов',
                'deleted_count': deleted_count,
                'deleted_ids': media_ids
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка при массовом удалении: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CheckDensityCalculationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get(self, request, pk=None):
        try:
            density_calculation = Application.objects.get(id=pk, client=request.user)
            return Response({
                'exists': True,
                'id': density_calculation.id,
                'status': density_calculation.status,
                'owner': density_calculation.client.username,
                'populations_count': density_calculation.orderinapplication_set.count()
            })
        except Application.DoesNotExist:
            return Response({
                'exists': False,
                'message': f'Расчет плотности с ID {pk} не найден или не принадлежит вам'
            }, status=status.HTTP_404_NOT_FOUND)


class GetOrCreateDraftView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get(self, request):
        user = request.user

        print(f"🔍 [DEBUG] Поиск черновика для пользователя: {user.username} (ID: {user.id})")

        # Ищем существующий черновик
        draft = Application.objects.filter(
            client=user,
            status=Application.ApplicationStatus.DRAFT
        ).order_by('-creation_datetime').first()

        if draft:
            print(f"✅ [DEBUG] Найден существующий черновик: ID {draft.id}")
            print(f"📊 [DEBUG] Количество населения в черновике: {draft.orderinapplication_set.count()}")

            return Response({
                'success': True,
                'density_calculation_id': draft.id,
                'exists': True,
                'populations_count': draft.orderinapplication_set.count(),
                'message': 'Черновик уже существует'
            })
        else:
            # Создаем новый черновик
            print(f"📝 [DEBUG] Создание нового черновика для пользователя {user.username}")

            try:
                new_draft = Application.objects.create(
                    client=user,
                    status=Application.ApplicationStatus.DRAFT,
                    title=f'Черновик расчета от {timezone.now().strftime("%d.%m.%Y %H:%M")}'
                )

                print(f"✅ [DEBUG] Создан новый черновик: ID {new_draft.id}")

                return Response({
                    'success': True,
                    'density_calculation_id': new_draft.id,
                    'exists': False,
                    'created': True,
                    'populations_count': 0,
                    'message': 'Черновик успешно создан'
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                print(f"❌ [DEBUG] Ошибка создания черновика: {str(e)}")
                return Response({
                    'success': False,
                    'error': f'Ошибка создания черновика: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AddToCartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def post(self, request, population_id):
        user = request.user

        density_calculation, created = Application.objects.get_or_create(
            client=user,
            status=Application.ApplicationStatus.DRAFT,
            defaults={
                'client': user,
                'status': Application.ApplicationStatus.DRAFT,
                'title': f'Черновик расчета от {timezone.now().strftime("%d.%m.%Y %H:%M")}',
            }
        )

        try:
            population = Orders.objects.get(id=population_id)
        except Orders.DoesNotExist:
            return Response(
                {'error': f'Тип населения с ID {population_id} не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        if OrderInApplication.objects.filter(
                application=density_calculation,
                order=population
        ).exists():
            return Response({
                'error': 'Этот тип населения уже в корзине',
                'density_calculation_id': density_calculation.id
            }, status=status.HTTP_400_BAD_REQUEST)

        order_in_app = OrderInApplication.objects.create(
            application=density_calculation,
            order=population,
            comment=request.data.get('comment', '')
        )

        density_calculation.refresh_from_db()

        return Response({
            'success': True,
            'message': 'Тип населения добавлен в корзину',
            'density_calculation_id': density_calculation.id,
            'populations_count': density_calculation.orderinapplication_set.count(),
            'added_population': PopulationInDensityCalculationSerializer(
                order_in_app,
                context={'request': request}
            ).data,
            'density_calculation': ApplicationSerializer(
                density_calculation,
                context={'request': request}
            ).data
        }, status=status.HTTP_201_CREATED)


# Вставьте этот код после существующих классов в api_views.py

class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get(self, request):
        user = request.user

        density_calculation, created = Application.objects.filter(
            client=user,
            status=Application.ApplicationStatus.DRAFT
        ).first(), False

        if not density_calculation:
            density_calculation = Application.objects.create(
                client=user,
                status=Application.ApplicationStatus.DRAFT,
                title=f'Черновик расчета от {timezone.now().strftime("%d.%m.%Y %H:%M")}',
            )
            created = True

        populations_count = density_calculation.orderinapplication_set.count()

        # Получаем детальные данные для каждого населения в корзине
        populations_data = []
        for order_in_app in density_calculation.orderinapplication_set.all():
            population = order_in_app.order

            # Получаем первый медиа-файл (изображение) для этого населения
            first_media = None
            if hasattr(population, 'media_files') and population.media_files.exists():
                first_media = population.media_files.filter(file_type='image').first()
                if not first_media:
                    first_media = population.media_files.first()

            # Формируем URL изображения
            population_image = None
            if first_media:
                # Получаем полный URL медиа-файла
                population_image = request.build_absolute_uri(first_media.file_url)
            elif population.image:
                # Используем старое изображение, если есть
                if population.image.startswith('http'):
                    population_image = population.image
                else:
                    population_image = request.build_absolute_uri(population.image)

            populations_data.append({
                'id': order_in_app.id,
                'population': population.id,
                'population_title': population.title,
                'population_image': population_image or '/default-image.jpg',
                'comment': order_in_app.comment,
                'building_density': population.building_density,
                'people_per_building': population.people_per_building,
                'has_media': first_media is not None,
                'media_count': population.media_files.count() if hasattr(population, 'media_files') else 0
            })

        return Response({
            'id': density_calculation.id,
            'status': density_calculation.status,
            'creation_datetime': density_calculation.creation_datetime,
            'title': density_calculation.title,
            'description': density_calculation.description,
            'density_calculation_id': density_calculation.id,
            'populations_count': populations_count,
            'created': created,
            'populations': populations_data
        })


class AsyncCalculateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthenticationWithoutCSRF, TokenAuthentication]

    def post(self, request, pk=None):
        logger.info(f"🔐 [AsyncCalculateView] Запрос от пользователя: {request.user.username}")

        try:
            application = Application.objects.get(id=pk)

            # Простые проверки статуса и данных
            if application.status != Application.ApplicationStatus.COMPLETED:
                return Response(
                    {'error': 'Расчет плотности должен быть завершен (статус COMPLETED)'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not application.territory_area or application.territory_area <= 0:
                return Response(
                    {'error': 'Не указана площадь территории для расчета'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not application.orderinapplication_set.exists():
                return Response(
                    {'error': 'В расчете плотности нет типов населения'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"✅ Данные валидны, запуск асинхронного расчета для {application.id}")

            from .async_service import async_population_service
            # Передаем None для session_key (не используется)
            result = async_population_service.send_calculation_request(application, None)

            if result['status'] == 'processing':
                logger.info(f"✅ Асинхронный расчет запущен для расчета {application.id}")
                return Response({
                    'message': '✅ Асинхронный расчет запущен!',
                    'application_id': application.id,
                    'status': 'processing',
                    'estimated_time': '5-10 секунд',
                    'note': 'Поле calculated_population будет обновлено автоматически',
                    **result.get('response', {})
                }, status=status.HTTP_202_ACCEPTED)
            else:
                logger.error(f"❌ Ошибка запуска расчета: {result['message']}")
                return Response({
                    'error': result['message'],
                    'details': result.get('response')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Application.DoesNotExist:
            logger.error(f"❌ Расчет плотности {pk} не найден")
            return Response(
                {'error': 'Расчет плотности не найден'},
                status=status.HTTP_404_NOT_FOUND
            )


class AsyncResultView(APIView):
    # Разрешаем доступ всем, но проверяем специальный токен для асинхронного сервиса
    permission_classes = []

    def put(self, request, pk=None):
        return self.handle_request(request, pk)

    def post(self, request, pk=None):
        return self.handle_request(request, pk)

    def handle_request(self, request, pk=None):
        logger.info(f"📥 Получен результат для расчета {pk}")
        logger.info(f"📦 Данные: {request.data}")

        # Проверяем специальный токен для асинхронного сервиса
        auth_token = request.data.get('auth_token')
        expected_token = settings.ASYNC_RESULT_TOKEN

        if auth_token != expected_token:
            logger.error(f"❌ Неверный токен. Получен: {auth_token}, Ожидался: {expected_token}")
            return Response(
                {'error': 'Invalid authentication token'},
                status=status.HTTP_403_FORBIDDEN  # Возвращаем 403 вместо 401
            )

        try:
            application = Application.objects.get(id=pk)
            logger.info(f"✅ Найден расчет плотности {pk}")
        except Application.DoesNotExist:
            logger.error(f"❌ Расчет плотности {pk} не найден")
            return Response(
                {'error': 'Расчет плотности не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        async_population = request.data.get('async_population')

        if async_population is not None:
            application.calculated_population = async_population
            application.save(update_fields=['calculated_population'])

            logger.info(f"✅ Расчет {pk} обновлен: население = {async_population}")
            return Response({
                'message': 'Population updated successfully',
                'application_id': pk,
                'calculated_population': async_population,
            })
        else:
            logger.error("❌ Отсутствует поле async_population в запросе")
            return Response(
                {'error': 'async_population field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )


class CheckSessionView(APIView):
    """
    Эндпоинт для проверки валидности сессии Django
    Используется FastAPI сервисом для проверки авторизации
    """
    authentication_classes = [SessionAuthentication]
    permission_classes = []  # Убираем IsAuthenticated, чтобы проверять сессию напрямую

    def get(self, request):
        """
        Проверяет валидность сессии и возвращает данные пользователя
        """
        # Проверяем, аутентифицирован ли пользователь через сессию
        if not request.user.is_authenticated:
            logger.warning(f"❌ Проверка сессии: пользователь не аутентифицирован")
            return Response(
                {'authenticated': False, 'error': 'Пользователь не аутентифицирован'},
                status=status.HTTP_403_FORBIDDEN
            )

        logger.info(f"✅ Проверка сессии успешна для пользователя: {request.user.username}")
        return Response({
            'authenticated': True,
            'user_id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'is_staff': request.user.is_staff,
            'session_key': request.session.session_key
        })


# api_views.py
class CheckSessionAuthView(APIView):
    """Эндпоинт для проверки аутентификации через сессию"""
    authentication_classes = [SessionAuthenticationWithoutCSRF]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Возвращает информацию о текущей сессии и пользователе"""

        # Получаем все активные сессии из базы данных
        from django.contrib.sessions.models import Session
        from django.contrib.auth.models import User
        import time

        sessions_data = []
        active_sessions = Session.objects.filter(expire_date__gt=timezone.now())

        for session in active_sessions:
            session_dict = session.get_decoded()
            user_id = session_dict.get('_auth_user_id')
            user = None
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    user = None

            sessions_data.append({
                'session_key': session.session_key,
                'user_id': user_id,
                'username': user.username if user else None,
                'expire_date': session.expire_date,
                'is_current': session.session_key == request.session.session_key
            })

        return Response({
            'authenticated': True,
            'current_user': {
                'id': request.user.id,
                'username': request.user.username,
                'email': request.user.email,
                'is_staff': request.user.is_staff,
            },
            'current_session': {
                'session_key': request.session.session_key,
                'session_data': dict(request.session),
            },
            'all_active_sessions': sessions_data,
            'total_active_sessions': len(sessions_data)
        })