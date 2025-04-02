import stripe
import requests
import time
import base64
import uuid
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.mail import send_mail
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from rest_framework.renderers import JSONRenderer
from .models import Product, Order, Category, PasswordResetToken
from .serializers import (
    ProductSerializer, OrderSerializer, UserSerializer,
    LoginSerializer, CategorySerializer, ForgotPasswordSerializer, ResetPasswordSerializer
)

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

# Set Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY

# Utility function to calculate shipping fee
def calculate_shipping_fee(order):
    total_weight = sum(item.quantity * item.product.weight for item in order.items.all())
    base_fee = Decimal('5.00')  # Default for Kenya
    if order.shipping_location and order.shipping_location.lower() != 'kenya':
        base_fee = Decimal('15.00')  # International shipping
    weight_fee = Decimal('2.00') * (total_weight - 2) if total_weight > 2 else Decimal('0.00')
    return base_fee + weight_fee

# Home View
class HomeView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        return Response({
            "message": "Welcome to the Merch E-Commerce API! Use /api/ for API endpoints or /admin/ for the admin panel."
        })

# Registration View
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

# Login View
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            return Response({'token': token.key, 'user_id': user.id}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Product Views
class ProductList(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

class ProductDetail(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'id'
    permission_classes = [AllowAny]

# Order Views
class OrderList(generics.ListCreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        shipping_location = self.request.data.get('shipping_location', 'Kenya')
        order = serializer.save(user=self.request.user, shipping_location=shipping_location)
        order.shipping_fee = calculate_shipping_fee(order)
        order.total = sum(item.quantity * item.unit_price for item in order.items.all()) + order.shipping_fee
        order.save()

# Stripe Payment View
class StripePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            order = Order.objects.get(id=request.data['order_id'], user=request.user)
            amount = int(order.total * 100)  # Stripe expects amount in cents
            payment_intent = stripe.PaymentIntent.create(
                amount=amount,
                currency='usd',
                payment_method=request.data['payment_method_id'],
                confirm=True
            )
            order.payment_status = 'COMPLETED'
            order.save()
            return Response({
                'status': 'succeeded',
                'payment_intent_id': payment_intent.id,
                'order_id': order.id
            }, status=status.HTTP_200_OK)
        except (stripe.error.StripeError, Order.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except KeyError as e:
            return Response({'error': f'Missing required field: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

# M-Pesa Payment View
class MpesaPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            order = Order.objects.get(id=request.data['order_id'], user=request.user)
            phone = request.data['phone']
            if not phone.startswith('254') or len(phone) != 12:
                return Response({'error': 'Phone number must be in the format 2547XXXXXXXX'}, status=status.HTTP_400_BAD_REQUEST)

            access_token = get_mpesa_access_token()
            response = requests.post(
                'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest',
                json={
                    'BusinessShortCode': settings.MPESA_SHORTCODE,
                    'Password': get_mpesa_password(),
                    'Timestamp': get_mpesa_timestamp(),
                    'TransactionType': 'CustomerPayBillOnline',
                    'Amount': int(order.total),
                    'PartyA': phone,
                    'PartyB': settings.MPESA_SHORTCODE,
                    'PhoneNumber': phone,
                    'CallBackURL': settings.MPESA_CALLBACK_URL,
                    'AccountReference': f'Order {order.id}',
                    'TransactionDesc': 'Payment for order'
                },
                headers={'Authorization': f'Bearer {access_token}'}
            )
            if response.status_code == 200:
                data = response.json()
                order.checkout_request_id = data.get('CheckoutRequestID')
                order.payment_status = 'PENDING'
                order.save()
                return Response({
                    'status': 'initiated',
                    'checkout_request_id': order.checkout_request_id,
                    'order_id': order.id
                }, status=status.HTTP_200_OK)
            return Response({'error': 'M-Pesa payment failed', 'details': response.text}, status=status.HTTP_400_BAD_REQUEST)
        except (Order.DoesNotExist, KeyError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'Unexpected error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Utility functions for M-Pesa
def get_mpesa_access_token():
    try:
        response = requests.get(
            'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
            auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET)
        )
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.RequestException as e:
        raise Exception(f"Failed to get M-Pesa access token: {str(e)}")

def get_mpesa_password():
    return base64.b64encode(f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{get_mpesa_timestamp()}".encode()).decode()

def get_mpesa_timestamp():
    return time.strftime('%Y%m%d%H%M%S')

# Category Views
class CategoryListCreateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CategoryDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, id):
        try:
            category = Category.objects.get(id=id)
            serializer = CategorySerializer(category)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Category.DoesNotExist:
            return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, id):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            category = Category.objects.get(id=id)
            serializer = CategorySerializer(category, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Category.DoesNotExist:
            return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, id):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            category = Category.objects.get(id=id)
            category.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Category.DoesNotExist:
            return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)

# Password Reset Views
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email=email)
            token = str(uuid.uuid4())
            PasswordResetToken.objects.create(user=user, token=token)

            reset_link = f"{request.build_absolute_uri('/api/reset-password/')}{token}"
            try:
                send_mail(
                    subject='Password Reset Request',
                    message=f'Click the link to reset your password: {reset_link}',
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[email],
                    fail_silently=False,
                )
                return Response({'message': 'Password reset link sent to your email!'}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': f'Failed to send email: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, token):
        try:
            reset_token = PasswordResetToken.objects.get(token=token)
        except PasswordResetToken.DoesNotExist:
            return Response({'error': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)

        if reset_token.is_expired():
            reset_token.delete()
            return Response({'error': 'Token has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_password = serializer.validated_data['new_password']
        user = reset_token.user
        user.set_password(new_password)
        user.save()

        reset_token.delete()
        return Response({'message': 'Password reset successful!'}, status=status.HTTP_200_OK)
    
# user views 



class UserDetailView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "username": user.username,
            "email": user.email
        }, status=status.HTTP_200_OK)

    def put(self, request):
        user = request.user
        username = request.data.get('username', user.username)
        email = request.data.get('email', user.email)
        password = request.data.get('password', None)

        # Check if username is already taken by another user
        if username != user.username and User.objects.filter(username=username).exists():
            return Response({"detail": "Username already taken"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if email is already taken by another user
        if email != user.email and User.objects.filter(email=email).exists():
            return Response({"detail": "Email already taken"}, status=status.HTTP_400_BAD_REQUEST)

        # Update user details
        user.username = username
        user.email = email
        if password:
            user.set_password(password)
        user.save()

        return Response({
            "username": user.username,
            "email": user.email
        }, status=status.HTTP_200_OK)