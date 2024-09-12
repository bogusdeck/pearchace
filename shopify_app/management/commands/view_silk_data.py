import psutil
from django.core.management.base import BaseCommand
from silk.models import Request

class Command(BaseCommand):
    help = 'Display Django Silk profiling data and memory usage in the terminal'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Number of most recent requests to display',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        requests = Request.objects.all().order_by('-start_time')[:limit]

        
        memory_info = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)

        if not requests:
            self.stdout.write(self.style.NOTICE('No profiling data available.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Memory Usage: {memory_info.percent}%'))
        self.stdout.write(self.style.SUCCESS(f'CPU Usage: {cpu_percent}%'))
        
        for request in requests:
            self.stdout.write(f'ID: {request.id}')
            self.stdout.write(f'Start Time: {request.start_time}')
            self.stdout.write(f'End Time: {request.end_time}')
            self.stdout.write(f'Duration: {request.end_time - request.start_time}')
            self.stdout.write(f'Path: {request.path}')
            self.stdout.write('---')

        self.stdout.write(self.style.SUCCESS(f'Displayed {len(requests)} request(s).'))
