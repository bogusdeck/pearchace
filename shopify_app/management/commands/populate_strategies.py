from django.core.management.base import BaseCommand
from shopify_app.models import ClientAlgo
from shopify_app.strategies_data import PRIMARY_STRATEGIES

class Command(BaseCommand):
    help = 'Populates the ClientAlgo table with primary strategies'

    def handle(self, *args, **kwargs):
        try:
            for strategy in PRIMARY_STRATEGIES:
                if ClientAlgo.objects.filter(algo_name=strategy["algo_name"], is_primary=True, shop__isnull=True).exists():
                    self.stdout.write(self.style.WARNING(f'Strategy "{strategy["algo_name"]}" already exists as a global strategy. Skipping.'))
                    continue

                ClientAlgo.objects.create(
                    algo_name=strategy["algo_name"],
                    number_of_buckets=strategy["number_of_buckets"],
                    boost_tags=[],
                    bury_tags=[],
                    bucket_parameters=strategy["bucket_parameters"],
                    is_primary=True,
                    shop=None  
                )

                self.stdout.write(self.style.SUCCESS(f'Successfully added primary strategy: {strategy["algo_name"]}'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error occurred: {str(e)}'))
