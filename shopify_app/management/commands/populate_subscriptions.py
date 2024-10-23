from django.core.management.base import BaseCommand
from yourapp.models import Subscription, Usage, SortingPlan  # Adjust the import based on your app structure
from django.utils import timezone
from datetime import timedelta
import random

class Command(BaseCommand):
    help = 'Populate fake subscription and usage data'

    def handle(self, *args, **kwargs):
        # Create some SortingPlan instances manually if needed
        plans = [
            SortingPlan.objects.create(name='Basic Plan'),
            SortingPlan.objects.create(name='Pro Plan'),
            SortingPlan.objects.create(name='VIP Plan'),
        ]

        # Populate Subscription model
        for i in range(10):  # Change the range for the number of subscriptions you want to create
            shop_id = f'shop_{i}'  # Simple shop_id for each subscription
            plan = random.choice(plans)  # Randomly select a plan
            status = random.choice(['active', 'canceled'])  # Random status

            # Set the billing dates
            current_period_start = timezone.now()
            current_period_end = current_period_start + timedelta(days=30)
            next_billing_date = current_period_start + timedelta(days=30)

            # Create the subscription
            subscription = Subscription.objects.create(
                shop_id=shop_id,
                plan=plan,
                status=status,
                current_period_start=current_period_start,
                current_period_end=current_period_end,
                next_billing_date=next_billing_date,
                charge_id=f'charge_{i}',  # Simple charge ID
            )
            self.stdout.write(self.style.SUCCESS(f'Created subscription: {subscription}'))

            # Populate Usage model for each subscription
            for j in range(random.randint(1, 5)):  # Random number of usage entries for each subscription
                usage_date = timezone.now().date() - timedelta(days=random.randint(0, 30))  # Random date within the last 30 days
                Usage.objects.create(
                    shop_id=shop_id,
                    subscription=subscription,
                    sorts_count=random.randint(0, 100),  
                    orders_count=random.randint(0, 50),  
                    addon_sorts_count=random.randint(0, 20),  # 
                    charge_id=f'usage_charge_{j}',
                    usage_date=usage_date,
                )

        self.stdout.write(self.style.SUCCESS('Finished populating fake subscription and usage data'))
