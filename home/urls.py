from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='root_path'),
    path('api/collections/', views.get_collections, name='collections_list_api'),
    path('api/products/', views.get_products, name='product_list_api'),
]
