from django.db import models
from django.utils import timezone
from timezone_field import TimeZoneField
from django.contrib.postgres.fields import CICharField  
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager

#done
class ClientManager(BaseUserManager):
    def create_user(self, shop_name, email, shop_id, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        client = self.model(shop_name=shop_name, email=email, shop_id=shop_id, **extra_fields)
        client.set_password(password)  
        client.save(using=self._db)
        return client

    def create_superuser(self, shop_name, email, shop_id, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_staff', True)
        return self.create_user(shop_name, email, shop_id, password, **extra_fields)

class Client(AbstractBaseUser):
    id = models.BigAutoField(primary_key=True)
    shop_id = models.CharField(max_length=255, unique=True)
    shop_name = models.CharField(max_length=255, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    shop_url = models.URLField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    contact_email = models.EmailField(max_length=255, blank=True, null=True)
    currency = models.CharField(max_length=10, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    access_token = models.TextField(blank=True, null=True)
    trial_used = models.BooleanField(default=False)
    installation_date = models.DateTimeField(auto_now_add=True)
    uninstall_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    default_algo = models.ForeignKey('SortingAlgorithm', on_delete=models.SET_NULL, null=True, blank=True)
    member = models.BooleanField(default=False)
    timezone = models.CharField(default='UTC', max_length=3)
    createdateshopify = models.DateTimeField(blank=True, null=True)
    billingAddress = models.JSONField(default=dict)
    
    
    password = models.CharField(max_length=128)  
    last_login = models.DateTimeField(blank=True, null=True)

    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

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

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['shop_name', 'shop_id']

    objects = ClientManager()

    def __str__(self):
        return self.shop_name

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

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
    shop_id = models.CharField(max_length=255)  

    class Meta:
        unique_together = ('shop_id', 'plan_id')  

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
class ClientCollections(models.Model):
    id = models.BigAutoField(primary_key=True)
    collectionid = models.BigIntegerField(unique=True)
    shop_id = models.CharField(max_length=255)
    collection_name = models.CharField(max_length=255)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    products_count = models.IntegerField(default=0)
    sort_date = models.DateTimeField(null=True, blank=True)
    pinned_products = models.JSONField(blank=True, null=True)
    algo = models.ForeignKey('SortingAlgorithm', on_delete=models.CASCADE, null=True, blank=True)
    parameters_used = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)
    out_of_stock_down = models.BooleanField(default=False)
    pinned_out_of_stock_down = models.BooleanField(default=False)
    new_out_of_stock_down = models.BooleanField(default=False)
    lookback_periods = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        unique_together = ('shop_id', 'collectionid')  

    def __str__(self):
        return f"{self.collection_name} (ID: {self.collectionid}) for shop_id {self.shop_id} - Sorted on {self.sort_date}"

#done
class Subscription(models.Model):
    subscription_id = models.AutoField(primary_key=True)
    shop_id = models.CharField(max_length=255)  
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

    class Meta:
        unique_together = ('shop_id', 'subscription_id')  

    def __str__(self):
        return f"Subscription {self.subscription_id} for shop_id {self.shop_id}"

#done
class Usage(models.Model):
    usage_id = models.AutoField(primary_key=True)
    shop_id = models.CharField(max_length=255)  
    subscription = models.ForeignKey('Subscription', on_delete=models.CASCADE)
    sorts_count = models.IntegerField(default=0)
    orders_count = models.IntegerField(default=0)
    addon_sorts_count = models.IntegerField(default=0)
    usage_date = models.DateField()
    additional_sorts_purchased = models.IntegerField(default=0)
    additional_sorts_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('shop_id', 'usage_id') 

    def __str__(self):
        return f"Usage {self.usage_id} for shop_id {self.shop_id} on {self.usage_date}"
    
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
    
