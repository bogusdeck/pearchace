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
from datetime import datetime, timedelta
from django.utils import timezone
import pytz
from django.views.decorators.http import require_GET
import shopify
from django.views.decorators.csrf import csrf_protect
from django.core.exceptions import ObjectDoesNotExist
from shopify_app.models import (
    Client,
    Usage,
    Subscription,
    SortingPlan,
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
    async_cron_sort_product_order,
    async_sort_product_order,
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
             "subscription_status":user.member,
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
            usage = Usage.objects.get(shop_id=client.shop_id)
            subscription = Subscription.objects.get(subscription_id=usage.subscription_id)
            sorting_plan = SortingPlan.objects.get(plan_id=subscription.plan_id)

            sort_limit = sorting_plan.sort_limit
            available_sorts = sort_limit - usage.sorts_count

            return Response(
                {
                    "available_sorts": available_sorts,
                    "total_sorts": sort_limit,
                    "used_sorts": usage.sorts_count,
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_graph(request):
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
        
        shop_id = user.shop_id  

        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')

        try:
            start_date = datetime.strptime(start_date_str, "%d/%m/%Y").date()
            end_date = datetime.strptime(end_date_str, "%d/%m/%Y").date()

            adjusted_end_date = end_date - timedelta(days=1)

            if start_date > adjusted_end_date:
                return Response({"error": "Start date must be earlier than the day before end date."}, status=status.HTTP_400_BAD_REQUEST)

            delta = adjusted_end_date - start_date
            date_list = [start_date + timedelta(days=i) for i in range(delta.days + 1)]

            revenue_data = {date: 0 for date in date_list}

            revenue_entries = ClientGraph.objects.filter(shop_id=shop_id, date__range=[start_date, adjusted_end_date])

            for entry in revenue_entries:
                revenue_data[entry.date] = entry.revenue

            dates_data = [{"date": date.strftime("%d/%m/%Y"), "revenue": revenue_data[date]} for date in date_list]

            # top 5 products globally on the basis of REVENUE
            top_products_by_revenue = ClientProducts.objects.filter(shop_id=shop_id)\
                .order_by('-total_revenue')[:5] 
            
            top_products_revenue_data = [
                {
                    'product_id': product.product_id,
                    'product_name': product.product_name,
                    'total_revenue': product.total_revenue,
                }
                for product in top_products_by_revenue
            ]

            # top 5 products globally on the basis of SALES
            top_products_by_sales = ClientProducts.objects.filter(shop_id=shop_id)\
                .order_by('-total_sold_units')[:5]  
            
            top_products_sales_data = [
                {
                    'product_id': product.product_id,
                    'product_name': product.product_name,
                    'total_sold_units': product.total_sold_units,
                }
                for product in top_products_by_sales
            ]
            
            # top 5 collections globally on the basis of REVENUE
            top_collections_by_revenue = ClientCollections.objects.filter(shop_id=shop_id)\
                .order_by('-collection_total_revenue')[:5]  
            
            top_collections_revenue_data = [
                {
                    'collection_id': collection.collection_id,
                    'collection_name': collection.collection_name,
                    'collection_total_revenue': collection.collection_total_revenue,
                }
                for collection in top_collections_by_revenue
            ]
            
            # top 5 collections globally on the basis of SALES
            top_collections_by_sales = ClientCollections.objects.filter(shop_id=shop_id)\
                .order_by('-collection_sold_units')[:5]  
            
            top_collections_sales_data = [
                {
                    'collection_id': collection.collection_id,
                    'collection_name': collection.collection_name,
                    'collection_sold_units': collection.collection_sold_units,
                }
                for collection in top_collections_by_sales
            ]

            # Construct the final response
            response_data = {
                'dates': dates_data,  # Dates with corresponding revenues
                'top_products_by_revenue': top_products_revenue_data,
                'top_products_by_sales': top_products_sales_data,
                'top_collections_by_revenue': top_collections_revenue_data,
                'top_collections_by_sales': top_collections_sales_data,
            }

            return Response(response_data)

        except ValueError:
            return Response({"error": "Invalid date format. Please use DD/MM/YYYY."}, status=status.HTTP_400_BAD_REQUEST)
        except ClientGraph.DoesNotExist:
            return JsonResponse(
                {"error": "Usage record not found"}, status=status.HTTP_404_NOT_FOUND
            )
        
    except InvalidToken:
        return JsonResponse(
            {"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        return JsonResponse(
            {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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

        print("running")
        shop_url = user.shop_url
        shop_id = user.shop_id

        print(shop_url, shop_id)

        if not shop_url:
            return Response(
                {"error": "Shop URL not found "}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = Client.objects.get(shop_url=shop_url)
            print(client)

            collections = ClientCollections.objects.filter(
                shop_id=shop_id, status=True
            ).order_by("-sort_date")[:5]

            print("collections", collections)

            collections_data = []
            for collection in collections:
                print("collection loop", collection.collection_id)
                algo_name = ClientAlgo.objects.get(algo_id=collection.algo_id).algo_name #
                print(algo_name)
                collections_data.append(
                    {
                        "collection_id": collection.collection_id,
                        "collection_name": collection.collection_name,
                        "product_count": collection.products_count,
                        "sort_date": collection.sort_date,
                        "algo_name": algo_name,
                    }
                )


            if collections_data:
                response_data = {"collections": collections_data}
            else:
                response_data = {"message": "No sort data found"}

            return Response(response_data, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        except ClientCollections.DoesNotExist:
            return Response(
                {"error": "No collections found"}, status=status.HTTP_404_NOT_FOUND
            )

        except ClientAlgo.DoesNotExist:
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
                response_data = {"message": "No usage data found for this client"}

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
        return Response({"errore": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                    algo_id=collection.algo_id
                ).algo_id

                collections_data.append(
                    {
                        "collection_name": collection.collection_name,
                        "collection_id": collection.collection_id,
                        "status": collection.status,
                        "last_sorted_date":collection.sort_date,
                        "product_count":collection.products_count,
                        "algo_id": algo_id
                    }
                )

            return paginator.get_paginated_response(collections_data)

        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except ClientAlgo.DoesNotExist:
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
        try:
            collections = ClientCollections.objects.filter(
                shop_id=client_id, collection_name__icontains=query
            )

            print("collections found: ", collections)
            paginator = ClientCollectionsPagination()
            paginated_collections = paginator.paginate_queryset(
                collections, request
            )
            
            collections_data = []
            for collection in paginated_collections:
                algo_id = ClientAlgo.objects.get(
                    algo_id=collection.algo_id
                ).algo_id
                
                collections_data.append(
                    {
                        "collection_name": collection.collection_name,
                        "collection_id": collection.collection_id,
                        "status": collection.status,
                        "last_sorted_date": collection.sort_date,
                        "product_count":collection.products_count,
                        "algo_id":algo_id
                    }
                )

            return paginator.get_paginated_response(collections_data)
        
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
                algo = ClientAlgo.objects.get(algo_id=algo_id)
                collection.algo = algo
                updated = True
            except ClientAlgo.DoesNotExist:
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
    
@api_view(["POST"]) # not sort button for now
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

        async_cron_sort_product_order.delay(shop_id, collection_id, algo_id, parameters)

        return Response({"message": "Sorting initiated"}, status=status.HTTP_202_ACCEPTED)

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({"errore": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


################################  COLLECTION SETTING #######################################
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
                "collection_name":collection.collection_name,
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
        
        try:
            collection=ClientCollections.objects.filter(
                shop_id = shop_id, collection_id = collection_id
            ).first()

            if not collection:
                return Response(
                    {"error":"Collection not found"}, status=status.HTTP_404_NOT_FOUND
                )
            
            if isinstance(collection.pinned_products, str):
                pinned_product_ids = json.loads(collection.pinned_products)
            else:
                pinned_product_ids = collection.pinned_products
            
            client_products = ClientProducts.objects.filter(collection_id=collection_id)

            pinned_products = []
            non_pinned_products = []

            for product in client_products:
                product_data = {
                    "id" : product.product_id,
                    "title" : product.product_name,
                    "total_inventory" : product.total_inventory,
                    "image_link" : product.image_link,
                }

                if str(product.product_id) in map(str, pinned_product_ids):
                    pinned_products.append(product_data)
                else:
                    non_pinned_products.append(product_data)


            return Response({
                "pinned_products": pinned_products,
                "products":non_pinned_products 
            }, status=status.HTTP_200_OK)
            
        except ObjectDoesNotExist:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)
        
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
                        "id": product.product_id,
                        "title": product.product_name,
                        "total_inventory": product.total_inventory,
                        "image_link": product.image_link
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
@permission_classes([IsAuthenticated]) #not using
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

        async_cron_sort_product_order.delay(shop_id, collection_id, algo_id)

        return Response({"message": "Sorting initiated"}, status=status.HTTP_202_ACCEPTED)
        
    except InvalidToken:
        return Response({"error":"Invalid Token"}, status = status.HTTP_401_UNAUTHORIZED)    
                    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated]) #not using
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
        algo_id = request.data.get("algo_id")
        
        if not collection_id or not algo_id:
            return Response(
                {"error": "Both collection_id and algo_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client_algo = ClientAlgo.objects.get(algo_id=algo_id)
        except ClientAlgo.DoesNotExist:
            return Response({"error": "Algorithm not found for this shop"}, status=status.HTTP_404_NOT_FOUND)

        bucket_parameters = client_algo.bucket_parameters
        if not bucket_parameters:
            return Response({"error": "Bucket parameters not found"}, status=status.HTTP_400_BAD_REQUEST)

        task = async_sort_product_order.delay(shop_id, collection_id, algo_id)

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
                "algo_id": client_algo.algo_id,
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
def update_all_algo(request, algo_id):
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
            client_algo = ClientAlgo.objects.get(algo_id=algo_id, shop=user.shop_id)
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
        algo_id = data.get("clalgo_id")

        if not collection_ids or not algo_id:
            return Response({"error": "collection_ids and algo_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        ClientCollections.objects.filter(shop_id=shop_id, collection_id__in=collection_ids).update(algo=algo_id)

        return Response({"message": "Updated successfully."}, status=status.HTTP_200_OK)

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


############################## GENERAL SETTINGS FOR COLLECTION ####################################
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sort_now(request):  
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
            usage = Usage.objects.get(shop_id=shop_id)
            subscription = Subscription.objects.get(subscription_id=usage.subscription_id)
            sorting_plan = SortingPlan.objects.get(plan_id=subscription.plan_id)
            sort_limit = sorting_plan.sort_limit
            # available_sorts = sort_limit - usage.sorts_count
            
        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Usage.DoesNotExist:
            return Response(
                {'error': 'Usage not found'}, status=status.HTTP_404_NOT_FOUND
            )
        except SortingPlan.DoesNotExist:
            return Response(
                {'error': 'Sorting Plan not found'}, status=status.HTTP_404_NOT_FOUND
            )
        
        collection_id = request.data.get("collection_id")
        algo_id = request.data.get("algo_id")

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

        if usage.sorts_count <= sort_limit:   
            return Response(
                {"error": "No available sorts remaining for today"},
                status=status.HTTP_403_FORBIDDEN,
            )


        async_sort_product_order.delay(shop_id, collection_id, algo_id)
        return Response({"message": "Sorting initiated"}, status=status.HTTP_202_ACCEPTED)

    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_collection_analytics(request, collection_id):
    try:
        collection = ClientCollections.objects.filter(collection_id=collection_id).first()

        if not collection:
            return JsonResponse({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        # Fetch top 5 products by total revenue
        top_products_by_revenue = ClientProducts.objects.filter(collection_id=collection_id).order_by('-total_revenue')[:5]

        # Fetch top 5 products by total sold units
        top_products_by_sold_units = ClientProducts.objects.filter(collection_id=collection_id).order_by('-total_sold_units')[:5]

        # Prepare response data for products by revenue
        top_revenue_data = [
            {
                "product_id": product.product_id,
                "product_name": product.product_name,
                "total_revenue": product.total_revenue,
            }
            for product in top_products_by_revenue
        ]

        # Prepare response data for products by sold units
        top_sold_units_data = [
            {
                "product_id": product.product_id,
                "product_name": product.product_name,
                "total_sold_units": product.total_sold_units,
            }
            for product in top_products_by_sold_units
        ]

        # Final response structure
        response_data = {
            "collection_id": collection.collection_id,
            "collection_name": collection.collection_name,
            "top_products_by_revenue": top_revenue_data,
            "top_products_by_sold_units": top_sold_units_data,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

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

        default_algo = client.default_algo

        def get_algorithm_description(algo_name):
            descriptions = {
                "Promote New": "Promotes new products based on the number of days they have been listed.",
                "Promote High Revenue Products": "Promotes products with high revenue based on the number of days and percentile.",
                "Promote High Inventory Products": "Promotes products with high inventory based on the number of days and percentile.",
                "Bestsellers": "Promotes products based on sales, sorted from high to low or low to high sales volume",
                "Promote High Variant Availability": "Promotes products with high variant availability based on a variant threshold.",
                "I Am Feeling Lucky": "Randomly Choose Sorting to promote products.",
                "RFM Sort": "Promotes products based on Recency, Frequency, and Monetary value."
            }
            return descriptions.get(algo_name, "Description not available.")


        primary_algorithms = ClientAlgo.objects.filter(is_primary=True)
        primary_algo_data = []
        for algo in primary_algorithms:
            primary_algo_data.append(
                {
                    "algo_id": algo.algo_id,
                    "name": algo.algo_name,
                    "description": get_algorithm_description(algo.algo_name),
                    "default": algo == default_algo
                }
            )


        client_algorithms = ClientAlgo.objects.filter(shop_id=client)
        client_algo_data = []
        for algo in client_algorithms:
            client_algo_data.append(
                {
                    "algo_id": algo.algo_id,
                    "name": algo.algo_name,
                    "number_of_buckets": algo.number_of_buckets,
                    "default": algo == default_algo  
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
            algo = ClientAlgo.objects.get(algo_id=algo_id)
        except ClientAlgo.DoesNotExist:
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
def sorting_rule(request, algo_id):
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
            client_algo = ClientAlgo.objects.get(algo_id=algo_id, shop_id=shop_id)

            algo_data = {
                "algo_id": client_algo.algo_id,
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
from shopify_app.tasks import sort_active_collections

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_global_settings(request):    
    try:
        logger.info("API hit: update_global_settings")
        data = request.data

        auth_header = request.headers.get("Authorization", None)
        if auth_header is None:
            logger.error("Authorization header missing")
            return Response({"error": "Authorization header missing"}, status=status.HTTP_401_UNAUTHORIZED)

        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        if not shop_id:
            logger.error("Shop ID not found in session")
            return Response({"error": "Shop ID not found in session"}, status=status.HTTP_400_BAD_REQUEST)

        client = Client.objects.get(shop_id=shop_id)

        # Schedule frequency update
        if "schedule_frequency" in data and data["schedule_frequency"].strip():
            # Clear existing schedule tasks for this client
            PeriodicTask.objects.filter(name__startswith=f"sort_collections_{client.shop_id}").delete()

            client.schedule_frequency = data["schedule_frequency"]
            logger.info(f"Schedule frequency set to: {data['schedule_frequency']}")

            # Handle schedule based on frequency
            if data["schedule_frequency"] == "hourly":
                interval_schedule, _ = IntervalSchedule.objects.get_or_create(every=1, period=IntervalSchedule.HOURS)
                PeriodicTask.objects.create(
                    interval=interval_schedule,
                    name=f"sort_collections_{client.shop_id}_hourly",
                    task="shopify_app.tasks.sort_active_collections",
                    args=json.dumps([client.id])
                )

            elif data["schedule_frequency"] == "daily":
                crontab_schedule, _ = CrontabSchedule.objects.get_or_create(minute=0, hour=0)  # Midnight
                PeriodicTask.objects.create(
                    crontab=crontab_schedule,
                    name=f"sort_collections_{client.shop_id}_daily",
                    task="shopify_app.tasks.sort_active_collections",
                    args=json.dumps([client.id])
                )

            elif data["schedule_frequency"] == "weekly":
                crontab_schedule, _ = CrontabSchedule.objects.get_or_create(minute=0, hour=0, day_of_week="1")  # Monday
                PeriodicTask.objects.create(
                    crontab=crontab_schedule,
                    name=f"sort_collections_{client.shop_id}_weekly",
                    task="shopify_app.tasks.sort_active_collections",
                    args=json.dumps([client.id])
                )

            elif data["schedule_frequency"] == "custom":
                start_time = data.get("custom_start_time")
                stop_time = data.get("custom_stop_time")
                frequency_in_hours = data.get("custom_frequency_in_hours")

                if start_time and stop_time and frequency_in_hours:
                    start_hour, start_minute = map(int, start_time.split(':'))
                    stop_hour, stop_minute = map(int, stop_time.split(':'))

                    if start_hour >= stop_hour:
                        return Response({"error": "Start time must be before stop time"}, status=status.HTTP_400_BAD_REQUEST)

                    current_hour = start_hour
                    while current_hour < stop_hour:
                        crontab_schedule, _ = CrontabSchedule.objects.get_or_create(minute=start_minute, hour=current_hour)
                        PeriodicTask.objects.create(
                            crontab=crontab_schedule,
                            name=f"sort_collections_{client.shop_id}_custom_{current_hour}",
                            task="shopify_app.tasks.sort_active_collections",
                            args=json.dumps([client.id])
                        )
                        current_hour += frequency_in_hours
                    
                    client.custom_start_time = start_time
                    client.custom_stop_time = stop_time
                    client.custom_frequency_in_hours = frequency_in_hours
                else:
                    return Response({"error": "Invalid custom schedule parameters"}, status=status.HTTP_400_BAD_REQUEST)

        # Update stock location only if it's not an empty string
        if "stock_location" in data and data["stock_location"].strip():
            client.stock_location = data["stock_location"]

        # Update lookback period only if it's a positive integer
        if "lookback_period" in data:
            lookback_period_value = data["lookback_period"]
            # Check if it's a positive integer
            if isinstance(lookback_period_value, int) and lookback_period_value > 0:
                client.lookback_period = lookback_period_value
            elif isinstance(lookback_period_value, str):
                # If it's a string, try to convert it to an integer
                try:
                    value_as_int = int(lookback_period_value)
                    if value_as_int > 0:
                        client.lookback_period = value_as_int
                except ValueError:
                    logger.error("Invalid lookback period value")
                    return Response({"error": "Invalid lookback period value"}, status=status.HTTP_400_BAD_REQUEST)


        client.save()

        return Response({
            "message": "Global settings updated successfully",
            "shop_id": client.shop_id,
            "schedule_frequency": client.schedule_frequency,
            "custom_start_time":client.custom_start_time,
            "custom_stop_time":client.custom_stop_time,
            "custom_frequency_in_hours":client.custom_frequency_in_hours,
            "stock_location": client.stock_location,
            "lookback_period": client.lookback_period
        }, status=status.HTTP_200_OK)

    except Client.DoesNotExist:
        logger.error("Client not found")
        return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Exception occurred: {str(e)}")
        return Response({"error for view": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_and_update_collections(request):
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
# ██████  ██ ██      ██      ██ ███    ██  ██████  
# ██   ██ ██ ██      ██      ██ ████   ██ ██       
# ██████  ██ ██      ██      ██ ██ ██  ██ ██   ███ 
# ██   ██ ██ ██      ██      ██ ██  ██ ██ ██    ██ 
# ██████  ██ ███████ ███████ ██ ██   ████  ██████  ⁡
#######################################################################################################

from shopify_app.api import fetch_order_for_billing

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fetch_last_month_order_count(request):
    # Get the first and last dates of the previous month
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
        if not shop_url:
            return Response(
                {"error": "Shop URL not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        
        today = datetime.today()
        print("today : ",today)
        first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_day_last_month = today.replace(day=1) - timedelta(days=1)

        print("1st day : ",first_day_last_month," last day : ", last_day_last_month)

        order_count = fetch_order_for_billing(shop_url, first_day_last_month, last_day_last_month)
        print("result : ", order_count)

        order_count = 16000
        
        if not order_count:
            return Response({"error": "Error fetching orders"}, status=500)
        
        return Response({"order_count": order_count}, status=status.HTTP_200_OK)
    
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





