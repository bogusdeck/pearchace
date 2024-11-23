from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from shopify_app.models import Client  # Replace 'myapp' with the name of the app where your Client model is defined

class Command(BaseCommand):
    help = "Make the Client user 'Pearch-test1' an admin and set the password to '2299#'."

    def handle(self, *args, **kwargs):
        shop_name = "Pearch-test1"
        password = "2299#"

        try:
            client = Client.objects.get(shop_name=shop_name)

            # Update client attributes
            client.is_staff = True
            client.is_superuser = True
            client.password = make_password(password)

            client.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Client '{shop_name}' has been successfully updated to admin status with the new password."
                )
            )
        except Client.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Client with shop_name '{shop_name}' does not exist."))
