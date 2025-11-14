"""
Management command to generate productivity reports.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta, date
from productivity.utils import ProductivityCalculator, bulk_generate_reports


class Command(BaseCommand):
    help = 'Generate productivity reports for users'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username to generate reports for (default: all users with activity)',
        )
        parser.add_argument(
            '--report-type',
            type=str,
            choices=['daily', 'weekly', 'monthly'],
            default='daily',
            help='Type of report to generate (default: daily)',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Specific date to generate report for (YYYY-MM-DD format)',
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=7,
            help='Number of days back to generate reports for (default: 7)',
        )
        parser.add_argument(
            '--bulk',
            action='store_true',
            help='Generate reports for all users in bulk',
        )
    
    def handle(self, *args, **options):
        user = options.get('user')
        report_type = options['report_type']
        date_str = options.get('date')
        days_back = options['days_back']
        bulk = options['bulk']
        
        if bulk:
            self.stdout.write('Generating reports in bulk mode...')
            generated_count = bulk_generate_reports(report_type, days_back)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully generated {generated_count} reports')
            )
            return
        
        # Parse date if provided
        if date_str:
            try:
                report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError(f'Invalid date format: {date_str}. Use YYYY-MM-DD format.')
        else:
            report_date = timezone.now().date()
        
        # Get user(s) to generate reports for
        if user:
            try:
                user_obj = User.objects.get(username=user)
                users = [user_obj]
            except User.DoesNotExist:
                raise CommandError(f'User "{user}" does not exist.')
        else:
            # Get all users with activity in the specified period
            start_date = report_date - timedelta(days=days_back)
            users = User.objects.filter(
                activity_logs__timestamp__date__gte=start_date
            ).distinct()
            
            if not users.exists():
                self.stdout.write(
                    self.style.WARNING('No users with activity found in the specified period.')
                )
                return
        
        generated_count = 0
        error_count = 0
        
        for user_obj in users:
            try:
                calculator = ProductivityCalculator(user_obj)
                
                if date_str:
                    # Generate report for specific date
                    report = calculator.generate_performance_report(report_date, report_type)
                    self.stdout.write(f'Generated {report_type} report for {user_obj.username} on {report_date}')
                    generated_count += 1
                else:
                    # Generate reports for the past days_back days
                    current_date = report_date - timedelta(days=days_back)
                    while current_date <= report_date:
                        try:
                            report = calculator.generate_performance_report(current_date, report_type)
                            generated_count += 1
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f'Error generating report for {user_obj.username} on {current_date}: {e}')
                            )
                            error_count += 1
                        
                        # Move to next period
                        if report_type == 'daily':
                            current_date += timedelta(days=1)
                        elif report_type == 'weekly':
                            current_date += timedelta(weeks=1)
                        elif report_type == 'monthly':
                            if current_date.month == 12:
                                current_date = current_date.replace(year=current_date.year + 1, month=1)
                            else:
                                current_date = current_date.replace(month=current_date.month + 1)
                    
                    self.stdout.write(f'Generated reports for {user_obj.username}')
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing user {user_obj.username}: {e}')
                )
                error_count += 1
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated {generated_count} reports')
        )
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(f'{error_count} errors occurred during generation')
            )