import asyncio
import shopify
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from shopify_app.decorators import shop_login_required
from django.views import View
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.utils.decorators import method_decorator
from django.views import View
from asgiref.sync import sync_to_async

from shopify_app.models import Client
from shopify_app.api import fetch_collections, fetch_products_by_collection, update_collection_products_order

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
    shop_url = request.session.get('shopify', {}).get('shop_url')  
    collection_id = request.GET.get('collection_id')  

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


@csrf_protect
@shop_login_required
@require_POST
def update_product_order(request):
    """
    API endpoint to update the order of products in a collection.

    Returns:
        JsonResponse: A JSON response indicating success or failure.
    """
    shop_url = request.session.get('shopify', {}).get('shop_url')  
    collection_id = request.POST.get('collection_id')  
    
    #need to update this later --> sorted algo give this product order
    products_order = request.POST.getlist('products_order[]')  

    if not shop_url:
        return JsonResponse({'error': 'Shop URL not found in session'}, status=400)
    
    if not collection_id:
        return JsonResponse({'error': 'Collection ID is required'}, status=400)

    if not products_order:
        return JsonResponse({'error': 'Products order is required'}, status=400)

    try:
        success = asyncio.run(update_collection_products_order(shop_url, collection_id, products_order))
        if success:
            return JsonResponse({'success': True}, status=200)
        else:
            return JsonResponse({'error': 'Failed to update product order'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    

@shop_login_required
@require_GET
def get_client_info(request):
    """
    API endpoint to get the client information for the current session.

    Returns:
        JsonResponse: A JSON response with client information.
    """
    shop_url = request.session.get('shopify', {}).get('shop_url')

    if not shop_url:
        return JsonResponse({'error': 'Shop URL not found in session'}, status=400)

    try:
        # Fetch the client based on the shop_url synchronously
        client = Client.objects.get(shop_url=shop_url)
        
        client_data = {
            'client_id': client.client_id,
            'shop_name': client.shop_name,
            'email': client.email,
            'phone_number': client.phone_number,
            'shop_url': client.shop_url,
            'country': client.country,
            'is_active': client.is_active,
            'access_token': client.access_token,
            'trial_used': client.trial_used,
            'installation_date': client.installation_date,
            'uninstall_date': client.uninstall_date,
            'created_at': client.created_at,
            'updated_at': client.updated_at,
            'default_algo': client.default_algo.name if client.default_algo else None,
            'schedule_frequency': client.schedule_frequency,
            'stock_location': client.stock_location,
            'member': client.member,
        }

        return JsonResponse({'client': client_data}, status=200)
    
    except Client.DoesNotExist:
        return JsonResponse({'error': 'Client not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
