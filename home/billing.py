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


load_dotenv()


def decimal_to_float(data):
    if isinstance(data, Decimal):
        return float(data)
    if isinstance(data, dict):
        return {k: decimal_to_float(v) for k, v in data.items()}
    if isinstance(data, list):
        return [decimal_to_float(i) for i in data]
    return data


import logging

logger = logging.getLogger(__name__)

import uuid
from datetime import datetime, timedelta

# Function to generate a temporary token
def generate_temp_token():
    return str(uuid.uuid4())


def store_temp_token(shop_url, shop_id, temp_token, expiration_minutes=15):
    expiration_time = timezone.now() + timedelta(minutes=expiration_minutes)

    try:
        billing_token = BillingTokens.objects.get(shop_id=shop_id, shop_url=shop_url)

        billing_token.temp_token = temp_token
        billing_token.expiration_time = expiration_time
        billing_token.status = 'active'
        billing_token.save()

    except BillingTokens.DoesNotExist:
        BillingTokens.objects.create(
            shop_id=shop_id,
            shop_url=shop_url,
            temp_token=temp_token,
            expiration_time=expiration_time,
            status='active'
        )


import logging
from django.utils import timezone
import shopify

logger = logging.getLogger('shopify_django_app')

def get_selected_plan(request):
    plan_id = request.GET.get('plan_id')
    print("chl rha hu mai")
    return SortingPlan.objects.get(plan_id=plan_id)


def get_access_token(shop_url):
    client = Client.objects.get(shop_url=shop_url)
    print("me running")
    return client.access_token

def activate_recurring_charge(shop_url, shop_id, access_token, charge_id):
    logger.debug(f"Starting activate_recurring_charge for shop_url: {shop_url}, shop_id: {shop_id}, charge_id: {charge_id}")

    try:
        shopify.Session.setup(api_key=os.environ.get('SHOPIFY_API_KEY'), secret=os.environ.get('SHOPIFY_API_SECRET'))
        session = shopify.Session(shop_url, os.environ.get('SHOPIFY_API_VERSION'), access_token)
        shopify.ShopifyResource.activate_session(session)

        logger.debug("Shopify session activated successfully.")

        charge = shopify.RecurringApplicationCharge.find(charge_id)
        logger.debug(f"RecurringApplicationCharge found: {charge}")

        if charge.status == 'accepted':
            # Activate the charge if it's accepted
            charge.activate()
            logger.debug(f"Charge {charge_id} activated successfully.")

        elif charge.status == 'active':
            logger.debug(f"Charge {charge_id} is already active. No action needed.")

        else:
            logger.error(f"Charge {charge_id} status is not accepted or active. Status: {charge.status}")
            return False

        # Now handle the subscription logic, regardless of whether we activated the charge or not
        try:
            subscription = Subscription.objects.get(shop_id=shop_id)
            logger.debug(f"Subscription found for shop_id {shop_id}")

            # Update the subscription fields
            subscription.status = 'active'
            subscription.current_period_start = timezone.now()
            subscription.current_period_end = subscription.current_period_start + timezone.timedelta(days=30)
            subscription.next_billing_date = subscription.current_period_end
            subscription.updated_at = timezone.now()
            subscription.save()
            logger.debug(f"Subscription for shop_id {shop_id} updated successfully.")

        except Subscription.DoesNotExist:
            # If the subscription does not exist, fetch the plan and create a new subscription
            logger.debug(f"No subscription found for shop_id {shop_id}, creating a new subscription.")
            try:
                plan = SortingPlan.objects.get(name=charge.name)
                logger.debug(f"Plan found: {plan.name}, creating subscription for shop_id {shop_id}.")

                Subscription.objects.create(
                    shop_id=shop_id,
                    plan=plan,
                    status='active',
                    current_period_start=timezone.now(),
                    current_period_end=timezone.now() + timezone.timedelta(days=30),
                    next_billing_date=timezone.now() + timezone.timedelta(days=30),
                )
                logger.debug(f"New subscription created successfully for shop_id {shop_id}.")

            except SortingPlan.DoesNotExist:
                logger.error(f"SortingPlan with name '{charge.name}' not found for shop_id {shop_id}.")
                return False
            except Exception as e:
                logger.exception(f"Error while creating subscription for shop_id {shop_id}: {e}")
                return False

        return True

    except Exception as e:
        logger.exception(f"Error occurred while activating recurring charge for shop_id {shop_id} with charge_id {charge_id}: {e}")
        return False


