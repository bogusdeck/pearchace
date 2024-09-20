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
from rest_framework.permissions import AllowAny
from .models import Client, ClientCollections
import os
from dotenv import load_dotenv

load_dotenv()

def _new_session(shop_url):
    api_version = apps.get_app_config('shopify_app').SHOPIFY_API_VERSION
    return shopify.Session(shop_url, api_version)

def login(request):
    shop_url = request.GET.get('shop')
    print(shop_url)
    if not shop_url:
        return JsonResponse({'error': 'Shop URL parameter is required'}, status=400)

    scope = apps.get_app_config('shopify_app').SHOPIFY_API_SCOPE
    print(scope)
    ngrok_url = os.environ.get('BACKEND_URL')
    redirect_uri = f"{ngrok_url}{reverse('finalize')}".replace('p//', 'p/')   
    # redirect_uri = request.build_absolute_uri(reverse('finalize'))
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
        if not shop_url:
            return JsonResponse({'error': 'Missing shop URL'}, status=400)
        
        session = _new_session(shop_url)
        access_token = session.request_token(request.GET)

        if not access_token:
            return JsonResponse({'error': 'Failed to obtain access token'}, status=500)

        print('data:', shop_url, access_token)

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







# mandatory webhooks
@api_view(['POST'])
@permission_classes([AllowAny])
def customer_data_request(request):
    email = request.data.get('email')
    
    if not email:
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = Client.objects.get(email=email)
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

        return Response(client_data, status=status.HTTP_200_OK)
    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([AllowAny])
def customer_data_erasure(request):
    email = request.data.get('email')

    if not email:
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = Client.objects.get(email=email)
        # ClientCollections.objects.filter(shop_id=client.shop_id).delete()  
        # client.delete()  
        if client:
            return Response({'message': 'Customer data erased successfully'}, status=status.HTTP_200_OK)
        else: 
            return Response({'message': 'Customer data Not found'}, status= status.HTTP_400_BAD_REQUEST)

    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([AllowAny])
def shop_data_erasure(request):
    shop_id = request.data.get('shop_id')

    if not shop_id:
        return Response({'error': 'Shop ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # ClientCollections.objects.filter(shop_id=shop_id).delete()
        if ClientCollections.objects.filter(shop_id=shop_id):
            return Response({'message': 'Shop data erased successfully'}, status=status.HTTP_200_OK)
        else: 
            return Response({'message': 'Shop data Not found'}, status= status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

from shopify_django_app.mongodb import get_mongo_client
from pymongo.errors import PyMongoError

@api_view(['GET'])
def faq_list(request):
    try:
        db = get_mongo_client()
        faqs_collection = db.faqs 
        faqs = list(faqs_collection.find({}, {'_id': 0})) 
        return JsonResponse(faqs, safe=False)
    except PyMongoError as e:
        return JsonResponse({'error': str(e)}, status=500)


   

import pymongo
from django.http import JsonResponse

def test_mongodb_connection(request):
    try:
        # Replace with your MongoDB connection details
        client = pymongo.MongoClient("mongodb://pearch:pearchpwd@3.108.104.68:27017/?authSource=admin")
        
        # Select the database
        db = client['shopify_app']

        # Perform a test query
        collection = db['your_collection_name']  # Replace with an actual collection name
        document = collection.find_one()

        # Return the document as a response
        return JsonResponse({
            'status': 'success',
            'data': document
        })

    except pymongo.errors.PyMongoError as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)
