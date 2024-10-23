import shopify
from django.shortcuts import redirect
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from rest_framework import status
from shopify_app.models import Client, SortingPlan, Subscription
import os
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from dotenv import load_dotenv
from decimal import Decimal
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


load_dotenv()


def decimal_to_float(data):
    if isinstance(data, Decimal):
        return float(data)
    if isinstance(data, dict):
        return {k: decimal_to_float(v) for k, v in data.items()}
    if isinstance(data, list):
        return [decimal_to_float(i) for i in data]
    return data



def activate_recurring_charge(shop_url, access_token, charge_id):
    # Initialize a Shopify session
    shopify.Session.setup(api_key=os.environ.get('SHOPIFY_API_KEY'), secret=os.environ.get('SHOPIFY_API_SECRET'))
    session = shopify.Session(shop_url, os.environ.get('SHOPIFY_API_VERSION'), access_token)
    shopify.ShopifyResource.activate_session(session)
    
    # Find and activate the charge
    charge = shopify.RecurringApplicationCharge.find(charge_id)
    
    if charge.status == 'accepted':
        charge.activate()
        subscription = Subscription.objects.get(shop_id=shop_url)
        subscription.status = 'active'
        subscription.current_period_end = timezone.now() + timezone.timedelta(days=30)  # Assuming 30-day billing cycle
        subscription.next_billing_date = subscription.current_period_end
        subscription.save()

        return True
    else:
        return False

def cancel_active_recurring_charges(shop_url, access_token):
    shopify.Session.setup(api_key=os.environ.get('SHOPIFY_API_KEY'), secret=os.environ.get('SHOPIFY_API_SECRET'))
    session = shopify.Session(shop_url, os.environ.get('SHOPIFY_API_VERSION'), access_token)
    shopify.ShopifyResource.activate_session(session)

    # Get all active recurring charges and cancel them
    active_charges = shopify.RecurringApplicationCharge.find(status='active')
    for charge in active_charges:
        charge.cancel()
    
    client = Client.objects.get(shop_url=shop_url)
    shop_id = client.shop_id

    subscription = Subscription.objects.filter(shop_id=shop_id, status='active').first()
    if subscription:
        subscription.status = 'cancelled'
        subscription.cancelled_at = timezone.now()
        subscription.save()

def create_one_time_charge(shop_url, access_token, charge_name, charge_price, return_url):
    # Initialize a Shopify session
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
            additional_sorts = request.GET.get('sorts', 100)  
            charge_name = f"Purchase {additional_sorts} Additional Sorts"
            charge_price = 5.00  

            url = os.environ.get('BACKEND_URL')
            return_url = f"{url}/api/billing/confirm/"  
            
            billing_url = create_one_time_charge(shop_url, access_token, charge_name, charge_price, return_url)
            return billing_url 

        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
    
    except InvalidToken:
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({'error': str(e)}, status=400)

# SHOPIFY 
def create_recurring_charge(shop_url, access_token, plan_id, is_annual):
    print("creation of recurring charge ......")
    
    # Shopify session setup
    shopify.Session.setup(api_key=os.environ.get('SHOPIFY_API_KEY'), secret=os.environ.get('SHOPIFY_API_SECRET'))
    session = shopify.Session(shop_url, os.environ.get('SHOPIFY_API_VERSION'), access_token)
    shopify.ShopifyResource.activate_session(session)
    
    # Fetch the plan details
    print('getting plan.....')
    plan = SortingPlan.objects.get(plan_id=plan_id)
    print(plan)
    
    plan_name = plan.name
    # Determine the price based on whether the subscription is annual or monthly
    plan_price = float(plan.cost_annual) if is_annual else float(plan.cost_month)
    print(f"Billing plan: {plan_name}, Price: {plan_price}")
    
    url = os.environ.get('BACKEND_URL')

    charge = shopify.RecurringApplicationCharge({
        "name": plan_name,
        "price": plan_price,
        "trial_days": 14,
        "return_url": f"{url}/api/billing/confirm/",
        "terms": f"{plan_name} subscription with {'annual' if is_annual else 'monthly'} billing"
    })
    
    print("charge....", charge)
    
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
        if not isinstance(plan_id, (int, float)):  # Ensure plan_id is a number (int or float)
            return Response({'error': 'Plan ID must be a number'}, status=status.HTTP_400_BAD_REQUEST)

        if is_annual is None:
            return Response({'error': 'is_annual is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(is_annual, bool):  # Ensure is_annual is a boolean
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

        billing_url = create_recurring_charge(shop_url, access_token, plan_id, is_annual)
        
        print(billing_url)
        # return billing_url
        return JsonResponse({'billing_url': billing_url}, status=status.HTTP_200_OK)

    except InvalidToken:
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    


# View to handle billing confirmation
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def confirm_billing(request):
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
            return Response({'error': 'Shop url not found in session'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client.objects.get(shop_id=shop_id)
            access_token = client.access_token
            charge_id = request.GET.get('charge_id')
            if not charge_id:
                return JsonResponse({'error': 'Charge ID is missing'}, status=400)

            success = activate_recurring_charge(shop_url, access_token, charge_id)
            if success:
                return JsonResponse({'status': 'Billing activated successfully'}, status=200)
            else:
                return JsonResponse({'error': 'Failed to activate billing'}, status=400)
            
        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
        except SortingPlan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=404)
    
    except InvalidToken:
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({'error': str(e)}, status=400)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@csrf_exempt
def handle_app_uninstall(request):
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        return Response({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        token = auth_header.split(' ')[1]
        jwt_auth = JWTAuthentication()

        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        
        shop_url = user.shop_url
        access_token =user.access_token
        if not shop_url:
            return Response({'error': 'Shop url not found in session'}, status=status.HTTP_400_BAD_REQUEST)
        
        access_token = get_access_token(shop_url)
        if not access_token:
            return Response({'error': 'access token not found in session'}, status=status.HTTP_400_BAD_REQUEST)   
        
        cancel_active_recurring_charges(shop_url, access_token)
        return Response({'status': 'App uninstall handled successfully'}, status=200)
        
    except InvalidToken:
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({'errorr': str(e)}, status=400)

    
def get_selected_plan(request):
    plan_id = request.GET.get('plan_id')
    print("chl rha hu mai")
    return SortingPlan.objects.get(plan_id=plan_id)


def get_access_token(shop_url):
    client = Client.objects.get(shop_url=shop_url)
    print("me running")
    return client.access_token