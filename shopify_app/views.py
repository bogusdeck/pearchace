from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.urls import reverse
from django.template import RequestContext
from django.apps import apps
import hmac, base64, hashlib, binascii, os
import shopify
from .models import Client
from .decorators import shop_login_required
from .api import fetch_client_data
import asyncio
from datetime import datetime
import pytz

def _new_session(shop_url):
    api_version = apps.get_app_config('shopify_app').SHOPIFY_API_VERSION
    return shopify.Session(shop_url, api_version)

def login(request):
    """
    Initiates the Shopify OAuth process by redirecting to Shopify for authentication.
    """
    shop_url = request.GET.get('shop')
    if not shop_url:
        return JsonResponse({'error': 'Shop URL parameter is required'}, status=400)

    scope = apps.get_app_config('shopify_app').SHOPIFY_API_SCOPE
    redirect_uri = request.build_absolute_uri(reverse('finalize'))
    state = binascii.b2a_hex(os.urandom(15)).decode("utf-8")
    request.session['shopify_oauth_state_param'] = state
    permission_url = _new_session(shop_url).create_permission_url(scope, redirect_uri, state)
    return redirect(permission_url)


def finalize(request):
    """
    Handles the OAuth callback from Shopify, finalizes authentication, and stores the access token.
    """
    api_secret = apps.get_app_config('shopify_app').SHOPIFY_API_SECRET
    params = request.GET.dict()

    # Validate the state parameter
    if request.session.get('shopify_oauth_state_param') != params.get('state'):
        return JsonResponse({'error': 'Invalid state parameter'}, status=400)

    myhmac = params.pop('hmac')
    line = '&'.join([f'{key}={value}' for key, value in sorted(params.items())])
    h = hmac.new(api_secret.encode('utf-8'), line.encode('utf-8'), hashlib.sha256)
    
    # Verify the HMAC signature
    if not hmac.compare_digest(h.hexdigest(), myhmac):
        return JsonResponse({'error': 'Could not verify secure login'}, status=400)

    try:
        shop_url = params.get('shop')
        session = _new_session(shop_url)
        access_token = session.request_token(request.GET)

        # Fetch client data asynchronously
        shop_data = asyncio.run(fetch_client_data(shop_url))

        # Print shop data for debugging
        print(shop_data)

        email = shop_data.get('email', '')
        name = shop_data.get('name', '')
        contact_email = shop_data.get('contact_email', '')
        currency = shop_data.get('currency_code', '')
        timezone = shop_data.get('timezone_abbreviation', '')
        billing_address = {
            'address1': shop_data.get('billing_address1', ''),
            'address2': shop_data.get('billing_address2', ''),
            'city': shop_data.get('billing_city', ''),
            'province': shop_data.get('billing_province', ''),
            'countryCodeV2': shop_data.get('billing_country', ''),
            'phone': shop_data.get('billing_phone', ''),
            'zip': shop_data.get('billing_zip', '')
        }
        created_at_str = shop_data.get('created_at', '')

        # Parsing created_at
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

        # Store session info
        request.session['shopify'] = {
            "shop_url": shop_url,
            "access_token": access_token
        }

        return JsonResponse({'success': 'Logged in successfully'}, status=200)

    except Exception as e:
        return JsonResponse({'error': f'Could not log in: {str(e)}'}, status=500)

    
@shop_login_required
def logout(request):
    """
    Logs out the user by clearing the session and deactivating the access token.
    """
    if 'shopify' in request.session:
        shop_url = request.session['shopify']['shop_url']

        try:
            client = Client.objects.get(shop_name=shop_url)
            client.access_token = None
            client.is_active = False
            client.save()

            request.session.pop('shopify', None)
            return JsonResponse({'success': 'Successfully logged out'}, status=200)
        except Client.DoesNotExist:
            return JsonResponse({'error': 'Client does not exist'}, status=404)
    else:
        return JsonResponse({'error': 'Not logged in'}, status=400)
    

async def client_update(shop_url):
    """
    Fetches client data from Shopify and updates or creates the Client entry in the database asynchronously.

    Args:
        shop_url (str): The URL of the Shopify store.

    Returns:
        dict: A dictionary containing the client data or an error message.
    """
    try:
        # Fetch client data asynchronously
        shop_data = await fetch_client_data(shop_url)

        # Access the nested 'shop' object
        shop = shop_data.get('data', {}).get('shop', {})

        # Access the fields from 'shop'
        email = shop.get('email', '')
        name = shop.get('name', '')
        contact_email = shop.get('contactEmail', '')
        currency = shop.get('currencyCode', '')
        timezone = shop.get('timezoneAbbreviation', '')
        billing_address = shop.get('billingAddress', {})
        created_at_str = shop.get('createdAt', '')

        # Parsing created_at
        created_at = None
        if created_at_str:
            try:
                created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%SZ')
                created_at = created_at.replace(tzinfo=pytz.UTC)  # Ensure UTC timezone
            except ValueError:
                created_at = None

        # Get or create the client entry in the database
        client, created = await asyncio.to_thread(
            Client.objects.get_or_create,
            shop_name=shop_url,
            defaults={
                'email': email, 
                'phone_number': billing_address.get('phone', None),
                'shop_url': shop_url,
                'country': billing_address.get('countryCodeV2', ''),
                'contact_email': contact_email,  # Correctly populated from shop['contactEmail']
                'currency': currency,
                'billingAddress': billing_address,
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
            client.is_active = True
            client.uninstall_date = None
            client.shop_name = name or client.shop_name
            client.timezone = timezone or client.timezone
            client.createdateshopify = created_at or client.createdateshopify

            await asyncio.to_thread(client.save)

        return {'success': 'Client data updated successfully'}

    except Exception as e:
        return {'error': f'Failed to update client: {str(e)}'}