def cancel_active_recurring_charges(shop_url, access_token):
    shopify.Session.setup(api_key=os.environ.get('SHOPIFY_API_KEY'), secret=os.environ.get('SHOPIFY_API_SECRET'))
    session = shopify.Session(shop_url, os.environ.get('SHOPIFY_API_VERSION'), access_token)
    shopify.ShopifyResource.activate_session(session)

    logger.debug(f"Fetching all recurring application charges for shop_url: {shop_url}")

    try:
        # Fetch all recurring charges
        all_charges = shopify.RecurringApplicationCharge.find()
        logger.debug(f"Total charges found: {len(all_charges)}")
        
        # Filter active charges
        active_charges = [charge for charge in all_charges if charge.status == 'active']
        
        if not active_charges:
            logger.info(f"No active charges found for shop_url: {shop_url}")
        else:
            for charge in active_charges:
                charge.cancel()
                logger.info(f"Canceled charge with ID {charge.id} for shop_url: {shop_url}")

        # Update the subscription status in your models
        client = Client.objects.get(shop_url=shop_url)
        shop_id = client.shop_id

        subscription = Subscription.objects.filter(shop_id=shop_id, status='active').first()
        if subscription:
            subscription.status = 'cancelled'
            subscription.cancelled_at = timezone.now()
            subscription.save()
            logger.info(f"Subscription for shop_id {shop_id} cancelled.")

        # Optionally delete the BillingTokens for the shop
        BillingTokens.objects.filter(shop_id=shop_id).delete()
        logger.info(f"Deleted all BillingTokens for shop_id {shop_id}.")

    except Exception as e:
        logger.exception(f"Error occurred while canceling recurring charges for shop_url: {shop_url}: {e}")


###################################################################################################
# ██████  ██       █████  ███    ██ ███████     ██████  ██ ██      ██      ██ ███    ██  ██████  
# ██   ██ ██      ██   ██ ████   ██ ██          ██   ██ ██ ██      ██      ██ ████   ██ ██       
# ██████  ██      ███████ ██ ██  ██ ███████     ██████  ██ ██      ██      ██ ██ ██  ██ ██   ███ 
# ██      ██      ██   ██ ██  ██ ██      ██     ██   ██ ██ ██      ██      ██ ██  ██ ██ ██    ██ 
# ██      ███████ ██   ██ ██   ████ ███████     ██████  ██ ███████ ███████ ██ ██   ████  ██████  
###################################################################################################


def create_recurring_charge(shop_url, access_token, plan_id, is_annual, shop_id):
    print("Creation of recurring charge ......")
    
    # Shopify session setup
    shopify.Session.setup(api_key=os.environ.get('SHOPIFY_API_KEY'), secret=os.environ.get('SHOPIFY_API_SECRET'))
    session = shopify.Session(shop_url, os.environ.get('SHOPIFY_API_VERSION'), access_token)
    shopify.ShopifyResource.activate_session(session)

    # Fetch the plan details
    print('Getting plan.....')
    plan = SortingPlan.objects.get(plan_id=plan_id)
    plan_name = plan.name
    plan_price = float(plan.cost_annual) if is_annual else float(plan.cost_month)
    
    print(f"Billing plan: {plan_name}, Price: {plan_price}")
    
    url = os.environ.get('BACKEND_URL')

    # Generate and store the temporary token
    temp_token = generate_temp_token()
    store_temp_token(shop_url ,shop_id , temp_token)  

    charge = shopify.RecurringApplicationCharge({
        "name": plan_name,
        "price": plan_price,
        "trial_days": 14,
        "test": True,
        "return_url": f"{url}/api/billing/confirm/?temp_token={temp_token}",
        "terms": f"{plan_name} subscription with {'annual' if is_annual else 'monthly'} billing"
    })
    
    print("Charge....", charge)
    
    if charge.save():
        return charge.confirmation_url
    else:
        errors = charge.errors.full_messages()
        print(f"Charge save failed with errors: {errors}")
        raise Exception("Failed to create recurring charge.")


