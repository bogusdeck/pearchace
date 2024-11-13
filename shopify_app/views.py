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
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import AllowAny
from .models import Client, ClientCollections, ClientProducts
import os
import requests
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from dotenv import load_dotenv

load_dotenv()

import logging

logger = logging.getLogger(__name__)

def _new_session(shop_url):
    api_version = apps.get_app_config('shopify_app').SHOPIFY_API_VERSION
    logger.debug(f"Creating new session for shop_url: {shop_url} with API version: {api_version}")
    return shopify.Session(shop_url, api_version)

def login(request):
    shop_url = request.GET.get('shop')
    logger.info(f"Login initiated for shop_url: {shop_url}")
    
    if not shop_url:
        logger.warning("Shop URL parameter is missing in login request.")
        return JsonResponse({'error': 'Shop URL parameter is required'}, status=400)

    scope = apps.get_app_config('shopify_app').SHOPIFY_API_SCOPE
    ngrok_url = os.environ.get('BACKEND_URL')
    redirect_uri = f"{ngrok_url}{reverse('finalize')}".replace('p//', 'p/')
    
    state = binascii.b2a_hex(os.urandom(15)).decode("utf-8")
    request.session['shopify_oauth_state_param'] = state
    permission_url = _new_session(shop_url).create_permission_url(scope, redirect_uri, state)

    logger.debug(f"Generated permission URL: {permission_url}")
    return redirect(permission_url)

    
def register_app_uninstall_webhook(shop_url, access_token):
    base_url = os.getenv("BACKEND_URL")
    if not base_url:
        logger.error("BASE_URL is not set in environment variables.")
        return
    
    url = f"https://{shop_url}/admin/api/2023-07/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }
    
    callback_url = f"{base_url}/webhook/app_uninstall/"
    
    query = f"""
    mutation {{
        webhookSubscriptionCreate(
            topic: APP_UNINSTALLED
            webhookSubscription: {{
                callbackUrl: "{callback_url}"
                format: JSON
            }}
        ) {{
            userErrors {{
                field
                message
            }}
            webhookSubscription {{
                id
            }}
        }}
    }}
    """
    
    response = requests.post(url, json={"query": query}, headers=headers)
    data = response.json()
    logger.debug(data)
    
    if data.get("data") and not data["data"]["webhookSubscriptionCreate"]["userErrors"]:
        logger.info("Successfully registered app/uninstall webhook.")
    else:
        logger.error("Failed to register app/uninstall webhook: %s", data)

def finalize(request):
    logger.info("Finalizing OAuth callback from Shopify")
    api_secret = apps.get_app_config('shopify_app').SHOPIFY_API_SECRET
    params = request.GET.dict()
    state = params.get('state')

    if request.session.get('shopify_oauth_state_param') != state:
        logger.error("State parameter mismatch during Shopify OAuth callback.")
        return JsonResponse({'error': 'Invalid state parameter'}, status=400)

    myhmac = params.pop('hmac')
    line = '&'.join([f'{key}={value}' for key, value in sorted(params.items())])
    h = hmac.new(api_secret.encode('utf-8'), line.encode('utf-8'), hashlib.sha256)
    
    if not hmac.compare_digest(h.hexdigest(), myhmac):
        logger.error("HMAC verification failed.")
        return JsonResponse({'error': 'Could not verify secure login'}, status=400)

    try:
        shop_url = params.get('shop')
        if not shop_url:
            logger.error("Missing shop URL in OAuth callback.")
            return JsonResponse({'error': 'Missing shop URL'}, status=400)
        
        session = _new_session(shop_url)
        access_token = session.request_token(request.GET)

        if not access_token:
            logger.error("Failed to obtain access token from Shopify.")
            return JsonResponse({'error': 'Failed to obtain access token'}, status=500)

        logger.info(f"Successfully obtained access token for shop_url: {shop_url}")
        request.session['shopify'] = {
            "shop_url": shop_url,
            "access_token": access_token
        }
        logger.debug(f"finalization for shop url {shop_url}, registering of shop_url")
        register_app_uninstall_webhook(shop_url, access_token)

        return redirect('root_path')

    except Exception as e:
        logger.exception("An error occurred during Shopify login finalization.")
        return JsonResponse({'error': f'Could not log in: {str(e)}'}, status=500)


