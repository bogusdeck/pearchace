from django.urls import path
from . import views
from .views import customer_data_request, customer_data_erasure, shop_data_erasure

urlpatterns = [
    path('login/', views.login, name='login'),
    path('finalize/', views.finalize, name='finalize'),
    path('logout/', views.logout, name='logout'),

     # mandatory webhooks
    path('webhooks/customer-data-request/', customer_data_request, name='customer-data-request'),
    path('webhooks/customer-data-erasure/', customer_data_erasure, name='customer-data-erasure'),
    path('webhooks/shop-data-erasure/', shop_data_erasure, name='shop-data-erasure'),
]
