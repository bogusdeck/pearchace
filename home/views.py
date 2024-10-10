from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from django.shortcuts import redirect
from shopify_app.decorators import shop_login_required
from django.http import JsonResponse
from datetime import datetime
from django.utils import timezone
import pytz
from django.views.decorators.http import require_GET
import shopify
from django.views.decorators.csrf import csrf_protect
from shopify_app.models import (
    Client,
    Usage,
    Subscription,
    SortingPlan,
    SortingAlgorithm,
    ClientCollections,
    ClientProducts,
    ClientGraph,
    ClientAlgo
)
from shopify_app.api import (
    fetch_collections,
    fetch_client_data,
)
from .strategies import (
    promote_new,
    promote_high_revenue_products,
    promote_high_inventory_products,
    bestsellers_high_variant_availability,
    promote_high_variant_availability,
    clearance_sale,
    promote_high_revenue_new_products,
)

from django.shortcuts import get_object_or_404
from django.contrib.auth.tokens import default_token_generator

ALGO_ID_TO_FUNCTION = {
    "001": promote_new,
    "002": promote_high_revenue_products,
    "003": promote_high_inventory_products,
    "004": bestsellers_high_variant_availability,
    "005": promote_high_variant_availability,
    "006": clearance_sale,
    "007": promote_high_revenue_new_products,
}

from shopify_app.tasks import (
    async_quick_sort_product_order,
    async_advance_sort_product_order,
    async_fetch_and_store_collections,
    async_fetch_and_store_products,
)

from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

import os
from dotenv import load_dotenv

load_dotenv()

##########################################################################################################################
# ██████   █████  ███████ ██   ██ ██████   ██████   █████  ██████  ██████  
# ██   ██ ██   ██ ██      ██   ██ ██   ██ ██    ██ ██   ██ ██   ██ ██   ██ 
# ██   ██ ███████ ███████ ███████ ██████  ██    ██ ███████ ██████  ██   ██ 
# ██   ██ ██   ██      ██ ██   ██ ██   ██ ██    ██ ██   ██ ██   ██ ██   ██ 
# ██████  ██   ██ ███████ ██   ██ ██████   ██████  ██   ██ ██   ██ ██████ 
###########################################################################################################################

#come here after auth and client info fetched and stored inside the database , and this endpoint redirect to the frontend link
@shop_login_required
def index(request):
    try:
        shop_url = request.session.get("shopify", {}).get("shop_url")
        access_token = request.session.get("shopify", {}).get("access_token")
        if not shop_url or not access_token:
            return JsonResponse(
                {"error": "Shopify authentication required"}, status=403
            )

        shop_data = fetch_client_data(shop_url, access_token)

        if not shop_data:
            return JsonResponse(
                {"error": "Failed to fetch client data from Shopify"}, status=500
            )

        shop_gid = shop_data.get("id", "")
        shop_id = shop_gid.split("/")[-1]
        email = shop_data.get("email", "")
        name = shop_data.get("name", "")
        contact_email = shop_data.get("contactEmail", "")
        currency = shop_data.get("currencyCode", "")
        timezone = shop_data.get("timezoneAbbreviation", "")
        billing_address = shop_data.get("billingAddress", {})
        created_at_str = shop_data.get("createdAt", "")

        created_at = None
        if created_at_str:
            try:
                created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ")
                created_at = created_at.replace(tzinfo=pytz.UTC)
            except ValueError:
                created_at = None

        client, created = Client.objects.update_or_create(
            shop_id=shop_id,
            defaults={
                "shop_url": shop_url,
                "shop_name": name,
                "email": email,
                "phone_number": billing_address.get("phone", None),
                "country": billing_address.get("countryCodeV2", ""),
                "contact_email": contact_email,
                "currency": currency,
                "billingAddress": billing_address,
                "access_token": access_token,
                "is_active": True,
                "uninstall_date": None,
                "trial_used": False,
                "timezone": timezone,
                "createdateshopify": created_at,
            },
        )

        if created:
            client.member = False
        client.save()

        refresh = RefreshToken.for_user(client)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)


        frontend_url = os.environ.get("FRONTEND_URL")
        print(frontend_url)
        print("\n")
        print("access_token" , access_token)
        redirect_url = f"{frontend_url}?access_token={access_token}&refresh_token={refresh_token}&shop_url={shop_url}"

        return redirect(redirect_url)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@api_view(["GET"]) # first api called by frontend to show client name and url on the dashboard
