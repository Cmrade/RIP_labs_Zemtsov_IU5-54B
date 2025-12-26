from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, permission_classes
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
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
from django.contrib.auth.models import User  # Добавлен этот импорт
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
import logging
import time
import random
from django.db import transaction
from decimal import Decimal
import json

logger = logging.getLogger(__name__)

# Явно импортируем все нужные сериализаторы
from .serializers import (
    UserSerializer,
    UserLoginSerializer,
    UserRegisterSerializer,
    PopulationsSerializer,
    PopulationInDensityCalculationSerializer,
    ApplicationSerializer,
    ApplicationListSerializer,
    ApplicationDetailSerializer
)

class DecimalEncoder(json.JSONEncoder):
    """Кастомный JSON encoder для обработки Decimal"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

logger = logging.getLogger(__name__)


class CSRFTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = get_token(request)
        return Response({'csrfToken': token})


# Обновите UserViewSet для работы с токенами
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
        """
        Разные разрешения для разных действий
        """
        if self.action in ['login', 'register', 'profile']:
            return [permissions.AllowAny()]
        elif self.action in ['update_profile', 'logout']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        """
        POST аутентификация с возвратом токена
        """
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']

            user = authenticate(request, username=username, password=password)

            if user is not None:
                # Логин для сессий
                login(request, user)

                # Получаем или создаем токен
                token, created = Token.objects.get_or_create(user=user)

                # Возвращаем данные пользователя и токен
                user_data = UserSerializer(user).data

                return Response({
                    'message': 'Аутентификация успешна',
                    'user': user_data,
                    'token': token.key
                })
            else:
                return Response(
                    {'error': 'Неверные учетные данные'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        """
        POST деавторизация
        """
        # Удаляем токен при выходе (опционально)
        # Token.objects.filter(user=request.user).delete()

        logout(request)
        return Response({
            'message': 'Деавторизация успешна'
        })

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def register(self, request):
        """
        POST регистрация нового пользователя с возвратом токена
        """
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Создаем токен для нового пользователя
            token = Token.objects.create(user=user)

            # Автоматический вход после регистрации
            login(request, user)

            user_data = UserSerializer(user).data

            return Response({
                'user': user_data,
                'token': token.key,
                'message': 'Регистрация успешна'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def profile(self, request):
        """
        GET профиль текущего пользователя
        """
        if request.user.is_authenticated:
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
        else:
            return Response(
                {'error': 'Пользователь не аутентифицирован'},
                status=status.HTTP_401_UNAUTHORIZED
            )

    @action(detail=False, methods=['put', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def update_profile(self, request):
        """
        PUT пользователя (личный кабинет)
        """
        user = request.user
        serializer = self.get_serializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()

            # Если передается пароль, обновляем его отдельно
            new_password = request.data.get('password')
            if new_password:
                user.set_password(new_password)
                user.save()
                # Обновляем токен при смене пароля
                Token.objects.filter(user=user).delete()
                new_token = Token.objects.create(user=user)

            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Домен услуги
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
            # Генерация имени файла
            file_extension = os.path.splitext(image_file.name)[1]
            filename = f"order_{order.id}_{uuid.uuid4().hex}{file_extension}"

            # Удаление старого изображения
            if order.image and default_storage.exists(order.image):
                default_storage.delete(order.image)

            # Сохранение нового изображения
            file_path = default_storage.save(filename, image_file)

            # Сохраняем полный URL, а не только путь к файлу
            # Для Minio это может быть что-то вроде:
            # image_url = f"http://localhost:9000/{MINIO_STORAGE_MEDIA_BUCKET_NAME}/{file_path}"

            # Для локальной файловой системы:
            image_url = f"/media/{file_path}"  # или полный URL

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
        """GET список услуг с кэшированием"""
        redis_service = RedisService()

        # Пытаемся получить данные из кэша
        cached_orders = redis_service.get_cached_orders()
        if cached_orders:
            print("Используются кэшированные данные услуг")
            return Response(cached_orders)

        # Если в кэше нет, получаем из базы и кэшируем
        response = super().list(request, *args, **kwargs)
        redis_service.cache_orders_list()

        return response


# Домен заявки
# В классе ApplicationViewSet (он же DensityCalculationViewSet после переименования)
# Но давайте пока оставим название класса как есть, а изменим только методы

class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationListSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']
    # Упрощаем permissions для тестирования
    permission_classes = [permissions.AllowAny]  # Изменили для теста
    authentication_classes = []  # Убираем проверку аутентификации для теста

    def get_queryset(self):
        # Логика фильтрации остается, но без проверки аутентификации
        queryset = Application.objects.exclude(status='DELETED')

        # Если пользователь аутентифицирован, показываем только его расчеты
        if self.request.user.is_authenticated and not self.request.user.is_staff:
            queryset = queryset.filter(client=self.request.user)

        # Для списка дополнительно исключаем DRAFT для не-владельцев
        if self.action == 'list' and self.request.user.is_authenticated and not self.request.user.is_staff:
            queryset = queryset.exclude(status='DRAFT')

        # Для retrieve предзагружаем связанные данные
        if self.action == 'retrieve':
            queryset = queryset.select_related('client', 'manager').prefetch_related(
                'orderinapplication_set__order'
            )

        # Фильтрация по датам
        formation_date_start = self.request.query_params.get('formation_date_start')
        formation_date_end = self.request.query_params.get('formation_date_end')

        if formation_date_start:
            queryset = queryset.filter(formation_datetime__date__gte=formation_date_start)
        if formation_date_end:
            queryset = queryset.filter(formation_datetime__date__lte=formation_date_end)

        return queryset

    def retrieve(self, request, *args, **kwargs):
        """
        GET одна запись (полный расчет плотности с населением)
        """
        try:
            instance = self.get_object()

            # Используем ApplicationDetailSerializer для детального отображения
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
        """
        Выбираем сериализатор в зависимости от действия
        """
        if self.action == 'retrieve':
            return ApplicationDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ApplicationSerializer
        return ApplicationListSerializer

    # ... остальные методы класса ...

    @action(detail=True, methods=['post'], url_path='orders')
    def add_order_to_density_calculation(self, request, pk=None):
        """
        Добавление услуги в существующий расчет плотности-черновик
        POST /api/density_calculations/{id}/orders/
        """
        try:
            density_calculation = Application.objects.get(id=pk)
        except Application.DoesNotExist:
            return Response(
                {
                    'error': f'Расчет плотности с ID {pk} не найден',
                    'available_density_calculations': list(Application.objects.filter(
                        client=request.user,  # ИСПРАВЛЕНО: используем request.user
                        status=Application.ApplicationStatus.DRAFT
                    ).values('id', 'status'))
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверяем, что расчет плотности принадлежит текущему пользователю
        if density_calculation.client != request.user:
            return Response(
                {
                    'error': f'Расчет плотности принадлежит другому пользователю',
                    'density_calculation_owner': density_calculation.client.username if density_calculation.client else 'None',
                    'current_user': request.user.username
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Разрешаем только для расчетов плотности-черновиков
        if density_calculation.status != Application.ApplicationStatus.DRAFT:
            return Response(
                {
                    'error': f'Можно добавлять услуги только в расчет плотности-черновик. Текущий статус: {density_calculation.status}',
                    'current_status': density_calculation.status,
                    'required_status': Application.ApplicationStatus.DRAFT
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        order_id = request.data.get('order_id')
        if not order_id:
            return Response(
                {'error': 'order_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order = Orders.objects.get(id=order_id)
        except Orders.DoesNotExist:
            return Response(
                {
                    'error': f'Услуга с ID {order_id} не найдена',
                    'available_orders': list(Orders.objects.values('id', 'title'))
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверяем, не добавлена ли уже эта услуга в расчет плотности
        if OrderInApplication.objects.filter(application=density_calculation, order=order).exists():
            return Response(
                {'error': 'Эта услуга уже добавлена в расчет плотности'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Добавляем услугу в расчет плотности-черновик
        order_in_app = OrderInApplication.objects.create(
            application=density_calculation,
            order=order,
            comment=request.data.get('comment', '')
        )

        serializer = PopulationInDensityCalculationSerializer(order_in_app)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='orders/(?P<order_id>[^/.]+)')
    def remove_order_from_density_calculation(self, request, pk=None, order_id=None):
        """
        DELETE удаление из расчета плотности (без PK м-м)
        Удаляет услугу из расчета плотности по ID расчета плотности и ID услуги
        """
        try:
            density_calculation = self.get_object()
        except Application.DoesNotExist:
            return Response(
                {'error': 'Расчет плотности не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверяем, что расчет плотности в статусе DRAFT (можно удалять только из черновика)
        if density_calculation.status != Application.ApplicationStatus.DRAFT:
            return Response(
                {'error': 'Можно удалять услуги только из расчета плотности-черновика'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order = Orders.objects.get(id=order_id)
        except Orders.DoesNotExist:
            return Response(
                {'error': 'Услуга не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Находим и удаляем связь между расчетом плотности и услуги
        try:
            order_in_app = OrderInApplication.objects.get(
                application=density_calculation,
                order=order
            )
            order_in_app.delete()
        except OrderInApplication.DoesNotExist:
            return Response(
                {'error': 'Услуга не найдена в расчете плотности'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Возвращаем обновленные данные расчета плотности
        density_calculation.refresh_from_db()
        serializer = ApplicationSerializer(density_calculation)
        return Response(serializer.data)

    @action(detail=True, methods=['put'], url_path='orders/(?P<order_id>[^/.]+)')
    def update_order_in_density_calculation(self, request, pk=None, order_id=None):
        try:
            # Находим связь по density_calculation_id и order_id
            order_in_app = OrderInApplication.objects.get(
                application_id=pk,
                order_id=order_id
            )
        except OrderInApplication.DoesNotExist:
            return Response(
                {'error': 'Связь между расчетом плотности и услугой не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        new_comment = request.data.get('comment', '')
        order_in_app.comment = new_comment
        order_in_app.save()

        serializer = PopulationInDensityCalculationSerializer(order_in_app)
        return Response(serializer.data)

    @action(detail=True, methods=['put'], permission_classes=[IsModerator])
    def complete(self, request, pk=None):
        """Только модератор может завершать расчеты плотности"""
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
        """
        PUT сформировать создателем (дата формирования)
        Происходит проверка на обязательные поля
        """
        density_calculation = self.get_object()

        # Проверяем, что расчет плотности находится в статусе DRAFT
        if density_calculation.status != Application.ApplicationStatus.DRAFT:
            return Response(
                {'error': 'Расчет плотности уже сформирован или имеет другой статус'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Получаем territory_area из запроса
        territory_area = request.data.get('territory_area')

        # Проверка обязательных полей расчета плотности
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

        # Проверка, что в расчете плотности есть хотя бы один тип населения
        if not density_calculation.orderinapplication_set.exists():
            return Response(
                {'error': 'Добавьте хотя бы один тип населения в расчет плотности'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка, что все типы населения в расчете имеют необходимые данные для расчета
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

        # Устанавливаем territory_area из запроса
        density_calculation.territory_area = territory_area

        # Все проверки пройдены - формируем расчет плотности
        density_calculation.status = Application.ApplicationStatus.FORMED
        density_calculation.formation_datetime = timezone.now()
        density_calculation.save()

        # Вычисляем численность населения
        density_calculation.calculate_population()

        # Возвращаем обновленные данные расчета плотности
        serializer = ApplicationSerializer(density_calculation)
        return Response(serializer.data)


class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get(self, request):
        user = request.user  # Используем текущего пользователя

        # Проверяем, авторизован ли пользователь
        if not user.is_authenticated:
            return Response(
                {'error': 'Пользователь не авторизован'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        draft_application = Application.objects.filter(
            client=user,  # Используем текущего пользователя
            status=Application.ApplicationStatus.DRAFT
        ).first()

        if draft_application:
            orders_count = draft_application.orderinapplication_set.count()

            # Кэшируем количество (если RedisService это поддерживает)
            try:
                redis_service = RedisService()
                redis_service.cache_cart_count(user.id, orders_count)
            except:
                pass

            return Response({
                'application_id': draft_application.id,
                'orders_count': orders_count
            })
        else:
            new_application = Application.objects.create(
                client=user,  # Используем текущего пользователя
                status=Application.ApplicationStatus.DRAFT
            )
            return Response({
                'application_id': new_application.id,
                'orders_count': 0
            })

'''
# Домен м-м
class OrderInApplicationViewSet(viewsets.ModelViewSet):
    queryset = OrderInApplication.objects.all()
    serializer_class = OrderInApplicationSerializer
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        application_id = instance.application.id
        instance.delete()

        # Возвращаем обновленные данные заявки
        application = Application.objects.get(id=application_id)
        serializer = ApplicationSerializer(application)
        return Response(serializer.data)


class AddOrderToApplicationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    @action(detail=True, methods=['post'], url_path='orders')
    def add_order_to_application(self, request, pk=None):
        """
        Добавление услуги в существующую заявку-черновик
        POST /api/applications/{id}/orders/
        """
        try:
            application = Application.objects.get(id=pk)
        except Application.DoesNotExist:
            return Response(
                {
                    'error': f'Заявка с ID {pk} не найдена',
                    'available_applications': list(Application.objects.filter(
                        client=request.user,
                        status=Application.ApplicationStatus.DRAFT
                    ).values('id', 'status'))
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверяем, что заявка принадлежит текущему пользователю
        if application.client != request.user:
            return Response(
                {
                    'error': f'Заявка принадлежит другому пользователю',
                    'application_owner': application.client.username if application.client else 'None',
                    'current_user': request.user.username
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Разрешаем только для заявок-черновиков
        if application.status != Application.ApplicationStatus.DRAFT:
            return Response(
                {
                    'error': f'Можно добавлять услуги только в заявку-черновик. Текущий статус: {application.status}',
                    'current_status': application.status,
                    'required_status': Application.ApplicationStatus.DRAFT
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        order_id = request.data.get('order_id')
        if not order_id:
            return Response(
                {'error': 'order_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order = Orders.objects.get(id=order_id)
        except Orders.DoesNotExist:
            return Response(
                {
                    'error': f'Услуга с ID {order_id} не найдена',
                    'available_orders': list(Orders.objects.values('id', 'title'))
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверяем, не добавлена ли уже эта услуга в заявку
        if OrderInApplication.objects.filter(application=application, order=order).exists():
            return Response(
                {'error': 'Эта услуга уже добавлена в заявку'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Добавляем услугу в заявку-черновик
        order_in_app = OrderInApplication.objects.create(
            application=application,
            order=order,
            comment=request.data.get('comment', '')
        )

        # ВОТ ИСПРАВЛЕНИЕ: Возвращаем обновленную заявку, а не только связь
        # Обновляем объект из базы, чтобы получить свежие данные
        application.refresh_from_db()

        # Возвращаем всю заявку со всеми услугами
        serializer = ApplicationSerializer(application)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def post(self, request, order_id):
        user = request.user  # Используем текущего пользователя

        # Проверяем авторизацию
        if not user.is_authenticated:
            return Response(
                {'error': 'Пользователь не авторизован'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Находим или создаем заявку-черновик для текущего пользователя
        application, created = Application.objects.get_or_create(
            client=user,  # Используем текущего пользователя
            status=Application.ApplicationStatus.DRAFT,
            defaults={
                'client': user,
                'status': Application.ApplicationStatus.DRAFT,
            }
        )

        # Проверяем, существует ли услуга
        try:
            order = Orders.objects.get(id=order_id)
        except Orders.DoesNotExist:
            return Response(
                {'error': 'Услуга не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверяем, не добавлена ли уже эта услуга в заявку
        if OrderInApplication.objects.filter(
                application=application,
                order=order
        ).exists():
            return Response(
                {'error': 'Эта услуга уже добавлена в заявку'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Добавляем услугу в заявку
        order_in_app = OrderInApplication.objects.create(
            application=application,
            order=order,
            comment=request.data.get('comment', '')  # Опциональный комментарий
        )

        # Возвращаем информацию о добавленной услуге
        serializer = OrderInApplicationSerializer(order_in_app)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
'''
# Домен услуги (переименовано в Домен популяций)
class PopulationsViewSet(viewsets.ModelViewSet):
    queryset = Orders.objects.all()
    serializer_class = PopulationsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['title']
    # Упрощаем permissions для тестирования
    permission_classes = [permissions.AllowAny]  # Изменили на AllowAny для теста
    authentication_classes = []  # Убираем проверку аутентификации для теста

    def create(self, request, *args, **kwargs):
        # Для создания всё равно нужна аутентификация
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

    # ... остальные методы без изменений ...

    @action(detail=True, methods=['post'])
    def upload_image(self, request, pk=None):
        population = self.get_object()
        image_file = request.FILES.get('image')

        if not image_file:
            return Response({'error': 'No image provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Генерация имени файла
            file_extension = os.path.splitext(image_file.name)[1]
            filename = f"population_{population.id}_{uuid.uuid4().hex}{file_extension}"

            # Удаление старого изображения
            if population.image and default_storage.exists(population.image):
                default_storage.delete(population.image)

            # Сохранение нового изображения
            file_path = default_storage.save(filename, image_file)

            # Сохраняем полный URL, а не только путь к файлу
            image_url = f"/media/{file_path}"  # или полный URL

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
        """GET список популяций с кэшированием"""
        redis_service = RedisService()

        # Пытаемся получить данные из кэша
        cached_populations = redis_service.get_cached_populations()
        if cached_populations:
            print("Используются кэшированные данные популяций")
            return Response(cached_populations)

        # Если в кэше нет, получаем из базы и кэшируем
        response = super().list(request, *args, **kwargs)
        redis_service.cache_populations_list()

        return response


# Домен м-м (переименовано)
class PopulationInDensityCalculationViewSet(viewsets.ModelViewSet):
    queryset = OrderInApplication.objects.all()
    serializer_class = PopulationInDensityCalculationSerializer
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        density_calculation_id = instance.application.id
        instance.delete()

        # Возвращаем обновленные данные расчета плотности
        density_calculation = Application.objects.get(id=density_calculation_id)
        serializer = ApplicationSerializer(density_calculation)
        return Response(serializer.data)


class AddPopulationToDensityCalculationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    @action(detail=True, methods=['post'], url_path='populations')
    def add_population_to_density_calculation(self, request, pk=None):
        # ... код метода ...

        # Добавляем тип населения в расчет плотности-черновик
        order_in_app = OrderInApplication.objects.create(
            application=density_calculation,
            order=order,
            comment=request.data.get('comment', '')
        )

        serializer = PopulationInDensityCalculationSerializer(order_in_app)  # Исправлено
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def post(self, request, population_id):
        # ... код метода ...

        # Добавляем тип населения в расчет плотности
        order_in_app = OrderInApplication.objects.create(
            application=density_calculation,
            order=order,
            comment=request.data.get('comment', '')
        )

        # Возвращаем информацию о добавленном типе населения
        serializer = PopulationInDensityCalculationSerializer(order_in_app)  # Исправлено
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='populations')
    def add_population_to_density_calculation(self, request, pk=None):
        """
        Добавление популяции в существующий расчет плотности-черновик
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

        # Проверяем, что расчет плотности принадлежит текущему пользователю
        if density_calculation.client != request.user:
            return Response(
                {
                    'error': f'Расчет плотности принадлежит другому пользователю',
                    'density_calculation_owner': density_calculation.client.username if density_calculation.client else 'None',
                    'current_user': request.user.username
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Разрешаем только для расчетов плотности-черновиков
        if density_calculation.status != Application.ApplicationStatus.DRAFT:
            return Response(
                {
                    'error': f'Можно добавлять популяции только в расчет плотности-черновик. Текущий статус: {density_calculation.status}',
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
                    'error': f'Популяция с ID {population_id} не найдена',
                    'available_populations': list(Orders.objects.values('id', 'title'))
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверяем, не добавлена ли уже эта популяция в расчет плотности
        if OrderInApplication.objects.filter(application=density_calculation, order=population).exists():
            return Response(
                {'error': 'Эта популяция уже добавлена в расчет плотности'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Добавляем популяцию в расчет плотности-черновик
        population_in_density_calculation = OrderInApplication.objects.create(
            application=density_calculation,
            order=population,
            comment=request.data.get('comment', '')
        )

        # Возвращаем обновленный расчет плотности
        density_calculation.refresh_from_db()

        # Возвращаем весь расчет плотности со всеми популяциями
        serializer = ApplicationSerializer(density_calculation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def post(self, request, population_id):
        user = request.user  # Используем текущего пользователя

        # Проверяем авторизацию
        if not user.is_authenticated:
            return Response(
                {'error': 'Пользователь не авторизован'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Находим или создаем расчет плотности-черновик для текущего пользователя
        density_calculation, created = Application.objects.get_or_create(
            client=user,  # Используем текущего пользователя
            status=Application.ApplicationStatus.DRAFT,
            defaults={
                'client': user,
                'status': Application.ApplicationStatus.DRAFT,
            }
        )

        # Проверяем, существует ли популяция
        try:
            population = Orders.objects.get(id=population_id)
        except Orders.DoesNotExist:
            return Response(
                {'error': 'Популяция не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверяем, не добавлена ли уже эта популяция в расчет плотности
        if OrderInApplication.objects.filter(
                application=density_calculation,
                order=population
        ).exists():
            return Response(
                {'error': 'Эта популяция уже добавлена в расчет плотности'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Добавляем популяцию в расчет плотности
        population_in_density_calculation = OrderInApplication.objects.create(
            application=density_calculation,
            order=population,
            comment=request.data.get('comment', '')  # Опциональный комментарий
        )

        # Возвращаем информацию о добавленной популяции
        serializer = PopulationInDensityCalculationSerializer(population_in_density_calculation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# Также обновим импорты в начале файла:
from .serializers import (
    UserSerializer, UserLoginSerializer, UserRegisterSerializer,
    PopulationsSerializer,  # Было OrdersSerializer
    ApplicationSerializer, ApplicationListSerializer,
    PopulationInDensityCalculationSerializer  # Было OrderInApplicationSerializer
)


class AsyncCalculateView(APIView):
    """
    Endpoint для запуска асинхронного расчета через Go-сервис
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        """
        POST для запуска асинхронного расчета через Go-сервис
        """
        try:
            application = Application.objects.get(id=pk)

            # Проверяем, что заявка в статусе COMPLETED
            if application.status != Application.ApplicationStatus.COMPLETED:
                return Response(
                    {'error': 'Заявка должна быть завершена (статус COMPLETED)'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Проверяем, что есть данные для расчета
            if not application.territory_area or application.territory_area <= 0:
                return Response(
                    {'error': 'Не указана площадь территории для расчета'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not application.orderinapplication_set.exists():
                return Response(
                    {'error': 'В заявке нет услуг для расчета'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Используем AsyncPopulationService для отправки в Go-сервис
            from .async_service import AsyncPopulationService
            service = AsyncPopulationService()
            result = service.send_calculation_request(application)

            if result['status'] == 'processing':
                logger.info(f"Async calculation started for application {application.id}")
                return Response({
                    'message': '✅ Асинхронный расчет запущен в Go-сервисе!',
                    'application_id': application.id,
                    'status': 'processing',
                    'estimated_time': '5-10 секунд',
                    'note': 'Поле calculated_population будет обновлено автоматически',
                    **result
                }, status=status.HTTP_202_ACCEPTED)
            else:
                logger.error(f"Async calculation failed for application {application.id}: {result['message']}")
                return Response({
                    'error': result['message'],
                    'details': result.get('response')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Application.DoesNotExist:
            logger.error(f"Application {pk} not found for async calculation")
            return Response(
                {'error': 'Заявка не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )


class AsyncResultView(APIView):
    """
    Endpoint для получения результатов от внешнего Go-сервиса
    """
    permission_classes = [permissions.AllowAny]

    def put(self, request, pk=None):
        return self.handle_request(request, pk)

    def post(self, request, pk=None):
        return self.handle_request(request, pk)

    def handle_request(self, request, pk=None):
        logger.info(f"AsyncResultView: Received request for application {pk}")
        logger.info(f"AsyncResultView: Request data: {request.data}")

        # Простая проверка токена
        auth_token = request.data.get('auth_token')

        # Используем настройки Django
        from django.conf import settings
        expected_token = settings.ASYNC_RESULT_TOKEN

        if auth_token != expected_token:
            logger.error(f"AsyncResultView: Invalid token. Got: {auth_token}, Expected: {expected_token}")
            return Response(
                {'error': 'Invalid authentication token'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            application = Application.objects.get(id=pk)
            logger.info(f"AsyncResultView: Found application {pk}")
        except Application.DoesNotExist:
            logger.error(f"AsyncResultView: Application {pk} not found")
            return Response(
                {'error': 'Application not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Получаем результат расчета
        async_population = request.data.get('async_population')

        if async_population is not None:
            # Обновляем поле рассчитанной численности
            application.calculated_population = async_population
            application.save(update_fields=['calculated_population'])

            logger.info(f"AsyncResultView: Updated application {pk} with population {async_population}")
            return Response({
                'message': 'Population updated successfully',
                'application_id': pk,
                'calculated_population': async_population,
            })
        else:
            logger.error(f"AsyncResultView: async_population field is missing in request")
            return Response(
                {'error': 'async_population field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )


import concurrent.futures
import threading
import time
import random
from django.db import transaction

# Создаем глобальный пул потоков
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)


def async_calculation_task(application_id):
    """
    Функция для асинхронного расчета численности
    """
    try:
        print(f"[ASYNC] Начало расчета для заявки {application_id}")

        # Имитируем долгий расчет
        delay = 5 + random.randint(0, 5)
        print(f"[ASYNC] Задержка: {delay} секунд")
        time.sleep(delay)

        # Используем новое соединение с БД
        from django.db import connection
        connection.close()

        # Импортируем модели здесь, чтобы избежать циклических импортов
        from .models import Application, OrderInApplication

        # Получаем заявку в транзакции
        with transaction.atomic():
            # Используем select_for_update для безопасного обновления
            application = Application.objects.select_for_update().get(id=application_id)

            if not application.territory_area or application.territory_area <= 0:
                print(f"[ASYNC] Площадь территории не указана для заявки {application_id}")
                return None

            # Рассчитываем численность
            total_population = 0

            # Используем select_related для оптимизации запросов
            orders_in_app = application.orderinapplication_set.select_related('order').all()

            for order_in_app in orders_in_app:
                order = order_in_app.order
                if order.building_density and order.people_per_building:
                    # Формула: площадь × плотность × человек
                    population = float(application.territory_area) * order.building_density * order.people_per_building
                    total_population += population

            # Добавляем случайное отклонение (±10%)
            deviation = 0.9 + random.random() * 0.2
            final_population = int(total_population * deviation)

            # Обновляем поле
            application.calculated_population = final_population
            application.save(update_fields=['calculated_population'])

            print(f"[ASYNC] Расчет завершен для заявки {application_id}: {final_population} человек")
            return final_population

    except Exception as e:
        print(f"[ASYNC] Ошибка при расчете заявки {application_id}: {str(e)}")
        return None


class SimpleAsyncView(APIView):
    """
    Простой endpoint для асинхронного обновления (гарантированно работает)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        """
        Простой POST для демонстрации асинхронного обновления
        """
        import threading
        import time

        def update_in_background(app_id):
            """Функция, которая выполняется в фоне"""
            try:
                # Ждем 5 секунд
                time.sleep(5)

                # Закрываем все соединения
                from django.db import connections
                for conn in connections.all():
                    conn.close()

                # Открываем новое соединение
                from django.db import connection
                connection.connect()

                # Получаем и обновляем заявку
                from .models import Application
                app = Application.objects.get(id=app_id)

                if app.territory_area and app.territory_area > 0:
                    # Простой расчет
                    total = 0
                    for order_in_app in app.orderinapplication_set.all():
                        order = order_in_app.order
                        if order.building_density and order.people_per_building:
                            total += float(app.territory_area) * order.building_density * order.people_per_building

                    # Обновляем через queryset (работает надежнее)
                    Application.objects.filter(id=app_id).update(
                        calculated_population=int(total * 1.05)  # +5%
                    )

                    print(f"✅ [SimpleAsyncView] Заявка {app_id} обновлена: {int(total * 1.05)}")

            except Exception as e:
                print(f"❌ [SimpleAsyncView] Ошибка: {e}")

        # Запускаем в отдельном потоке
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
    """
    Прямое обновление через SQL (гарантированно работает)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        from django.db import connection
        import threading
        import time

        def direct_sql_update(app_id):
            """Прямое обновление через SQL"""
            try:
                # Ждем 5 секунд
                time.sleep(5)

                # Закрываем соединение
                connection.close()

                # Открываем новое
                connection.connect()

                # Выполняем SQL-запрос напрямую
                with connection.cursor() as cursor:
                    # Получаем данные заявки
                    cursor.execute(
                        "SELECT territory_area FROM bmstu_lab_application WHERE id = %s",
                        [app_id]
                    )
                    row = cursor.fetchone()

                    if row and row[0]:
                        territory_area = float(row[0])

                        # Получаем все услуги в заявке
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

                        # Обновляем поле
                        new_value = int(total * 1.05)  # +5%
                        cursor.execute(
                            "UPDATE bmstu_lab_application SET calculated_population = %s WHERE id = %s",
                            [new_value, app_id]
                        )

                        print(f"✅ [DirectUpdate] Заявка {app_id} обновлена через SQL: {new_value}")

            except Exception as e:
                print(f"❌ [DirectUpdate] Ошибка: {e}")

        # Запускаем поток
        thread = threading.Thread(target=direct_sql_update, args=(pk,))
        thread.daemon = True
        thread.start()

        return Response({
            'message': 'Прямое обновление запущено!',
            'status': 'success'
        }, status=202)