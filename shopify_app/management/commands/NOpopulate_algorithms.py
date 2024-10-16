from django.core.management.base import BaseCommand
from shopify_app.models import SortingAlgorithm

class Command(BaseCommand):
    help = 'Populates the database with predefined sorting algorithms'

    def handle(self, *args, **kwargs):
        algorithms = [
            {
                'name': 'Promote New Products',
                'description': 'Promotes new products based on the number of days they have been listed.',
                'default_parameters': {"days": None},  # Replace None with actual default value if needed
            },
            {
                'name': 'Promote High Revenue Products',
                'description': 'Promotes products with high revenue based on the number of days and percentile.',
                'default_parameters': {"days": None, "percentile": None},
            },
            {
                'name': 'Promote High Inventory Products',
                'description': 'Promotes products with high inventory based on the number of days and percentile.',
                'default_parameters': {"days": None, "percentile": None},
            },
            {
                'name': 'Bestsellers High Variant Products',
                'description': 'Promotes bestsellers with high variant availability based on days, revenue percentile, and variant threshold.',
                'default_parameters': {"days": None, "revenue_percentile": None, "variant_threshold": None},
            },
            {
                'name': 'Promote High Variant Availability',
                'description': 'Promotes products with high variant availability based on a variant threshold.',
                'default_parameters': {"variant_threshold": None},
            },
            {
                'name': 'Clearance Sale',
                'description': 'Promotes products on clearance sale based on days and bottom percentile threshold.',
                'default_parameters': {"days": None, "bottom_percentile_threshold": None},
            },
            {
                'name': 'Promote High Revenue New',
                'description': 'Promotes high revenue new products based on days and top percentile threshold.',
                'default_parameters': {"days": None, "top_percentile_threshold": None},
            },
            {
                'name': 'I\'m Feeling Lucky',
                'description': 'Randomly Choose Sortig to promotes products.',
                'default_parameters': {},
            },
            {
                'name': 'RFM',
                'description': 'Promotes products based on Recency, Frequency, and Monetary value.',
                'default_parameters': {},
            },
        ]

        for algo in algorithms:
            SortingAlgorithm.objects.create(**algo)

        self.stdout.write(self.style.SUCCESS('Sorting algorithms populated successfully!'))
