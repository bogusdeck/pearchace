import asyncio
import shopify
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from shopify_app.decorators import shop_login_required
from django.views import View
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required

from shopify_app.api import fetch_collections, fetch_products_by_collection

@shop_login_required
def index(request):
    return HttpResponse("<h1>Application and user is authenticated Running</h1> <h2>Dashboard</h2>")

@csrf_protect  
@shop_login_required
@require_GET  # only get requests are allowed (for now)
def get_collections(request):
    #api returns all collection 
    shop_url = request.session.get('shopify', {}).get('shop_url')  

    if not shop_url:
        return JsonResponse({'error': 'Shop URL not found in session'}, status=400)

    try:
        collections = asyncio.run(fetch_collections(shop_url))
        return JsonResponse({'collections': collections}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_protect
@shop_login_required
@require_GET
def get_products(request):
    # api returns all products of a collection 
    shop_url = request.session.get('shopify', {}).get('shop_url')  # Get the shop URL from the session
    collection_id = request.GET.get('collection_id')  # Get the collection ID from the request parameters

    if not shop_url:
        return JsonResponse({'error': 'Shop URL not found in session'}, status=400)
    
    if not collection_id:
        return JsonResponse({'error': 'Collection ID is required'}, status=400)

    try:
        # Fetch products asynchronously
        products = asyncio.run(fetch_products_by_collection(shop_url, collection_id))
        return JsonResponse({'products': products}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)