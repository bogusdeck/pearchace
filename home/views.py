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
from shopify_app.models import Client  # Assuming Client is in the same app
from datetime import datetime  # Import datetime for handling dates
import pytz  #

from shopify_app.models import Client
from shopify_app.api import fetch_collections, fetch_products_by_collection, update_collection_products_order, fetch_client_data
from asgiref.sync import sync_to_async
import asyncio

@shop_login_required
def index(request):
    try:
        shop_url = request.session.get('shopify', {}).get('shop_url')
        access_token = request.session.get('shopify', {}).get('access_token')

        if not shop_url or not access_token:
            return JsonResponse({'error': 'Shopify authentication required'}, status=403)

        # Call the async function using asyncio.run, and sync_to_async ensures it runs in sync context
        shop_data = asyncio.run(fetch_client_data(shop_url, access_token))

        if not shop_data:
            return JsonResponse({'error': 'Failed to fetch client data from Shopify'}, status=500)

        # Now update the client data in the database
        email = shop_data.get('email', '')
        name = shop_data.get('name', '')
        contact_email = shop_data.get('contactEmail', '')
        currency = shop_data.get('currencyCode', '')
        timezone = shop_data.get('timezoneAbbreviation', '')
        billing_address = shop_data.get('billingAddress', {})
        created_at_str = shop_data.get('createdAt', '')

        # Parse created_at
        created_at = None
        if created_at_str:
            try:
                created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%SZ')
                created_at = created_at.replace(tzinfo=pytz.UTC)  # Ensure UTC timezone
            except ValueError:
                created_at = None

        # Get or create the client entry in the database
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

        # Update the client if it already exists
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

@require_GET
@shop_login_required
def get_shopify_client_data(request):
    shop_url = request.session.get('shopify', {}).get('shop_url')

    if not shop_url:
        return JsonResponse({'error': 'Shop URL not found in session'}, status=400)

    try:
        # Fetch the client's shop data
        shop_data = asyncio.run(fetch_client_data(shop_url))
        if shop_data:
            return JsonResponse({'shop_data': shop_data}, status=200)
        else:
            return JsonResponse({'error': 'Failed to fetch shop data'}, status=500)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
