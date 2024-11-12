import shopify
from django.shortcuts import redirect
from django.http import JsonResponse
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from rest_framework import status
from shopify_app.models import Client, SortingPlan, Subscription, BillingTokens, Usage
import os
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from dotenv import load_dotenv
from decimal import Decimal
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from datetime import timedelta
import requests
from django.utils import timezone
import requests
import logging

logger = logging.getLogger(__name__)

import uuid
from datetime import datetime, timedelta


load_dotenv()

def generate_temp_token():
    return str(uuid.uuid4())

def get_access_token(shop_url):
    client = Client.objects.get(shop_url=shop_url)
    print("me running")
    return client.access_token


def store_temp_token(shop_url, shop_id, temp_token, expiration_minutes=15):
    expiration_time = timezone.now() + timedelta(minutes=expiration_minutes)
    cutoff_date = timezone.now() - timedelta(days=90)

    BillingTokens.objects.filter(created_at__lt=cutoff_date).delete()


    existing_tokens = BillingTokens.objects.filter(shop_id=shop_id, shop_url=shop_url)

    if existing_tokens.exists():
        existing_tokens.update(status='expired')
        
    BillingTokens.objects.create(
        shop_id=shop_id,
        shop_url=shop_url,
        temp_token=temp_token,
        expiration_time=expiration_time,
        status='active',
        charge_id=''  
    )

    print(f"New token created for shop {shop_id} with shop_url {shop_url}. All previous tokens are marked as expired.")

# GraphQL helper function
def execute_graphql(shop_url, access_token, query, variables=None):
    url = f"https://{shop_url}/admin/api/{os.environ['SHOPIFY_API_VERSION']}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }
    payload = {
        "query": query,
        "variables": variables or {}
    }
    response = requests.post(url, json=payload, headers=headers)
    response_data = response.json()
    
    if "errors" in response_data:
        raise Exception(f"GraphQL errors: {response_data['errors']}")
    
    return response_data["data"]


###################################################################################################
# ██████  ██       █████  ███    ██ ███████     ██████  ██ ██      ██      ██ ███    ██  ██████  
# ██   ██ ██      ██   ██ ████   ██ ██          ██   ██ ██ ██      ██      ██ ████   ██ ██       
# ██████  ██      ███████ ██ ██  ██ ███████     ██████  ██ ██      ██      ██ ██ ██  ██ ██   ███ 
# ██      ██      ██   ██ ██  ██ ██      ██     ██   ██ ██ ██      ██      ██ ██  ██ ██ ██    ██ 
# ██      ███████ ██   ██ ██   ████ ███████     ██████  ██ ███████ ███████ ██ ██   ████  ██████  
###################################################################################################

