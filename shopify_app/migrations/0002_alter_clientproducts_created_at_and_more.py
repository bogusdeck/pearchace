# Generated by Django 5.1.3 on 2024-11-29 06:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shopify_app', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clientproducts',
            name='created_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='clientproducts',
            name='published_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='clientproducts',
            name='updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]