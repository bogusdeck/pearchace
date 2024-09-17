from django.urls import path
from . import views
from .billing import initiate_billing, billing_confirmation

urlpatterns = [
    # header 
    path('', views.index, name='root_path'),
    path('api/get-client-info/', views.get_client_info, name="get_client_info"), #

    # dashboard 
    # path('api/get-graph/',views.graph_dashboard, name='get-graph')
    path('api/available-sorts/', views.available_sorts, name='available_sorts'), #
    path('api/last-active-collections/', views.last_active_collections, name='last_active_collections'), #
    # collection manager
    path('api/client-last-sorted-time/<int:client_id>/', views.get_last_sorted_time, name='get_last_sorted_time'),#
    path('api/search-collections/<int:client_id>/', views.search_collections, name='search_collections'),#
    path('api/client-collections/<int:client_id>/', views.get_client_collections, name='client_collections'), #
    # path('api/get-client-info/', views.get_client_info, name='get-client-info'),
    # path('api/collections/', views.get_collections, name='collections_list_api'),
    # path('api/products/', views.get_products, name='product_list_api'),
    path('api/update-products-order/', views.update_product_order, name="update_products_order_api"),
    # path('api/client-info/', views.get_client_info, name='get_client_info'),
    # path('api/shop-info/', views.get_shopify_client_data, name="get_shopify_client_info"),
    path('api/update-collections/<str:collection_id>/', views.update_collection, name='update_collection'),#
    path('api/update-collection-settings/', views.update_collection_settings, name='update-collection-settings'),#
    path('api/update-global-settings/', views.update_global_settings, name='update-global-settings'), #
    path('api/fetch-sort-date/', views.fetch_last_sort_date, name='fetch-sort-date'),#
    path('api/get-and-update-collections/', views.get_and_update_collections, name='get-and-update-collections'), # 
    path('api/get-products/', views.get_products, name='get-products'), #
    path('api/update-pinned-products/', views.update_pinned_products, name='update-pinned-products'), # 
    path('api/get-sorting-algorithms/', views.get_sorting_algorithms, name='get-sorting-algorithms'), #
    path('api/update-default-algo/', views.update_default_algo, name='update-default-algo'),# 

    # # Billing urls 
    path('api/create_subscription/', initiate_billing, name='create_subscription'),
    path('api/billing/confirm/', billing_confirmation, name='billing_confirmation'),  
]
