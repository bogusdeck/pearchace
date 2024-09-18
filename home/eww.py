from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django.utils import timezone
import json
import shopify
from shopify_app.models import SortingPlan, Subscription , Client
import os
from dotenv import load_dotenv

load_dotenv()

def initialize_shopify_session(shop_url, access_token):
    api_key = os.environ.get('SHOPIFY_API_KEY')
    secret_key = os.environ.get('SHOPIFY_API_SECRET')
    shopify.Session.setup(api_key=api_key, secret=secret_key)
    session = shopify.Session(shop_url, access_token)
    shopify.ShopifyResource.activate_session(session)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_billing(request):
    auth_header = request.headers.get('Authorization', None)
    if auth_header is None:
        return JsonResponse({'error': 'Authorization header missing'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        token = auth_header.split(' ')[1]  

        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)

        shop_url = user.shop_url
        shop_id = user.shop_id
        access_token = user.access_token
        if not shop_url:
            return JsonResponse({'error': 'Shop URL not found in token'}, status=status.HTTP_400_BAD_REQUEST)

        data = json.loads(request.body)
        plan_id = data.get('plan_id')

        try:
            plan = SortingPlan.objects.get(plan_id=plan_id)
            response = create_shopify_billing_subscription(plan, shop_url)

            if response['status'] == 'success':
            
                Subscription.objects.create(
                    shop_id=shop_id,
                    plan=plan,
                    status='pending',
                    current_period_start=timezone.now(),
                    current_period_end=timezone.now() + timezone.timedelta(days=30),  
                    is_on_trial=True,
                    trial_start_date=timezone.now(),
                    trial_end_date=timezone.now() + timezone.timedelta(days=14)  
                )
            
            return JsonResponse(response)
        except SortingPlan.DoesNotExist:
            return JsonResponse({'error': 'Plan not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    except InvalidToken:
        return JsonResponse({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def create_shopify_billing_subscription(plan, shop_url):
    try:
        charge = shopify.RecurringApplicationCharge()
        charge.name = plan.name
        charge.price = plan.cost_month
        charge.return_url = 'https://devbackend.pearchace.com/'
        
        if charge.save():
            return {
                'status': 'success',
                'billing_url': charge.confirmation_url
            }
        else:
            raise Exception('Failed to create billing subscription')
    except Exception as e:
        raise Exception(f'Error creating billing subscription: {str(e)}')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def billing_confirmation(request):
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

        charge_id = request.GET.get('charge_id')
        if not charge_id:
            return JsonResponse({'error': 'Charge ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        initialize_shopify_session(shop_url, user.access_token)

        try:
            charge = shopify.RecurringApplicationCharge.find(charge_id)
            if charge.status == 'accepted':
                charge.activate()
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Charge not accepted'}, status=400)
        except shopify.ShopifyError as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    except InvalidToken:
        return JsonResponse({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# from django.shortcuts import get_object_or_404
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.utils import timezone
# from shopify_app.models import Client, SortingPlan, Subscription
# from datetime import timedelta
# import json

# @csrf_exempt
# def initiate_billing(request):
#     """Endpoint to initiate the billing process for a client."""
#     if request.method == 'POST':
#         try:
#             client = get_object_or_404(Client, shopify_domain=request.session.get('shopify_domain'))
#             data = json.loads(request.body)
#             plan_id = data.get('plan_id')


#             sorting_plan = get_object_or_404(SortingPlan, id=plan_id)

#             if sorting_plan.is_trial:
#                 start_date = timezone.now()
#                 end_date = start_date + timedelta(days=sorting_plan.duration_days)
#                 Subscription.objects.create(
#                     client=client,
#                     sorting_plan=sorting_plan,
#                     start_date=start_date,
#                     end_date=end_date,
#                     is_active=True
#                 )
#                 return JsonResponse({'message': 'Free trial initiated', 'trial_end': end_date}, status=200)

                
#             subscription_url = create_billing_url(client, sorting_plan)
#             return JsonResponse({'billing_url': subscription_url}, status=200)

#         except Exception as e:
#             return JsonResponse({'error': str(e)}, status=400)

#     return JsonResponse({'error': 'Invalid request method'}, status=405)


# def create_billing_url(client, sorting_plan):
#     """Helper function to create a billing URL for the client based on the sorting plan."""
#     billing_type = "monthly" if sorting_plan.is_monthly else "annual"
#     billing_url = f"https://billing.shopify.com/subscribe/{client.shopify_domain}/{sorting_plan.name}/{billing_type}"
#     return billing_url


# @csrf_exempt
# def confirm_billing(request):
#     """Endpoint to confirm billing and activate the subscription."""
#     if request.method == 'POST':
#         try:
#             client = get_object_or_404(Client, shopify_domain=request.session.get('shopify_domain'))
#             data = json.loads(request.body)
#             plan_id = data.get('plan_id')
#             sorting_plan = get_object_or_404(SortingPlan, id=plan_id)

#             start_date = timezone.now()
#             end_date = start_date + timedelta(days=30) if sorting_plan.is_monthly else start_date + timedelta(days=365)
#             Subscription.objects.create(
#                 client=client,
#                 sorting_plan=sorting_plan,
#                 start_date=start_date,
#                 end_date=end_date,
#                 is_active=True
#             )

#             return JsonResponse({'message': 'Billing confirmed, subscription activated', 'end_date': end_date}, status=200)

#         except Exception as e:
#             return JsonResponse({'error': str(e)}, status=400)

#     return JsonResponse({'error': 'Invalid request method'}, status=405)