@shop_login_required
@api_view(['GET'])
def logout(request):
    if 'shopify' in request.session:
        shop_url = request.session['shopify']['shop_url']
        logger.info(f"Logout initiated for shop_url: {shop_url}")

        try:
            client = Client.objects.get(shop_url=shop_url)
            client.access_token = None
            client.is_active = False
            client.save()

            request.session.pop('shopify', None)
            logger.info("Successfully logged out and session cleared.")
            return Response({'success': 'Successfully logged out'}, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            logger.warning(f"Client with shop_url {shop_url} does not exist.")
            return Response({'error': 'Client does not exist'}, status=status.HTTP_404_NOT_FOUND)
    else:
        logger.warning("Logout attempted without an active session.")
        return Response({'error': 'Not logged in'}, status=status.HTTP_400_BAD_REQUEST)



# ███╗   ███╗ █████╗ ███╗   ██╗██████╗  █████╗ ████████╗ ██████╗ ██████╗ ██╗   ██╗
# ████╗ ████║██╔══██╗████╗  ██║██╔══██╗██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗╚██╗ ██╔╝
# ██╔████╔██║███████║██╔██╗ ██║██║  ██║███████║   ██║   ██║   ██║██████╔╝ ╚████╔╝ 
# ██║╚██╔╝██║██╔══██║██║╚██╗██║██║  ██║██╔══██║   ██║   ██║   ██║██╔══██╗  ╚██╔╝  
# ██║ ╚═╝ ██║██║  ██║██║ ╚████║██████╔╝██║  ██║   ██║   ╚██████╔╝██║  ██║   ██║   
# ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝   ╚═╝   
                                                                                
# ██╗    ██╗███████╗██████╗ ██╗  ██╗ ██████╗  ██████╗ ██╗  ██╗███████╗            
# ██║    ██║██╔════╝██╔══██╗██║  ██║██╔═══██╗██╔═══██╗██║ ██╔╝██╔════╝            
# ██║ █╗ ██║█████╗  ██████╔╝███████║██║   ██║██║   ██║█████╔╝ ███████╗            
# ██║███╗██║██╔══╝  ██╔══██╗██╔══██║██║   ██║██║   ██║██╔═██╗ ╚════██║            
# ╚███╔███╔╝███████╗██████╔╝██║  ██║╚██████╔╝╚██████╔╝██║  ██╗███████║            
#  ╚══╝╚══╝ ╚══════╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝            
                                                                                
@api_view(['GET'])
@permission_classes([AllowAny])
def check_scopes(request):
    try:
        auth_header = request.headers.get("Authorization", None)
        if auth_header is None:
            logger.warning("Authorization header missing in check_scopes request.")
            return Response(
                {"error": "Authorization header missing"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_url = user.shop_url
        if not shop_url:
            logger.error("Shop URL not provided for the authenticated user.")
            return JsonResponse({"error": "Shop URL not provided"}, status=400)
        
        logger.debug(f"Authenticated user with shop_url: {shop_url}")
    
        try:
            client = Client.objects.get(shop_url=shop_url)
            logger.debug(f"Client found for shop_url: {shop_url}")
            access_token = client.access_token  
            scopes_url = f"https://{shop_url}/admin/oauth/access_scopes.json"
            headers = {
                "X-Shopify-Access-Token": access_token
            }

            logger.debug("Sending request to Shopify to check access scopes.")
            response = requests.get(scopes_url, headers=headers)
            response_data = response.json()
            logger.debug(f"Received response from Shopify: {response_data}")

            if response.status_code == 200:
                return JsonResponse({"scopes": response_data.get("access_scopes", [])}, status=200)
            else:
                logger.error(f"Error response from Shopify: {response_data}")
                return JsonResponse({"error": response_data}, status=response.status_code)

        except Client.DoesNotExist:
            logger.warning(f"Client with shop_url {shop_url} not found.")
            return JsonResponse({"error": "Client not found"}, status=404)
        
    except InvalidToken:
        logger.error("Invalid token provided.")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("An error occurred in check_scopes.")
        return JsonResponse({"error": str(e)}, status=500)


# mandatory webhooks
@api_view(['POST'])
@permission_classes([AllowAny])
def customer_data_request(request):
    email = request.data.get('email')
    
    if not email:
        logger.warning("Email is required but missing in customer_data_request.")
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = Client.objects.get(email=email)
        logger.debug(f"Client found with email: {email}")
        client_data = {
            'shop_name': client.shop_name,
            'email': client.email,
            'phone_number': client.phone_number,
            'shop_url': client.shop_url,
            'country': client.country,
            'currency': client.currency,
            'billingAddress': client.billingAddress,
            'created_at': client.created_at,
            'updated_at': client.updated_at,
        }

        logger.info("Customer data request successful.")
        return Response(client_data, status=status.HTTP_200_OK)
    except Client.DoesNotExist:
        logger.warning(f"Client with email {email} not found.")
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([AllowAny])
def customer_data_erasure(request):
    email = request.data.get('email')

    if not email:
        logger.warning("Email is required but missing in customer_data_erasure.")
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = Client.objects.get(email=email)
        # Uncomment the following lines to delete associated data if needed
        # ClientProducts.objects.filter(shop_id=client.shop_id).delete()
        # ClientCollections.objects.filter(shop_id=client.shop_id).delete()  
        # client.delete()  
        
        if client:
            logger.info(f"Customer data erased for email: {email}")
            return Response({'message': 'Customer data erased successfully'}, status=status.HTTP_200_OK)
        else: 
            logger.warning(f"No data found to erase for email: {email}")
            return Response({'message': 'Customer data Not found'}, status= status.HTTP_400_BAD_REQUEST)

    except Client.DoesNotExist:
        logger.warning(f"Client with email {email} not found in customer_data_erasure.")
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([AllowAny])
def shop_data_erasure(request):
    shop_id = request.data.get('shop_id')

    if not shop_id:
        logger.warning("Shop ID is required but missing in shop_data_erasure.")
        return Response({'error': 'Shop ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Uncomment the following lines to delete associated data if needed
        # ClientProducts.objects.filter(shop_id=client.shop_id).delete()
        # ClientCollections.objects.filter(shop_id=shop_id).delete()
        # client.delete()  
        if ClientCollections.objects.filter(shop_id=shop_id):
            logger.info(f"Shop data erased for shop_id: {shop_id}")
            return Response({'message': 'Shop data erased successfully'}, status=status.HTTP_200_OK)
        else: 
            logger.warning(f"No data found to erase for shop_id: {shop_id}")
            return Response({'message': 'Shop data Not found'}, status= status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("An error occurred in shop_data_erasure.")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)    


