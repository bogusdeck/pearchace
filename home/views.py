from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import redirect
from shopify_app.decorators import shop_login_required
from django.http import JsonResponse
from datetime import datetime
import pytz
from django.views.decorators.http import require_GET
import shopify
from django.views.decorators.csrf import csrf_protect
from shopify_app.models import Client, Usage, Subscription, SortingPlan, SortingAlgorithm, ClientCollections
from shopify_app.api import fetch_collections, fetch_products_by_collection, update_collection_products_order, fetch_client_data
from .strategies import (
    promote_new, 
    promote_high_revenue_products, 
    promote_high_inventory_products, 
    bestsellers_high_variant_availability, 
    promote_high_variant_availability, 
    clearance_sale, 
    promote_high_revenue_new_products
)

from django.shortcuts import get_object_or_404
from django.contrib.auth.tokens import default_token_generator

ALGO_ID_TO_FUNCTION = {
    '001': promote_new,
    '002': promote_high_revenue_products,
    '003': promote_high_inventory_products,
    '004': bestsellers_high_variant_availability,
    '005': promote_high_variant_availability,
    '006': clearance_sale,
    '007': promote_high_revenue_new_products,
}

from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

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

        shop_gid = shop_data.get('id', '')
        shop_id = shop_gid.split('/')[-1]
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

        client, created = Client.objects.update_or_create(
            shop_id=shop_id,
            defaults={
                'shop_url': shop_url,
                'shop_name': name,
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
                'createdateshopify': created_at,
            }
        )

        if created:
            client.member = False
        client.save()

        refresh = RefreshToken.for_user(client)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        frontend_url = "https://pearch.vercel.app/"
        redirect_url = f"{frontend_url}?access_token={access_token}&refresh_token={refresh_token}&shop_url={shop_url}"

        return redirect(redirect_url)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_client_info(request): #working and tested
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        token = auth_header.split(' ')[1]
        jwt_auth = JWTAuthentication()

        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        
        shop_id = user.shop_id

        if not shop_id:
            return Response({'error': 'Shop ID not found in session'}, status=status.HTTP_400_BAD_REQUEST)

        try: 
            client = Client.objects.get(shop_id=shop_id)

            collections = fetch_collections(client.shop_url)

            for collection in collections:
                collection_id = int(collection['id'].split('/')[-1])  
                collection_name = collection['title']
                products_count = collection['products_count']  
                default_algo = SortingAlgorithm.objects.get(algo_id=1)

                client_collection, created = ClientCollections.objects.get_or_create(
                    collectionid=collection_id,
                    shop_id=shop_id,
                    defaults={
                        'collection_name': collection_name,
                        'products_count': products_count,
                        'status': False,
                        'algo': default_algo,  
                        'parameters_used': {},
                        'lookback_periods': None
                    }
                )

                if not created:
                    client_collection.collection_name = collection_name
                    client_collection.products_count = products_count
                    client_collection.save()

            return Response({
                'client_id': client.shop_id,
                'shop_url': client.shop_url,
                'shop_name': client.shop_name,
                'collections_fetched': len(collections)
            }, status=status.HTTP_200_OK)
        
        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
        except ClientCollections.DoesNotExist:
            return Response({'error': 'Clients collection not found'}, status=status.HTTP_404_NOT_FOUND)
    except InvalidToken:
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# @api_view(['GET'])
# @csrf_protect
# def get_collections(request):
#     shop_url = request.session.get('shopify', {}).get('shop_url')
    
#     if not shop_url:
#         return Response({'error': 'Shop URL not found in session'}, status=status.HTTP_400_BAD_REQUEST)

