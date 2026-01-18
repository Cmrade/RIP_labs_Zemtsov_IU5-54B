from rest_framework import serializers
from .models import Orders, Application, OrderInApplication
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from .models import Orders, Application, OrderInApplication, Media


class UserSerializer(serializers.ModelSerializer):
    token = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'token']

    def get_token(self, obj):
        token, created = Token.objects.get_or_create(user=obj)
        return token.key


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password', 'password_confirm']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Пароли не совпадают")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


# Обновим PopulationInDensityCalculationDetailSerializer чтобы добавить медиа
class PopulationInDensityCalculationDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для детального отображения типа населения в расчете плотности"""
    title = serializers.CharField(source='order.title', read_only=True)
    image = serializers.SerializerMethodField()
    main_information = serializers.CharField(source='order.main_information', read_only=True)
    more_information = serializers.CharField(source='order.more_information', read_only=True)
    building_density = serializers.IntegerField(source='order.building_density', read_only=True)
    people_per_building = serializers.IntegerField(source='order.people_per_building', read_only=True)
    calculated_population_for_type = serializers.SerializerMethodField()
    media_files = serializers.SerializerMethodField()

    class Meta:
        model = OrderInApplication
        fields = ['id', 'order_id', 'title', 'image', 'main_information', 'more_information',
                  'building_density', 'people_per_building', 'comment',
                  'calculated_population_for_type', 'media_files']

    def get_image(self, obj):
        """Метод для получения URL изображения"""
        request = self.context.get('request')
        if obj.order.image:
            # Если изображение уже полный URL, оставляем как есть
            if obj.order.image.startswith(('http://', 'https://')):
                return obj.order.image
            # Иначе добавляем домен и порт
            elif request:
                return request.build_absolute_uri(obj.order.image)
            else:
                return obj.order.image
        return None

    def get_calculated_population_for_type(self, obj):
        """Расчет численности населения для конкретного типа населения"""
        # Получаем расчет плотности из контекста
        density_calculation = self.context.get('density_calculation')
        if not density_calculation:
            return 0

        if (density_calculation.territory_area and
                obj.order.building_density and
                obj.order.people_per_building):
            # Формула расчета: площадь × плотность застройки × человек в постройке
            population = float(density_calculation.territory_area) * \
                         obj.order.building_density * \
                         obj.order.people_per_building
            return population
        return 0

    def get_media_files(self, obj):
        """Получаем все медиа-файлы для этого типа населения"""
        media_files = obj.order.media_files.all()
        serializer = MediaSerializer(
            media_files,
            many=True,
            context={'request': self.context.get('request')}
        )
        return serializer.data


class PopulationInDensityCalculationSerializer(serializers.ModelSerializer):
    """Базовый сериализатор для связи расчета плотности и типа населения"""
    order_title = serializers.CharField(source='order.title', read_only=True)
    order_image = serializers.SerializerMethodField()
    population_image = serializers.SerializerMethodField()  # Добавляем новое поле
    has_media = serializers.SerializerMethodField()  # Добавляем информацию о наличии медиа

    class Meta:
        model = OrderInApplication
        fields = [
            'id', 'order', 'order_title', 'order_image',
            'population_image', 'has_media', 'comment'
        ]
        read_only_fields = ('id',)

    def get_order_image(self, obj):
        request = self.context.get('request')
        order = obj.order

        # Сначала пытаемся получить первый медиа-файл
        if hasattr(order, 'media_files') and order.media_files.exists():
            first_media = order.media_files.filter(file_type='image').first()
            if not first_media:
                first_media = order.media_files.first()

            if first_media:
                file_url = first_media.file_url
                if file_url.startswith('http'):
                    return file_url
                elif request:
                    return request.build_absolute_uri(file_url)
                else:
                    return file_url

        # Если медиа нет, используем старое изображение
        if order.image:
            if order.image.startswith('http'):
                return order.image
            elif request:
                return request.build_absolute_uri(order.image)
            else:
                return order.image

        return None

    def get_population_image(self, obj):
        """Альтернативный метод получения изображения (для совместимости)"""
        return self.get_order_image(obj)

    def get_has_media(self, obj):
        """Проверяем, есть ли у типа населения медиа-файлы"""
        if hasattr(obj.order, 'media_files'):
            return obj.order.media_files.exists()
        return False


class ApplicationDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для детального отображения расчета плотности со всеми данными"""
    client_username = serializers.CharField(source='client.username', read_only=True)
    manager_username = serializers.CharField(source='manager.username', read_only=True)
    client_email = serializers.EmailField(source='client.email', read_only=True)
    populations = serializers.SerializerMethodField()
    populations_count = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            'id', 'status', 'status_display', 'title', 'description',
            'territory_area', 'calculated_population',
            'client_id', 'client_username', 'client_email',
            'manager_id', 'manager_username',
            'creation_datetime', 'formation_datetime',
            'completion_datetime', 'populations', 'populations_count'
        ]

    def get_populations(self, obj):
        """Получает типы населения с медиа-файлами"""
        populations_in_calc = obj.orderinapplication_set.all().select_related('order')

        populations_data = []
        for pop_in_calc in populations_in_calc:
            population = pop_in_calc.order

            # Получаем первый медиа-файл
            first_media = None
            if hasattr(population, 'media_files'):
                population.media_files.all()  # Загружаем медиа-файлы
                first_media = population.media_files.filter(file_type='image').first()
                if not first_media:
                    first_media = population.media_files.first()

            # Формируем URL изображения
            population_image = None
            if first_media:
                file_url = first_media.file_url
                request = self.context.get('request')
                if file_url.startswith('http'):
                    population_image = file_url
                elif request:
                    population_image = request.build_absolute_uri(file_url)
                else:
                    population_image = file_url
            elif population.image:
                request = self.context.get('request')
                if population.image.startswith('http'):
                    population_image = population.image
                elif request:
                    population_image = request.build_absolute_uri(population.image)
                else:
                    population_image = population.image

            populations_data.append({
                'id': pop_in_calc.id,
                'order_id': population.id,
                'population': population.id,
                'population_title': population.title,
                'population_image': population_image or '/default-image.jpg',
                'main_information': population.main_information,
                'more_information': population.more_information,
                'building_density': population.building_density,
                'people_per_building': population.people_per_building,
                'comment': pop_in_calc.comment,
                'has_media': first_media is not None,
                'media_count': population.media_files.count() if hasattr(population, 'media_files') else 0
            })

        return populations_data

    def get_populations_count(self, obj):
        return obj.orderinapplication_set.count()

    def get_status_display(self, obj):
        return obj.get_status_display()
    '''
    def get_populations(self, obj):
        """Получает типы населения с дополнительным контекстом"""
        populations_in_calc = obj.orderinapplication_set.all()
        serializer = PopulationInDensityCalculationDetailSerializer(
            populations_in_calc,
            many=True,
            context={
                'density_calculation': obj,
                'request': self.context.get('request')
            }
        )
        return serializer.data

    def get_populations_count(self, obj):
        return obj.orderinapplication_set.count()

    def get_status_display(self, obj):
        """Возвращает человеко-читаемое название статуса"""
        return obj.get_status_display()

    def get_creation_date_formatted(self, obj):
        if obj.creation_datetime:
            return obj.creation_datetime.strftime('%d.%m.%Y')
        return None

    def get_creation_time_formatted(self, obj):
        if obj.creation_datetime:
            return obj.creation_datetime.strftime('%H:%M')
        return None

    def get_formation_date_formatted(self, obj):
        if obj.formation_datetime:
            return obj.formation_datetime.strftime('%d.%m.%Y')
        return None

    def get_formation_time_formatted(self, obj):
        if obj.formation_datetime:
            return obj.formation_datetime.strftime('%H:%M')
        return None

    def get_completion_date_formatted(self, obj):
        if obj.completion_datetime:
            return obj.completion_datetime.strftime('%d.%m.%Y')
        return None

    def get_completion_time_formatted(self, obj):
        if obj.completion_datetime:
            return obj.completion_datetime.strftime('%H:%M')
        return None'''


