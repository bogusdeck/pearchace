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

    if request.session.get('shopify_oauth_state_param') != params.get('state'):
        return JsonResponse({'error': 'Invalid state parameter'}, status=400)

    myhmac = params.pop('hmac')
    line = '&'.join([f'{key}={value}' for key, value in sorted(params.items())])
    h = hmac.new(api_secret.encode('utf-8'), line.encode('utf-8'), hashlib.sha256)
    if not hmac.compare_digest(h.hexdigest(), myhmac):
        return JsonResponse({'error': 'Could not verify secure login'}, status=400)

    try:
        shop_url = params.get('shop')
        session = _new_session(shop_url)
        access_token = session.request_token(request.GET)

        client, created = Client.objects.get_or_create(
            shop_name=shop_url,
            defaults={
                'email': params.get('email', ''),
                'phone_number': params.get('phone_number', ''),
                'shop_url': shop_url,
                'country': params.get('country', ''),
                'access_token': access_token,
                'is_active': True,
                'uninstall_date': None,
                'trial_used': False,
            }
        )

        if not created: 
            client.email = params.get('email', client.email)
            client.phone_number = params.get('phone_number', client.phone_number)
            client.shop_url = shop_url
            client.country = params.get('country', client.country)
            client.access_token = access_token
            client.is_active = True
            client.uninstall_date = None
            client.trial_used = False
            client.save()

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
    

