# Generated by Django 5.1.1 on 2024-10-09 13:04

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shopify_app', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clientcollections',
            name='algo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='shopify_app.clientalgo'),
        ),
    ]
