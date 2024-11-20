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
            ("2024-10-25", 700.00),
            ("2024-10-26", 500.25),
            ("2024-10-27", 850.50),
            ("2024-10-28", 1200.75),
            ("2024-10-29", 650.00),
            ("2024-10-30", 400.25),
            ("2024-10-31", 300.50),
            ("2024-11-01", 800.00),
            ("2024-11-02", 900.50),
            ("2024-11-03", 750.25),
            ("2024-11-04", 1100.00),
            ("2024-11-05", 1200.00),
            ("2024-11-06", 850.75),
            ("2024-11-07", 950.00),
            ("2024-11-08", 500.00),
            ("2024-11-09", 400.75),
            ("2024-11-10", 800.00),
            ("2024-11-11", 900.00),
            ("2024-11-12", 950.50),
            ("2024-11-13", 750.00),
            ("2024-11-14", 1050.25),
            ("2024-11-15", 850.00),
            ("2024-11-16", 1200.00),
            ("2024-11-17", 900.50),
            ("2024-11-18", 800.25),
            ("2024-11-19", 950.75),
            ("2024-11-20", 700.00),
            ("2024-11-21", 500.50),
            ("2024-11-22", 400.00),
            ("2024-11-23", 750.25),
            ("2024-11-24", 1050.75),
            ("2024-11-25", 850.00),
            ("2024-11-26", 1200.50),
            ("2024-11-27", 900.75),
        ]

        # Create and save the ClientGraph instances
        for date, revenue in data:
            ClientGraph.objects.create(shop=client, date=date, revenue=revenue)
            self.stdout.write(self.style.SUCCESS(f'Successfully added revenue data for {date}: ${revenue}'))

        self.stdout.write(self.style.SUCCESS('Finished populating ClientGraph model.'))
