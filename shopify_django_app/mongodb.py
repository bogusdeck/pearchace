import pymongo
from pymongo.errors import PyMongoError
from pymongo import MongoClient
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view

@api_view(['GET'])
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
def status_list(request):
    try:
        db = get_mongo_client()
        status_collection = db.status_fd  
        status_data = list(status_collection.find({}, {'_id': 0}))  
        return JsonResponse(status_data, safe=False)
    except PyMongoError as e:
        return JsonResponse({'error': str(e)}, status=500)
