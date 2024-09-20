import pymongo
from pymongo.errors import PyMongoError
from pymongo import MongoClient
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

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
        collection = db['your_collection_name']  
        document = collection.find_one()
        return JsonResponse({
            'status': 'success',
            'data': document
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
        status_data = list(status_collection.find({}, {'_id': 0}))  
        return JsonResponse(status_data, safe=False)
    except PyMongoError as e:   
        return JsonResponse({'error': str(e)}, status=500)
