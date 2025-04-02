from django.urls import path
from .views import UserDetailView
from .views import (
    ProductList, ProductDetail, OrderList, StripePaymentView, MpesaPaymentView,
    RegisterView, LoginView, CategoryListCreateView, CategoryDetailView,
    ForgotPasswordView, ResetPasswordView
)

app_name = 'store'  # Added for namespacing

urlpatterns = [
    # User authentication endpoints
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/<str:token>/', ResetPasswordView.as_view(), name='reset-password'),

    # Product endpoints
    path('products/', ProductList.as_view(), name='product-list'),
    path('products/<int:id>/', ProductDetail.as_view(), name='product-detail'),

    # Order endpoints
    path('orders/', OrderList.as_view(), name='order-list'),

    # Payment endpoints
    path('stripe-payment/', StripePaymentView.as_view(), name='stripe-payment'),
    path('mpesa-payment/', MpesaPaymentView.as_view(), name='mpesa-payment'),

    # Category endpoints
    path('categories/', CategoryListCreateView.as_view(), name='category-list'),
    path('categories/<int:id>/', CategoryDetailView.as_view(), name='category-detail'),




    path('api/user/', UserDetailView.as_view(), name='user-detail'),
    # Other URLs...

]