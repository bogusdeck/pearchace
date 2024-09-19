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


# Function to safely convert Decimal fields to JSON serializable format
def decimal_to_float(data):
    if isinstance(data, Decimal):
        return float(data)
    if isinstance(data, dict):
        return {k: decimal_to_float(v) for k, v in data.items()}
    if isinstance(data, list):
        return [decimal_to_float(i) for i in data]
    return data

# Shopify Billing Logic
def create_recurring_charge(shop_url, access_token, plan_id):
    shopify.Session.setup(api_key=os.environ.get('SHOPIFY_API_KEY'), secret=os.environ.get('SHOPIFY_API_SECRET'))
    session = shopify.Session(shop_url, os.environ.get('SHOPIFY_API_VERSION'), access_token)
    shopify.ShopifyResource.activate_session(session)
    

    plan = SortingPlan.objects.get(plan_id=plan_id)
    plan_name = plan.name
    plan_price = plan.cost_month

    charge = shopify.RecurringApplicationCharge({
        "name": plan_name,
        "price": plan_price,
        "test": True,
        "trial_days": 14,
        "return_url": "https://pearch.vercel.app",
        "terms": "Your plan description here"
    })

    if charge.save():
        return charge.confirmation_url
    else:
        # Print full error messages
        errors = charge.errors.full_messages()
        print(f"Charge save failed with errors: {errors}")
        raise Exception("Failed to create recurring charge.")


def activate_recurring_charge(shop_url, access_token, charge_id):
    # Initialize a Shopify session
    shopify.Session.setup(api_key=os.environ.get('SHOPIFY_API_KEY'), secret=os.environ.get('SHOPIFY_API_SECRET'))
    session = shopify.Session(shop_url, os.environ.get('SHOPIFY_API_VERSION'), access_token)
    shopify.ShopifyResource.activate_session(session)
    
    # Find and activate the charge
    charge = shopify.RecurringApplicationCharge.find(charge_id)
    
    if charge.status == 'accepted':
        charge.activate()
        # Update the subscription in the local database
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


# View to create a billing plan and redirect for confirmation
@api_view(['GET'])
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
        
        shop_url = user.shop_url
        shop_id = user.shop_id

        if not shop_url:
            return Response({'error': 'Shop url not found in session'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan_id = request.GET.get('plan_id')
            client = Client.objects.get(shop_id=shop_id)
            if not plan_id:
                return JsonResponse({'error': 'Plan ID is missing'}, status=400)

            access_token = client.access_token

            if not shop_id or not access_token:
                return JsonResponse({'error': 'Shop id or access token is missing'}, status=400)

            billing_url = create_recurring_charge(shop_url, access_token, plan_id)
            return redirect(billing_url)
        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
        except SortingPlan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=404)
        
    except InvalidToken:
        return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({'error': str(e)}, status=400)


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


# App Uninstall Webhook to handle charge cancellation
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
        # client = Client.objects.get(shop_id=shop_id)
        # access_token = client.access_token   
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