@permission_classes([IsAuthenticated]) # fetch and store collection done 
def get_client_info(request):   
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
        
        async_fetch_and_store_collections.delay(shop_id)

        return Response(
            {
             "client_id": user.shop_id,
             "shop_url":user.shop_url,
             "shop_name":user.shop_name,
             "message": "Collection fetch initiated."},
            status=status.HTTP_200_OK,
        )

        

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@permission_classes([IsAuthenticated]) # return the available sorts left for client to use based on its usage and subscriptions
def available_sorts(request):  
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        return JsonResponse(
            {"error": "Authorization header missing"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        token = auth_header.split(" ")[1]

        jwt_auth = JWTAuthentication()

        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_url = user.shop_url

        if not shop_url:
            return JsonResponse(
                {"error": "Shop URL not found in token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            client = Client.objects.get(shop_url=shop_url)
            usage = Usage.objects.get(client=client)
            subscription = Subscription.objects.get(id=usage.subscription_id)
            sorting_plan = SortingPlan.objects.get(id=subscription.plan_id)

            sort_limit = sorting_plan.sort_limit
            available_sorts = sort_limit - usage.sort_count

            return Response(
                {
                    "available_sorts": available_sorts,
                    "sort_limit": sort_limit,
                    "used_sorts": usage.sort_count,
                },
                status=status.HTTP_200_OK,
            )

        except Usage.DoesNotExist:
            return JsonResponse(
                {"error": "Usage record not found"}, status=status.HTTP_404_NOT_FOUND
            )

        except Subscription.DoesNotExist:
            return JsonResponse(
                {"error": "Subscription record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except SortingPlan.DoesNotExist:
            return JsonResponse(
                {"error": "Sorting plan record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    except InvalidToken:
        return JsonResponse(
            {"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        return JsonResponse(
            {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET']) # graph data will be displayed for the user
def get_graph(request):
    date = request.GET.get('date')
    # revenue_data, top_products_by_revenue, top_products_by_sold_units = calculate_total_revenue(date)

    # response_data = {
    #     'date': date,
    #     'total_revenue': revenue_data['total_revenue'],
    #     'top_products_by_revenue': top_products_by_revenue,
    #     'top_products_by_sold_units': top_products_by_sold_units,
    # }
    response_data = "hi hi hi graph nhi hai bhai cron mai lgaunga"
    return Response(response_data)

@api_view(["GET"]) # client's last active collections which are sorted by us 
@permission_classes([IsAuthenticated])
def last_active_collections(request):  # working and tested
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

        shop_url = user.shop_url
        shop_id = user.shop_id

        if not shop_url:
            return Response(
                {"error": "Shop URL not found "}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = Client.objects.get(shop_url=shop_url)

            collections = ClientCollections.objects.filter(
                shop_id=shop_id, status=True
            ).order_by("-sort_date")[:5]

            collections_data = []
            for collection in collections:
                algo_name = SortingAlgorithm.objects.get(id=collection.algo.id).name

                collections_data.append(
                    {
                        "collection_id": collection.collection_id,
                        "collection_name": collection.collection_name,
                        "product_count": collection.products_count,
                        "sort_date": collection.sort_date,
                        "algo_name": algo_name,
                    }
                )

            return Response(
                {"collections": collections_data}, status=status.HTTP_200_OK
            )

        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        except ClientCollections.DoesNotExist:
            return Response(
                {"error": "No collections found"}, status=status.HTTP_404_NOT_FOUND
            )

        except SortingAlgorithm.DoesNotExist:
            return Response(
                {"error": "Sorting algorithm not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    except InvalidToken:
        return JsonResponse(
            {"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        return JsonResponse(
            {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


###########################################################################################################################
#  ██████  ██████  ██      ██      ███████  ██████ ████████ ██  ██████  ███    ██ 
# ██      ██    ██ ██      ██      ██      ██         ██    ██ ██    ██ ████   ██ 
# ██      ██    ██ ██      ██      █████   ██         ██    ██ ██    ██ ██ ██  ██ 
# ██      ██    ██ ██      ██      ██      ██         ██    ██ ██    ██ ██  ██ ██ 
#  ██████  ██████  ███████ ███████ ███████  ██████    ██    ██  ██████  ██   ████ 
                                                                                
# ███    ███  █████  ███    ██  █████   ██████  ███████ ██████                    
# ████  ████ ██   ██ ████   ██ ██   ██ ██       ██      ██   ██                   
# ██ ████ ██ ███████ ██ ██  ██ ███████ ██   ███ █████   ██████                    
# ██  ██  ██ ██   ██ ██  ██ ██ ██   ██ ██    ██ ██      ██   ██                   
# ██      ██ ██   ██ ██   ████ ██   ██  ██████  ███████ ██   ██                   
###########################################################################################################################

@api_view(["GET"])
@permission_classes([IsAuthenticated]) # give the last sorted date globally
def get_last_sorted_time(request, client_id):  # working not tested 
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

        shop_url = user.shop_url
        shop_id = user.shop_id

        if not shop_url:
            return Response(
                {"error": "Shop URL not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = Client.objects.get(shop_url=shop_url)

            if str(client.shop_id) != str(client_id):
                return Response(
                    {"error": "Client ID mismatch"}, status=status.HTTP_403_FORBIDDEN
                )

            latest_usage = (
                Usage.objects.filter(shop_id=shop_id).order_by("-updated_at").first()
            )

            if latest_usage:
                response_data = {"last_sorted_time": latest_usage.updated_at}
            else:
                response_data = {"error": "No usage data found for this client"}

            return Response(response_data, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        except Usage.DoesNotExist:
            return Response(
                {"error": "No usage data found"}, status=status.HTTP_404_NOT_FOUND
            )

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ClientCollectionsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

@api_view(["GET"])
@permission_classes([IsAuthenticated]) # all client collections given to the frontend with pagination (page size = 10)
def get_client_collections(request, client_id):  # working and tested
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

        shop_url = user.shop_url
        shop_id = user.shop_id


        if not shop_url:
            return Response(
                {"error": "Shop URL not found in session"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            client = Client.objects.get(shop_url=shop_url)

            if str(client.shop_id) != str(client_id):
                return Response(
                    {"error": "Client ID mismatch"}, status=status.HTTP_403_FORBIDDEN
                )

            client_collections = ClientCollections.objects.filter(
                shop_id=shop_id
            ).order_by("collection_id")

            paginator = ClientCollectionsPagination()
            paginated_collections = paginator.paginate_queryset(
                client_collections, request
            )

            collections_data = []
            for collection in paginated_collections:
                algo_id = ClientAlgo.objects.get(
                    clalgo_id=collection.algo_id
                ).clalgo_id

                collections_data.append(
                    {
                        "collection_name": collection.collection_name,
                        "collection_id": collection.collection_id,
                        "status": collection.status,
                        "algo_id": algo_id,
                    }
                )

            return paginator.get_paginated_response(collections_data)

        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except SortingAlgorithm.DoesNotExist:
            return Response(
                {"error": "Sorting algorithm not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated]) # can search  through all collections of client 
def search_collections(request, client_id):  # working and tested
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

        shop_url = user.shop_url
        # shop_id = user.shop_id

        if not shop_url:
            return Response(
                {"error": "Shop URL not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        query = request.GET.get("q", "")
        print(query)
        try:
            print(client_id)
            collections = ClientCollections.objects.filter(
                shop_id=client_id, collection_name__icontains=query
            )

            print("collections found: ", collections)
            collections_data = []
            for collection in collections:
                collections_data.append(
                    {
                        "collection_name": collection.collection_name,
                        "collection_id": collection.collection_id,
                        "status": collection.status,
                    }
                )

            return Response(
                {"collections": collections_data}, status=status.HTTP_200_OK
            )

        except ClientCollections.DoesNotExist:
            return Response(
                {"error": "Collections not found"}, status=status.HTTP_404_NOT_FOUND
            )

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated]) # celery implemented fetch and store products
def update_collection(request, collection_id):  # working not tested
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

        # client = Client.objects.get(shop_id=shop_id)
        collection = ClientCollections.objects.get(
            shop_id=shop_id, collection_id=collection_id
        )
        client = Client.objects.get(shop_id=shop_id)
        print(collection)
        print("client fetched  :", client )

        status_value = request.data.get("status")
        algo_id = request.data.get("algo_id")

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
                return Response(
                            {"error": "Algorithm not found"}, status=status.HTTP_404_NOT_FOUND
                )
        
        days=client.lookback_period
        if updated:
            collection.save()
            if collection.status:
                shop_url = user.shop_url
                async_fetch_and_store_products.delay(shop_url, shop_id, collection_id, days)

                return Response(
                    {"message": "Collection updated, product fetching initiated asynchronously"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"message": "Collection updated successfully"},
                    status=status.HTTP_200_OK,
                )
        else:
            return Response(
                {"error": "No valid fields provided to update"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except Client.DoesNotExist:
        return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)
    except ClientCollections.DoesNotExist:
        return Response(
            {"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["POST"]) # SORT NOW BUTTON
@permission_classes([IsAuthenticated]) # celery done sorting done in queue #not using this ewwwwwwwwwwwwwwwwwwwwwww
def update_product_order(request):  
    try:
        auth_header = request.headers.get("Authorization", None)
        if auth_header is None:
            return Response(
                {"error": "Authorization header missing"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        if not shop_id:
            return Response(
                {"error": "Shop ID not found in JWT token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            client = Client.objects.get(shop_id=shop_id)
        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        collection_id = request.data.get("collection_id")
        algo_id = request.data.get("algo_id")

        client_collections = ClientCollections.objects.get(
            shop_id=shop_id, collection_id=collection_id
        )

        if not collection_id:
            return Response(
                {"error": "Collection ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not algo_id:
            return Response(
                {"error": "Algorithm ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        access_token = client.access_token
        if not access_token:
            return Response(
                {"error": "Access token not found for this client or maybe expire reauth again"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        parameters_used = client_collections.parameters_used

        parameters = {
            "days":parameters_used.get("days", 7),
            "percentile":parameters_used.get("percentile", 100),
            "variant_threshold":parameters_used.get("variant_threshold", 5.0),
        }

        async_quick_sort_product_order.delay(shop_id, collection_id, algo_id, parameters)

        return Response({"message": "Sorting initiated"}, status=status.HTTP_202_ACCEPTED)

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({"errore": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



########## COLLECTION SETTING ############

@api_view(["GET"])
@permission_classes([IsAuthenticated]) # last sort date for that collection
def fetch_last_sort_date(request):  # working and tested
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

        collection_id = request.GET.get("collection_id")

        if not collection_id:
            return Response(
                {"error": "collection_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = Client.objects.get(shop_id=shop_id)

        collection = ClientCollections.objects.get(
            collection_id=collection_id, shop_id=shop_id
        )

        sort_date = collection.sort_date

        if not sort_date:
            sort_date = "no sort found"

        return Response(
            {
                "collection_id": collection.collection_id,
                "sort_date": sort_date,
            },
            status=status.HTTP_200_OK,
        )

    except Client.DoesNotExist:
        return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)

    except ClientCollections.DoesNotExist:
        return Response(
            {"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND
        )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


################################ PINNED PRODUCTS TAB #######################################
@api_view(["GET"]) #  
@permission_classes([IsAuthenticated])
@csrf_protect
def get_products(request, collection_id):
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
        print(shop_id)

        if not shop_id:
            return Response(
                {"error": "Shop ID not found in session"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # collection_id = request.data.get("collection_id")
        
        try:
            collection=ClientCollections.objects.filter(
                shop_id = shop_id, collection_id = collection_id
            ).first()

            if not collection:
                return Response(
                    {"error":"Collection not found"}, status=status.HTTP_404_NOT_FOUND
                )
            
            client_products = ClientProducts.objects.filter(collection_id=collection_id)

            response_products = [
                {
                    "id": product.product_id,
                    "title": product.product_name,
                    "total_inventory":product.total_inventory,
                    "image_link": product.image_link,
                }
                for product in client_products
            ] 

            return Response({"products": response_products}, status=status.HTTP_200_OK)
        except:
            return Response()
        
    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_pinned_products(request):  # working and tested
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
                {"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        collection_id = request.data.get("collection_id")
        pinned_products = request.data.get("pinned_products", [])

        if not collection_id:
            return Response(
                {"error": "Collection ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(pinned_products, list):
            return Response(
                {"error": "Pinned products should be a list of product IDs"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            client_collection = ClientCollections.objects.get(
                collection_id=collection_id
            )
        except ClientCollections.DoesNotExist:
            return Response(
                {"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND
            )

        client_collection.pinned_products = pinned_products
        client_collection.save()

        return Response(
            {
                "message": "Pinned products updated successfully",
                "pinned_products": client_collection.pinned_products,
            },
            status=status.HTTP_200_OK,
        )

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated]) # new api done and tested
def search_products(request, collection_id):  # 
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
                {"error": "Shop id not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        query = request.GET.get("q", "")
        print(query)
        try:
            print(collection_id)
            products = ClientProducts.objects.filter(
                shop_id=shop_id,collection_id=collection_id, product_name__icontains=query
            )

            if not products.exists():
                return Response(
                    {"error": "No products found for the given query and collection"},
                    status=status.HTTP_404_NOT_FOUND
                 )

            print("product found: ", products)
            
            products_data = [
                    {
                        "product_name": product.product_name,
                        "product_id": product.product_id,
                        "image": product.image_link,
                        "stock": product.total_inventory
                    }
                    for product in products
            ]
            return Response(
                {"products": products_data}, status=status.HTTP_200_OK
            )

        except ClientProducts.DoesNotExist:
            return Response(
                {"error": "Produts not found for given collection"}, status=status.HTTP_404_NOT_FOUND
            )

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated]) #done and tested
def preview_products(request):
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
                {"error":"Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        collection_id = request.data.get("collection_id")
        
        print(collection_id)

        if not collection_id:
            return Response(
                {'error':"Collection id is not provided"},status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            products = ClientProducts.objects.filter(
                shop_id=shop_id, collection_id=collection_id
            ).order_by('position_in_collection').values(
                'product_id','product_name','image_link','total_inventory'
            )

            print(products)
            product_data = {
                product['product_id']: {
                    'product_name': product['product_name'],
                    'image_link': product['image_link'],
                    'total_inventory': product['total_inventory']
                }
                for product in products
            }

            return Response(product_data, status=200)
        except ClientProducts.DoesNotExist:
            return Response({'error':'No products found for this collection'}, status=404)
    
    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


############################### SORTING SETTINGS ###########################################

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_quick_config(request):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        return Response(
            {'error':'Authorization header missing'},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    try:
        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user=jwt_auth.get_user(validated_token)

        shop_id = user.shop_id        
        if not shop_id:
            return Response({"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST)
        
        collection_id = request.data.get("collection_id")
        algo_id = request.data.get("algo_id")
        # parameters = request.data.get("parameters", {})
        
        if not collection_id or not algo_id:
            return Response(
                {"error": "Both collection_id and algo_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not algo_id:
            return Response(
                {"error": "Algorithm ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        async_quick_sort_product_order.delay(shop_id, collection_id, algo_id)

        return Response({"message": "Sorting initiated"}, status=status.HTTP_202_ACCEPTED)
        
    except InvalidToken:
        return Response({"error":"Invalid Token"}, status = status.HTTP_401_UNAUTHORIZED)    
                    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def advance_config(request):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        return Response(
            {'error': 'Authorization header missing'},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    try:
        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        if not shop_id:
            return Response({"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST)
        
        collection_id = request.data.get("collection_id")
        clalgo_id = request.data.get("clalgo_id")
        
        if not collection_id or not clalgo_id:
            return Response(
                {"error": "Both collection_id and clalgo_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client_algo = ClientAlgo.objects.get(clalgo_id=clalgo_id, shop_id=shop_id)
        except ClientAlgo.DoesNotExist:
            return Response({"error": "Algorithm not found for this shop"}, status=status.HTTP_404_NOT_FOUND)

        bucket_parameters = client_algo.bucket_parameters
        if not bucket_parameters:
            return Response({"error": "Bucket parameters not found"}, status=status.HTTP_400_BAD_REQUEST)

        task = async_advance_sort_product_order.delay(shop_id, collection_id, clalgo_id)

        return Response(
            {"message": "Sorting initiated with advanced system", "task_id": task.id},
            status=status.HTTP_200_OK
        )


    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["POST"])
@permission_classes([IsAuthenticated]) # not tested
def save_client_algorithm(request):
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
                {"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = Client.objects.get(shop_id=shop_id)
        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        algo_name = request.data.get('algo_name')
        boost_tags = request.data.get('boost_tags', [])
        bury_tags = request.data.get('bury_tags', [])
        bucket_parameters = request.data.get('bucket_parameters', [])

        if not algo_name:
            return Response(
                {"error": "Algorithm name is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not isinstance(boost_tags, list):
            return Response(
                {"error": "boost_tags must be a list of strings"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not isinstance(bury_tags, list):
            return Response(
                {"error": "bury_tags must be a list of strings"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not isinstance(bucket_parameters, list) or not all(isinstance(bp, dict) for bp in bucket_parameters):
            return Response(
                {"error": "bucket_parameters must be a list of dictionaries"}, status=status.HTTP_400_BAD_REQUEST
            )

        client_algo = ClientAlgo.objects.create(
            shop_id=shop_id,
            algo_name=algo_name,
            boost_tags=boost_tags,
            bury_tags=bury_tags,
            bucket_parameters=bucket_parameters,
            number_of_buckets=len(bucket_parameters),
        )

        return Response(
            {
                "message": "Algorithm created successfully",
                "clalgo_id": client_algo.clalgo_id,
                "algo_name": client_algo.algo_name,
            },
            status=status.HTTP_201_CREATED
        )

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_all_algo(request, clalgo_id):
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

        try:
            client_algo = ClientAlgo.objects.get(clalgo_id=clalgo_id, shop=user.shop_id)
        except ClientAlgo.DoesNotExist:
            raise NotFound("Algorithm not found for this client.")

        data = request.data

        if 'algo_name' in data:
            client_algo.algo_name = data['algo_name']
        if 'bury_tags' in data:
            client_algo.bury_tags = data['bury_tags']
        if 'boost_tags' in data:
            client_algo.boost_tags = data['boost_tags']
        if 'bucket_parameters' in data:
            client_algo.bucket_parameters = data['bucket_parameters']
        if 'number_of_buckets' in data:
            client_algo.number_of_buckets = data['number_of_buckets']

        client_algo.save()

        return Response({"message": "Algorithm updated successfully"}, status=status.HTTP_200_OK)

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_collections(request):
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
                {"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            collections = ClientCollections.objects.filter(
                    shop_id=shop_id, status=True
                )

            collection_data = [
                {
                    "collection_id": collection.collection_id,
                    "collection_name": collection.collection_name,
                }
                for collection in collections
            ]

            return Response({"active_collections":collection_data}, status=status.HTTP_200_OK)
        
        except ClientCollections.DoesNotExist:
            return Response(
                {"error": "client's collection not found"}, status=status.HTTP_404_NOT_FOUND
            )

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@permission_classes([IsAuthenticated]) # done and tested
def applied_on_active_collection(request):
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

        data = request.data
        collection_ids = data.get("collection_ids", [])
        clalgo_id = data.get("clalgo_id")

        if not collection_ids or not clalgo_id:
            return Response({"error": "collection_ids and clalgo_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        ClientCollections.objects.filter(shop_id=shop_id, collection_id__in=collection_ids).update(algo=clalgo_id)

        return Response({"message": "Updated successfully."}, status=status.HTTP_200_OK)

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



############################## GENERAL SETTINGS FOR COLLECTION ####################################

@api_view(["POST"])
@permission_classes([IsAuthenticated]) # require to update lookback periods as it is moved to global settings
def update_collection_settings(request):  # working and tested
    try:
        data = request.data
        collection_id = data.get("collection_id")

        if not collection_id:
            return Response(
                {"error": "collection_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        auth_header = request.headers.get("Authorization", None)
        if auth_header is None:
            return Response(
                {"error": "Authorization header missing"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

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

        client = Client.objects.get(shop_id=shop_id)
        collection = ClientCollections.objects.get(
            collection_id=collection_id, shop_id=shop_id
        )

        if "out_of_stock_down" in data:
            collection.out_of_stock_down = data["out_of_stock_down"]

        if "pinned_out_of_stock_down" in data:
            collection.pinned_out_of_stock_down = data["pinned_out_of_stock_down"]

        if "new_out_of_stock_down" in data:
            collection.new_out_of_stock_down = data["new_out_of_stock_down"]

        collection.save()

        return Response(
            {
                "message": "Collection settings updated successfully",
                "collection_id": collection.collection_id,
                "shop_id": shop_id,
                "out_of_stock_down": collection.out_of_stock_down,
                "pinned_out_of_stock_down": collection.pinned_out_of_stock_down,
                "new_out_of_stock_down": collection.new_out_of_stock_down,
                "lookback_periods": collection.lookback_periods,
            },
            status=status.HTTP_200_OK,
        )

    except Client.DoesNotExist:
        return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)

    except ClientCollections.DoesNotExist:
        return Response(
            {"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND
        )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


############################ ANALYTICS TABS FOR COLLECTION ########################################


########################################################################################################
# ███████  ██████  ██████  ████████ ██ ███    ██  ██████      ██████  ██    ██ ██      ███████ ███████ 
# ██      ██    ██ ██   ██    ██    ██ ████   ██ ██           ██   ██ ██    ██ ██      ██      ██      
# ███████ ██    ██ ██████     ██    ██ ██ ██  ██ ██   ███     ██████  ██    ██ ██      █████   ███████ 
#      ██ ██    ██ ██   ██    ██    ██ ██  ██ ██ ██    ██     ██   ██ ██    ██ ██      ██           ██ 
# ███████  ██████  ██   ██    ██    ██ ██   ████  ██████      ██   ██  ██████  ███████ ███████ ███████ 
########################################################################################################

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_sorting_algorithms(request):  # Updated for new UI
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
                {"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = Client.objects.get(shop_id=shop_id)
        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        primary_algorithms = SortingAlgorithm.objects.all()
        primary_algo_data = []
        for algo in primary_algorithms:
            primary_algo_data.append(
                {
                    "algo_id": algo.algo_id,
                    "name": algo.name,
                    "description": algo.description,
                }
            )

        client_algorithms = ClientAlgo.objects.filter(shop_id=client)
        client_algo_data = []
        for algo in client_algorithms:
            client_algo_data.append(
                {
                    "clalgo_id": algo.clalgo_id,
                    "algo_name": algo.algo_name,
                    "number_of_buckets": algo.number_of_buckets,
                }
            )

        response_data = {
            "primary_algorithms": primary_algo_data,
            "client_algorithms": client_algo_data,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_default_algo(request):  # working and tested
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
                {"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        algo_id = request.data.get("algo_id")

        if not shop_id or not algo_id:
            return Response(
                {"error": "Client ID and Algorithm ID are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            client = Client.objects.get(shop_id=shop_id)
        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            algo = SortingAlgorithm.objects.get(algo_id=algo_id)
        except SortingAlgorithm.DoesNotExist:
            return Response(
                {"error": "Sorting algorithm not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        client.default_algo = algo
        client.save()

        return Response(
            {
                "message": "Default algorithm updated successfully",
                "default_algo": algo.algo_id,
            },
            status=status.HTTP_200_OK,
        )

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated]) # done and tested
def sorting_rule(request, clalgo_id):
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

        try:
            client_algo = ClientAlgo.objects.get(clalgo_id=clalgo_id, shop_id=shop_id)

            algo_data = {
                "clalgo_id": client_algo.clalgo_id,
                "algo_name": client_algo.algo_name,
                "number_of_buckets": client_algo.number_of_buckets,
                "boost_tags": client_algo.boost_tags,
                "bury_tags": client_algo.bury_tags,
                "bucket_parameters": client_algo.bucket_parameters,
                "is_primary": client_algo.is_primary,
            }

            return Response(algo_data, status=status.HTTP_200_OK)

        except ClientAlgo.DoesNotExist:
            return Response({"error": "Algorithm not found."}, status=status.HTTP_404_NOT_FOUND)

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#######################################################################################################
#  ██████  ██       ██████  ██████   █████  ██                    
# ██       ██      ██    ██ ██   ██ ██   ██ ██                    
# ██   ███ ██      ██    ██ ██████  ███████ ██                    
# ██    ██ ██      ██    ██ ██   ██ ██   ██ ██                    
#  ██████  ███████  ██████  ██████  ██   ██ ███████               
                                                                                                                                
# ███████ ███████ ████████ ████████ ██ ███    ██  ██████  ███████ 
# ██      ██         ██       ██    ██ ████   ██ ██       ██      
# ███████ █████      ██       ██    ██ ██ ██  ██ ██   ███ ███████ 
#      ██ ██         ██       ██    ██ ██  ██ ██ ██    ██      ██ 
# ███████ ███████    ██       ██    ██ ██   ████  ██████  ███████ 
#######################################################################################################
import logging

logger = logging.getLogger('myapp')

from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
import json

@api_view(["POST"])
@permission_classes([IsAuthenticated]) 
def update_global_settings(request):  # working and not tested 
    try:
        logger.info("API hit: update_global_settings")
        data = request.data

        auth_header = request.headers.get("Authorization", None)
        if auth_header is None:
            logger.error("Authorization header missing")
            return Response(
                {"error": "Authorization header missing"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        if not shop_id:
            logger.error("Shop ID not found in session")
            return Response(
                {"error": "Shop ID not found in session"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = Client.objects.get(shop_id=shop_id)

        if "schedule_frequency" in data:
            PeriodicTask.objects.filter(name=f"sort_collections_{client.shop_id}").delete()

            client.schedule_frequency = data["schedule_frequency"]
            logger.info(f"Schedule frequency set to: {data['schedule_frequency']}")
            
            if data["schedule_frequency"] == "hourly":
                interval_schedule, _ = IntervalSchedule.objects.get_or_create(
                    every=1,
                    period=IntervalSchedule.HOURS
                )
                PeriodicTask.objects.create(
                    interval=interval_schedule,  
                    name=f"sort_collections_{client.shop_id}",
                    task="your_app.tasks.sort_active_collections",
                    args=json.dumps([client.id])
                )
            
            elif data["schedule_frequency"] == "daily":
                crontab_schedule, _ = CrontabSchedule.objects.get_or_create(
                    minute=0,
                    hour=0,  
                )
                PeriodicTask.objects.create(
                    crontab=crontab_schedule,  
                    name=f"sort_collections_{client.shop_id}",
                    task="your_app.tasks.sort_active_collections",
                    args=json.dumps([client.id])
                )
            
            elif data["schedule_frequency"] == "weekly":
                crontab_schedule, _ = CrontabSchedule.objects.get_or_create(
                    minute=0,
                    hour=0,
                    day_of_week="1",  
                )
                PeriodicTask.objects.create(
                    crontab=crontab_schedule, 
                    name=f"sort_collections_{client.shop_id}",
                    task="your_app.tasks.sort_active_collections",
                    args=json.dumps([client.id])
                )
            
            elif data["schedule_frequency"] == "custom":
                start_time = data.get("custom_start_time")
                stop_time = data.get("custom_stop_time")
                frequency_in_hours = data.get("custom_frequency_in_hours")

                if start_time and stop_time and frequency_in_hours:
                    start_hour, start_minute = map(int, start_time.split(':'))
                    stop_hour, stop_minute = map(int, stop_time.split(':'))

                    current_hour = start_hour
                    while current_hour < stop_hour:
                        crontab_schedule, _ = CrontabSchedule.objects.get_or_create(
                            minute=start_minute,
                            hour=current_hour,
                        )
                        PeriodicTask.objects.create(
                            crontab=crontab_schedule,
                            name=f"sort_collections_{client.shop_id}_custom_{current_hour}",
                            task="your_app.tasks.sort_active_collections",
                            args=json.dumps([client.id])
                        )
                        current_hour += frequency_in_hours
                        
        if "stock_location" in data:
            client.stock_location = data["stock_location"]

        
        if "lookback_periods" in data:
            client.lookback_period = data["lookback_period"]

        client.save()

        return Response(
            {
                "message": "Global settings updated successfully",
                "shop_id": client.shop_id,
                "schedule_frequency": client.schedule_frequency,
                "stock_location": client.stock_location,
            },
            status=status.HTTP_200_OK,
        )

    except Client.DoesNotExist:
        logger.error("Client not found")
        return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Exception occurred: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_and_update_collections(request):  # working and tested
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
                {"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = Client.objects.get(shop_id=shop_id)

            access_token = client.access_token

            collections = fetch_collections(client.shop_url)

            for collection in collections:
                collection_data = {
                    "collection_id": collection["id"].split("/")[-1],
                    "collection_name": collection["title"],
                    "products_count": collection["products_count"],
                }

                ClientCollections.objects.update_or_create(
                    collection_id=collection_data["collection_id"],
                    shop_id=shop_id,
                    defaults={
                        "collection_name": collection_data["collection_name"],
                        "products_count": collection_data["products_count"],
                        "status": False,
                    },
                )

            return Response(
                {"message": "Collections updated successfully"},
                status=status.HTTP_200_OK,
            )

        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#######################################################################################################
# ██   ██ ██ ███████ ████████  ██████  ██████  ██    ██ 
# ██   ██ ██ ██         ██    ██    ██ ██   ██  ██  ██  
# ███████ ██ ███████    ██    ██    ██ ██████    ████   
# ██   ██ ██      ██    ██    ██    ██ ██   ██    ██    
# ██   ██ ██ ███████    ██     ██████  ██   ██    ██    
#######################################################################################################
                                                      
# ⁡⁣⁢⁣status api endpoint ⁡





