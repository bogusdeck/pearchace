from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from shopify import RecurringApplicationCharge 
from shopify_app.models import Client, SortingPlan, Subscription
from django.utils import timezone
import json

# POST /billing/initiate/
def initiate_billing(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            plan_id = data.get('plan_id')
            client = request.user  
            plan = get_object_or_404(SortingPlan, plan_id=plan_id)

            billing_params = {
                'name': plan.name,
                'price': plan.cost_month,  
                'trial_days': 14,  
                'return_url': 'https://{request.get_host()}/billing/confirm',
                'test': True  
            }

            
            charge = RecurringApplicationCharge.create(billing_params)

            if charge.id:
                return JsonResponse({
                    'billing_url': charge.confirmation_url,
                    'message': 'Billing initiation successful'
                })
            else:
                return JsonResponse({'error': 'Billing initiation failed'}, status=400)
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON")
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return HttpResponseBadRequest("Only POST requests are allowed.")

# POST /billing/confirm/
def confirm_billing(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            charge_id = data.get('charge_id')
            client = request.user 

            charge = RecurringApplicationCharge.find(charge_id)

            if charge.status == 'accepted':
                charge.activate()

                Subscription.objects.update_or_create(
                    client=client,
                    defaults={
                        'plan': SortingPlan.objects.get(name=charge.name),
                        'status': 'active',
                        'current_period_start': timezone.now(),
                        'current_period_end': timezone.now() + timezone.timedelta(days=30),
                        'next_billing_date': timezone.now() + timezone.timedelta(days=30)
                    }
                )

                return JsonResponse({
                    'message': 'Billing confirmed and subscription activated',
                    'status': 'active'
                })
            else:
                return JsonResponse({'error': 'Billing was not accepted'}, status=400)

        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON")
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return HttpResponseBadRequest("Only POST requests are allowed.")
