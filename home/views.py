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
from datetime import datetime  
import pytz  

from shopify_app.models import Client
from shopify_app.api import fetch_collections, fetch_products_by_collection, update_collection_products_order, fetch_client_data
from asgiref.sync import sync_to_async
import asyncio
from .strategies import (
    promote_new, 
    promote_high_revenue_products, 
    promote_high_inventory_products, 
    bestsellers_high_variant_availability, 
    promote_high_variant_availability, 
    clearance_sale, 
    promote_high_revenue_new_products
)

# Map algo_id to sorting functions
ALGO_ID_TO_FUNCTION = {
    '001': promote_new,
    '002': promote_high_revenue_products,
    '003': promote_high_inventory_products,
    '004': bestsellers_high_variant_availability,
    '005': promote_high_variant_availability,
    '006': clearance_sale,
    '007': promote_high_revenue_new_products
}

@shop_login_required
def index(request):
    try:
        shop_url = request.session.get('shopify', {}).get('shop_url')
        access_token = request.session.get('shopify', {}).get('access_token')

        if not shop_url or not access_token:
            return JsonResponse({'error': 'Shopify authentication required'}, status=403)

        shop_data = asyncio.run(fetch_client_data(shop_url, access_token))

        if not shop_data:
            return JsonResponse({'error': 'Failed to fetch client data from Shopify'}, status=500)

        email = shop_data.get('email', '')
        name = shop_data.get('name', '')
        contact_email = shop_data.get('contactEmail', '')
        currency = shop_data.get('currencyCode', '')
        timezone = shop_data.get('timezoneAbbreviation', '')
        billing_address = shop_data.get('billingAddress', {})
        created_at_str = shop_data.get('createdAt', '')

        created_at = None
        if created_at_str:
            try:
                created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%SZ')
                created_at = created_at.replace(tzinfo=pytz.UTC)  
            except ValueError:
                created_at = None

        client, created = Client.objects.get_or_create(
            shop_name=shop_url,
            defaults={
                'email': email, 
                'phone_number': billing_address.get('phone', None),
                'shop_url': shop_url,
                'country': billing_address.get('countryCodeV2', ''),
                'contact_email': contact_email,
                'currency': currency,
                'billingAddress': billing_address,
                'access_token': access_token,
                'is_active': True,
                'uninstall_date': None,
                'trial_used': False,
                'timezone': timezone,
                'createdateshopify': created_at
            }
        )

        if not created:
            client.email = email or client.email
            client.phone_number = billing_address.get('phone', client.phone_number)
            client.country = billing_address.get('countryCodeV2', client.country)
            client.contact_email = contact_email or client.contact_email
            client.currency = currency or client.currency
            client.billingAddress = billing_address or client.billingAddress
            client.access_token = access_token
            client.is_active = True
            client.uninstall_date = None
            client.shop_name = name or client.shop_name
            client.timezone = timezone or client.timezone
            client.createdateshopify = created_at or client.createdateshopify

            client.save()

        return JsonResponse({
            'success': 'Client info fetched and stored successfully',
            'client_data': shop_data
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_protect  
@shop_login_required
@require_GET  
def get_collections(request):
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
    shop_url = request.session.get('shopify', {}).get('shop_url')  
    collection_id = request.GET.get('collection_id')  

    if not shop_url:
        return JsonResponse({'error': 'Shop URL not found in session'}, status=400)
    
    if not collection_id:
        return JsonResponse({'error': 'Collection ID is required'}, status=400)

    try:
        products = asyncio.run(fetch_products_by_collection(shop_url, collection_id))
        return JsonResponse({'products': products}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_protect
@shop_login_required
@require_POST
def update_product_order(request):
    """
    API endpoint to update the order of products in a collection based on a sorting algorithm.

    Returns:
        JsonResponse: A JSON response indicating success or failure.
    """
    shop_url = request.session.get('shopify', {}).get('shop_url')  
    collection_id = request.POST.get('collection_id')  
    algo_id = request.POST.get('algo_id')  # Get algo_id from the request

    if not shop_url:
        return JsonResponse({'error': 'Shop URL not found in session'}, status=400)
    
    if not collection_id:
        return JsonResponse({'error': 'Collection ID is required'}, status=400)
    
    if not algo_id:
        return JsonResponse({'error': 'Algorithm ID is required'}, status=400)
    
    # Ensure the algo_id is valid and maps to a function
    sort_function = ALGO_ID_TO_FUNCTION.get(algo_id)
    if not sort_function:
        return JsonResponse({'error': 'Invalid algorithm ID provided'}, status=400)

    try:
        # Fetch the products of the collection (This function should fetch the collection's products)
        products = asyncio.run(fetch_collection_products(shop_url, collection_id))
        if not products:
            return JsonResponse({'error': 'Failed to fetch products for the collection'}, status=500)

        # Apply the sorting algorithm
        sorted_products = sort_function(products)

        # Extract product IDs in sorted order
        sorted_product_ids = [p['id'] for p in sorted_products]

        # Update the product order in Shopify
        success = asyncio.run(update_collection_products_order(shop_url, collection_id, sorted_product_ids))
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

@require_GET
@shop_login_required
def get_shopify_client_data(request):
    shop_url = request.session.get('shopify', {}).get('shop_url')

    if not shop_url:
        return JsonResponse({'error': 'Shop URL not found in session'}, status=400)

    try:
        shop_data = asyncio.run(fetch_client_data(shop_url))
        if shop_data:
            return JsonResponse({'shop_data': shop_data}, status=200)
        else:
            return JsonResponse({'error': 'Failed to fetch shop data'}, status=500)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
