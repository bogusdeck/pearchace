from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.urls import reverse
from django.template import RequestContext
from django.apps import apps
import hmac, base64, hashlib, binascii, os
import shopify
from .decorators import shop_login_required
from datetime import datetime  
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Client

def _new_session(shop_url):
    api_version = apps.get_app_config('shopify_app').SHOPIFY_API_VERSION
    return shopify.Session(shop_url, api_version)

def login(request):
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

        request.session['shopify'] = {
            "shop_url": shop_url,
            "access_token": access_token
        }

        return redirect('root_path')  

    except Exception as e:
        return JsonResponse({'error': f'Could not log in: {str(e)}'}, status=500)


@shop_login_required
@api_view(['GET'])
def logout(request):
    if 'shopify' in request.session:
        shop_url = request.session['shopify']['shop_url']

        try:
            client = Client.objects.get(shop_url=shop_url)
            client.access_token = None
            client.is_active = False
            client.save()

            request.session.pop('shopify', None)

            return Response({'success': 'Successfully logged out'}, status=status.HTTP_200_OK)
        except Client.DoesNotExist:
            return Response({'error': 'Client does not exist'}, status=status.HTTP_404_NOT_FOUND)
    else:
        return Response({'error': 'Not logged in'}, status=status.HTTP_400_BAD_REQUEST)