# View to create a billing plan and redirect for confirmation
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
        
        print("Billing plan creating...")

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
        
        print(f"Shop URL: {shop_url}, Access Token: {access_token}, Plan ID: {plan_id}")
        print(f"Billing URL generation for {'annual' if is_annual else 'monthly'} plan...")

        refresh = RefreshToken.for_user(user)
        temp_token = refresh.access_token
        temp_token.set_exp(lifetime=timedelta(minutes=10))
        
        billing_url = create_recurring_charge(shop_url, access_token, plan_id, is_annual, shop_id)
        print(billing_url)
        
        return JsonResponse({'billing_url': billing_url}, status=status.HTTP_200_OK)

    except InvalidToken:
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
# View to handle billing confirmation
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


            if billing_token.is_expired():
                return JsonResponse({'error': 'Temporary token has expired'}, status=400)

            
            shop_id = billing_token.shop_id  
        
            client = Client.objects.get(shop_id=shop_id)
            shop_url = client.shop_url  
            access_token = client.access_token
            
            success = activate_recurring_charge(shop_url, shop_id, access_token, charge_id)
            if success:
                billing_token.status = 'expired'
                billing_token.save()
                
                client.member = True
                client.save()

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
    

@api_view(['GET'])
@permission_classes([AllowAny])
@csrf_exempt    
def handle_app_uninstall(request):
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
        
        access_token = get_access_token(shop_url)
        if not access_token:
            logger.error('Access token not found for shop_url: %s', shop_url)
            return Response({'error': 'Access token not found in session'}, status=status.HTTP_400_BAD_REQUEST)   
        
        cancel_active_recurring_charges(shop_url, access_token)
        logger.info('Successfully handled app uninstall for shop_url: %s', shop_url)
        return Response({'status': 'App uninstall handled successfully'}, status=200)
        
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
    shopify.Session.setup(api_key=os.environ.get('SHOPIFY_API_KEY'), secret=os.environ.get('SHOPIFY_API_SECRET'))
    session = shopify.Session(shop_url, os.environ.get('SHOPIFY_API_VERSION'), access_token)
    shopify.ShopifyResource.activate_session(session)
    
    charge = shopify.ApplicationCharge({
        "name": charge_name,
        "price": charge_price,
        "return_url": return_url,
        "test": True  
    })
    
    if charge.save():
        return charge.confirmation_url
    else:
        errors = charge.errors.full_messages()
        print(f"One-time charge save failed with errors: {errors}")
        raise Exception("Failed to create one-time charge.")
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def purchase_additional_sorts(request):
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        # Extract and validate JWT token
        token = auth_header.split(' ')[1]
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_url = user.shop_url
        shop_id = user.shop_id

        if not shop_url:
            return Response({'error': 'Shop url not found'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Fetch the client object
            client = Client.objects.get(shop_id=shop_id)
            access_token = client.access_token

            # Retrieve the number of additional sorts from request data (default to 100)
            additional_sorts = request.data.get('sorts', 100)  
            charge_name = f"Purchase {additional_sorts} Additional Sorts"
            charge_price = 5.00  # Assuming a fixed price of $5 per additional sorts

            # Prepare the return URL for billing confirmation
            url = os.environ.get('BACKEND_URL')  
            temp_token = generate_temp_token()
            store_temp_token(shop_url ,shop_id , temp_token)  
            return_url = f"{url}/api/billing/confirm/?temp_token={temp_token}"
            
            # Create the one-time charge using the Shopify API
            billing_url = create_one_time_charge(shop_url, access_token, charge_name, charge_price, return_url)

            if billing_url:
                return Response({'billing_url': billing_url}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to create one-time charge'}, status=status.HTTP_400_BAD_REQUEST)

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

            # Update the charge_id field in Subscription
            subscription.charge_id = charge_id
            subscription.save()

            # Update addon_sorts_count in Usage
            usage = Usage.objects.filter(shop_id=shop_id, subscription=subscription).first()
            if not usage:
                # Create a new usage entry if not found for the current period
                usage = Usage.objects.create(
                    shop_id=shop_id,
                    subscription=subscription,
                    usage_date=timezone.now().date(),
                    addon_sorts_count=additional_sorts
                )
            else:
                # Add additional sorts to the existing usage
                usage.addon_sorts_count += additional_sorts
                usage.save()

            # Expire billing token after successful update
            billing_token.status = 'expired'
            billing_token.save()
            
            frontend_url = os.environ.get('FRONTEND_URL')
            return HttpResponseRedirect(frontend_url)


        except BillingTokens.DoesNotExist:
            return JsonResponse({'error': 'Temporary token is invalid or inactive'}, status=400)
        except Client.DoesNotExist:
            return JsonResponse({'error': 'Client not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)