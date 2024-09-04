from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login, name='login'),
    path('finalize/', views.finalize, name='finalize'),
    path('logout/', views.logout, name='logout'),
]
