from django.urls import path, include

urlpatterns = [
    path('auth/', include('shopify_app.urls')), # urls for auth and graphql
    path('', include('home.urls')), # main urls
]
