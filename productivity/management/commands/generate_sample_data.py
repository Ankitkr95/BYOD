"""
Management command to generate sample activity data for testing.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from devices.models import Device
from productivity.utils import generate_sample_activity_data


class Command(BaseCommand):
    help = 'Generate sample activity data for testing productivity features'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username to generate data for (default: all users with devices)',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=14,
            help='Number of days to generate data for (default: 14)',
        )
        parser.add_argument(
            '--device',
            type=str,
            help='Specific device name to use (default: first device of each user)',
        )
    
    def handle(self, *args, **options):
        user = options.get('user')
        days = options['days']
        device_name = options.get('device')
        
        # Get user(s) to generate data for
        if user:
            try:
                user_obj = User.objects.get(username=user)
                users = [user_obj]
            except User.DoesNotExist:
                raise CommandError(f'User "{user}" does not exist.')
        else:
            # Get all users with registered devices
            users = User.objects.filter(devices__isnull=False).distinct()
            
            if not users.exists():
                self.stdout.write(
                    self.style.WARNING('No users with registered devices found.')
                )
                return
        
        generated_count = 0
        error_count = 0
        
        for user_obj in users:
            try:
                # Get device for this user
                if device_name:
                    try:
                        device = Device.objects.get(user=user_obj, name=device_name)
                    except Device.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(f'Device "{device_name}" not found for user {user_obj.username}')
                        )
                        error_count += 1
                        continue
                else:
                    # Use first device of the user
                    device = user_obj.devices.first()
                    if not device:
                        self.stdout.write(
                            self.style.ERROR(f'No devices found for user {user_obj.username}')
                        )
                        error_count += 1
                        continue
                
                # Generate sample data
                self.stdout.write(f'Generating {days} days of sample data for {user_obj.username} using device {device.name}...')
                generate_sample_activity_data(user_obj, device, days)
                generated_count += 1
                
                self.stdout.write(f'Generated sample data for {user_obj.username}')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error generating data for user {user_obj.username}: {e}')
                )
                error_count += 1
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated sample data for {generated_count} users')
        )
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(f'{error_count} errors occurred during generation')
            )