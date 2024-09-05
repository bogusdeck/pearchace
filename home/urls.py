from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='root_path'),
    path('api/collections/', views.get_collections, name='collections_list_api'),
    path('api/products/', views.get_products, name='product_list_api'),
    path('api/update-products-order/', views.update_product_order, name="update_products_order_api"),
    path('api/client-info/', views.get_client_info, name='get_client_info'),
    path('api/shop-info/', views.get_shopify_client_data, name="get_shopify_client_info")
]
