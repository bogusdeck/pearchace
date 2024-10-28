from django.core.management.base import BaseCommand
from shopify_app.models import ClientGraph, Client 

class Command(BaseCommand):
    help = 'Populate ClientGraph model with specific revenue data for the last 30 days.'

    def handle(self, *args, **kwargs):
        shop_id = '63270879430'
        
        # Get the client object
        try:
            client = Client.objects.get(shop_id=shop_id)
        except Client.DoesNotExist:
            self.stdout.write(self.style.ERROR('Client with shop_id does not exist.'))
            return

        # Manually define dates and revenue
        data = [
            ("2024-08-12", 100.00),
            ("2024-08-15", 550.00),
            ("2024-08-22", 850.00),
            ("2024-09-10", 200.00),
            ("2024-09-24", 500.00),
            ("2024-09-25", 600.50),
            ("2024-09-28", 800.00),
            ("2024-09-29", 300.00),
            ("2024-09-30", 650.75),
            ("2024-10-01", 1200.00),
            ("2024-10-02", 900.50),
            ("2024-10-03", 1100.00),
            ("2024-10-04", 500.00),
            ("2024-10-05", 700.25),
            ("2024-10-06", 300.00),
            ("2024-10-07", 600.00),
            ("2024-10-08", 950.75),
            ("2024-10-09", 850.00),
            ("2024-10-10", 400.50),
            ("2024-10-11", 750.00),
            ("2024-10-12", 820.00),
            ("2024-10-13", 530.00),
            ("2024-10-18", 440.00),
            ("2024-10-19", 920.00),
            ("2024-10-20", 1050.50),
            ("2024-10-24", 950.00),
        ]

        # Create and save the ClientGraph instances
        for date, revenue in data:
            ClientGraph.objects.create(shop=client, date=date, revenue=revenue)
            self.stdout.write(self.style.SUCCESS(f'Successfully added revenue data for {date}: ${revenue}'))

        self.stdout.write(self.style.SUCCESS('Finished populating ClientGraph model.'))
