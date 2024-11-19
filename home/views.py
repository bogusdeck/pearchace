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
from .email import send_welcome_email
from shopify_app.models import (
    Client,
    Usage,
    Subscription,
    SortingPlan,
    ClientCollections,
    ClientProducts,
    ClientGraph,
    ClientAlgo,
    History
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

import logging
logger = logging.getLogger(__name__)

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
            logger.warning("Shopify authentication required - missing shop_url or access_token.")
            return JsonResponse({"error": "Shopify authentication required"}, status=403)

        logger.info(f"Fetching client data for shop URL: {shop_url}")
        shop_data = fetch_client_data(shop_url, access_token)

        if not shop_data:
            logger.error("Failed to fetch client data from Shopify")
            return JsonResponse({"error": "Failed to fetch client data from Shopify"}, status=500)

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
                logger.info("Parsed created_at date successfully.")
            except ValueError:
                logger.warning("Invalid date format for created_at; set to None.")
                created_at = None

        logger.info("Retrieving default algorithm.")
        default_algo = get_object_or_404(ClientAlgo, algo_id=1)

        logger.info("Updating or creating client data in the database.")
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
                "timezone": timezone,
                "createdateshopify": created_at,
                "default_algo": default_algo
            },
        )
    
        newcomer = "false"

        if created:
            logger.info("New client created, setting default values.")
            client.member = False
            client.trial_used = False
            client.lookback_period = 30     
            client.custom_start_time = None
            client.custom_stop_time = None
            client.custom_frequency_in_hours = None
            client.stock_location = 'all'  
            newcomer = "true"
            status, body, headers = send_welcome_email(email, name)
            if status == 202:
                logger.info(f"Welcome Email sent Successfully to {email}")
            else:
                logger.error(f"Failed to send welcome email to {email}")
            
        client.save()
        
        refresh = RefreshToken.for_user(client)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        frontend_url = os.environ.get("FRONTEND_URL")
        logger.debug(f"Frontend URL: {frontend_url}")
        logger.debug(f"Generated access token: {access_token}")
        
        redirect_url = f"{frontend_url}?access_token={access_token}&refresh_token={refresh_token}&shop_url={shop_url}&created={newcomer}"
        logger.info("Redirecting to frontend with tokens and shop URL.")
        
        return redirect(redirect_url)

    except Exception as e:
        logger.exception("An error occurred in the index function.")
        return JsonResponse({"error": str(e)}, status=500)
    