#     try:
#         collections = fetch_collections(shop_url)
#         return Response({'collections': collections}, status=status.HTTP_200_OK)
#     except Exception as e:
#         return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

        success = update_collection_products_order(shop_url, access_token, collection_id, sorted_product_ids)
        print("\n\n",success)
        if success:
            return Response({'success': True}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Failed to update product order'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_sorts(request): #working and tested
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        return JsonResponse({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        token = auth_header.split(' ')[1]  

        jwt_auth = JWTAuthentication()
        
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        
        shop_url = user.shop_url

        if not shop_url:
            return JsonResponse({'error': 'Shop URL not found in token'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client.objects.get(shop_url=shop_url)
            usage = Usage.objects.get(client=client)
            subscription = Subscription.objects.get(id=usage.subscription_id)
            sorting_plan = SortingPlan.objects.get(id=subscription.plan_id)

            sort_limit = sorting_plan.sort_limit
            available_sorts = sort_limit - usage.sort_count

            return Response({
                "available_sorts": available_sorts,
                "sort_limit": sort_limit,
                "used_sorts": usage.sort_count
            },status=status.HTTP_200_OK)

        except Usage.DoesNotExist:
            return JsonResponse({"error": "Usage record not found"}, status=status.HTTP_404_NOT_FOUND)
        
        except Subscription.DoesNotExist:
            return JsonResponse({"error": "Subscription record not found"}, status=status.HTTP_404_NOT_FOUND)
        
        except SortingPlan.DoesNotExist:
            return JsonResponse({"error": "Sorting plan record not found"}, status=status.HTTP_404_NOT_FOUND)

    except InvalidToken:
        return JsonResponse({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def last_active_collections(request):   #working and tested
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        token = auth_header.split(' ')[1]  
        
        jwt_auth = JWTAuthentication()
    
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        
        shop_url = user.shop_url

        if not shop_url:
            return Response({'error': 'Shop URL not found '}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client.objects.get(shop_url=shop_url)

            collections = ClientCollections.objects.filter(client=client, status=True).order_by('-sort_date')[:5]

            collections_data = []
            for collection in collections:
                algo_name = SortingAlgorithm.objects.get(id=collection.algo.id).name

                collections_data.append({
                    'collection_id': collection.collectionid,
                    'collection_name': collection.collection_name,
                    'product_count': collection.products_count,
                    'sort_date': collection.sort_date,
                    'algo_name': algo_name
                })

            return Response({'collections': collections_data}, status=status.HTTP_200_OK)


        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        except ClientCollections.DoesNotExist:
            return Response({'error': 'No collections found'}, status=status.HTTP_404_NOT_FOUND)
    
        except SortingAlgorithm.DoesNotExist:
            return Response({'error': 'Sorting algorithm not found'}, status=status.HTTP_404_NOT_FOUND)

    except InvalidToken:
        return JsonResponse({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

class ClientCollectionsPagination(PageNumberPagination):
    page_size = 10  
    page_size_query_param = 'page_size'
    max_page_size = 100

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_client_collections(request, client_id): #working and tested
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        token = auth_header.split(' ')[1]
        jwt_auth = JWTAuthentication()

        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        
        shop_url = user.shop_url

        if not shop_url:
            return Response({'error': 'Shop URL not found in session'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client.objects.get(shop_url=shop_url)

            if str(client.shop_id) != str(client_id):
                return Response({'error': 'Client ID mismatch'}, status=status.HTTP_403_FORBIDDEN)

            client_collections = ClientCollections.objects.filter(client=client).order_by('collectionid')

            paginator = ClientCollectionsPagination()
            paginated_collections = paginator.paginate_queryset(client_collections, request)

            collections_data = []
            for collection in paginated_collections:
                algo_name = SortingAlgorithm.objects.get(algo_id=collection.algo_id).name

                collections_data.append({
                    'collection_name': collection.collection_name,
                    'collection_id': collection.collectionid,
                    'status': collection.status,
                    'algo_name': algo_name
                })

            return paginator.get_paginated_response(collections_data)

        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
        except SortingAlgorithm.DoesNotExist:
            return Response({'error': 'Sorting algorithm not found'}, status=status.HTTP_404_NOT_FOUND)

    except InvalidToken:
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_last_sorted_time(request, client_id): #working not tested
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        token = auth_header.split(' ')[1]  
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        
        shop_url = user.shop_url  

        if not shop_url:
            return Response({'error': 'Shop URL not found'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client.objects.get(shop_url=shop_url)

            if str(client.shop_id) != str(client_id):
                return Response({'error': 'Client ID mismatch'}, status=status.HTTP_403_FORBIDDEN)

            latest_usage = Usage.objects.filter(client_id=client_id).order_by('-updated_at').first()

            if latest_usage:
                response_data = {
                    'last_sorted_time': latest_usage.updated_at
                }
            else:
                response_data = {
                    'error': 'No usage data found for this client'
                }

            return Response(response_data, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        except Usage.DoesNotExist:
            return Response({'error': 'No usage data found'}, status=status.HTTP_404_NOT_FOUND)

    except InvalidToken:
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_collections(request, client_id): #working and tested
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        token = auth_header.split(' ')[1]  
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        
        shop_url = user.shop_url  

        if not shop_url:
            return Response({'error': 'Shop URL not found'}, status=status.HTTP_400_BAD_REQUEST)
    
        query = request.GET.get('q', '')
        print(query)
        try:
            print(client_id)
            collections = ClientCollections.objects.filter(shop_id=client_id, collection_name__icontains=query)

            print("collections found: ", collections)
            collections_data = []
            for collection in collections:
                collections_data.append({
                    'collection_name': collection.collection_name,
                    'collection_id': collection.collectionid,
                    'status': collection.status,
                })

            return Response({'collections': collections_data}, status=status.HTTP_200_OK)

        except ClientCollections.DoesNotExist:
            return Response({'error': 'Collections not found'}, status=status.HTTP_404_NOT_FOUND)
        
    except InvalidToken:
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_collection(request, collection_id): #working not tested      
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        token = auth_header.split(' ')[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        if not shop_id:
            return Response({'error': 'Shop ID not found in session'}, status=status.HTTP_400_BAD_REQUEST)

        # client = Client.objects.get(shop_id=shop_id)
        collection = ClientCollections.objects.get(shop_id=shop_id, collectionid=collection_id)

        print(collection)

        status_value = request.data.get('status')
        algo_id = request.data.get('algo_id')

        updated = False

        if status_value is not None:
            collection.status = status_value
            updated = True

        if algo_id is not None:
            try:
                algo = SortingAlgorithm.objects.get(algo_id=algo_id)
                collection.algo = algo
                updated = True
            except SortingAlgorithm.DoesNotExist:
                return Response({'error': 'Algorithm not found'}, status=status.HTTP_404_NOT_FOUND)

        if updated:
            collection.save()
            return Response({'message': 'Collection updated successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'No valid fields provided to update'}, status=status.HTTP_400_BAD_REQUEST)

    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
    except ClientCollections.DoesNotExist:
        return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_collection_settings(request): # working and tested
    try:
        data = request.data
        collectionid = data.get('collectionid')

        if not collectionid:
            return Response({'error': 'collectionid is required'}, status=status.HTTP_400_BAD_REQUEST)

        auth_header = request.headers.get('Authorization', None)
        if auth_header is None:
            return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)
        
        token = auth_header.split(' ')[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        if not shop_id:
            return Response({'error': 'Shop ID not found in session'}, status=status.HTTP_400_BAD_REQUEST)

        client = Client.objects.get(shop_id=shop_id)
        collection = ClientCollections.objects.get(collectionid=collectionid, shop_id=shop_id)

        if 'out_of_stock_down' in data:
            collection.out_of_stock_down = data['out_of_stock_down']
        
        if 'pinned_out_of_stock_down' in data:
            collection.pinned_out_of_stock_down = data['pinned_out_of_stock_down']
        
        if 'new_out_of_stock_down' in data:
            collection.new_out_of_stock_down = data['new_out_of_stock_down']
        
        if 'lookback_periods' in data:
            collection.lookback_periods = data['lookback_periods']
        
        collection.save()

        return Response({
            'message': 'Collection settings updated successfully',
            'collectionid': collection.collectionid,
            'shop_id': shop_id,
            'out_of_stock_down': collection.out_of_stock_down,
            'pinned_out_of_stock_down': collection.pinned_out_of_stock_down,
            'new_out_of_stock_down': collection.new_out_of_stock_down,
            'lookback_periods': collection.lookback_periods
        }, status=status.HTTP_200_OK)

    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

    except ClientCollections.DoesNotExist:
        return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_global_settings(request): # working and tested
    try:
        data = request.data

        auth_header = request.headers.get('Authorization', None)
        if auth_header is None:
            return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)
        
        token = auth_header.split(' ')[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        if not shop_id:
            return Response({'error': 'Shop ID not found in session'}, status=status.HTTP_400_BAD_REQUEST)

        client = Client.objects.get(shop_id=shop_id)

        if 'schedule_frequency' in data:
            client.schedule_frequency = data['schedule_frequency']
        
        if 'stock_location' in data:
            client.stock_location = data['stock_location']
        
        client.save()

        return Response({
            'message': 'Global settings updated successfully',
            'shop_id': client.shop_id,
            'schedule_frequency': client.schedule_frequency,
            'stock_location': client.stock_location
        }, status=status.HTTP_200_OK)

    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@shop_login_required
@api_view(['GET'])
def fetch_last_sort_date(request):
    #GET /api/fetch-sort-date/?collectionid=12345&clientid=1
    collectionid = request.GET.get('collectionid')
    clientid = request.GET.get('clientid')

    if not collectionid or not clientid:
        return Response({'error': 'collectionid and clientid are required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = Client.objects.get(id=clientid)

        collection = ClientCollections.objects.get(collectionid=collectionid, client=client)

        return Response({
            'collectionid': collection.collectionid,
            'sort_date': collection.sort_date
        }, status=status.HTTP_200_OK)

    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

    except ClientCollections.DoesNotExist:
        return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@shop_login_required
@api_view(['POST']) 
@csrf_protect
def get_and_update_collections(request):
    client_id = request.data.get('clientid')

    if not client_id:
        return Response({'error': 'Client ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = Client.objects.get(id=client_id)
        access_token = 123 # update this 

        collections = fetch_collections(client.shop_url,access_token)

        for collection in collections:
            collection_data = {
                'collectionid': collection['id'],
                'collection_name': collection['title'],
                'products_count': collection['products_count']
            }

            ClientCollections.objects.update_or_create(
                collectionid=collection_data['collectionid'],
                client=client,
                defaults={
                    'collection_name': collection_data['collection_name'],
                    'products_count': collection_data['products_count'],
                    'status': False,  
                }
            )

        return Response({'message': 'Collections updated successfully'}, status=status.HTTP_200_OK)

    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@shop_login_required
@api_view(['POST'])  
@csrf_protect
def get_products(request):
    shop_url = request.session.get('shopify', {}).get('shop_url')
    collection_id = request.data.get('collection_id')  

    if not shop_url:
        return Response({'error': 'Shop URL not found in session'}, status=status.HTTP_400_BAD_REQUEST)
    if not collection_id:
        return Response({'error': 'Collection ID is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        products = fetch_products_by_collection(shop_url, collection_id)
        try:
            client_collection = ClientCollections.objects.get(collectionid=collection_id)
        except ClientCollections.DoesNotExist:
            return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)

        pinned_products = client_collection.pinned_products or []


        products_filtered = [product for product in products if product['id'] not in pinned_products]

        return Response({
            'products': products_filtered,
            'pinned_products': pinned_products
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@shop_login_required
@api_view(['POST'])
@csrf_protect
def update_pinned_products(request):
    collection_id = request.data.get('collection_id')
    pinned_products = request.data.get('pinned_products', [])

    if not collection_id:
        return Response({'error': 'Collection ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    if not isinstance(pinned_products, list):
        return Response({'error': 'Pinned products should be a list of product IDs'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        
        client_collection = ClientCollections.objects.get(collectionid=collection_id)

        client_collection.pinned_products = pinned_products
        client_collection.save()

        return Response({
            'message': 'Pinned products updated successfully',
            'pinned_products': client_collection.pinned_products
        }, status=status.HTTP_200_OK)

    except ClientCollections.DoesNotExist:
        return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@shop_login_required
@api_view(['GET'])
def get_sorting_algorithms(request):
    # GET /api/get-sorting-algorithms/?client_id=1
    client_id = request.GET.get('client_id')

    if not client_id:
        return Response({'error': 'Client ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = Client.objects.get(id=client_id)
        default_algo = client.default_algo

        algorithms = SortingAlgorithm.objects.all()

        algo_data = []

        for algo in algorithms:
            collections_count = ClientCollections.objects.filter(algo_id=algo.algo_id).count()

            algo_data.append({
                'algo_id': algo.algo_id,
                'name': algo.name,
                'description': algo.description,
                'default_parameters': algo.default_parameters,
                'collections_using_algo': collections_count
            })

        return Response({
            'default_algo': default_algo,
            'algorithms': algo_data
        }, status=status.HTTP_200_OK)

    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@shop_login_required
@api_view(['POST'])
def update_default_algo(request):
    client_id = request.data.get('client_id')
    algo_id = request.data.get('algo_id')

    if not client_id or not algo_id:
        return Response({'error': 'Client ID and Algorithm ID are required'}, status=status.HTTP_400_BAD_REQUEST)

    try:

        client = Client.objects.get(id=client_id)

        algo = SortingAlgorithm.objects.get(algo_id=algo_id)

        client.default_algo = algo_id
        client.save()

        return Response({
            'message': 'Default algorithm updated successfully',
            'default_algo': client.default_algo
        }, status=status.HTTP_200_OK)

    except Client.DoesNotExist:
        return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

    except SortingAlgorithm.DoesNotExist:
        return Response({'error': 'Sorting algorithm not found'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)