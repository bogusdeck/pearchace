from django.core.management.base import BaseCommand
from shopify_app.models import SortingPlan

class Command(BaseCommand):
    help = 'Populates the database with predefined billing plans'

    def handle(self, *args, **kwargs):
        plans = [
            {
                'name': 'Limited Plan',
                'is_monthly': True,
                'cost_month': 10.00,
                'cost_annual': 100.00,
                'sort_limit': 1000,
                'order_limit': 500,
                'is_trial': False,
            },
            {
                'name': 'Basic Plan',
                'is_monthly': True,
                'cost_month': 20.00,
                'cost_annual': 200.00,
                'sort_limit': 5000,
                'order_limit': 5000,
                'is_trial': False,
            },
            {
                'name': 'Pro Plan',
                'is_monthly': True,
                'cost_month': 50.00,
                'cost_annual': 500.00,
                'sort_limit': 10000,
                'order_limit': 10000,
                'is_trial': False,
            },
            {
                'name': 'VIP Plan',
                'is_monthly': True,
                'cost_month': 100.00,
                'cost_annual': 1000.00,
                'sort_limit': 25000,
                'order_limit': 50000,
                'is_trial': False,
            },
            {
                'name': 'Free Trial',
                'is_trial': True,
                'duration_days': 14,
                'sort_limit': 100,
                'order_limit': 0,
                'is_monthly': False,
            },
        ]

        for plan in plans:
            SortingPlan.objects.create(**plan)

        self.stdout.write(self.style.SUCCESS('Billing plans populated successfully!'))
