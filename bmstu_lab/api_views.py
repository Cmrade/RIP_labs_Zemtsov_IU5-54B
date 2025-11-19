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
from .serializers import *
from .permissions import IsOwner, IsModerator, IsOwnerOrModerator, IsAuthenticatedOrReadOnlyForNonModerator
from django.contrib.auth import authenticate, login, logout
from rest_framework.authtoken.models import Token
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from django.middleware.csrf import get_token
from .redis_service import RedisService
from django.core.files.storage import default_storage
import uuid
import os


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
    serializer_class = OrdersSerializer
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
class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationListSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get_queryset(self):
        user = self.request.user

        # Всегда исключаем удаленные заявки
        queryset = Application.objects.exclude(status='DELETED')

        # Для обычных пользователей показываем только их заявки
        if not user.is_staff:
            queryset = queryset.filter(client=user)

        # Для списка дополнительно исключаем DRAFT для не-владельцев
        if self.action == 'list' and not user.is_staff:
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

    # Остальные методы остаются без изменений...

    def retrieve(self, request, *args, **kwargs):
        """
        GET одна запись (поля заявки + ее услуги)
        Возвращает заявку со списком ее услуг с картинками
        """
        try:
            instance = self.get_object()

            # Используем ApplicationSerializer который включает orders через OrderInApplicationSerializer
            serializer = ApplicationSerializer(instance)

            return Response(serializer.data)

        except Application.DoesNotExist:
            return Response(
                {'error': 'Заявка не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

    def destroy(self, request, *args, **kwargs):
        """
        DELETE удаление (меняет статус на DELETED вместо удаления из БД)
        """
        try:
            application = self.get_object()

            # Проверяем, что заявка не уже удалена
            if application.status == Application.ApplicationStatus.DELETED:
                return Response(
                    {'error': 'Заявка уже удалена'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Проверяем, что заявка находится в допустимом статусе для удаления
            # (обычно можно удалять только черновики или сформированные заявки)
            if application.status not in [Application.ApplicationStatus.DRAFT,
                                          Application.ApplicationStatus.FORMED]:
                return Response(
                    {'error': f'Нельзя удалить заявку со статусом {application.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Меняем статус на DELETED вместо удаления из БД
            application.status = Application.ApplicationStatus.DELETED
            application.save()

            return Response(
                {'message': 'Заявка успешно удалена (статус изменен на DELETED)'},
                status=status.HTTP_200_OK
            )

        except Application.DoesNotExist:
            return Response(
                {'error': 'Заявка не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

    def get_serializer_class(self):
        """
        Выбираем сериализатор в зависимости от действия
        """
        if self.action in ['retrieve', 'update', 'partial_update', 'create']:
            return ApplicationSerializer
        return ApplicationListSerializer

    @action(detail=True, methods=['put'])
    def form(self, request, pk=None):
        """
        PUT сформировать создателем (дата формирования)
        Происходит проверка на обязательные поля
        """
        application = self.get_object()

        # Проверяем, что заявка находится в статусе DRAFT
        if application.status != Application.ApplicationStatus.DRAFT:
            return Response(
                {'error': 'Заявка уже сформирована или имеет другой статус'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка обязательных полей заявки
        required_fields = []
        # Убрали проверку на title, так как его не должно быть
        if not application.territory_area:
            required_fields.append('territory_area')

        if required_fields:
            return Response(
                {
                    'error': 'Не заполнены обязательные поля заявки',
                    'missing_fields': required_fields,
                    'message': f'Заполните следующие поля: {", ".join(required_fields)}'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка, что в заявке есть хотя бы одна услуга
        if not application.orderinapplication_set.exists():
            return Response(
                {'error': 'Добавьте хотя бы одну услугу в заявку'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка, что все услуги в заявке имеют необходимые данные для расчета
        orders_with_missing_data = []
        for order_in_app in application.orderinapplication_set.all():
            order = order_in_app.order
            if not order.building_density or not order.people_per_building:
                orders_with_missing_data.append({
                    'order_id': order.id,
                    'order_title': order.title,
                    'missing_building_density': not order.building_density,
                    'missing_people_per_building': not order.people_per_building
                })

        if orders_with_missing_data:
            return Response(
                {
                    'error': 'Некоторые услуги не имеют данных для расчета',
                    'orders_with_missing_data': orders_with_missing_data,
                    'message': 'Заполните плотность застройки и количество человек в постройке для всех услуг'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Все проверки пройдены - формируем заявку
        application.status = Application.ApplicationStatus.FORMED
        application.formation_datetime = timezone.now()
        application.save()

        # Возвращаем обновленные данные заявки
        serializer = ApplicationSerializer(application)
        return Response(serializer.data)

    def perform_create(self, serializer):
        # Автоматическое назначение текущего пользователя как клиента
        serializer.save(client=self.request.user)

    @action(detail=True, methods=['put'], permission_classes=[IsModerator])
    def complete(self, request, pk=None):
        """Только модератор может завершать заявки"""
        application = self.get_object()
        action_type = request.data.get('action')

        if application.status != Application.ApplicationStatus.FORMED:
            return Response(
                {'error': 'Заявка должна быть в статусе FORMED'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if action_type == 'complete':
            application.status = Application.ApplicationStatus.COMPLETED
            # Вычисление стоимости
            self.calculate_application_total(application)
        elif action_type == 'reject':
            application.status = Application.ApplicationStatus.REJECTED
        else:
            return Response(
                {'error': 'Неверное действие'},
                status=status.HTTP_400_BAD_REQUEST
            )

        application.completion_datetime = timezone.now()
        application.manager = request.user  # Текущий модератор
        application.save()

        return Response(ApplicationSerializer(application).data)

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
                        client=get_fixed_user(),
                        status=Application.ApplicationStatus.DRAFT
                    ).values('id', 'status'))
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверяем, что заявка принадлежит фиксированному пользователю
        # В методе add_order_to_application замените временный код на:
        if application.client != get_fixed_user():
            return Response(
                {
                    'error': f'Заявка принадлежит другому пользователю',
                    'application_owner': application.client.username if application.client else 'None',
                    'current_user': get_fixed_user().username
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

        serializer = OrderInApplicationSerializer(order_in_app)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """
        PUT изменение заявки
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        # Запрещаем изменение системных полей
        request.data.pop('status', None)
        request.data.pop('creation_datetime', None)
        request.data.pop('formation_datetime', None)
        request.data.pop('completion_datetime', None)
        request.data.pop('client', None)
        request.data.pop('manager', None)
        request.data.pop('calculated_population', None)

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data)

    @action(detail=True, methods=['delete'], url_path='orders/(?P<order_id>[^/.]+)')
    def remove_order_from_application(self, request, pk=None, order_id=None):
        """
        DELETE удаление из заявки (без PK м-м)
        Удаляет услугу из заявки по ID заявки и ID услуги
        """
        try:
            application = self.get_object()
        except Application.DoesNotExist:
            return Response(
                {'error': 'Заявка не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Проверяем, что заявка в статусе DRAFT (можно удалять только из черновика)
        if application.status != Application.ApplicationStatus.DRAFT:
            return Response(
                {'error': 'Можно удалять услуги только из заявки-черновика'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order = Orders.objects.get(id=order_id)
        except Orders.DoesNotExist:
            return Response(
                {'error': 'Услуга не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Находим и удаляем связь между заявкой и услугой
        try:
            order_in_app = OrderInApplication.objects.get(
                application=application,
                order=order
            )
            order_in_app.delete()
        except OrderInApplication.DoesNotExist:
            return Response(
                {'error': 'Услуга не найдена в заявке'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Возвращаем обновленные данные заявки
        serializer = ApplicationSerializer(application)
        return Response(serializer.data)

    @action(detail=True, methods=['put'], url_path='orders/(?P<order_id>[^/.]+)')
    def update_order_in_application(self, request, pk=None, order_id=None):
        try:
            # Находим связь по application_id и order_id
            order_in_app = OrderInApplication.objects.get(
                application_id=pk,
                order_id=order_id
            )
        except OrderInApplication.DoesNotExist:
            return Response(
                {'error': 'Связь между заявкой и услугой не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        new_comment = request.data.get('comment', '')
        order_in_app.comment = new_comment
        order_in_app.save()

        serializer = OrderInApplicationSerializer(order_in_app)
        return Response(serializer.data)

    def calculate_order_total(self, application):
        # Реализовать вычисление по формуле из лабораторной работы 2
        # Например: total = sum(order.calculate_cost() for order in application.orders.all())
        pass

    def calculate_application_total(self, application):
        """Расчет численности населения для заявки"""
        application.calculate_population()


class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get(self, request):
        user = request.user
        draft_application = Application.objects.filter(
            client=user,
            status=Application.ApplicationStatus.DRAFT
        ).first()

        if draft_application:
            orders_count = draft_application.orderinapplication_set.count()

            redis_service.cache_cart_count(user.id, orders_count)

            return Response({
                'application_id': draft_application.id,
                'orders_count': orders_count
            })
        else:
            new_application = Application.objects.create(
                client=user,
                status=Application.ApplicationStatus.DRAFT
            )
            return Response({
                'application_id': new_application.id,
                'orders_count': 0
            })


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

    def post(self, request, order_id):
        user = request.user

        # Находим или создаем заявку-черновик
        application, created = Application.objects.get_or_create(
            client=user,
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