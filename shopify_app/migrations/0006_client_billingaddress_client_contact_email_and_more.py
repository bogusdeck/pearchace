# Generated by Django 5.1.1 on 2024-09-08 05:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shopify_app', '0005_client_member'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='billingAddress',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='client',
            name='contact_email',
            field=models.EmailField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='client',
            name='createdateshopify',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='client',
            name='currency',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='client',
            name='timezone',
            field=models.CharField(default='UTC', max_length=3),
        ),
        migrations.AlterField(
            model_name='client',
            name='shop_name',
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
