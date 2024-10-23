from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),  
    path('auth/', include('shopify_app.urls')),  
    path('', include('home.urls')),
]