class ApplicationSerializer(serializers.ModelSerializer):
    """Сериализатор для списка расчетов плотности"""
    client_username = serializers.CharField(source='client.username', read_only=True)
    manager_username = serializers.CharField(source='manager.username', read_only=True)
    calculated_population_formatted = serializers.SerializerMethodField()
    territory_area_formatted = serializers.SerializerMethodField()
    description = serializers.CharField(read_only=True, allow_blank=True, allow_null=True)

    class Meta:
        model = Application
        fields = [
            'id',
            'status',
            'title',
            'description',
            'creation_datetime',
            'formation_datetime',
            'completion_datetime',
            'client_username',
            'manager_username',
            'calculated_population_formatted',
            'territory_area_formatted'
        ]
        read_only_fields = ('id', 'creation_datetime', 'formation_datetime',
                            'completion_datetime', 'client', 'manager', 'calculated_population')

    def get_calculated_population_formatted(self, obj):
        if obj.calculated_population:
            return f"{obj.calculated_population:,.0f}".replace(',', ' ')
        return None

    def get_territory_area_formatted(self, obj):
        if obj.territory_area:
            return f"{obj.territory_area:,.1f}".replace(',', ' ')
        return None


class ApplicationListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка расчетов плотности"""
    client_username = serializers.CharField(source='client.username', read_only=True)
    manager_username = serializers.CharField(source='manager.username', read_only=True)
    populations_count = serializers.SerializerMethodField()
    calculated_population_formatted = serializers.SerializerMethodField()
    territory_area_formatted = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ['id', 'status', 'title', 'description', 'creation_datetime', 'formation_datetime',
                  'completion_datetime', 'client_username', 'manager_username',
                  'populations_count', 'calculated_population_formatted', 'territory_area_formatted']

    def get_populations_count(self, obj):
        return obj.orderinapplication_set.count()

    def get_calculated_population_formatted(self, obj):
        if obj.calculated_population:
            return f"{obj.calculated_population:,.0f}".replace(',', ' ')
        return None

    def get_territory_area_formatted(self, obj):
        if obj.territory_area:
            return f"{obj.territory_area:,.1f}".replace(',', ' ')
        return None


# Добавим новый сериализатор после существующих

class MediaSerializer(serializers.ModelSerializer):
    """Сериализатор для медиа-файлов"""

    class Meta:
        model = Media
        fields = ['id', 'population_id', 'file_url', 'file_type', 'upload_at']
        read_only_fields = ['id', 'upload_at']

    def to_representation(self, instance):
        """Переопределяем для добавления полного URL"""
        representation = super().to_representation(instance)

        # Добавляем превью для изображений
        if instance.file_type == Media.MediaType.IMAGE:
            representation['is_image'] = True
            representation['is_video'] = False
        else:
            representation['is_image'] = False
            representation['is_video'] = True

        # Если URL уже полный, оставляем как есть, иначе добавляем base URL
        request = self.context.get('request')
        if request and not instance.file_url.startswith(('http://', 'https://')):
            representation['file_url'] = request.build_absolute_uri(instance.file_url)

        return representation


class MediaDetailSerializer(serializers.ModelSerializer):
    """Детальный сериализатор для медиа-файлов"""

    population_title = serializers.CharField(source='population.title', read_only=True)

    class Meta:
        model = Media
        fields = ['id', 'population_id', 'population_title', 'file_url',
                  'file_type', 'upload_at', 'clip_embedding']
        read_only_fields = ['id', 'upload_at']


class PopulationsSerializer(serializers.ModelSerializer):
    media_files = MediaSerializer(many=True, read_only=True, source='media_files.all')
    media_count = serializers.SerializerMethodField()
    first_media_image = serializers.SerializerMethodField()  # Добавляем поле для первого изображения

    class Meta:
        model = Orders
        fields = '__all__'
        read_only_fields = ('id', 'app_flag', 'media_files')

    def get_media_count(self, obj):
        return obj.media_files.count()

    def get_first_media_image(self, obj):
        """Возвращает первый медиа-файл типа изображение"""
        request = self.context.get('request')
        if obj.media_files.exists():
            # Ищем первое изображение
            first_image = obj.media_files.filter(file_type='image').first()
            if first_image:
                file_url = first_image.file_url
                if file_url.startswith('http'):
                    return file_url
                elif request:
                    return request.build_absolute_uri(file_url)
                else:
                    return file_url

            # Если изображений нет, берем первый медиа-файл любого типа
            first_media = obj.media_files.first()
            if first_media:
                file_url = first_media.file_url
                if file_url.startswith('http'):
                    return file_url
                elif request:
                    return request.build_absolute_uri(file_url)
                else:
                    return file_url

        # Возвращаем старое изображение, если медиа нет
        if obj.image:
            if obj.image.startswith('http'):
                return obj.image
            elif request:
                return request.build_absolute_uri(obj.image)
            else:
                return obj.image

        return None

    def to_representation(self, instance):
        """Переопределяем для добавления первого изображения в основной объект"""
        representation = super().to_representation(instance)

        # Добавляем первое изображение в основное поле image, если оно пустое
        if not representation.get('image') or representation['image'] == '/default-image.jpg':
            first_media_image = self.get_first_media_image(instance)
            if first_media_image:
                representation['image'] = first_media_image

        return representation