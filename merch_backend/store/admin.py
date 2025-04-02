from django.contrib import admin
from .models import Category, Product, Order, OrderItem, PasswordResetToken

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'description']
    search_fields = ['name', 'description']
    list_filter = ['name']
    ordering = ['name']  # Added for default sorting
    list_per_page = 25  # Added for better pagination

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'price', 'weight', 'category']  # Added 'id' and 'category'
    list_filter = ['price', 'category']  # Added 'category' to filters
    search_fields = ['name', 'description']  # Added 'description' to search
    ordering = ['name']  # Added for default sorting
    list_per_page = 25  # Added for better pagination

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'total', 'shipping_fee', 'shipping_location', 'payment_status', 'payment_method', 'created_at']  # Added 'user' and 'created_at'
    list_filter = ['payment_status', 'payment_method', 'created_at']  # Added 'created_at' to filters
    search_fields = ['user__username', 'shipping_location']  # Added search by username and location
    ordering = ['-created_at']  # Added for default sorting
    list_per_page = 25  # Added for better pagination

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product', 'quantity', 'unit_price', 'total_price_display']  # Fixed 'price' to 'unit_price', added 'id' and 'total_price_display'
    list_filter = ['order']  # Added filter by order
    search_fields = ['product__name']  # Added search by product name
    ordering = ['order']  # Added for default sorting
    list_per_page = 25  # Added for better pagination

    def total_price_display(self, obj):
        return obj.total_price  # Display the total_price property
    total_price_display.short_description = 'Total Price'  # Set column header

@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'token', 'created_at', 'expires_at', 'is_expired']
    search_fields = ['user__username', 'token']
    list_filter = ['created_at', 'expires_at']
    ordering = ['-created_at']  # Added for default sorting
    list_per_page = 25  # Added for better pagination

    def is_expired(self, obj):
        return obj.is_expired()  # Display whether the token is expired
    is_expired.boolean = True  # Show as a boolean (green check/red cross)
    is_expired.short_description = 'Expired'  # Set column header