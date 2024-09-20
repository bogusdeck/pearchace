# from pymongo import MongoClient
# from django.conf import settings

# def get_mongo_db():
#     client = MongoClient(
#         host=settings.MONGODB_SETTINGS['host'],
#         username=settings.MONGODB_SETTINGS.get('username'),
#         password=settings.MONGODB_SETTINGS.get('password'),
#         authSource=settings.MONGODB_SETTINGS.get('authSource', 'admin')
#     )
#     return client[settings.MONGODB_SETTINGS['db']]



# mongo_client.py
from pymongo import MongoClient
from django.conf import settings

client = MongoClient(settings.MONGODB_SETTINGS['host'])
db = client[settings.MONGODB_SETTINGS['db']]
faqs_collection = db.faqs  


def get_all_faqs():
    return list(faqs_collection.find())


def update_faq(faq_id, question, answer):
    result = faqs_collection.update_one(
        {'_id': faq_id},
        {'$set': {'question': question, 'answer': answer}}
    )
    return result.modified_count  
