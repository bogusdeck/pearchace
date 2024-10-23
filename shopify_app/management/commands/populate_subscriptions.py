from django.core.management.base import BaseCommand
from shopify_app.models import Subscription, Usage, SortingPlan  
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Populate a specific subscription and usage data'

    def handle(self, *args, **kwargs):
        # Get the specific SortingPlan instance (plan id 1, assuming it's the Limited Plan)
        try:
            limited_plan = SortingPlan.objects.get(id=1)
        except SortingPlan.DoesNotExist:
            self.stdout.write(self.style.ERROR('Limited Plan with id 1 does not exist.'))
            return

        # Set the specific values for shop_id and charge_id
        shop_id = '63270879430'
        charge_id = '26896433350'
        status = 'active'  # Assuming it's an active subscription

        # Set the billing dates
        current_period_start = timezone.now()
        current_period_end = current_period_start + timedelta(days=30)
        next_billing_date = current_period_start + timedelta(days=30)

        # Create the subscription with the predefined values
        subscription, created = Subscription.objects.get_or_create(
            shop_id=shop_id,
            plan=limited_plan,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            next_billing_date=next_billing_date,
            charge_id=charge_id,
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created subscription: {subscription}'))
        else:
            self.stdout.write(self.style.WARNING(f'Subscription for shop_id {shop_id} already exists.'))

        usage_date = timezone.now().date()  # Today's date as usage date
        usage, created = Usage.objects.get_or_create(
            shop_id=shop_id,
            subscription=subscription,
            defaults={
                'sorts_count': 0,  
                'orders_count': 0,  
                'addon_sorts_count': 0,  
                'charge_id': charge_id,
                'usage_date': usage_date,
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created usage record: {usage}'))
        else:
            self.stdout.write(self.style.WARNING(f'Usage record for shop_id {shop_id} on {usage_date} already exists.'))

        self.stdout.write(self.style.SUCCESS('Finished populating the specific subscription and usage data'))
