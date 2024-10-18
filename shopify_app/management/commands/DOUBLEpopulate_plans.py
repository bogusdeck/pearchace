from django.core.management.base import BaseCommand
from shopify_app.models import SortingPlan

class Command(BaseCommand):
    help = 'Populates the database with predefined billing plans'

    def handle(self, *args, **kwargs):
        plans = [
            # Annual Plans
            {'name': 'Limited Plan', 'cost_month': None, 'cost_annual': 209.00, 'sort_limit': 1000, 'order_limit': 500, 'is_annually': True},
            {'name': 'Basic Plan', 'cost_month': None, 'cost_annual': 979.00, 'sort_limit': 5000, 'order_limit': 5000, 'is_annually': True},
            {'name': 'Pro Plan', 'cost_month': None, 'cost_annual': 2189.00, 'sort_limit': 10000, 'order_limit': 10000, 'is_annually': True},
            {'name': 'VIP Plan', 'cost_month': None, 'cost_annual': 3289.00, 'sort_limit': 25000, 'order_limit': 50000, 'is_annually': True},
            # Monthly Plans
            {'name': 'Limited Plan', 'cost_month': 19.00, 'cost_annual': None, 'sort_limit': 1000, 'order_limit': 500, 'is_annually': False},
            {'name': 'Basic Plan', 'cost_month': 89.00, 'cost_annual': None, 'sort_limit': 5000, 'order_limit': 5000, 'is_annually': False},
            {'name': 'Pro Plan', 'cost_month': 199.00, 'cost_annual': None, 'sort_limit': 10000, 'order_limit': 10000, 'is_annually': False},
            {'name': 'VIP Plan', 'cost_month': 299.00, 'cost_annual': None, 'sort_limit': 25000, 'order_limit': 50000, 'is_annually': False},
            # Free Plan
            {'name': 'Free Plan', 'cost_month': 0.00, 'cost_annual': 0.00, 'sort_limit': 100, 'order_limit': 0, 'is_annually': False},
        ]

        for plan in plans:
            SortingPlan.objects.update_or_create(
                shop_id='default_shop_id',  # Replace with your logic for shop_id
                name=plan['name'],
                is_annually=plan['is_annually'],
                defaults={
                    'cost_month': plan['cost_month'],
                    'cost_annual': plan['cost_annual'],
                    'sort_limit': plan['sort_limit'],
                    'order_limit': plan['order_limit'],
                }
            )

        self.stdout.write(self.style.SUCCESS('Billing plans populated successfully!'))
