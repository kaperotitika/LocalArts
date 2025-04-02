from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from .models import Product, Order, OrderItem, Category
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

# Use get_user_model for flexibility with custom user models
User = get_user_model()

# Serializer for user registration
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']  # Added 'id' for better API response

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        Token.objects.create(user=user)
        return user

    def validate_email(self, value):
        # Ensure email is unique
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        # Ensure username is unique
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

# Serializer for user login
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get("username")
        password = data.get("password")

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid username or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")

        data["user"] = user
        return data

# Serializer for Category model
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']

    def validate_name(self, value):
        # Ensure category name is unique
        if self.instance is None and Category.objects.filter(name=value).exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value

# Serializer for Product model
class ProductSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True, required=False
    )
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    image_url = serializers.SerializerMethodField()  # Added to return absolute image URL

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'description', 'image', 'image_url', 'category', 'category_id', 'weight']  # Added 'weight'

    def get_image_url(self, obj):
        # Return absolute URL for the image
        if obj.image:
            return self.context['request'].build_absolute_uri(obj.image.url)
        return None

    def validate_price(self, value):
        # Ensure price is non-negative
        if value < 0:
            raise serializers.ValidationError("Price must be non-negative.")
        return value

# Serializer for OrderItem model
class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    total_price = serializers.SerializerMethodField()  # Added to expose total_price

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_id', 'quantity', 'unit_price', 'total_price']  # Added 'unit_price' and 'total_price'

    def get_total_price(self, obj):
        # Use the total_price property from the model
        return obj.total_price

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

# Serializer for Order model
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    shipping_fee = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    user = serializers.StringRelatedField(read_only=True)  # Added to display username

    class Meta:
        model = Order
        fields = [
            'id',
            'user',  # Added
            'total',
            'shipping_fee',
            'shipping_location',
            'payment_status',
            'payment_method',
            'checkout_request_id',  # Added
            'created_at',  # Added
            'updated_at',  # Added
            'items',
        ]

    def validate_payment_status(self, value):
        valid_statuses = [choice[0] for choice in Order.PAYMENT_STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Payment status must be one of {valid_statuses}.")
        return value

    def validate_payment_method(self, value):
        valid_methods = [choice[0] for choice in Order.PAYMENT_METHOD_CHOICES]
        if value not in valid_methods:
            raise serializers.ValidationError(f"Payment method must be one of {valid_methods}.")
        return value

    def validate_shipping_location(self, value):
        if not value:
            raise serializers.ValidationError("Shipping location is required.")
        return value

    def validate(self, data):
        if self.context['request'].method == 'POST':
            items = data.get('items', [])
            if not items:
                raise serializers.ValidationError("At least one item is required to create an order.")
        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        order = Order.objects.create(**validated_data)

        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)

        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        instance.shipping_location = validated_data.get('shipping_location', instance.shipping_location)
        instance.payment_status = validated_data.get('payment_status', instance.payment_status)
        instance.payment_method = validated_data.get('payment_method', instance.payment_method)
        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                OrderItem.objects.create(order=instance, **item_data)

        return instance

# Serializer for Forgot Password
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        # Ensure email exists
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user with this email exists.")
        return value

# Serializer for Reset Password
class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(min_length=8)

    def validate_new_password(self, value):
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError("Password must contain at least one digit.")
        if not any(char.isupper() for char in value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not any(char.islower() for char in value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.")
        return value