from django.shortcuts import render
import shopify
from django.http import JsonResponse, HttpResponse
from shopify_app.decorators import shop_login_required

@shop_login_required
def index(request):
    return HttpResponse("<h1>Application and user is authenticated Running</h1> <h2>Dashboard</h2>")
