from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='root_path'),
    path('api/collections/', views.get_collections, name='collections_list_api'),
    path('api/products/', views.get_products, name='product_list_api'),
    path('api/update-products-order/', views.update_product_order, name="update_products_order_api"),
    path('api/client-info/', views.get_client_info, name='get_client_info'),
    path('api/shop-info/', views.get_shopify_client_data, name="get_shopify_client_info"),
    path('api/available-sorts/', views.available_sorts, name='available_sorts'),
    path('api/last-active-collections/', views.last_active_collections, name='last_active_collections'),  
    path('api/client-collections/<int:client_id>/', views.get_client_collections, name='client_collections'), 
    path('api/client-last-sorted-time/<int:client_id>/', views.get_last_sorted_time, name='get_last_sorted_time'),
    path('api/search-collections/<int:client_id>/', views.search_collections, name='search_collections'),
    path('api/update-collections/<str:collection_id>/', views.update_collection, name='update_collection'),
    
]
