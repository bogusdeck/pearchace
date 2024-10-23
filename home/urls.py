from django.urls import path
from . import views
from .billing import create_billing_plan, confirm_billing, handle_app_uninstall, purchase_additional_sorts , extra_sort_confirm

urlpatterns = [
    # header 
    path('', views.index, name='root_path'),
    path('api/get-client-info/', views.get_client_info, name="get_client_info"), #
    # dashboard 
    path('api/get-graph/', views.get_graph, name='get-graph'),
    # path('api/get-graph/',views.graph_dashboard, name='get-graph'),
    path('api/available-sorts/', views.available_sorts, name='available_sorts'), #
    path('api/last-active-collections/', views.last_active_collections, name='last_active_collections'), #
    # collection manager
    path('api/client-last-sorted-time/<int:client_id>/', views.get_last_sorted_time, name='get_last_sorted_time'),#
    path('api/search-collections/<int:client_id>/', views.search_collections, name='search_collections'),#
    path('api/client-collections/<int:client_id>/', views.get_client_collections, name='client_collections'), #
    # path('api/collections/', views.get_collections, name='collections_list_api'),
    # path('api/products/', views.get_products, name='product_list_api'),
    path('api/sort-now/', views.sort_now, name="sort_now"),
    
    path('api/update-collections/<str:collection_id>/', views.update_collection, name='update_collection'),#
    path('api/update-collection-settings/', views.update_collection_settings, name='update-collection-settings'),#
    path('api/update-global-settings/', views.update_global_settings, name='update-global-settings'), # 
    path('api/fetch-sort-date/', views.fetch_last_sort_date, name='fetch-sort-date'),#
    path('api/get-and-update-collections/', views.get_and_update_collections, name='get-and-update-collections'), # 
    path('api/get-products/<str:collection_id>/', views.get_products, name='get-products'), #
    path('api/update-pinned-products/', views.update_pinned_products, name='update-pinned-products'), # 
    path('api/update-default-algo/', views.update_default_algo, name='update-default-algo'), # 

    # # Billing urls 
    # path('api/create_subscription/', initiate_billing, name='create_subscription'),
    # path('api/billing/confirm/', billing_confirmation, name='billing_confirmation'),  
    path('api/billing/create/', create_billing_plan, name='create_billing_plan'),
    path('api/billing/confirm/', confirm_billing, name='confirm_billing'),
    path('api/billing/addon-sorts/', purchase_additional_sorts, name='additional_sorts'),
    path('api/billing/extra-sort-confirm/', extra_sort_confirm, name='extra_sorts_confirm'),
    path('api/billing/uninstall/', handle_app_uninstall, name='handle_app_uninstall'),   

    # new apis
    path('api/preview-products/', views.preview_products, name='preview-products'),
    path('api/post-quick-config/', views.post_quick_config, name='post-quick-config'),
    path('api/get-sorting-algorithms/', views.get_sorting_algorithms, name='get-sorting-algorithms'), 
    path('api/save-client-algorithm/', views.save_client_algorithm, name='save-client-algorithm'),
    path('api/get-active-collections/', views.get_active_collections, name="get-active-collections"), # post man 
    path('api/search-products/<str:collection_id>/', views.search_products, name='search-collections'), # no use yet
    path('api/update-all-algo/<int:algo_id>/', views.update_all_algo, name='update-all-algo'), # 
    path('api/applied-on-active-collection/', views.applied_on_active_collection, name='applied-on-active-collection'),
    path('api/sorting-rule/<int:algo_id>/', views.sorting_rule, name='sorting-rule'),
    path('api/advance-config/', views.advance_config, name='advance-config'),
    path('api/get-collection-analytics/<int:collection_id>/', views.get_collection_analytics, name='get-collection-analytics'),
    path('api/order-count/', views.fetch_last_month_order_count, name='fetch_last_month_order_count'),
]
