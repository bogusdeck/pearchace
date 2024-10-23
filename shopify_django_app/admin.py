from django.contrib import admin
from django_celery_results.models import TaskResult
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule, SolarSchedule, ClockedSchedule

@admin.register(TaskResult)
class TaskResultAdmin(admin.ModelAdmin):
    list_display = ('task_id', 'status', 'date_done', 'result', 'task_name')
    search_fields = ('task_id', 'status', 'task_name')

# You can use the default PeriodicTaskAdmin or create a custom one
class PeriodicTaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'task', 'enabled', 'interval', 'crontab', 'solar', 'clocked', 'last_run_at')
    search_fields = ('name', 'task')
    list_filter = ('enabled', 'interval', 'crontab')

try:
    admin.site.unregister(PeriodicTask)
except admin.sites.NotRegistered:
    pass  

admin.site.register(PeriodicTask, PeriodicTaskAdmin)

@admin.register(CrontabSchedule)
class CrontabScheduleAdmin(admin.ModelAdmin):
    list_display = ('minute', 'hour', 'day_of_week', 'day_of_month', 'month_of_year')

@admin.register(IntervalSchedule)
class IntervalScheduleAdmin(admin.ModelAdmin):
    list_display = ('every', 'period')

@admin.register(SolarSchedule)
class SolarScheduleAdmin(admin.ModelAdmin):
    list_display = ('event', 'latitude', 'longitude')

@admin.register(ClockedSchedule)
class ClockedScheduleAdmin(admin.ModelAdmin):
    list_display = ('clocked_time',)
