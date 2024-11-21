from django.core.management.base import BaseCommand
from shopify_app.models import SortingPlan

class Command(BaseCommand):
    help = 'Populates the database with predefined billing plans'

    def handle(self, *args, **kwargs):
        plans = [
            {
                'name': 'Limited Plan',
                'cost_month': 19.00,  
                'cost_annual': 209.00,
                'sort_limit': 1000,
                'order_limit': 500,
                'addon_sorts_count': None,  
                'addon_sorts_price': None,  
            },
            {
                'name': 'Basic Plan',
                'cost_month': 89.00,
                'cost_annual': 979.00,
                'sort_limit': 5000,
                'order_limit': 5000,
                'addon_sorts_count': None,  
                'addon_sorts_price': None,  
            },
            {
                'name': 'Advance Plan',
                'cost_month': 199.00,
                'cost_annual': 2189.00,
                'sort_limit': 10000,
                'order_limit': 10000,
                'addon_sorts_count': None,  
                'addon_sorts_price': None,  
            },
            {
                'name': 'Pro Plan',
                'cost_month': 299.00,
                'cost_annual': 3289.00,
                'sort_limit': 25000,
                'order_limit': 50000,
                'addon_sorts_count': None,  
                'addon_sorts_price': None,  
            },
            {
                'name': 'Free Trial',
                'cost_month': 0.00,
                'cost_annual': 0.00,
                'sort_limit': 100,
                'order_limit': 0,
                'addon_sorts_count': None,  
                'addon_sorts_price': None,  
            },
        ]

        for plan in plans:
            SortingPlan.objects.create(**plan)

        self.stdout.write(self.style.SUCCESS('Billing plans populated successfully!'))
