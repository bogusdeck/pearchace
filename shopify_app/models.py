from django.db import models
from django.utils import timezone
from timezone_field import TimeZoneField
from django.contrib.postgres.fields import CICharField  

#done
class Client(models.Model):
    client_id = models.BigAutoField(primary_key=True)
    shop_name = models.CharField(max_length=255, unique=True)
    email = models.EmailField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    shop_url = models.URLField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    contact_email = models.EmailField(max_length=255, blank=True, null=True) 
    currency = models.CharField(max_length=10, blank=True, null=True) 
    is_active = models.BooleanField(default=None, null=True)
    access_token = models.TextField(blank=True, null=True)
    trial_used = models.BooleanField(default=False)
    installation_date = models.DateTimeField(auto_now_add=True)
    uninstall_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # subscription_status = models.BooleanField(max_length=50, default="inactive")
    default_algo = models.ForeignKey('SortingAlgorithm', on_delete=models.SET_NULL, null=True, blank=True)
    member = models.BooleanField(default=False)
    timezone = models.CharField(default='UTC', max_length=3)  
    createdateshopify = models.DateTimeField(blank=True, null=True) 
    billingAddress = models.JSONField(default=dict)

    SCHEDULE_FREQUENCY_CHOICES = [
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('custom', 'Custom'),
    ]
    schedule_frequency = models.CharField(
        max_length=10, 
        choices=SCHEDULE_FREQUENCY_CHOICES, 
        default='daily'
    )

    STOCK_LOCATION_CHOICES = [
        ('all', 'All Locations'),
        ('online', 'Online Locations'),
        ('offline', 'Offline Locations'),
    ]
    stock_location = models.CharField(
        max_length=10, 
        choices=STOCK_LOCATION_CHOICES, 
        default='all'
    )

    def __str__(self):
        return self.shop_name

#done
class SortingPlan(models.Model):
    plan_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    addon_sorts_count = models.IntegerField(null=True, blank=True)
    addon_sorts_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    cost_month = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_annual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sort_limit = models.IntegerField(null=True, blank=True)
    order_limit = models.IntegerField(null=True, blank=True)
    client_id = models.ForeignKey('Client', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.name

#done
class SortingAlgorithm(models.Model):
    algo_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    default_parameters = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

#done
class CollectionSort(models.Model):
    sort_id = models.AutoField(primary_key=True)
    client = models.ForeignKey('Client', on_delete=models.CASCADE)
    collection_id = models.CharField(max_length=255)
    algo = models.ForeignKey('SortingAlgorithm', on_delete=models.CASCADE)
    parameters_used = models.JSONField(default=dict)
    sort_date = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Collection Sort {self.sort_id} for {self.client.shop_name} on {self.sort_date}"

class ClientCollections(models.Model):
    collectionid = models.CharField(max_length=255, unique=True)  
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='collections')  
    collection_name = models.CharField(max_length=255)  
    status = models.BooleanField(default=True)  
    created_at = models.DateTimeField(auto_now_add=True)  
    products_count = models.IntegerField(default=0)  
    sort_date = models.DateTimeField(null=True, blank=True)  
    pinned_products = models.JSONField(blank=True, null=True)  

    def __str__(self):
        return f"{self.collection_name} (ID: {self.collectionid}) for {self.client.shop_name}"


#done
class Subscription(models.Model):
    subscription_id = models.AutoField(primary_key=True)
    client = models.ForeignKey('Client', on_delete=models.CASCADE)
    plan = models.ForeignKey(SortingPlan, on_delete=models.CASCADE)
    status = models.CharField(max_length=50)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    next_billing_date = models.DateTimeField(null=True, blank=True)
    trial_start_date = models.DateTimeField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_on_trial = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Subscription {self.subscription_id} for {self.client.shop_name}"
#done
class Usage(models.Model):
    usage_id = models.AutoField(primary_key=True)
    client = models.ForeignKey('Client', on_delete=models.CASCADE)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    sorts_count = models.IntegerField(default=0)
    orders_count = models.IntegerField(default=0)
    addon_sorts_count = models.IntegerField(default=0)
    usage_date = models.DateField()
    additional_sorts_purchased = models.IntegerField(default=0)
    additional_sorts_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Usage {self.usage_id} for {self.client.shop_name} on {self.usage_date}"

#done not dealing with it much 
class PlanHistory(models.Model):
    id = models.AutoField(primary_key=True)
    client = models.ForeignKey('Client', on_delete=models.CASCADE)
    plan = models.ForeignKey(SortingPlan, on_delete=models.CASCADE)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Plan History {self.id} for {self.client.shop_name}"
    
