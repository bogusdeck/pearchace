from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from shopify_app.models import Client, SortingPlan, Subscription
from datetime import timedelta
import json

@csrf_exempt
def initiate_billing(request):
    """Endpoint to initiate the billing process for a client."""
    if request.method == 'POST':
        try:
            client = get_object_or_404(Client, shopify_domain=request.session.get('shopify_domain'))
            data = json.loads(request.body)
            plan_id = data.get('plan_id')


            sorting_plan = get_object_or_404(SortingPlan, id=plan_id)

            if sorting_plan.is_trial:
                start_date = timezone.now()
                end_date = start_date + timedelta(days=sorting_plan.duration_days)
                Subscription.objects.create(
                    client=client,
                    sorting_plan=sorting_plan,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True
                )
                return JsonResponse({'message': 'Free trial initiated', 'trial_end': end_date}, status=200)

                
            subscription_url = create_billing_url(client, sorting_plan)
            return JsonResponse({'billing_url': subscription_url}, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


def create_billing_url(client, sorting_plan):
    """Helper function to create a billing URL for the client based on the sorting plan."""
    billing_type = "monthly" if sorting_plan.is_monthly else "annual"
    billing_url = f"https://billing.shopify.com/subscribe/{client.shopify_domain}/{sorting_plan.name}/{billing_type}"
    return billing_url


@csrf_exempt
def confirm_billing(request):
    """Endpoint to confirm billing and activate the subscription."""
    if request.method == 'POST':
        try:
            client = get_object_or_404(Client, shopify_domain=request.session.get('shopify_domain'))
            data = json.loads(request.body)
            plan_id = data.get('plan_id')
            sorting_plan = get_object_or_404(SortingPlan, id=plan_id)

            start_date = timezone.now()
            end_date = start_date + timedelta(days=30) if sorting_plan.is_monthly else start_date + timedelta(days=365)
            Subscription.objects.create(
                client=client,
                sorting_plan=sorting_plan,
                start_date=start_date,
                end_date=end_date,
                is_active=True
            )

            return JsonResponse({'message': 'Billing confirmed, subscription activated', 'end_date': end_date}, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)
