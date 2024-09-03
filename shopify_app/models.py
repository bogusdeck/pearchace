from django.db import models
from django.utils import timezone

#change
class Client(models.Model):
    client_id = models.BigAutoField(primary_key=True)  
    shop_name = models.CharField(max_length=255)  
    email = models.EmailField(max_length=255)  
    phone_number = models.CharField(max_length=20, blank=True, null=True)  
    shop_url = models.URLField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=None, null=True) 
    access_token = models.TextField(blank=True, null=True) 
    trial_used = models.BooleanField(default=False)  
    installation_date = models.DateTimeField(auto_now_add=True)  
    uninstall_date = models.DateTimeField(blank=True, null=True)  
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True)  
    #schedule frequency = hourly, daily, weekly, custom
    #stock location = all location, online loc, offline loc
    

    def __str__(self):
        return self.shop_name

#change
class SortingPlan(models.Model):
    plan_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    is_monthly = models.BooleanField(null=True, blank=True)
    is_trial = models.BooleanField(default=False)
    duration_days = models.IntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    monthly_sorts_limit = models.IntegerField(null=True, blank=True)
    monthly_orders_limit = models.IntegerField(null=True, blank=True)
    addon_sorts_count = models.IntegerField(null=True, blank=True)
    addon_sorts_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

#change
class SortingAlgorithm(models.Model):
    algo_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    default_parameters = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
#change
class CollectionSort(models.Model):
    sort_id = models.AutoField(primary_key=True)
    client = models.ForeignKey('Client', on_delete=models.CASCADE)
    collection_id = models.CharField(max_length=255)
    algo = models.ForeignKey(SortingAlgorithm, on_delete=models.CASCADE)
    parameters_used = models.JSONField(default=dict)
    sort_date = models.DateTimeField()
    products_count = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Collection Sort {self.sort_id} for {self.client.shop_name} on {self.sort_date}"

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

#no need right now
# class ClientAlgoParams(models.Model):
#     id = models.AutoField(primary_key=True)
#     client = models.ForeignKey('Client', on_delete=models.CASCADE)
#     algo = models.ForeignKey(SortingAlgorithm, on_delete=models.CASCADE)
#     custom_parameters = models.JSONField(default=dict)
#     created_at = models.DateTimeField(default=timezone.now)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return f"Algorithm Params for {self.client.shop_name} - {self.algo.name}"

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
    
#no need
# class Billing(models.Model):
#     id = models.AutoField(primary_key=True)
#     client = models.ForeignKey('Client', on_delete=models.CASCADE)
#     amount = models.DecimalField(max_digits=10, decimal_places=2)
#     billing_date = models.DateTimeField(default=timezone.now)
#     description = models.TextField(null=True, blank=True)
#     created_at = models.DateTimeField(default=timezone.now)

#     def __str__(self):
#         return f"Billing {self.id} for {self.client.shop_name}"

#new model
#class Sorting_rule(models.Model):
#   client = models.ForeignKey('Client', on_delete=models.CASCADE)
#   rules_name = model.CharField(maxlength=255)
#   Applied_collection = model.IntegerField(null=True, blank=True)
#   Default = model.BooleanField(default=False)