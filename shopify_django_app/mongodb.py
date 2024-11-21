import pymongo
from pymongo.errors import PyMongoError
from pymongo import MongoClient
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status
from shopify_app.models import History, Client
from home.apps import convert_utc_to_local

import logging
logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def faq_list(request):
    try:
        db = get_mongo_client()
        faqs_collection = db.faqs 
        faqs = list(faqs_collection.find({}, {'_id': 0})) 
        return JsonResponse(faqs, safe=False)
    except PyMongoError as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_mongo_client():
    client = MongoClient(settings.MONGODB_SETTINGS['host'])
    return client[settings.MONGODB_SETTINGS['db']]
   
@api_view(['GET'])
def test_mongodb_connection(request):
    try:
        client = pymongo.MongoClient("mongodb://pearch:pearchpwd@3.108.104.68:27017/?authSource=admin")
        
        db = client['shopify_app']
        collections = db.list_collection_names()
        return JsonResponse({
            'status': 'success',
            'data': collections
        })

    except pymongo.errors.PyMongoError as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def status_list(request):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        return Response(
            {"error": "Authorization header missing"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()

        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        if not shop_id:
            return Response(
                {"error": "Shop ID not found in session"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        db = get_mongo_client()
        status_collection = db.status_fd  

        paginator = PageNumberPagination()
        paginator.page_size = request.query_params.get('page_size', 10)  
        page = request.query_params.get('page', 1)  

        status_data = list(status_collection.find({}, {'_id': 0}))

        paginated_data = paginator.paginate_queryset(status_data, request)

        return paginator.get_paginated_response(paginated_data)

    except PyMongoError as e:   
        return JsonResponse({'error': str(e)}, status=500)
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def history_status(request):
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        logger.error("Authorization header missing")
        return Response(
            {"error": "Authorization header missing"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        try:
            token = auth_header.split(" ")[1]
        except IndexError:
            logger.error("Invalid Authorization header format")
            return Response(
                {"error": "Invalid Authorization header format"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        if not shop_id:
            logger.warning("Shop ID not found in JWT token for user %s", user)
            return Response(
                {"error": "Shop ID not found in session"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        client = Client.objects.get(shop_id=shop_id)

        history_queryset = History.objects.filter(shop_id=shop_id).order_by('-requested_at')
        logger.info("History data retrieved for shop_id %s", shop_id)
        

        paginator = PageNumberPagination()
        paginator.page_size = request.query_params.get('page_size', 10)
        paginated_queryset = paginator.paginate_queryset(history_queryset, request)
        logger.info("Paginated history data for shop_id %s with page_size %s", shop_id, paginator.page_size)
        timezone_offset = client.timezone_offset
        
        history_data = [
            {
                "requested_at": convert_utc_to_local(history.requested_at, timezone_offset).strftime('%Y-%m-%d %H:%M:%S') if history.requested_at else "-",
                "started_at": convert_utc_to_local(history.started_at, timezone_offset).strftime('%Y-%m-%d %H:%M:%S') if history.started_at else "-",
                "ended_at": convert_utc_to_local(history.ended_at, timezone_offset).strftime('%Y-%m-%d %H:%M:%S') if history.ended_at else "-",
                "requested_by": history.requested_by,
                "product_count": history.product_count,
                "status": history.status,
                "collection_name": history.collection_name,
            }
            for history in paginated_queryset
        ]
        
        
        logger.info("History data serialization completed for shop_id %s", shop_id)
        return paginator.get_paginated_response(history_data)

    except Exception as e:
        logger.exception("Unexpected error in status API")
        return Response(
            {'error': 'An unexpected error occurred. Please try again later.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
