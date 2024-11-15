from django.urls import path
from . import views
from .views import customer_data_request, customer_data_erasure, shop_data_erasure
from shopify_django_app.mongodb import faq_list, test_mongodb_connection,status_list, history_status


urlpatterns = [
    path('login/', views.login, name='login'),
    path('finalize/', views.finalize, name='finalize'),
    path('logout/', views.logout, name='logout'),
    path('check-scopes/', views.check_scopes, name='check_scopes'),

     # mandatory webhooks
    path('webhooks/customer-data-request/', customer_data_request, name='customer-data-request'),
    path('webhooks/customer-data-erasure/', customer_data_erasure, name='customer-data-erasure'),
    path('webhooks/shop-data-erasure/', shop_data_erasure, name='shop-data-erasure'),

    # FAQs
    path('faqs/', faq_list, name='faq_list'),
    path('test-mongodb/', test_mongodb_connection,name='test_mongo'),
    # path('status/', status_list, name='fake_status_list'),
    path('history-status/',history_status, name="history_status")
]
