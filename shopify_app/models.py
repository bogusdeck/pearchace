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
    email = models.EmailField(max_length=255, unique=False)
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
    default_algo = models.ForeignKey('ClientAlgo', on_delete=models.SET_NULL, to_field='algo_id',null=True, blank=True)
    member = models.BooleanField(default=False)
    lookback_period = models.IntegerField(default=30, blank=True, null=True)
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

    custom_start_time = models.TimeField(blank=True, null=True) 
    custom_stop_time = models.TimeField(blank=True, null=True)  
    custom_frequency_in_hours = models.IntegerField(blank=True, null=True) 

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

    USERNAME_FIELD = 'shop_name'
    REQUIRED_FIELDS = ['shop_id']

    objects = ClientManager()

    def __str__(self):
        return self.shop_name

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser
    
#done
class ClientCollections(models.Model):
    id = models.BigAutoField(primary_key=True)
    collection_id = models.BigIntegerField(unique=True)
    shop = models.ForeignKey(Client, on_delete=models.CASCADE, to_field='shop_id')  # Updated shop_id
    collection_name = models.CharField(max_length=255)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    products_count = models.IntegerField(default=0)
    sort_date = models.DateTimeField(null=True, blank=True)
    pinned_products = models.JSONField(blank=True, default=list)
    algo = models.ForeignKey('ClientAlgo', on_delete=models.CASCADE, to_field='algo_id', default=1) 
    parameters_used = models.JSONField(default=dict)
    updated_at = models.DateTimeField(null=True, blank=True)
    out_of_stock_down = models.BooleanField(default=False)
    pinned_out_of_stock_down = models.BooleanField(default=False)
    new_out_of_stock_down = models.BooleanField(default=False)
    refetch = models.BooleanField(default=True)
    collection_total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    collection_sold_units = models.IntegerField(default=0)
    never_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('shop', 'collection_id')  

    def __str__(self):
        return f"{self.collection_name} (ID: {self.collection_id}) for shop {self.shop} - Sorted on {self.sort_date}"
    
#new
class ClientProducts(models.Model):
    product_id = models.CharField(max_length=255, primary_key=True)
    shop = models.ForeignKey(Client, on_delete=models.CASCADE, to_field='shop_id')
    collection = models.ForeignKey(ClientCollections, on_delete=models.CASCADE, to_field='collection_id')
    product_name = models.CharField(max_length=255)
    image_link = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField()
    tags = models.JSONField(blank=True, null=True)
    updated_at = models.DateTimeField()
    published_at = models.DateTimeField()
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    variant_count = models.IntegerField(default=0)
    variant_availability = models.IntegerField(default=0)
    total_inventory = models.IntegerField(default=0)
    sales_velocity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_sold_units = models.IntegerField(default=0)
    position_in_collection = models.IntegerField(default=0)
    recency_score = models.FloatField(default=0)


    def __str__(self):
        return f"Product {self.product_name} (ID: {self.product_id}) for shop_id {self.shop_id}"
    
#new
class ClientAlgo(models.Model):
    shop = models.ForeignKey('Client', on_delete=models.CASCADE, to_field='shop_id', null=True, blank=True)  
    algo_id = models.AutoField(primary_key=True)
    algo_name = models.CharField(max_length=255)
    number_of_buckets = models.IntegerField()
    boost_tags = models.JSONField(blank=True, default=list)
    bury_tags = models.JSONField(blank=True, default=list)
    bucket_parameters = models.JSONField(blank=True, default=dict)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.algo_name} - {self.shop_id}"


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

# Subscription Model
class Subscription(models.Model):
    subscription_id = models.AutoField(primary_key=True)
    shop = models.ForeignKey(Client, on_delete=models.CASCADE, to_field='shop_id')  
    plan = models.ForeignKey(SortingPlan, on_delete=models.CASCADE)
    status = models.CharField(max_length=50)  
    is_annual = models.BooleanField(default=False) 
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)
    charge_id = models.CharField(max_length=255, null=True, blank=True)  
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('shop', 'subscription_id')  

    def __str__(self):
        return f"Subscription {self.subscription_id} for shop {self.shop}"

# Usage Model
class Usage(models.Model):
    usage_id = models.AutoField(primary_key=True)
    shop = models.ForeignKey(Client, on_delete=models.CASCADE, to_field='shop_id')  
    subscription = models.ForeignKey('Subscription', on_delete=models.CASCADE)
    sorts_count = models.IntegerField(default=0)
    orders_count = models.IntegerField(default=0)
    addon_sorts_count = models.IntegerField(default=0)
    charge_id = models.CharField(max_length=255, null=True, blank=True)
    usage_date = models.DateField(null=True, default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('shop', 'usage_id')  

    def __str__(self):
        return f"Usage {self.usage_id} for shop {self.shop} on {self.usage_date}"
        

#clientgraph
class ClientGraph(models.Model):
    shop = models.ForeignKey(Client, on_delete=models.CASCADE, to_field='shop_id')
    date = models.DateField()
    revenue = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"Graph for {self.client.shop_id} on {self.date}"

#BillingToken
class BillingTokens(models.Model):
    TOKEN_STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
    ]

    shop = models.ForeignKey(Client, on_delete=models.CASCADE, to_field='shop_id')
    shop_url = models.CharField(max_length=255)
    temp_token = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=10, choices=TOKEN_STATUS_CHOICES, default='active')
    charge_id = models.CharField(max_length=255)  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expiration_time = models.DateTimeField()

    def __str__(self):
        return f"{self.shop} - {self.temp_token} ({self.status})"

    def is_expired(self):
        return timezone.now() > self.expiration_time
