# Generated by Django 5.1.3 on 2024-11-12 05:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shopify_app', '0002_clientcollections_never_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientproducts',
            name='discount_percentage',
            field=models.FloatField(default=0.0),
        ),
    ]