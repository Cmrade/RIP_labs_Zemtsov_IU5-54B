from rest_framework import serializers
from .models import Orders, Application, OrderInApplication
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


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


class PopulationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Orders
        fields = '__all__'
        read_only_fields = ('id', 'app_flag')


class PopulationInDensityCalculationSerializer(serializers.ModelSerializer):
    """Базовый сериализатор для связи расчета плотности и типа населения"""
    order_title = serializers.CharField(source='order.title', read_only=True)
    order_image = serializers.SerializerMethodField()

    class Meta:
        model = OrderInApplication
        fields = ['id', 'order', 'order_title', 'order_image', 'comment']
        read_only_fields = ('id',)

    def get_order_image(self, obj):
        request = self.context.get('request')
        if obj.order.image:
            if obj.order.image.startswith('http'):
                return obj.order.image
            elif request:
                return request.build_absolute_uri(obj.order.image)
            else:
                return obj.order.image
        return None


class PopulationInDensityCalculationDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для детального отображения типа населения в расчете плотности"""
    title = serializers.CharField(source='order.title', read_only=True)
    image = serializers.SerializerMethodField()
    main_information = serializers.CharField(source='order.main_information', read_only=True)
    more_information = serializers.CharField(source='order.more_information', read_only=True)
    building_density = serializers.IntegerField(source='order.building_density', read_only=True)
    people_per_building = serializers.IntegerField(source='order.people_per_building', read_only=True)
    calculated_population_for_type = serializers.SerializerMethodField()

    class Meta:
        model = OrderInApplication
        fields = ['id', 'order_id', 'title', 'image', 'main_information', 'more_information',
                  'building_density', 'people_per_building', 'comment', 'calculated_population_for_type']
        read_only_fields = ('id',)

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.order.image:
            if obj.order.image.startswith('http'):
                return obj.order.image
            elif request:
                return request.build_absolute_uri(obj.order.image)
            else:
                return obj.order.image
        return None

    def get_calculated_population_for_type(self, obj):
        """Рассчитывает население для конкретного типа на основе площади территории"""
        density_calculation = self.context.get('density_calculation')
        if not density_calculation or not density_calculation.territory_area:
            return 0

        if obj.order.building_density and obj.order.people_per_building:
            # Преобразуем все значения к float для безопасного умножения
            territory_area = float(density_calculation.territory_area)
            building_density = float(obj.order.building_density) if obj.order.building_density else 0
            people_per_building = float(obj.order.people_per_building) if obj.order.people_per_building else 0

            return territory_area * building_density * people_per_building
        return 0


class ApplicationDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для детального отображения расчета плотности со всеми данными"""
    client_username = serializers.CharField(source='client.username', read_only=True)
    manager_username = serializers.CharField(source='manager.username', read_only=True)
    client_email = serializers.EmailField(source='client.email', read_only=True)
    populations = serializers.SerializerMethodField()
    populations_count = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    # ... остальные поля ...

    def get_populations(self, obj):
        """Получает типы населения с дополнительным контекстом"""
        populations_in_calc = obj.orderinapplication_set.all()
        serializer = PopulationInDensityCalculationDetailSerializer(
            populations_in_calc,
            many=True,
            context={'density_calculation': obj, 'request': self.context.get('request')}
        )
        return serializer.data

    # Форматированные поля дат через SerializerMethodField
    creation_date_formatted = serializers.SerializerMethodField()
    creation_time_formatted = serializers.SerializerMethodField()
    formation_date_formatted = serializers.SerializerMethodField()
    formation_time_formatted = serializers.SerializerMethodField()
    completion_date_formatted = serializers.SerializerMethodField()
    completion_time_formatted = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            'id', 'status', 'status_display', 'title', 'description',
            'territory_area', 'calculated_population',
            'client_id', 'client_username', 'client_email',
            'manager_id', 'manager_username',
            'creation_datetime', 'creation_date_formatted', 'creation_time_formatted',
            'formation_datetime', 'formation_date_formatted', 'formation_time_formatted',
            'completion_datetime', 'completion_date_formatted', 'completion_time_formatted',
            'populations', 'populations_count'
        ]

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
        return None


class ApplicationSerializer(serializers.ModelSerializer):
    """Основной сериализатор для расчета плотности"""
    populations = PopulationInDensityCalculationDetailSerializer(
        source='orderinapplication_set',
        many=True,
        read_only=True
    )
    client_username = serializers.CharField(source='client.username', read_only=True)
    manager_username = serializers.CharField(source='manager.username', read_only=True)
    populations_count = serializers.SerializerMethodField()

    territory_area = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0.01,
        max_value=999999.99,
        help_text='Площадь территории в гектарах'
    )

    class Meta:
        model = Application
        fields = '__all__'
        read_only_fields = ('id', 'creation_datetime', 'formation_datetime',
                            'completion_datetime', 'client', 'manager', 'calculated_population')

    def get_populations_count(self, obj):
        return obj.orderinapplication_set.count()


class ApplicationListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка расчетов плотности"""
    client_username = serializers.CharField(source='client.username', read_only=True)
    manager_username = serializers.CharField(source='manager.username', read_only=True)
    populations_count = serializers.SerializerMethodField()
    calculated_population_formatted = serializers.SerializerMethodField()
    territory_area_formatted = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ['id', 'status', 'title', 'creation_datetime', 'formation_datetime',
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