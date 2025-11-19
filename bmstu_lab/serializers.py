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
        # Создаем или получаем токен для пользователя
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


# Остальные сериализаторы остаются без изменений
class OrdersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Orders
        fields = '__all__'
        read_only_fields = ('id', 'app_flag')


class OrderInApplicationSerializer(serializers.ModelSerializer):
    order_title = serializers.CharField(source='order.title', read_only=True)
    order_image = serializers.CharField(source='order.image', read_only=True)

    class Meta:
        model = OrderInApplication
        fields = ['id', 'order', 'order_title', 'order_image', 'comment']
        read_only_fields = ('id',)


class ApplicationSerializer(serializers.ModelSerializer):
    orders = OrderInApplicationSerializer(source='orderinapplication_set', many=True, read_only=True)
    client_username = serializers.CharField(source='client.username', read_only=True)
    manager_username = serializers.CharField(source='manager.username', read_only=True)

    class Meta:
        model = Application
        fields = '__all__'
        read_only_fields = ('id', 'creation_datetime', 'formation_datetime',
                            'completion_datetime', 'client', 'manager')


class ApplicationListSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source='client.username', read_only=True)
    manager_username = serializers.CharField(source='manager.username', read_only=True)
    orders_count = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ['id', 'status', 'creation_datetime', 'formation_datetime',
                  'completion_datetime', 'client_username', 'manager_username', 'orders_count']

    def get_orders_count(self, obj):
        return obj.orderinapplication_set.count()