@api_view(["GET"])  # First API called by frontend to show client name and URL on the dashboard
@permission_classes([IsAuthenticated])  # Fetch and store collection done
def get_client_info(request):   
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.warning("Authorization header missing.")
        return Response(
            {"error": "Authorization header missing"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    try:
        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()

        logger.info("Validating JWT token.")
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        if not shop_id:
            logger.error("Shop ID not found in user session.")
            return Response(
                {"error": "Shop ID not found in session"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(f"Initiating collection fetch for shop ID: {shop_id}")
        async_fetch_and_store_collections.delay(shop_id)

        logger.info("Returning client information to frontend.")
        return Response(
            {
                "client_id": user.shop_id,
                "shop_url": user.shop_url,
                "shop_name": user.shop_name,
                "subscription_status": user.member,
                "message": "Collection fetch initiated."
            },
            status=status.HTTP_200_OK,
        )

    except InvalidToken:
        logger.warning("Invalid token provided.")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.exception("An error occurred in get_client_info.")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])  # Return the available sorts left for client to use based on its usage and subscriptions
def available_sorts(request):  
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.warning("Authorization header missing.")
        return JsonResponse(
            {"error": "Authorization header missing"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        token = auth_header.split(" ")[1]

        jwt_auth = JWTAuthentication()

        logger.info("Validating JWT token.")
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_url = user.shop_url

        if not shop_url:
            logger.error("Shop URL not found in token.")
            return JsonResponse(
                {"error": "Shop URL not found in token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            logger.info(f"Fetching client data for shop URL: {shop_url}")
            client = Client.objects.get(shop_url=shop_url)
            usage = Usage.objects.get(shop_id=client.shop_id)
            subscription = Subscription.objects.get(subscription_id=usage.subscription_id)
            sorting_plan = SortingPlan.objects.get(plan_id=subscription.plan_id)

            sort_limit = sorting_plan.sort_limit
            sort_limit += usage.addon_sorts_count
            available_sorts = sort_limit - usage.sorts_count

            logger.info(f"Available sorts: {available_sorts}, Total sorts: {sort_limit}, Used sorts: {usage.sorts_count}")

            return Response(
                {
                    "available_sorts": available_sorts,
                    "total_sorts": sort_limit,
                    "used_sorts": usage.sorts_count,
                },
                status=status.HTTP_200_OK,
            )

        except Usage.DoesNotExist:
            logger.warning("Usage record not found.")
            return JsonResponse(
                {"error": "Usage record not found"}, status=status.HTTP_404_NOT_FOUND
            )
        
        except Subscription.DoesNotExist:
            logger.warning("Subscription record not found.")
            return JsonResponse(
                {"error": "Subscription record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except SortingPlan.DoesNotExist:
            logger.warning("Sorting plan record not found.")
            return JsonResponse(
                {"error": "Sorting plan record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    except InvalidToken:
        logger.warning("Invalid token provided.")
        return JsonResponse(
            {"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logger.exception("An error occurred in available_sorts.")
        return JsonResponse(
            {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_graph(request):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.warning("Authorization header missing.")
        return JsonResponse(
            {"error": "Authorization header missing"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        token = auth_header.split(" ")[1]

        jwt_auth = JWTAuthentication()

        logger.info("Validating JWT token.")
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_url = user.shop_url

        if not shop_url:
            logger.error("Shop URL not found in token.")
            return JsonResponse(
                {"error": "Shop URL not found in token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        shop_id = user.shop_id  
        currency = user.currency
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')

        try:
            logger.info(f"Processing date range: {start_date_str} to {end_date_str}")
            start_date = datetime.strptime(start_date_str, "%d/%m/%Y").date()
            end_date = datetime.strptime(end_date_str, "%d/%m/%Y").date()

            adjusted_end_date = end_date - timedelta(days=1)

            if start_date > adjusted_end_date:
                logger.warning("Start date must be earlier than the day before end date.")
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
                'currency': currency,
                'dates': dates_data,  
                'top_products_by_revenue': top_products_revenue_data,
                'top_products_by_sales': top_products_sales_data,
                'top_collections_by_revenue': top_collections_revenue_data,
                'top_collections_by_sales': top_collections_sales_data,
            }

            logger.info("Returning the graph data.")
            return Response(response_data)

        except ValueError:
            logger.warning("Invalid date format provided.")
            return Response({"error": "Invalid date format. Please use DD/MM/YYYY."}, status=status.HTTP_400_BAD_REQUEST)
        except ClientGraph.DoesNotExist:
            logger.warning(f"No revenue entries found for shop ID: {shop_id} between {start_date_str} and {end_date_str}.")
            return JsonResponse(
                {"error": "Usage record not found"}, status=status.HTTP_404_NOT_FOUND
            )

    except InvalidToken:
        logger.warning("Invalid token provided.")
        return JsonResponse(
            {"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logger.exception("An error occurred in get_graph.")
        return JsonResponse(
            {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def last_active_collections(request):
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
            collections = ClientCollections.objects.filter(
                shop_id=shop_id, status=True
            ).order_by("-sort_date")[:5].select_related("algo")

            collections_data = [
                {
                    "collection_id": collection.collection_id,
                    "collection_name": collection.collection_name,
                    "product_count": collection.products_count,
                    "sort_date": collection.sort_date,
                    "algo_name": collection.algo.algo_name,  
                }
                for collection in collections
            ]

            if collections_data:
                response_data = {"collections": collections_data}
            else:
                response_data = {"message": "No sort data found"}

            return Response(response_data, status=status.HTTP_200_OK)

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
@permission_classes([IsAuthenticated])  # give the last sorted date globally
def get_last_sorted_time(request, client_id):  # working not tested
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.warning("Authorization header missing")
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
            logger.error("Shop URL not found for user: %s", user)
            return Response(
                {"error": "Shop URL not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = Client.objects.get(shop_url=shop_url)
            logger.info("Client found: %s", client)

            if str(client.shop_id) != str(client_id):
                logger.warning("Client ID mismatch: provided %s, expected %s", client_id, client.shop_id)
                return Response(
                    {"error": "Client ID mismatch"}, status=status.HTTP_403_FORBIDDEN
                )

            latest_usage = (
                Usage.objects.filter(shop_id=shop_id).order_by("-updated_at").first()
            )

            if latest_usage:
                logger.info("Last sorted time for client %s: %s", client_id, latest_usage.updated_at)
                response_data = {"last_sorted_time": latest_usage.updated_at}
            else:
                logger.info("No usage data found for client %s", client_id)
                response_data = {"message": "No usage data found for this client"}

            return Response(response_data, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            logger.error("Client with shop_url %s not found", shop_url)
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        except Usage.DoesNotExist:
            logger.warning("No usage data found for shop_id %s", shop_id)
            return Response(
                {"error": "No usage data found"}, status=status.HTTP_404_NOT_FOUND
            )

    except InvalidToken:
        logger.warning("Invalid token received")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("An error occurred: %s", e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class ClientCollectionsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

@api_view(["GET"])
@permission_classes([IsAuthenticated])  # all client collections given to the frontend with pagination (page size = 10)
def get_client_collections(request, client_id):  # working and tested
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.warning("Authorization header missing")
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
            logger.error("Shop URL not found in session for user: %s", user)
            return Response(
                {"error": "Shop URL not found in session"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            client = Client.objects.get(shop_url=shop_url)
            logger.info("Client found: %s", client)

            if str(client.shop_id) != str(client_id):
                logger.warning("Client ID mismatch: provided %s, expected %s", client_id, client.shop_id)
                return Response(
                    {"error": "Client ID mismatch"}, status=status.HTTP_403_FORBIDDEN
                )

            # Get filter and pageSize parameters from request
            filter_param = int(request.query_params.get("filter", 0))  # Default to 0
            page_size = int(request.query_params.get("pageSize", 10))  # Default page size is 10

            # Filter collections based on filter_param
            if filter_param == 1:
                client_collections = ClientCollections.objects.filter(
                    shop_id=shop_id, status=True  # Active collections only
                )
            elif filter_param == 2:
                client_collections = ClientCollections.objects.filter(
                    shop_id=shop_id, status=False  # Inactive collections only
                )
            elif filter_param == 3:
                client_collections = ClientCollections.objects.filter(
                    shop_id=shop_id, never_active=True  # Collections where never_active is True
                )
            else:
                client_collections = ClientCollections.objects.filter(shop_id=shop_id)  # All collections

            client_collections = client_collections.order_by("collection_id")
            logger.info("Fetched %d collections for client %s", client_collections.count(), client_id)

            # Paginate with custom page size
            paginator = ClientCollectionsPagination()
            paginator.page_size = page_size
            paginated_collections = paginator.paginate_queryset(client_collections, request)

            collections_data = []
            for collection in paginated_collections:
                try:
                    algo_id = ClientAlgo.objects.get(algo_id=collection.algo_id).algo_id
                    collections_data.append(
                        {
                            "collection_name": collection.collection_name,
                            "collection_id": collection.collection_id,
                            "status": collection.status,
                            "last_sorted_date": collection.sort_date,
                            "product_count": collection.products_count,
                            "algo_id": algo_id,
                        }
                    )
                    logger.debug("Collection added to response: %s", collection.collection_id)
                except ClientAlgo.DoesNotExist:
                    logger.error("Sorting algorithm for collection %s not found", collection.collection_id)
                    return Response(
                        {"error": "Sorting algorithm not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            logger.info("Paginated response ready for client %s", client_id)
            return paginator.get_paginated_response(collections_data)

        except Client.DoesNotExist:
            logger.error("Client with shop_url %s not found", shop_url)
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

    except InvalidToken:
        logger.warning("Invalid token received")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])  # allows searching through all collections of client
def search_collections(request, client_id):  # working and tested
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.warning("Authorization header missing")
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
            logger.error("Shop URL not found for user: %s", user)
            return Response(
                {"error": "Shop URL not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        query = request.GET.get("q", "")
        logger.info("Searching collections for client_id %s with query: '%s'", client_id, query)

        try:
            collections = ClientCollections.objects.filter(
                shop_id=client_id, collection_name__icontains=query
            )
            logger.info("Found %d collections matching query for client_id %s", collections.count(), client_id)

            paginator = ClientCollectionsPagination()
            paginated_collections = paginator.paginate_queryset(collections, request)
            
            collections_data = []
            for collection in paginated_collections:
                try:
                    algo_id = ClientAlgo.objects.get(algo_id=collection.algo_id).algo_id
                    collections_data.append(
                        {
                            "collection_name": collection.collection_name,
                            "collection_id": collection.collection_id,
                            "status": collection.status,
                            "last_sorted_date": collection.sort_date,
                            "product_count": collection.products_count,
                            "algo_id": algo_id,
                        }
                    )
                    logger.debug("Added collection %s to response data", collection.collection_id)
                except ClientAlgo.DoesNotExist:
                    logger.error("Sorting algorithm for collection %s not found", collection.collection_id)
                    return Response(
                        {"error": "Sorting algorithm not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            logger.info("Paginated response prepared for client_id %s", client_id)
            return paginator.get_paginated_response(collections_data)

        except ClientCollections.DoesNotExist:
            logger.warning("No collections found for client_id %s with query: '%s'", client_id, query)
            return Response(
                {"error": "Collections not found"}, status=status.HTTP_404_NOT_FOUND
            )

    except InvalidToken:
        logger.warning("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])  # celery implemented fetch and store products
def update_collection(request, collection_id):  # working not tested
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.warning("Authorization header missing")
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
            logger.error("Shop ID not found for user: %s", user)
            return Response(
                {"error": "Shop ID not found in session"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            collection = ClientCollections.objects.get(shop_id=shop_id, collection_id=collection_id)
            client = Client.objects.get(shop_id=shop_id)
            logger.info("Fetched collection %s and client %s", collection_id, client.shop_url)
        except Client.DoesNotExist:
            logger.warning("Client with shop_id %s not found", shop_id)
            return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)
        except ClientCollections.DoesNotExist:
            logger.warning("Collection %s not found for shop_id %s", collection_id, shop_id)
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        status_value = request.data.get("status")
        algo_id = request.data.get("algo_id")
        updated = False

        if status_value is not None:
            collection.status = status_value
            collection.never_active = False
            updated = True
            logger.info("Updated status for collection %s to %s", collection_id, status_value)

        if algo_id is not None:
            try:
                algo = ClientAlgo.objects.get(algo_id=algo_id)
                collection.algo = algo
                logger.info("Updated algo for collection %s to %s", collection_id, algo_id)
            except ClientAlgo.DoesNotExist:
                logger.error("Algorithm with ID %s not found", algo_id)
                return Response(
                    {"error": "Algorithm not found"}, status=status.HTTP_404_NOT_FOUND
                )

        days = client.lookback_period

        if updated:
            collection.save()
            if collection.status:
                shop_url = user.shop_url
                logger.info("Starting asynchronous product fetch for collection %s", collection_id)
                async_fetch_and_store_products.delay(shop_url, shop_id, collection_id, days)
                return Response(
                    {"message": "Collection updated, product fetching initiated asynchronously"},
                    status=status.HTTP_200_OK,
                )
            else:
                logger.info("Collection %s updated successfully without product fetch", collection_id)
                return Response(
                    {"message": "Collection updated successfully"},
                    status=status.HTTP_200_OK,
                )
        else:
            logger.warning("No valid fields provided to update for collection %s", collection_id)
            return Response(
                {"error": "No valid fields provided to update"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except InvalidToken:
        logger.warning("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["POST"])
@permission_classes([IsAuthenticated])  # Celery is used for sorting in queue
def update_product_order(request):
    try:
        # Check for Authorization header
        auth_header = request.headers.get("Authorization", None)
        if auth_header is None:
            logger.warning("Authorization header missing")
            return Response(
                {"error": "Authorization header missing"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Validate the JWT token
        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        if not shop_id:
            logger.error("Shop ID not found in JWT token for user %s", user)
            return Response(
                {"error": "Shop ID not found in JWT token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve the client based on shop_id
        try:
            client = Client.objects.get(shop_id=shop_id)
            logger.info("Client %s retrieved for shop ID %s", client, shop_id)
        except Client.DoesNotExist:
            logger.warning("Client with shop ID %s not found", shop_id)
            return Response(
                {"error": "Client not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get collection_id and algo_id from request data
        collection_id = request.data.get("collection_id")
        algo_id = request.data.get("algo_id")

        if not collection_id:
            logger.warning("Collection ID missing in request")
            return Response(
                {"error": "Collection ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not algo_id:
            logger.warning("Algorithm ID missing in request")
            return Response(
                {"error": "Algorithm ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve the client collection based on collection_id and shop_id
        try:
            client_collections = ClientCollections.objects.get(shop_id=shop_id, collection_id=collection_id)
            logger.info("Collection %s found for client %s", collection_id, client)
        except ClientCollections.DoesNotExist:
            logger.warning("Collection %s for shop ID %s not found", collection_id, shop_id)
            return Response(
                {"error": "Collection not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if access token is available
        access_token = client.access_token
        if not access_token:
            logger.error("Access token not found or expired for client %s", client)
            return Response(
                {"error": "Access token not found for this client or it may have expired, please re-authenticate"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prepare sorting parameters
        parameters_used = client_collections.parameters_used or {}
        parameters = {
            "days": parameters_used.get("days", 7),
            "percentile": parameters_used.get("percentile", 100),
            "variant_threshold": parameters_used.get("variant_threshold", 5.0),
        }
        logger.info("Parameters used for sorting: %s", parameters)

        # Initiate asynchronous sorting task
        async_cron_sort_product_order.delay(shop_id, collection_id, algo_id, parameters)
        logger.info("Sorting initiated for collection %s with algorithm %s", collection_id, algo_id)

        return Response(
            {"message": "Sorting initiated"},
            status=status.HTTP_202_ACCEPTED,
        )

    except InvalidToken:
        logger.warning("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

################################  COLLECTION SETTING #######################################

@api_view(["GET"])
@permission_classes([IsAuthenticated])  # Fetch last sort date for the collection
def fetch_last_sort_date(request):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.warning("Authorization header missing")
        return Response(
            {"error": "Authorization header missing"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        # Validate the JWT token
        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        # Extract shop_id and validate
        shop_id = user.shop_id
        if not shop_id:
            logger.error("Shop ID not found in JWT token for user %s", user)
            return Response(
                {"error": "Shop ID not found in JWT token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get collection_id from query parameters
        collection_id = request.GET.get("collection_id")
        if not collection_id:
            logger.warning("collection_id parameter is missing")
            return Response(
                {"error": "collection_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve client based on shop_id
        try:
            client = Client.objects.get(shop_id=shop_id)
            logger.info("Client %s retrieved for shop ID %s", client, shop_id)
        except Client.DoesNotExist:
            logger.warning("Client with shop ID %s not found", shop_id)
            return Response(
                {"error": "Client not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Retrieve collection based on collection_id and shop_id
        try:
            collection = ClientCollections.objects.get(
                collection_id=collection_id, shop_id=shop_id
            )
            logger.info("Collection %s found for client %s", collection_id, client)
        except ClientCollections.DoesNotExist:
            logger.warning("Collection %s for shop ID %s not found", collection_id, shop_id)
            return Response(
                {"error": "Collection not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get the last sort date or default to "no sort found"
        sort_date = collection.sort_date if collection.sort_date else "no sort found"
        logger.info("Fetched last sort date for collection %s: %s", collection_id, sort_date)

        return Response(
            {
                "collection_id": collection.collection_id,
                "collection_name": collection.collection_name,
                "sort_date": sort_date,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

################################ PINNED PRODUCTS TAB #######################################

@api_view(["GET"])
@permission_classes([IsAuthenticated]) #pagination update needed
def get_products(request, collection_id):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.warning("Authorization header missing in request.")
        return Response(
            {"error": "Authorization header missing"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        # Extract and validate JWT token
        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        # Extract shop_id from the token's user data
        shop_id = user.shop_id
        if not shop_id:
            logger.error("Shop ID not found in JWT token for user %s", user)
            return Response(
                {"error": "Shop ID not found in JWT token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve collection by shop_id and collection_id
        collection = ClientCollections.objects.filter(
            shop_id=shop_id, collection_id=collection_id
        ).first()

        if not collection:
            logger.warning("Collection %s not found for shop ID %s", collection_id, shop_id)
            return Response(
                {"error": "Collection not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Load pinned products list from JSON or directly use if already in list format
        if isinstance(collection.pinned_products, str):
            pinned_product_ids = json.loads(collection.pinned_products)
        else:
            pinned_product_ids = collection.pinned_products

        # Retrieve all products in the specified collection
        client_products = ClientProducts.objects.filter(collection_id=collection_id)
        pinned_products = []
        non_pinned_products = []

        # Separate pinned and non-pinned products
        for product in client_products:
            product_data = {
                "id": product.product_id,
                "title": product.product_name,
                "total_inventory": product.total_inventory,
                "image_link": product.image_link,
            }
            if str(product.product_id) in map(str, pinned_product_ids):
                pinned_products.append(product_data)
            else:
                non_pinned_products.append(product_data)

        logger.info("Successfully fetched products for collection %s", collection_id)
        return Response(
            {
                "pinned_products": pinned_products,
                "products": non_pinned_products
            },
            status=status.HTTP_200_OK
        )

    except ClientCollections.DoesNotExist:
        logger.warning("Collection %s for shop ID %s not found", collection_id, shop_id)
        return Response(
            {"error": "Collection not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    except InvalidToken:
        logger.warning("Invalid token provided in request.")
        return Response(
            {"error": "Invalid token"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        
@api_view(["POST"])
@permission_classes([IsAuthenticated])  
def update_pinned_products(request):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.warning("Authorization header missing in request.")
        return Response(
            {"error": "Authorization header missing"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        # Extract and validate JWT token
        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        # Extract shop_id from the token's user data
        shop_id = user.shop_id
        if not shop_id:
            logger.error("Shop ID not found in JWT token for user %s", user)
            return Response(
                {"error": "Shop ID not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve collection_id and pinned_products from request data
        collection_id = request.data.get("collection_id")
        pinned_products = request.data.get("pinned_products", [])

        if not collection_id:
            logger.warning("Collection ID is required but not provided.")
            return Response(
                {"error": "Collection ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(pinned_products, list):
            logger.warning("Pinned products provided are not in list format.")
            return Response(
                {"error": "Pinned products should be a list of product IDs"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve the client collection and update pinned products
        try:
            client_collection = ClientCollections.objects.get(
                collection_id=collection_id, shop_id=shop_id
            )
        except ClientCollections.DoesNotExist:
            logger.warning("Collection %s not found for shop ID %s", collection_id, shop_id)
            return Response(
                {"error": "Collection not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        client_collection.pinned_products = pinned_products
        client_collection.save()

        logger.info("Pinned products updated successfully for collection %s", collection_id)
        return Response(
            {
                "message": "Pinned products updated successfully",
                "pinned_products": client_collection.pinned_products,
            },
            status=status.HTTP_200_OK,
        )

    except InvalidToken:
        logger.warning("Invalid token provided in request.")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        
@api_view(["GET"])
@permission_classes([IsAuthenticated]) #pagination update needed 
def search_products(request, collection_id):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.warning("Authorization header missing in request.")
        return Response(
            {"error": "Authorization header missing"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        # Extract and validate JWT token
        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        # Extract shop_id from the token's user data
        shop_id = user.shop_id
        if not shop_id:
            logger.error("Shop ID not found in JWT token for user %s", user)
            return Response(
                {"error": "Shop ID not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve search query parameter
        query = request.GET.get("q", "")
        logger.info("Search query received: '%s' for collection %s", query, collection_id)

        # Filter products by shop_id, collection_id, and product name
        products = ClientProducts.objects.filter(
            shop_id=shop_id, collection_id=collection_id, product_name__icontains=query
        )

        if not products.exists():
            logger.info("No products found for shop ID %s, collection ID %s, and query '%s'", shop_id, collection_id, query)
            return Response(
                {"error": "No products found for the given query and collection"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Prepare response data
        products_data = [
            {
                "id": product.product_id,
                "title": product.product_name,
                "total_inventory": product.total_inventory,
                "image_link": product.image_link
            }
            for product in products
        ]
        logger.info("Found %d products matching query '%s' in collection %s", len(products_data), query, collection_id)

        return Response(
            {"products": products_data},
            status=status.HTTP_200_OK
        )

    except ClientProducts.DoesNotExist:
        logger.warning("No products found for collection ID %s", collection_id)
        return Response(
            {"error": "Products not found for given collection"},
            status=status.HTTP_404_NOT_FOUND
        )

    except InvalidToken:
        logger.warning("Invalid token provided in request.")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ProductsPagination(PageNumberPagination):
    page_size = 10  # You can adjust the page size here
    page_size_query_param = 'page_size'
    max_page_size = 100  # Define a max page size limit
    
@api_view(['GET'])
@permission_classes([IsAuthenticated]) #done and tested #pagination needed 
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

        collection_id = request.GET.get("collection_id")
        
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
            product_data = [
                {
                    'product_id' : product['product_id'],
                    'product_name': product['product_name'],
                    'image_link': product['image_link'],
                    'total_inventory': product['total_inventory']
                }
                for product in products
            ]

            return Response(product_data, status=200)
        except ClientProducts.DoesNotExist:
            return Response({'error':'No products found for this collection'}, status=404)
    
    except InvalidToken:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


############################### SORTING SETTINGS ###########################################
@api_view(['POST'])
@permission_classes([IsAuthenticated])  # not using
def post_quick_config(request):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.error("Authorization header missing")
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
            logger.warning("Shop ID not found for user %s", user.id)
            return Response(
                {"error": "Shop ID not found"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        collection_id = request.data.get("collection_id")
        algo_id = request.data.get("algo_id")
        
        if not collection_id or not algo_id:
            logger.warning("Missing collection_id or algo_id in request")
            return Response(
                {"error": "Both collection_id and algo_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info("Initiating sorting for shop_id %s, collection_id %s, algo_id %s", shop_id, collection_id, algo_id)

        # Call to async task for sorting
        async_cron_sort_product_order.delay(shop_id, collection_id, algo_id)
        
        logger.info("Sorting initiated successfully for collection_id %s", collection_id)

        return Response(
            {"message": "Sorting initiated"}, 
            status=status.HTTP_202_ACCEPTED
        )

    except InvalidToken:
        logger.error("Invalid token provided")
        return Response(
            {"error": "Invalid Token"}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

    except Exception as e:
        logger.exception("Unexpected error occurred during quick config API execution")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
                

@api_view(['POST'])
@permission_classes([IsAuthenticated])  # not using
def advance_config(request):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.error("Authorization header missing")
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
            logger.warning("Shop ID not found for user %s", user.id)
            return Response(
                {"error": "Shop ID not found"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        collection_id = request.data.get("collection_id")
        algo_id = request.data.get("algo_id")
        
        if not collection_id or not algo_id:
            logger.warning("Both collection_id and algo_id are required")
            return Response(
                {"error": "Both collection_id and algo_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client_algo = ClientAlgo.objects.get(algo_id=algo_id)
            logger.info("Algorithm found for shop_id %s: %s", shop_id, algo_id)
        except ClientAlgo.DoesNotExist:
            logger.warning("Algorithm not found for shop_id %s, algo_id %s", shop_id, algo_id)
            return Response(
                {"error": "Algorithm not found for this shop"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        bucket_parameters = client_algo.bucket_parameters
        if not bucket_parameters:
            logger.warning("Bucket parameters not found for algo_id %s", algo_id)
            return Response(
                {"error": "Bucket parameters not found"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info("Initiating advanced sorting for shop_id %s, collection_id %s, algo_id %s", shop_id, collection_id, algo_id)

        history_entry = History.objects.create(
            shop_id = client,
            requested_by = "Manual",
            product_count=ClientProducts.objects.filter(shop_id=shop_id,collection_id=collection_id).count(),
            status='Active',
            collection_name=client_collection.collection_name
        )

    
        # Call to async task for sorting
        task = async_sort_product_order.delay(shop_id, collection_id, algo_id, history_entry.id)

        logger.info("Sorting initiated with advanced system, task_id: %s", task.id)

        return Response(
            {"message": "Sorting initiated with advanced system", "task_id": task.id},
            status=status.HTTP_200_OK
        )

    except InvalidToken:
        logger.error("Invalid token provided")
        return Response(
            {"error": "Invalid token"}, 
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    except Exception as e:
        logger.exception("Unexpected error occurred during advanced config API execution")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["POST"])
@permission_classes([IsAuthenticated])  # not tested
def save_client_algorithm(request):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.error("Authorization header missing")
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
            logger.warning("Shop ID not found for user %s", user.id)
            return Response(
                {"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = Client.objects.get(shop_id=shop_id)
            logger.info("Client found for shop_id %s", shop_id)
        except Client.DoesNotExist:
            logger.warning("Client not found for shop_id %s", shop_id)
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        algo_name = request.data.get('algo_name')
        boost_tags = request.data.get('boost_tags', [])
        bury_tags = request.data.get('bury_tags', [])
        bucket_parameters = request.data.get('bucket_parameters', [])

        if not algo_name:
            logger.warning("Algorithm name is missing")
            return Response(
                {"error": "Algorithm name is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not isinstance(boost_tags, list):
            logger.warning("boost_tags is not a list of strings")
            return Response(
                {"error": "boost_tags must be a list of strings"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not isinstance(bury_tags, list):
            logger.warning("bury_tags is not a list of strings")
            return Response(
                {"error": "bury_tags must be a list of strings"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not isinstance(bucket_parameters, list) or not all(isinstance(bp, dict) for bp in bucket_parameters):
            logger.warning("bucket_parameters is not a list of dictionaries")
            return Response(
                {"error": "bucket_parameters must be a list of dictionaries"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Creating the algorithm
        client_algo = ClientAlgo.objects.create(
            shop_id=shop_id,
            algo_name=algo_name,
            boost_tags=boost_tags,
            bury_tags=bury_tags,
            bucket_parameters=bucket_parameters,
            number_of_buckets=len(bucket_parameters),
        )

        logger.info("Algorithm created successfully for shop_id %s, algo_id %s", shop_id, client_algo.algo_id)

        return Response(
            {
                "message": "Algorithm created successfully",
                "algo_id": client_algo.algo_id,
                "algo_name": client_algo.algo_name,
            },
            status=status.HTTP_201_CREATED
        )

    except InvalidToken:
        logger.error("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("Unexpected error occurred during save_client_algorithm API execution")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_all_algo(request, algo_id):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.error("Authorization header missing")
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
            logger.info("Found algorithm with algo_id %s for shop_id %s", algo_id, user.shop_id)
        except ClientAlgo.DoesNotExist:
            logger.warning("Algorithm not found for algo_id %s and shop_id %s", algo_id, user.shop_id)
            raise NotFound("Algorithm not found for this client.")

        data = request.data

        if 'algo_name' in data:
            logger.info("Updating algorithm name to %s", data['algo_name'])
            client_algo.algo_name = data['algo_name']
        if 'bury_tags' in data:
            logger.info("Updating bury_tags to %s", data['bury_tags'])
            client_algo.bury_tags = data['bury_tags']
        if 'boost_tags' in data:
            logger.info("Updating boost_tags to %s", data['boost_tags'])
            client_algo.boost_tags = data['boost_tags']
        if 'bucket_parameters' in data:
            logger.info("Updating bucket_parameters to %s", data['bucket_parameters'])
            client_algo.bucket_parameters = data['bucket_parameters']
        if 'number_of_buckets' in data:
            logger.info("Updating number_of_buckets to %d", data['number_of_buckets'])
            client_algo.number_of_buckets = data['number_of_buckets']

        client_algo.save()

        logger.info("Algorithm with algo_id %s successfully updated", algo_id)

        return Response({"message": "Algorithm updated successfully"}, status=status.HTTP_200_OK)

    except InvalidToken:
        logger.error("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("Unexpected error occurred during update_all_algo API execution")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_collections(request):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.error("Authorization header missing")
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
            logger.warning("Shop ID not found for user: %s", user)
            return Response(
                {"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            collections = ClientCollections.objects.filter(
                shop_id=shop_id, status=True
            )
            logger.info("Fetched active collections for shop_id %s", shop_id)

            collection_data = [
                {
                    "collection_id": collection.collection_id,
                    "collection_name": collection.collection_name,
                }
                for collection in collections
            ]

            logger.info("Returning %d active collections for shop_id %s", len(collection_data), shop_id)
            return Response({"active_collections": collection_data}, status=status.HTTP_200_OK)
        
        except ClientCollections.DoesNotExist:
            logger.warning("No active collections found for shop_id %s", shop_id)
            return Response(
                {"error": "Client's collection not found"}, status=status.HTTP_404_NOT_FOUND
            )

    except InvalidToken:
        logger.error("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("Unexpected error in get_active_collections")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["POST"])
@permission_classes([IsAuthenticated]) # done and tested
def applied_on_active_collection(request):
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.error("Authorization header missing")
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
            logger.warning("Shop ID not found in session for user: %s", user)
            return Response(
                {"error": "Shop ID not found in session"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data
        collection_ids = data.get("collection_ids", [])
        algo_id = data.get("clalgo_id")

        if not collection_ids or not algo_id:
            logger.warning("Missing collection_ids or algo_id in request data for shop_id %s", shop_id)
            return Response(
                {"error": "collection_ids and algo_id are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update collections with the provided algorithm ID
        update_count = ClientCollections.objects.filter(
            shop_id=shop_id, collection_id__in=collection_ids
        ).update(algo=algo_id)

        logger.info(
            "Applied algorithm %s to %d collections for shop_id %s",
            algo_id, update_count, shop_id
        )

        return Response({"message": "Updated successfully."}, status=status.HTTP_200_OK)

    except InvalidToken:
        logger.error("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("Unexpected error in applied_on_active_collection")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

############################## GENERAL SETTINGS FOR COLLECTION ####################################
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sort_now(request):
    try:
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
            logger.warning("Shop ID not found in JWT token for user %s", user)
            return Response(
                {"error": "Shop ID not found in JWT token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            client = Client.objects.get(shop_id=shop_id)
            usage = Usage.objects.get(shop_id=shop_id)
            subscription = Subscription.objects.get(subscription_id=usage.subscription_id)
            sorting_plan = SortingPlan.objects.get(plan_id=subscription.plan_id)
            sort_limit = sorting_plan.sort_limit + usage.addon_sorts_count

            logger.info("Retrieved sort limit (%d) for shop_id %s", sort_limit, shop_id)

        except Client.DoesNotExist:
            logger.error("Client not found for shop_id %s", shop_id)
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Usage.DoesNotExist:
            logger.error("Usage record not found for shop_id %s", shop_id)
            return Response(
                {"error": "Usage not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Subscription.DoesNotExist:
            logger.error("Subscription not found for shop_id %s", shop_id)
            return Response(
                {"error": "Subscription not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except SortingPlan.DoesNotExist:
            logger.error("Sorting Plan not found for shop_id %s", shop_id)
            return Response(
                {"error": "Sorting Plan not found"}, status=status.HTTP_404_NOT_FOUND
            )

        collection_id = request.data.get("collection_id")
        algo_id = request.data.get("algo_id")

        if not collection_id:
            logger.warning("Collection ID missing in request data for shop_id %s", shop_id)
            return Response(
                {"error": "Collection ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not algo_id:
            logger.warning("Algorithm ID missing in request data for shop_id %s", shop_id)
            return Response(
                {"error": "Algorithm ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if usage.sorts_count >= sort_limit:
            logger.info("Sort limit exceeded for shop_id %s", shop_id)
            return Response(
                {"error": "No available sorts remaining for today"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        history_entry = History.objects.create(
            shop_id = client,
            requested_by = "Manual",
            product_count=ClientProducts.objects.filter(shop_id=shop_id,collection_id=collection_id).count(),
            status='Active',
            collection_name=ClientCollections.objects.get(collection_id=collection_id).collection_name,
        ) 

        async_sort_product_order.delay(shop_id, collection_id, algo_id,history_entry.id)
        logger.info("Sorting initiated for shop_id %s, collection_id %s, algo_id %s", shop_id, collection_id, algo_id)
        
        return Response({"message": "Sorting initiated"}, status=status.HTTP_202_ACCEPTED)

    except InvalidToken:
        logger.error("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("Unexpected error in sort_now")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_collection_settings(request):
    try:
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
            logger.warning("Shop ID not found in JWT token for user %s", user)
            return Response(
                {"error": "Shop ID not found in JWT token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data
        collection_id = data.get("collection_id")
        if not collection_id:
            logger.warning("collection_id is missing in request data for shop_id %s", shop_id)
            return Response(
                {"error": "collection_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            client = Client.objects.get(shop_id=shop_id)
            collection = ClientCollections.objects.get(
                collection_id=collection_id, shop_id=shop_id
            )
            logger.info("Collection %s found for shop_id %s", collection_id, shop_id)

        except Client.DoesNotExist:
            logger.error("Client not found for shop_id %s", shop_id)
            return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)

        except ClientCollections.DoesNotExist:
            logger.error("Collection %s not found for shop_id %s", collection_id, shop_id)
            return Response(
                {"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if "out_of_stock_down" in data:
            collection.out_of_stock_down = data["out_of_stock_down"]
            logger.info("out_of_stock_down set to %s for collection %s", data["out_of_stock_down"], collection_id)

        if "pinned_out_of_stock_down" in data:
            collection.pinned_out_of_stock_down = data["pinned_out_of_stock_down"]
            logger.info("pinned_out_of_stock_down set to %s for collection %s", data["pinned_out_of_stock_down"], collection_id)

        if "new_out_of_stock_down" in data:
            collection.new_out_of_stock_down = data["new_out_of_stock_down"]
            logger.info("new_out_of_stock_down set to %s for collection %s", data["new_out_of_stock_down"], collection_id)

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

    except InvalidToken:
        logger.error("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("Unexpected error in update_collection_settings")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
############################ ANALYTICS TABS FOR COLLECTION ########################################

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_collection_analytics(request, collection_id):
    logger.info("Starting get_collection_analytics API call")
    auth_header = request.headers.get("Authorization", None)
    if auth_header is None:
        logger.error("Authorization header missing")
        return Response(
            {"error": "Authorization header missing"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        token = auth_header.split(" ")[1]
        logger.debug(f"Extracted token: {token}")

        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        
        shop_id = getattr(user, "shop_id", None)
        currency = getattr(user, "currency", "USD")
        # currency = "USD"
        logger.debug(f"User shop_id: {shop_id}, currency: {currency}")

        if not shop_id:
            logger.error("Shop ID not found in JWT token")
            return Response(
                {"error": "Shop ID not found in JWT token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            collection = ClientCollections.objects.filter(collection_id=collection_id).first()
            if not collection:
                logger.error(f"Collection with ID {collection_id} not found")
                return JsonResponse({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

            logger.info(f"Collection found: {collection.collection_name}")

            top_products_by_revenue = ClientProducts.objects.filter(collection_id=collection_id).order_by('-total_revenue')[:5]
            logger.debug(f"Top products by revenue for collection {collection_id}: {top_products_by_revenue}")

            top_products_by_sold_units = ClientProducts.objects.filter(collection_id=collection_id).order_by('-total_sold_units')[:5]
            logger.debug(f"Top products by sold units for collection {collection_id}: {top_products_by_sold_units}")

            top_revenue_data = [
                {
                    "product_id": product.product_id,
                    "product_name": product.product_name,
                    "total_revenue": product.total_revenue,
                }
                for product in top_products_by_revenue
            ]

            top_sold_units_data = [
                {
                    "product_id": product.product_id,
                    "product_name": product.product_name,
                    "total_sold_units": product.total_sold_units,
                }
                for product in top_products_by_sold_units
            ]

            # currency="USD"
            response_data = {
                "currency": currency,
                "collection_id": collection.collection_id,
                "collection_name": collection.collection_name,
                "top_products_by_revenue": top_revenue_data,
                "top_products_by_sold_units": top_sold_units_data,
            }

            logger.info("Successfully generated response data")
            return Response(response_data, status=status.HTTP_200_OK)

        except ClientCollections.DoesNotExist:
            logger.error("Collection not found in database")
            return JsonResponse(
                {"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND
            )

    except InvalidToken:
        logger.error("Invalid token provided")
        return JsonResponse(
            {"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
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
def get_sorting_algorithms(request):
    try:
        # Check for authorization header
        auth_header = request.headers.get("Authorization", None)
        if auth_header is None:
            logger.error("Authorization header missing")
            return Response(
                {"error": "Authorization header missing"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Validate token
        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        if not shop_id:
            logger.warning("Shop ID not found in JWT token for user %s", user)
            return Response(
                {"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch client instance
        try:
            client = Client.objects.get(shop_id=shop_id)
            logger.info("Client found for shop_id %s", shop_id)
        except Client.DoesNotExist:
            logger.error("Client not found for shop_id %s", shop_id)
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Set up default algorithm and descriptions
        default_algo = client.default_algo

        def get_algorithm_description(algo_name):
            descriptions = {
                "Promote New": "Promotes new products based on the number of days they have been listed.",
                "Promote High Revenue Products": "Promotes products with high revenue based on the number of days and percentile.",
                "Promote High Inventory Products": "Promotes products with high inventory based on the number of days and percentile.",
                "Bestsellers": "Promotes products based on sales, sorted from high to low or low to high sales volume",
                "Promote High Variant Availability": "Promotes products with high variant availability based on a variant threshold.",
                "I Am Feeling Lucky": "Randomly chooses sorting to promote products.",
                "RFM Sort": "Promotes products based on Recency, Frequency, and Monetary value."
            }
            return descriptions.get(algo_name, "Description not available.")

        # Retrieve primary algorithms
        primary_algorithms = ClientAlgo.objects.filter(is_primary=True)
        primary_algo_data = []
        for algo in primary_algorithms:
            primary_algo_data.append({
                "algo_id": algo.algo_id,
                "name": algo.algo_name,
                "description": get_algorithm_description(algo.algo_name),
                "default": algo == default_algo
            })
            logger.info("Primary algorithm %s added to response", algo.algo_name)

        # Retrieve client-specific algorithms
        client_algorithms = ClientAlgo.objects.filter(shop_id=client)
        client_algo_data = []
        for algo in client_algorithms:
            client_algo_data.append({
                "algo_id": algo.algo_id,
                "name": algo.algo_name,
                "number_of_buckets": algo.number_of_buckets,
                "default": algo == default_algo
            })
            logger.info("Client algorithm %s added to response for shop_id %s", algo.algo_name, shop_id)

        # Construct response data
        response_data = {
            "primary_algorithms": primary_algo_data,
            "client_algorithms": client_algo_data,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except InvalidToken:
        logger.error("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("Unexpected error in get_sorting_algorithms")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_default_algo(request):
    try:
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
            logger.warning("Shop ID not found in JWT token for user %s", user)
            return Response(
                {"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        algo_id = request.data.get("algo_id")
        if not algo_id:
            logger.error("Algorithm ID is missing in request data")
            return Response(
                {"error": "Algorithm ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            client = Client.objects.get(shop_id=shop_id)
            logger.info("Client found for shop_id %s", shop_id)
        except Client.DoesNotExist:
            logger.error("Client not found for shop_id %s", shop_id)
            return Response(
                {"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            algo = ClientAlgo.objects.get(algo_id=algo_id)
            logger.info("Algorithm with algo_id %s found", algo_id)
        except ClientAlgo.DoesNotExist:
            logger.error("Algorithm not found with algo_id %s", algo_id)
            return Response(
                {"error": "Sorting algorithm not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        client.default_algo = algo
        client.save()
        logger.info("Default algorithm updated to %s for shop_id %s", algo_id, shop_id)

        return Response(
            {
                "message": "Default algorithm updated successfully",
                "default_algo": algo.algo_id,
            },
            status=status.HTTP_200_OK,
        )

    except InvalidToken:
        logger.error("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("Unexpected error in update_default_algo")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sorting_rule(request, algo_id):
    try:
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
            logger.warning("Shop ID not found in JWT token for user %s", user)
            return Response(
                {"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client_algo = ClientAlgo.objects.get(algo_id=algo_id, shop_id=shop_id)
            logger.info("Algorithm found for shop_id %s with algo_id %s", shop_id, algo_id)

            # Construct response data
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
            logger.error("Algorithm not found for shop_id %s with algo_id %s", shop_id, algo_id)
            return Response(
                {"error": "Algorithm not found."},
                status=status.HTTP_404_NOT_FOUND
            )

    except InvalidToken:
        logger.error("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("Unexpected error in sorting_rule")
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


from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
import json
from shopify_app.tasks import sort_active_collections

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_global_settings(request):
    try:
        logger.info("API hit: update_global_settings")
        data = request.data

        # Check for authorization header
        auth_header = request.headers.get("Authorization", None)
        if auth_header is None:
            logger.error("Authorization header missing")
            return Response(
                {"error": "Authorization header missing"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Validate token
        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        # Retrieve shop_id from user
        shop_id = user.shop_id
        if not shop_id:
            logger.warning("Shop ID not found in JWT token for user %s", user)
            return Response(
                {"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get client instance
        client = Client.objects.get(shop_id=shop_id)

        # Update schedule frequency
        if "schedule_frequency" in data and data["schedule_frequency"].strip():
            # Clear existing tasks
            PeriodicTask.objects.filter(name__startswith=f"sort_collections_{client.shop_id}").delete()
            client.schedule_frequency = data["schedule_frequency"]
            logger.info("Schedule frequency set to: %s", data["schedule_frequency"])

            # Handle specific schedule frequencies
            if data["schedule_frequency"] == "hourly":
                interval_schedule, _ = IntervalSchedule.objects.get_or_create(
                    every=1, period=IntervalSchedule.HOURS
                )
                PeriodicTask.objects.create(
                    interval=interval_schedule,
                    name=f"sort_collections_{client.shop_id}_hourly",
                    task="shopify_app.tasks.sort_active_collections",
                    args=json.dumps([client.id]),
                )

            elif data["schedule_frequency"] == "daily":
                crontab_schedule, _ = CrontabSchedule.objects.get_or_create(
                    minute=0, hour=0
                )
                PeriodicTask.objects.create(
                    crontab=crontab_schedule,
                    name=f"sort_collections_{client.shop_id}_daily",
                    task="shopify_app.tasks.sort_active_collections",
                    args=json.dumps([client.id]),
                )

            elif data["schedule_frequency"] == "weekly":
                crontab_schedule, _ = CrontabSchedule.objects.get_or_create(
                    minute=0, hour=0, day_of_week="1"
                )
                PeriodicTask.objects.create(
                    crontab=crontab_schedule,
                    name=f"sort_collections_{client.shop_id}_weekly",
                    task="shopify_app.tasks.sort_active_collections",
                    args=json.dumps([client.id]),
                )

            elif data["schedule_frequency"] == "custom":
                start_time = data.get("custom_start_time")
                stop_time = data.get("custom_stop_time")
                frequency_in_hours = data.get("custom_frequency_in_hours")

                if start_time and stop_time and frequency_in_hours:
                    start_hour, start_minute = map(int, start_time.split(":"))
                    stop_hour, stop_minute = map(int, stop_time.split(":"))

                    if start_hour >= stop_hour:
                        logger.error("Start time must be before stop time")
                        return Response(
                            {"error": "Start time must be before stop time"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    current_hour = start_hour
                    while current_hour < stop_hour:
                        crontab_schedule, _ = CrontabSchedule.objects.get_or_create(
                            minute=start_minute, hour=current_hour
                        )
                        PeriodicTask.objects.create(
                            crontab=crontab_schedule,
                            name=f"sort_collections_{client.shop_id}_custom_{current_hour}",
                            task="shopify_app.tasks.sort_active_collections",
                            args=json.dumps([client.id]),
                        )
                        current_hour += frequency_in_hours

                    client.custom_start_time = start_time
                    client.custom_stop_time = stop_time
                    client.custom_frequency_in_hours = frequency_in_hours
                    logger.info(
                        "Custom schedule created for start: %s, stop: %s, frequency: %s hours",
                        start_time,
                        stop_time,
                        frequency_in_hours,
                    )
                else:
                    logger.error("Invalid custom schedule parameters")
                    return Response(
                        {"error": "Invalid custom schedule parameters"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        # Update stock location if it's not an empty string
        if "stock_location" in data and data["stock_location"].strip():
            client.stock_location = data["stock_location"]

        # Update lookback period if it's a positive integer
        if "lookback_period" in data:
            lookback_period_value = data["lookback_period"]
            if isinstance(lookback_period_value, int) and lookback_period_value > 0:
                client.lookback_period = lookback_period_value
            elif isinstance(lookback_period_value, str):
                try:
                    value_as_int = int(lookback_period_value)
                    if value_as_int > 0:
                        client.lookback_period = value_as_int
                except ValueError:
                    logger.error("Invalid lookback period value")
                    return Response(
                        {"error": "Invalid lookback period value"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        client.save()

        return Response(
            {
                "message": "Global settings updated successfully",
                "shop_id": client.shop_id,
                "schedule_frequency": client.schedule_frequency,
                "custom_start_time": client.custom_start_time,
                "custom_stop_time": client.custom_stop_time,
                "custom_frequency_in_hours": client.custom_frequency_in_hours,
                "stock_location": client.stock_location,
                "lookback_period": client.lookback_period,
            },
            status=status.HTTP_200_OK,
        )

    except Client.DoesNotExist:
        logger.error("Client not found for shop_id: %s", shop_id)
        return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)

    except InvalidToken:
        logger.error("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.exception("Unexpected error in update_global_settings")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_and_update_collections(request):
    try:
        logger.info("API hit: get_and_update_collections")

        # Check for Authorization header
        auth_header = request.headers.get("Authorization", None)
        if not auth_header:
            logger.error("Authorization header missing")
            return Response({"error": "Authorization header missing"}, status=status.HTTP_401_UNAUTHORIZED)

        # Token validation
        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        # Verify shop_id from user
        shop_id = user.shop_id
        if not shop_id:
            logger.error("Shop ID not found")
            return Response({"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST)

        # Get client instance
        try:
            client = Client.objects.get(shop_id=shop_id)
            access_token = client.access_token

            # Fetch collections from Shopify
            collections = fetch_collections(client.shop_url)
            logger.info(f"Fetched {len(collections)} collections for shop_id: {shop_id}")

            # Update or create collections in the database
            for collection in collections:
                collection_data = {
                    "collection_id": collection["id"].split("/")[-1],
                    "collection_name": collection["title"],
                    "products_count": collection.get("products_count", 0),  # Default to 0 if not provided
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

            logger.info("Collections updated successfully")
            return Response(
                {"message": "Collections updated successfully"},
                status=status.HTTP_200_OK,
            )

        except Client.DoesNotExist:
            logger.error("Client not found for shop_id: %s", shop_id)
            return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)

    except JWTAuthentication.exceptions.InvalidToken:
        logger.error("Invalid token")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
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
    try:
        logger.info("API hit: fetch_last_month_order_count")

        auth_header = request.headers.get("Authorization", None)
        if not auth_header:
            logger.error("Authorization header missing")
            return Response({"error": "Authorization header missing"}, status=status.HTTP_401_UNAUTHORIZED)

        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_url = user.shop_url
        if not shop_url:
            logger.error("Shop URL not found for the user")
            return Response({"error": "Shop URL not found"}, status=status.HTTP_400_BAD_REQUEST)

        today = datetime.today()
        first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_day_last_month = today.replace(day=1) - timedelta(days=1)
        logger.debug(f"First and last dates of last month: {first_day_last_month} - {last_day_last_month}")

        order_count = fetch_order_for_billing(shop_url, first_day_last_month, last_day_last_month)
        logger.debug(f"Fetched order count: {order_count}")

        if order_count is None:
            logger.error("Error fetching orders for billing")
            return Response({"error": "Error fetching orders"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"order_count": order_count}, status=status.HTTP_200_OK)

    except JWTAuthentication.exceptions.InvalidToken:
        logger.error("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_subscription_plan(request):
    try:
        logger.info("API hit: current_subscription_plan")

        auth_header = request.headers.get("Authorization", None)
        if not auth_header:
            logger.error("Authorization header missing")
            return Response({"error": "Authorization header missing"}, status=status.HTTP_401_UNAUTHORIZED)

        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_id = user.shop_id
        shop_url = user.shop_url
        if not shop_id:
            logger.error("Shop ID not found for the user")
            return Response({"error": "Shop ID not found"}, status=status.HTTP_400_BAD_REQUEST)
        if not shop_url:
            logger.error("Shop URL not found for the user")
            return Response({"error": "Shop URL not found"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client.objects.get(shop_url=shop_url)
        except Client.DoesNotExist:
            logger.error(f"Client not found for shop URL: {shop_url}")
            return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            usage = Usage.objects.get(shop_id=client.shop_id)
        except Usage.DoesNotExist:
            logger.error(f"Usage data not found for shop ID: {client.shop_id}")
            return Response({"error": "Usage data not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            subscription = Subscription.objects.get(subscription_id=usage.subscription_id)
        except Subscription.DoesNotExist:
            logger.error(f"Subscription not found for subscription ID: {usage.subscription_id}")
            return Response({"error": "Subscription not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            sorting_plan = SortingPlan.objects.get(plan_id=subscription.plan_id)
        except SortingPlan.DoesNotExist:
            logger.error(f"Sorting plan not found for plan ID: {subscription.plan_id}")
            return Response({"error": "Sorting plan not found"}, status=status.HTTP_404_NOT_FOUND)

        sort_limit = sorting_plan.sort_limit
        available_sorts = sort_limit - usage.sorts_count

        subscription_data = {
            'billing_cycle': subscription.is_annual,
            'current_period_start': subscription.current_period_start,
            'next_billing_date': subscription.next_billing_date,
            'plan_name': subscription.plan.name,
            'sort_remaining': available_sorts,
            'total_sorts': sort_limit,
            'extra_sort': usage.addon_sorts_count,
        }

        logger.debug(f"Subscription data for {shop_url}: {subscription_data}")
        return Response(subscription_data, status=status.HTTP_200_OK)

    except JWTAuthentication.exceptions.InvalidToken:
        logger.error("Invalid token provided")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)    
     

#######################################################################################################
# ██   ██ ██ ███████ ████████  ██████  ██████  ██    ██ 
# ██   ██ ██ ██         ██    ██    ██ ██   ██  ██  ██  
# ███████ ██ ███████    ██    ██    ██ ██████    ████   
# ██   ██ ██      ██    ██    ██    ██ ██   ██    ██    
# ██   ██ ██ ███████    ██     ██████  ██   ██    ██    
#######################################################################################################                                        
# ⁡⁣⁢⁣status api endpoint ⁡





