"""
Utility functions for productivity calculations and report generation.
"""

import json
from datetime import datetime, timedelta, date
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from django.contrib.auth.models import User
from .models import ActivityLog, PerformanceReport
from devices.models import Device


class ProductivityCalculator:
    """
    Class for calculating productivity metrics and generating performance reports.
    """
    
    def __init__(self, user=None):
        """
        Initialize calculator for a specific user or all users.
        
        Args:
            user: User instance or None for all users
        """
        self.user = user
    
    def calculate_productivity_score(self, start_date, end_date):
        """
        Calculate productivity score for the given date range.
        
        Args:
            start_date: Start date for calculation
            end_date: End date for calculation
            
        Returns:
            float: Productivity score (0-100)
        """
        # Get activity logs for the period
        queryset = self._get_activity_queryset(start_date, end_date)
        
        if not queryset.exists():
            return 0.0
        
        # Calculate total time and productive time
        total_duration = queryset.aggregate(total=Sum('duration'))['total']
        if not total_duration:
            return 0.0
        
        productive_activities = queryset.filter(
            activity_type__in=['web_browsing', 'application_usage', 'file_access', 'active']
        )
        productive_duration = productive_activities.aggregate(total=Sum('duration'))['total']
        
        if not productive_duration:
            productive_ratio = 0.0
        else:
            productive_ratio = (productive_duration.total_seconds() / total_duration.total_seconds()) * 100
        
        # Calculate engagement score based on activity frequency
        activity_count = queryset.count()
        days_in_period = (end_date - start_date).days + 1
        activities_per_day = activity_count / days_in_period if days_in_period > 0 else 0
        
        # Normalize engagement score (optimal range: 5-20 activities per day)
        engagement_score = min(100, (activities_per_day / 20) * 100) if activities_per_day > 0 else 0
        
        # Calculate consistency score based on daily activity distribution
        consistency_score = self._calculate_consistency_score(queryset, start_date, end_date)
        
        # Weighted final score
        final_score = (
            productive_ratio * 0.5 +      # 50% weight on productive activities
            engagement_score * 0.3 +      # 30% weight on engagement level
            consistency_score * 0.2       # 20% weight on consistency
        )
        
        return min(100.0, max(0.0, final_score))
    
    def calculate_attendance_percentage(self, start_date, end_date, expected_days=None):
        """
        Calculate attendance percentage for the given date range.
        
        Args:
            start_date: Start date for calculation
            end_date: End date for calculation
            expected_days: Number of expected attendance days (defaults to weekdays)
            
        Returns:
            float: Attendance percentage (0-100)
        """
        if expected_days is None:
            # Count weekdays in the period
            expected_days = self._count_weekdays(start_date, end_date)
        
        if expected_days == 0:
            return 100.0  # No expected days means 100% attendance
        
        # Count days with login activity
        queryset = self._get_activity_queryset(start_date, end_date)
        login_activities = queryset.filter(activity_type='login')
        
        # Get unique days with login activity
        attended_days = login_activities.extra(
            select={'day': 'date(timestamp)'}
        ).values('day').distinct().count()
        
        return (attended_days / expected_days) * 100
    
    def generate_performance_report(self, report_date, report_type='daily'):
        """
        Generate a performance report for the specified date and type.
        
        Args:
            report_date: Date for the report
            report_type: Type of report ('daily', 'weekly', 'monthly')
            
        Returns:
            PerformanceReport: Generated report instance
        """
        if not self.user:
            raise ValueError("User must be specified for report generation")
        
        # Calculate date range based on report type
        start_date, end_date = self._get_report_date_range(report_date, report_type)
        
        # Get or create report
        report, created = PerformanceReport.objects.get_or_create(
            user=self.user,
            report_type=report_type,
            report_date=report_date,
            defaults={
                'start_date': start_date,
                'end_date': end_date,
            }
        )
        
        # Calculate metrics
        queryset = self._get_activity_queryset(start_date, end_date)
        
        # Basic metrics
        report.productivity_score = self.calculate_productivity_score(start_date, end_date)
        report.attendance_percentage = self.calculate_attendance_percentage(start_date, end_date)
        
        # Time metrics
        total_active = queryset.filter(
            activity_type__in=['web_browsing', 'application_usage', 'file_access', 'active']
        ).aggregate(total=Sum('duration'))['total'] or timedelta(0)
        
        total_idle = queryset.filter(
            activity_type='idle'
        ).aggregate(total=Sum('duration'))['total'] or timedelta(0)
        
        report.total_active_time = total_active
        report.total_idle_time = total_idle
        
        # Activity metrics
        report.login_count = queryset.filter(activity_type='login').count()
        
        # Count unique devices used
        device_ids = queryset.values_list('device_id', flat=True).distinct()
        report.devices_used = len(set(device_ids))
        
        # Detailed metrics (stored as JSON)
        detailed_metrics = self._calculate_detailed_metrics(queryset, start_date, end_date)
        report.set_detailed_metrics(detailed_metrics)
        
        # Recalculate productivity score using the model's method
        report.productivity_score = report.calculate_productivity_score()
        
        report.save()
        return report
    
    def _get_activity_queryset(self, start_date, end_date):
        """
        Get activity logs queryset for the specified date range and user.
        """
        queryset = ActivityLog.objects.filter(
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        )
        
        if self.user:
            queryset = queryset.filter(user=self.user)
        
        return queryset
    
    def _calculate_consistency_score(self, queryset, start_date, end_date):
        """
        Calculate consistency score based on daily activity distribution.
        """
        # Group activities by day
        daily_activities = queryset.extra(
            select={'day': 'date(timestamp)'}
        ).values('day').annotate(
            count=Count('id'),
            duration=Sum('duration')
        ).order_by('day')
        
        if not daily_activities:
            return 0.0
        
        # Calculate coefficient of variation for daily activity counts
        activity_counts = [day['count'] for day in daily_activities]
        if len(activity_counts) < 2:
            return 100.0  # Perfect consistency with only one day
        
        mean_count = sum(activity_counts) / len(activity_counts)
        if mean_count == 0:
            return 0.0
        
        variance = sum((count - mean_count) ** 2 for count in activity_counts) / len(activity_counts)
        std_dev = variance ** 0.5
        cv = std_dev / mean_count
        
        # Convert coefficient of variation to consistency score (lower CV = higher consistency)
        consistency_score = max(0, 100 - (cv * 50))  # Scale CV to 0-100 range
        
        return consistency_score
    
    def _count_weekdays(self, start_date, end_date):
        """
        Count weekdays (Monday-Friday) in the given date range.
        """
        count = 0
        current_date = start_date
        
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Monday=0, Friday=4
                count += 1
            current_date += timedelta(days=1)
        
        return count
    
    def _get_report_date_range(self, report_date, report_type):
        """
        Calculate start and end dates for the report based on type.
        """
        if report_type == 'daily':
            return report_date, report_date
        elif report_type == 'weekly':
            # Start from Monday of the week
            start_date = report_date - timedelta(days=report_date.weekday())
            end_date = start_date + timedelta(days=6)
            return start_date, end_date
        elif report_type == 'monthly':
            # Start from first day of the month
            start_date = report_date.replace(day=1)
            # End on last day of the month
            if start_date.month == 12:
                next_month = start_date.replace(year=start_date.year + 1, month=1)
            else:
                next_month = start_date.replace(month=start_date.month + 1)
            end_date = next_month - timedelta(days=1)
            return start_date, end_date
        else:
            raise ValueError(f"Unsupported report type: {report_type}")
    
    def _calculate_detailed_metrics(self, queryset, start_date, end_date):
        """
        Calculate detailed metrics for the report.
        """
        # Activity type breakdown
        activity_breakdown = {}
        for activity_type, _ in ActivityLog.ACTIVITY_TYPE_CHOICES:
            activities = queryset.filter(activity_type=activity_type)
            count = activities.count()
            duration = activities.aggregate(total=Sum('duration'))['total']
            
            activity_breakdown[activity_type] = {
                'count': count,
                'duration_seconds': duration.total_seconds() if duration else 0,
                'percentage': (count / queryset.count() * 100) if queryset.count() > 0 else 0
            }
        
        # Daily breakdown
        daily_breakdown = {}
        daily_activities = queryset.extra(
            select={'day': 'date(timestamp)'}
        ).values('day').annotate(
            count=Count('id'),
            duration=Sum('duration')
        ).order_by('day')
        
        for day_data in daily_activities:
            day_str = day_data['day'] if isinstance(day_data['day'], str) else day_data['day'].strftime('%Y-%m-%d')
            daily_breakdown[day_str] = {
                'count': day_data['count'],
                'duration_seconds': day_data['duration'].total_seconds() if day_data['duration'] else 0
            }
        
        # Device usage breakdown
        device_breakdown = {}
        device_activities = queryset.values('device__name', 'device__device_type').annotate(
            count=Count('id'),
            duration=Sum('duration')
        ).order_by('-count')
        
        for device_data in device_activities:
            device_name = device_data['device__name']
            device_breakdown[device_name] = {
                'type': device_data['device__device_type'],
                'count': device_data['count'],
                'duration_seconds': device_data['duration'].total_seconds() if device_data['duration'] else 0
            }
        
        return {
            'activity_breakdown': activity_breakdown,
            'daily_breakdown': daily_breakdown,
            'device_breakdown': device_breakdown,
            'calculation_date': timezone.now().isoformat(),
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        }


