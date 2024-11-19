
import random
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from shopify_app.models import ClientProducts, Client, ClientCollections

class Command(BaseCommand):
    help = "Populate ClientProducts with fake data"

    def handle(self, *args, **kwargs):
        shop_id = "63270879430"
        collection_id = "310899245254"

        # Ensure the shop and collection exist
        try:
            shop = Client.objects.get(shop_id=shop_id)
            collection = ClientCollections.objects.get(collection_id=collection_id)
        except Client.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Shop with ID {shop_id} does not exist."))
            return
        except ClientCollections.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Collection with ID {collection_id} does not exist."))
            return

        for i in range(1, 30):  # Creating 100 products
            product_id = f"{i:04d}"  # Example: P0001, P0002, ...
            product_name = f"Fake Product {i}"
            image_link = f"https://example.com/images/product_{i}.jpg"

            # Use timezone-aware datetimes
            created_at = timezone.now() - datetime.timedelta(days=random.randint(0, 365))
            updated_at = created_at + datetime.timedelta(days=random.randint(1, 100))
            published_at = created_at + datetime.timedelta(days=random.randint(0, 30))

            # Other fields remain the same
            tags = {"tag1": "value1", "tag2": "value2"}
            total_revenue = round(random.uniform(100, 500), 2)
            variant_count = random.randint(1, 20)
            variant_availability = random.randint(1, variant_count)
            total_inventory = random.randint(0, 500)
            sales_velocity = round(random.uniform(0, 50), 2)
            total_sold_units = random.randint(0, 500)
            position_in_collection = random.randint(1, 100)
            recency_score = round(random.uniform(0, 10), 2)
            discount_absolute = round(random.uniform(0, 50), 2)
            discount_percentage = round(random.uniform(0, 30), 2)

            # Create product
            ClientProducts.objects.create(
                product_id=product_id,
                shop=shop,
                collection=collection,
                product_name=product_name,
                image_link=image_link,
                created_at=created_at,
                tags=tags,
                updated_at=updated_at,
                published_at=published_at,
                total_revenue=total_revenue,
                variant_count=variant_count,
                variant_availability=variant_availability,
                total_inventory=total_inventory,
                sales_velocity=sales_velocity,
                total_sold_units=total_sold_units,
                position_in_collection=position_in_collection,
                recency_score=recency_score,
                discount_absolute=discount_absolute,
                discount_percentage=discount_percentage,
            )

        self.stdout.write(self.style.SUCCESS(f"Successfully populated 100 products for shop {shop_id} and collection {collection_id}."))
