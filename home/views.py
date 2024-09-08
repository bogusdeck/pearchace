from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from shopify_app.decorators import shop_login_required
from django.http import JsonResponse
from datetime import datetime
import pytz
from django.views.decorators.csrf import csrf_protect
from shopify_app.models import Client
from shopify_app.api import fetch_collections, fetch_products_by_collection, update_collection_products_order, fetch_client_data
from .strategies import (
    promote_new, 
    promote_high_revenue_products, 
    promote_high_inventory_products, 
    bestsellers_high_variant_availability, 
    promote_high_variant_availability, 
    clearance_sale, 
    promote_high_revenue_new_products,
    sort_alphabetically
)

# Mapping algorithm IDs to their corresponding functions
ALGO_ID_TO_FUNCTION = {
    '001': promote_new,
    '002': promote_high_revenue_products,
    '003': promote_high_inventory_products,
    '004': bestsellers_high_variant_availability,
    '005': promote_high_variant_availability,
    '006': clearance_sale,
    '007': promote_high_revenue_new_products,
    '008': sort_alphabetically
}

@shop_login_required
def index(request):
    try:
        shop_url = request.session.get('shopify', {}).get('shop_url')
        access_token = request.session.get('shopify', {}).get('access_token')

        if not shop_url or not access_token:
            return JsonResponse({'error': 'Shopify authentication required'}, status=403)

        shop_data = fetch_client_data(shop_url, access_token)

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

        # Use update_or_create to ensure no duplicate clients are created
        client, created = Client.objects.update_or_create(
            shop_name=shop_url,
            defaults={
                'email': email, 
                'phone_number': billing_address.get('phone', None),
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

        return JsonResponse({
            'success': 'Client info fetched and stored successfully',
            'client_data': shop_data
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
        
@shop_login_required
@api_view(['GET'])
@csrf_protect
def get_collections(request):
    shop_url = request.session.get('shopify', {}).get('shop_url')
    
    if not shop_url:
        return Response({'error': 'Shop URL not found in session'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        collections = fetch_collections(shop_url)
        return Response({'collections': collections}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@shop_login_required
@api_view(['GET'])
@csrf_protect
def get_products(request):
    shop_url = request.session.get('shopify', {}).get('shop_url')
    collection_id = request.GET.get('collection_id')

    if not shop_url:
        return Response({'error': 'Shop URL not found in session'}, status=status.HTTP_400_BAD_REQUEST)

    if not collection_id:
        return Response({'error': 'Collection ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        products = fetch_products_by_collection(shop_url, collection_id)
        return Response({'products': products}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@shop_login_required
@api_view(['POST'])
@csrf_protect
def update_product_order(request):
    shop_url = request.session.get('shopify', {}).get('shop_url')
    collection_id = request.data.get('collection_id')
    algo_id = request.data.get('algo_id')
    access_token = request.session.get('shopify', {}).get('access_token')
    print(f"Access token: {access_token}")

    if not shop_url:
        return Response({'error': 'Shop URL not found in session'}, status=status.HTTP_400_BAD_REQUEST)

    if not collection_id:
        return Response({'error': 'Collection ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    if not algo_id:
        return Response({'error': 'Algorithm ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    sort_function = ALGO_ID_TO_FUNCTION.get(algo_id)
    if not sort_function:
        return Response({'error': 'Invalid algorithm ID provided'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        products = fetch_products_by_collection(shop_url, collection_id)
        if not products:
            return Response({'error': 'Failed to fetch products for the collection'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        sorted_product_ids = sort_function(products)
        if not sorted_product_ids:
            return Response({'error': 'Failed to sort products'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        print(sorted_product_ids)

        success = update_collection_products_order(shop_url, collection_id, sorted_product_ids, access_token)
        print("\n\n",success)
        if success:
            return Response({'success': True}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Failed to update product order'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@shop_login_required
@api_view(['GET'])
def get_client_info(request):
    shop_url = request.session.get('shopify', {}).get('shop_url')

    if not shop_url:
        return Response({'error': 'Shop URL not found in session'}, status=status.HTTP_400_BAD_REQUEST)

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

        return Response({'client': client_data}, status=status.HTTP_200_OK)

    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@shop_login_required
@api_view(['GET'])
def get_shopify_client_data(request):
    shop_url = request.session.get('shopify', {}).get('shop_url')

    if not shop_url:
        return Response({'error': 'Shop URL not found in session'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        shop_data = fetch_client_data(shop_url)
        if shop_data:
            return Response({'shop_data': shop_data}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Failed to fetch shop data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