def generate_sample_activity_data(user, device, days=7):
    """
    Generate sample activity data for testing purposes.
    
    Args:
        user: User instance
        device: Device instance
        days: Number of days to generate data for
    """
    import random
    from datetime import datetime, timedelta
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days-1)
    
    activity_types = ['login', 'web_browsing', 'application_usage', 'active', 'idle', 'logout']
    
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        
        # Skip weekends for more realistic data
        if current_date.weekday() >= 5:
            continue
        
        # Generate 5-15 activities per day
        num_activities = random.randint(5, 15)
        
        for _ in range(num_activities):
            # Random time during the day (8 AM to 6 PM)
            hour = random.randint(8, 17)
            minute = random.randint(0, 59)
            timestamp = timezone.make_aware(
                datetime.combine(current_date, datetime.min.time().replace(hour=hour, minute=minute))
            )
            
            activity_type = random.choice(activity_types)
            
            # Duration based on activity type
            if activity_type in ['login', 'logout']:
                duration = timedelta(seconds=random.randint(1, 30))
            elif activity_type == 'idle':
                duration = timedelta(minutes=random.randint(1, 30))
            else:
                duration = timedelta(minutes=random.randint(5, 120))
            
            # Sample resources
            resources = []
            if activity_type == 'web_browsing':
                resources = ['https://example.com', 'https://education.site.com']
            elif activity_type == 'application_usage':
                resources = ['Microsoft Word', 'Google Chrome', 'Calculator']
            
            ActivityLog.objects.create(
                user=user,
                device=device,
                activity_type=activity_type,
                duration=duration,
                timestamp=timestamp,
                resources_accessed=json.dumps(resources) if resources else '',
                session_id=f"session_{current_date.strftime('%Y%m%d')}_{user.id}"
            )


def bulk_generate_reports(report_type='daily', days_back=30):
    """
    Generate reports for all users for the specified period.
    
    Args:
        report_type: Type of report to generate
        days_back: Number of days back to generate reports for
    """
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days_back)
    
    users_with_activity = User.objects.filter(
        activity_logs__timestamp__date__gte=start_date
    ).distinct()
    
    generated_count = 0
    
    for user in users_with_activity:
        calculator = ProductivityCalculator(user)
        
        current_date = start_date
        while current_date <= end_date:
            try:
                report = calculator.generate_performance_report(current_date, report_type)
                generated_count += 1
                print(f"Generated {report_type} report for {user.username} on {current_date}")
            except Exception as e:
                print(f"Error generating report for {user.username} on {current_date}: {e}")
            
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
    
    return generated_count