# Generated by Django 5.1.3 on 2024-11-22 08:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shopify_app', '0002_client_timezone_offset'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientcollections',
            name='is_smart',
            field=models.BooleanField(default=False),
        ),
    ]