def create_recurring_charge_graphql(shop_url, shop_id, access_token, plan_id, is_annual):
    logger.info("Starting GraphQL-based creation of recurring charge...")

    logger.debug("Fetching plan details...")
    plan = SortingPlan.objects.get(plan_id=plan_id)
    plan_name = plan.name
    plan_price = float(plan.cost_annual) if is_annual else float(plan.cost_month)
    
    logger.info(f"Billing plan: {plan_name}, Price: {plan_price}")

    url = os.environ.get("BACKEND_URL")
    temp_token = generate_temp_token()
    logger.info(f"Generating new temporary token for billing {temp_token}")
    store_temp_token(shop_url, shop_id, temp_token)
    logger.info("Temp token is stored SUCCESSFULLY")

    # Set the interval based on whether it's annual or monthly
    interval = "ANNUAL" if is_annual else "EVERY_30_DAYS"
    trial_days = 14  

    # Update the GraphQL query to use MoneyInput and set interval directly
    query = """
    mutation appSubscriptionCreate($name: String!, $price: MoneyInput!, $returnUrl: URL!, $trialDays: Int!, $test: Boolean) {
      appSubscriptionCreate(
        name: $name,
        lineItems: [
          {
            plan: {
              appRecurringPricingDetails: {
                price: $price,
                interval: %s  # Set interval directly as an enum value
              }
            }
          }
        ],
        returnUrl: $returnUrl,
        trialDays: $trialDays,
        test: $test
      ) {
        appSubscription {
          id
          status
          trialDays
          lineItems {
            plan {
              pricingDetails {
                ... on AppRecurringPricing {
                  interval
                  price {
                    amount
                  }
                }
              }
            }
          }
        }
        confirmationUrl
        userErrors {
          field
          message
        }
      }
    }
    """ % interval  # Use string formatting to insert interval value

    # Update variables to use MoneyInput for price
    variables = {
        "name": plan_name,
        "price": {"amount": f"{plan_price:.2f}", "currencyCode": "USD"},  # Proper MoneyInput format
        "returnUrl": f"{url}/api/billing/confirm/?temp_token={temp_token}",
        "trialDays": trial_days,
        "test":True
    }

    try:
        response = execute_graphql(shop_url, access_token, query, variables)
        confirmation_url = response["appSubscriptionCreate"]["confirmationUrl"]

        if confirmation_url:
            logger.info("GraphQL Recurring charge created successfully. Confirmation URL generated.")
            return confirmation_url
        else:
            errors = response["appSubscriptionCreate"].get("userErrors", [])
            logger.error(f"GraphQL charge creation failed with errors: {errors}")
            raise Exception("Failed to create recurring charge.")

    except Exception as e:
        logger.error(f"Error in creating recurring charge: {e}")
        raise


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_billing_plan(request):
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        token = auth_header.split(' ')[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        logger.info("Starting billing plan creation with GraphQL...")

        shop_url = user.shop_url
        shop_id = user.shop_id

        if not shop_url:
            return Response({'error': 'Shop URL not found in session'}, status=status.HTTP_400_BAD_REQUEST)

        plan_id = request.data.get('plan_id')
        is_annual = request.data.get('is_annual')

        if plan_id is None:
            return Response({'error': 'Plan ID is missing'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(plan_id, (int, float)):
            return Response({'error': 'Plan ID must be a number'}, status=status.HTTP_400_BAD_REQUEST)

        if is_annual is None:
            return Response({'error': 'is_annual is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(is_annual, bool):
            return Response({'error': 'is_annual must be a boolean'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client.objects.get(shop_id=shop_id)
        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        access_token = client.access_token
        if not access_token:
            return Response({'error': 'Access token is missing'}, status=status.HTTP_400_BAD_REQUEST)

        # Subscription creation or update
        try:
            subscription, created = Subscription.objects.get_or_create(
                shop_id=shop_id,
                defaults={
                    'status': 'pending',
                    'plan_id': plan_id,
                    'is_annual': is_annual,
                }
            )
            
            if not created:
                # Update existing subscription data to reflect pending status and input parameters
                subscription.status = 'pending'
                subscription.plan_id = plan_id
                subscription.is_annual = is_annual
                subscription.updated_at = timezone.now()
                subscription.save()
                logger.info(f"Subscription updated to pending status for shop_id {shop_id}.")
            else:
                logger.info(f"New subscription created with pending status for shop_id {shop_id}.")

        except Exception as e:
            logger.error(f"Error creating or updating subscription for shop_id {shop_id}: {str(e)}")
            return Response({'error': 'Failed to create or update subscription'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info(f"Billing URL generation for {'annual' if is_annual else 'monthly'} plan via GraphQL...")

        # Generate billing URL
        billing_url = create_recurring_charge_graphql(shop_url, shop_id, access_token, plan_id, is_annual)
        logger.info("Billing URL successfully generated via GraphQL.")
        
        return JsonResponse({'billing_url': billing_url}, status=status.HTTP_200_OK)

    except InvalidToken:
        logger.warning("Invalid token encountered.")
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def confirm_billing(request):
    try:
        charge_id = request.GET.get('charge_id')
        temp_token = request.GET.get('temp_token')

        if not charge_id or not temp_token:
            return JsonResponse({'error': 'Missing required parameters'}, status=400)

        try:
            billing_token = BillingTokens.objects.get(temp_token=temp_token, status='active')
            logger.debug(f"billing token retrieved: {billing_token}")

            if billing_token.is_expired():
                return JsonResponse({'error': 'Temporary token has expired'}, status=400)   
               
            shop_id = billing_token.shop_id  
            client = Client.objects.get(shop_id=shop_id)
            shop_url = client.shop_url  
            access_token = client.access_token
            
            success = activate_recurring_charge(shop_url, shop_id, access_token, charge_id)
            if success:
                billing_token.status = 'expired'
                billing_token.charge_id = charge_id
                billing_token.save()
                
                logger.debug(f"Billing token updated with status 'expired' and charge_id: {charge_id}")
            
                client.member = True
                client.save()
                logger.debug(f"Client status updated to member: {client.member}")
             
                frontend_url = os.environ.get('FRONTEND_URL')
                return HttpResponseRedirect(frontend_url)
            else:
                return JsonResponse({'error': 'Failed to activate billing'}, status=400)
        
        except BillingTokens.DoesNotExist:
            return JsonResponse({'error': 'Temporary token is invalid or inactive'}, status=400)
        except Client.DoesNotExist:
            return JsonResponse({'error': 'Client not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
def activate_recurring_charge(shop_url, shop_id, access_token, charge_id):
    logger.debug(f"Starting activate_recurring_charge for shop_url: {shop_url}, shop_id: {shop_id}, charge_id: {charge_id}")

    try:
        # Set up Shopify session
        shopify.Session.setup(api_key=os.environ.get('SHOPIFY_API_KEY'), secret=os.environ.get('SHOPIFY_API_SECRET'))
        session = shopify.Session(shop_url, os.environ.get('SHOPIFY_API_VERSION'), access_token)
        shopify.ShopifyResource.activate_session(session)

        logger.debug("Shopify session activated successfully.")

        # Find the charge using Shopify API
        charge = shopify.RecurringApplicationCharge.find(charge_id)
        logger.debug(f"RecurringApplicationCharge found: {charge}")

        # Activate charge if not already active
        if charge.status == 'accepted':
            charge.activate()
            logger.debug(f"Charge {charge_id} activated successfully.")
        elif charge.status == 'active':
            logger.debug(f"Charge {charge_id} is already active. No action needed.")
        else:
            logger.error(f"Charge {charge_id} status is not accepted or active. Status: {charge.status}")
            return False

        try:
            client = Client.objects.get(shop_id=shop_id)
            logger.debug(f"Client found for shop_id {shop_id}")
            
            subscription = Subscription.objects.get(shop_id=shop_id)
            plan = subscription.plan  
            is_annual = subscription.is_annual  

            # plan = SortingPlan.objects.get(name=charge.name)
            logger.debug(f"Plan found: {plan.name}, associating with subscription for shop_id {shop_id}.")

            if not client.trial_used:
                current_period_start = timezone.now() + timedelta(days=14)
                client.trial_used = True
                client.save(update_fields=['trial_used'])
                logger.debug("14-day trial period set; client.trial_used updated to True.")
            else:
                current_period_start = timezone.now()
                logger.debug("Trial already used; setting current period start to now.")

            period_length = 365 if is_annual else 30
            current_period_end = current_period_start + timedelta(days=period_length)

            # Update existing subscription to active status
            subscription.status = 'active'  
            subscription.current_period_start = current_period_start
            subscription.current_period_end = current_period_end
            subscription.next_billing_date = current_period_end
            subscription.charge_id = charge_id
            subscription.updated_at = timezone.now()
            subscription.save()
            logger.debug(f"Subscription for shop_id {shop_id} updated to active status successfully.")

        except SortingPlan.DoesNotExist:
            logger.error(f"SortingPlan with name '{charge.name}' not found for shop_id {shop_id}.")
            return False
        except Subscription.DoesNotExist:
            logger.error(f"Subscription not found for shop_id {shop_id}. Ensure it is created during billing plan.")
            return False
        except Exception as e:
            logger.exception(f"Error while updating subscription for shop_id {shop_id}: {e}")
            return False

        try:
            usage, created = Usage.objects.get_or_create(
            shop_id=shop_id, 
            subscription=subscription,
            defaults={
                'sorts_count': 0,
                'orders_count': 0,
                'addon_sorts_count': 0,
                'charge_id': charge_id,
                'usage_date': timezone.now().date(), 
                'created_at': timezone.now(),
                'updated_at': timezone.now()
                }
            )

            if created:
                logger.debug(f"New Usage record created for shop_id {shop_id}.")
            else:
                # Update fields for existing usage data
                usage.sorts_count = 0
                usage.addon_sorts_count = 0
                usage.usage_date = timezone.now().date()
                usage.updated_at = timezone.now()
                usage.charge_id = charge_id  
                usage.save()
                logger.debug(f"Existing Usage record updated for shop_id {shop_id}.")
                
        except Usage.DoesNotExist:
            logger.error(f"Usage record not found for shop_id {shop_id}. Ensure it is created during billing plan.")
            return False
    
        except Exception as e:
            logger.exception(f"Error while updating usage for shop_id {shop_id}: {e}")
            return False

        return True

    except Exception as e:
        logger.exception(f"Error occurred while activating recurring charge for shop_id {shop_id} with charge_id {charge_id}: {e}")
        return False


def cancel_active_recurring_charges(shop_url, access_token):
    shopify_graphql_url = f"https://{shop_url}/admin/api/{os.environ.get('SHOPIFY_API_VERSION')}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }


    query = """
    {
        currentAppInstallation {
            activeSubscriptions {
                id
                status
            }
        }
    }
    """


    response = requests.post(shopify_graphql_url, json={'query': query}, headers=headers)
    response_data = response.json()

    if 'errors' in response_data:
        logger.error(f"Error fetching subscriptions: {response_data['errors']}")
        return False

    active_subscriptions = response_data.get("data", {}).get("currentAppInstallation", {}).get("activeSubscriptions", [])

    if not active_subscriptions:
        logger.info(f"No active subscriptions found for shop_url: {shop_url}")
        return True  


    for subscription in active_subscriptions:
        subscription_id = subscription['id']


        cancel_query = """
        mutation appSubscriptionCancel($id: ID!) {
            appSubscriptionCancel(id: $id) {
                userErrors {
                    field
                    message
                }
            }
        }
        """
        variables = {"id": subscription_id}

        
        cancel_response = requests.post(shopify_graphql_url, json={'query': cancel_query, 'variables': variables}, headers=headers)
        cancel_response_data = cancel_response.json()

        if cancel_response_data.get("errors"):
            logger.error(f"Error canceling subscription {subscription_id}: {cancel_response_data['errors']}")
            return False

        user_errors = cancel_response_data.get("data", {}).get("appSubscriptionCancel", {}).get("userErrors", [])
        if user_errors:
            errors = [f"{error['field']}: {error['message']}" for error in user_errors]
            logger.error(f"User errors while canceling subscription {subscription_id}: {errors}")
            return False
        
        logger.info(f"Canceled subscription with ID {subscription_id} for shop_url: {shop_url}")


    client = Client.objects.get(shop_url=shop_url)
    shop_id = client.shop_id
    client.member=False
    client.save()
    
    subscription = Subscription.objects.filter(shop_id=shop_id, status='active').first()
    if subscription:
        subscription.status = 'cancelled'
        subscription.cancelled_at = timezone.now()
        subscription.save()
        logger.info(f"Subscription for shop_id {shop_id} cancelled.")

    
    BillingTokens.objects.filter(shop_id=shop_id).delete()
    logger.info(f"Deleted all BillingTokens for shop_id {shop_id}.")

    return True


@api_view(['GET'])
@permission_classes([AllowAny])
@csrf_exempt    
def handle_app_uninstall(request): # need changes
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        logger.error('Authorization header missing')
        return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        token = auth_header.split(' ')[1]
        jwt_auth = JWTAuthentication()

        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        
        shop_url = user.shop_url
        access_token = user.access_token
        if not shop_url:
            logger.error('Shop URL not found in session for user: %s', user)
            return Response({'error': 'Shop url not found in session'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Ensure access token is retrieved correctly
        access_token = get_access_token(shop_url)
        if not access_token:
            logger.error('Access token not found for shop_url: %s', shop_url)
            return Response({'error': 'Access token not found in session'}, status=status.HTTP_400_BAD_REQUEST)   

        # Cancel active recurring charges using GraphQL
        is_cancelled = cancel_active_recurring_charges(shop_url, access_token)

        if is_cancelled:
            logger.info('Successfully handled app uninstall for shop_url: %s', shop_url)
            return Response({'status': 'App uninstall handled successfully'}, status=200)
        else:
            logger.error('Failed to cancel recurring charges for shop_url: %s', shop_url)
            return Response({'error': 'Failed to cancel recurring charges'}, status=status.HTTP_400_BAD_REQUEST)
        
    except InvalidToken:
        logger.error('Invalid token provided during app uninstall')
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.exception('Error occurred while handling app uninstall: %s', str(e))
        return Response({'error': str(e)}, status=400)

      
#######################################################################################################################################
#  ██████  ███    ██ ███████       ████████ ██ ███    ███ ███████     ██████   █████  ██    ██ ███    ███ ███████ ███    ██ ████████ 
# ██    ██ ████   ██ ██               ██    ██ ████  ████ ██          ██   ██ ██   ██  ██  ██  ████  ████ ██      ████   ██    ██    
# ██    ██ ██ ██  ██ █████   █████    ██    ██ ██ ████ ██ █████       ██████  ███████   ████   ██ ████ ██ █████   ██ ██  ██    ██    
# ██    ██ ██  ██ ██ ██               ██    ██ ██  ██  ██ ██          ██      ██   ██    ██    ██  ██  ██ ██      ██  ██ ██    ██    
#  ██████  ██   ████ ███████          ██    ██ ██      ██ ███████     ██      ██   ██    ██    ██      ██ ███████ ██   ████    ██    
#######################################################################################################################################


def create_one_time_charge(shop_url, access_token, charge_name, charge_price, return_url):
    shopify_graphql_url = f"https://{shop_url}/admin/api/{os.environ.get('SHOPIFY_API_VERSION')}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }

    mutation = """
    mutation AppPurchaseOneTimeCreate($name: String!, $price: MoneyInput!, $returnUrl: URL!) {
      appPurchaseOneTimeCreate(
        name: $name,
        price: $price,
        returnUrl: $returnUrl,
        test : true
      ) {
        userErrors {
          field
          message
        }
        appPurchaseOneTime {
          createdAt  
          id
        }
        confirmationUrl  
      }
    }
    """

    variables = {
        "name": charge_name,
        "price": {"amount": charge_price, "currencyCode": "USD"},
        "returnUrl": return_url,
    }

    response = requests.post(shopify_graphql_url, json={'query': mutation, 'variables': variables}, headers=headers)
    response_data = response.json()
    logger.debug(f"response.json : {response_data}")

    # Log any errors if they occur
    if 'errors' in response_data:
        errors = response_data['errors']
        logger.error(f"One-time charge creation failed with errors: {errors}")
        raise Exception("Failed to create one-time charge.")

    user_errors = response_data.get('data', {}).get('appPurchaseOneTimeCreate', {}).get('userErrors', [])
    if user_errors:
        error_messages = [f"{error['field']}: {error['message']}" for error in user_errors]
        logger.error(f"GraphQL user errors: {error_messages}")
        raise Exception("Failed to create one-time charge due to user errors.")
    
    charge = response_data['data']['appPurchaseOneTimeCreate'].get('appPurchaseOneTime')
    confirmation_url = response_data.get('data', {}).get('appPurchaseOneTimeCreate', {}).get('confirmationUrl')

    if charge:
        charge_id = charge.get('id')
        logger.debug(f"Charge ID: {charge_id}")
        logger.debug(f"Confirmation URL: {confirmation_url}")
        return charge_id, confirmation_url  
    else:
        return None, None  



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def purchase_additional_sorts(request):
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        token = auth_header.split(' ')[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        
        shop_url = user.shop_url
        shop_id = user.shop_id

        if not shop_url:
            return Response({'error': 'Shop url not found'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client.objects.get(shop_id=shop_id)
            access_token = client.access_token

            additional_sorts = request.data.get('sorts', 100)
            charge_name = f"Purchase {additional_sorts} Additional Sorts"
            charge_price = float(5.00)
            
            logger.debug(f"{additional_sorts} for {charge_price} is being initiated...")

            url = os.environ.get('BACKEND_URL')  
            temp_token = generate_temp_token()
            logger.debug("Temp token generated")
            store_temp_token(shop_url, shop_id, temp_token)  
            logger.debug("Temp token stored successfully")
            
            return_url = f"{url}/api/billing/confirm/?temp_token={temp_token}&sorts={additional_sorts}"
            logger.debug("Return URL generated")

            charge_id, billing_url = create_one_time_charge(shop_url, access_token, charge_name, charge_price, return_url)

            if charge_id :
                logger.debug(f"charge id : {charge_id}")
                charge_id = charge_id.split('/')[-1]
                billing_token = BillingTokens.objects.get(temp_token=temp_token , status='active')
                billing_token.charge_id = charge_id
                billing_token.save()
                logger.debug("billing token charge id saved in db")
                
            if billing_url:
                logger.debug(f"Billing URL: {billing_url}")
                return Response({'billing_url': billing_url}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'failed to create one-time charge'}, status=status.HTTP_400_BAD_REQUEST)

        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

    except InvalidToken:
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.exception(f"Error occurred while processing additional sorts purchase: {e}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def extra_sort_confirm(request):
    try:
        charge_id = request.GET.get('charge_id')
        temp_token = request.GET.get('temp_token')
        additional_sorts = int(request.GET.get('sorts', 100))  

        if not charge_id or not temp_token:
            return JsonResponse({'error': 'Missing required parameters'}, status=400)

        try:
            # Fetch Billing Token 
            billing_token = BillingTokens.objects.get(temp_token=temp_token, status='active')
            if billing_token.is_expired():
                return JsonResponse({'error': 'Temporary token has expired'}, status=400)
            
            shop_id = billing_token.shop_id

            # Fetch Client
            client = Client.objects.get(shop_id=shop_id)
            subscription = Subscription.objects.filter(shop_id=shop_id, status='active').first()
            if not subscription:
                return JsonResponse({'error': 'Active subscription not found'}, status=404)


            # Update addon_sorts_count in Usage
            usage = Usage.objects.filter(shop_id=shop_id, subscription=subscription).first()
            if not usage:
                usage = Usage.objects.create(
                    shop_id=shop_id,
                    subscription=subscription,
                    usage_date=timezone.now().date(),
                    addon_sorts_count=additional_sorts
                )
            else:
                usage.addon_sorts_count += additional_sorts
                usage.save()

            billing_token.status = 'expired'
            billing_token.save()
            
            frontend_url = os.environ.get('FRONTEND_URL')
            return HttpResponseRedirect(frontend_url)

        except BillingTokens.DoesNotExist:
            return JsonResponse({'error': 'Temporary token is invalid or inactive'}, status=400)
        except Client.DoesNotExist:
            return JsonResponse({'error': 'Client not found'}, status=404)
        except Exception as e:
            logger.exception(f"Error occurred while confirming extra sort: {e}")
            return JsonResponse({'error': str(e)}, status=400)

    except Exception as e:
        logger.exception(f"Error occurred during extra sort confirmation: {e}")
        return JsonResponse({'error': str(e)}, status=400)