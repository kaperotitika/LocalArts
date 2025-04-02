from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from store.views import HomeView  # Import HomeView for the root URL

# Define the root URL patterns
urlpatterns = [
    path('', HomeView.as_view(), name='home'),  # Added root URL
    path('admin/', admin.site.urls),
    path('api/', include('store.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)