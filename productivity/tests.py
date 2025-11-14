from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta, date
import json

from .models import ActivityLog, PerformanceReport
from .utils import ProductivityCalculator, generate_sample_activity_data
from devices.models import Device


class ActivityLogModelTest(TestCase):
    """Test cases for ActivityLog model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.device = Device.objects.create(
            name='Test Device',
            device_type='laptop',
            mac_address='00:11:22:33:44:55',
            operating_system='windows',
            user=self.user
        )
        self.activity_data = {
            'user': self.user,
            'device': self.device,
            'activity_type': 'web_browsing',
            'duration': timedelta(minutes=30),
            'resources_accessed': '["https://example.com", "https://test.com"]',
            'session_id': 'test_session_123'
        }
    
    def test_activity_log_creation(self):
        """Test activity log creation with valid data."""
        activity = ActivityLog.objects.create(**self.activity_data)
        self.assertEqual(activity.user, self.user)
        self.assertEqual(activity.device, self.device)
        self.assertEqual(activity.activity_type, 'web_browsing')
        self.assertEqual(activity.duration, timedelta(minutes=30))
        self.assertEqual(activity.session_id, 'test_session_123')
    
    def test_activity_log_str_method(self):
        """Test ActivityLog string representation."""
        activity = ActivityLog.objects.create(**self.activity_data)
        expected = f"{self.user.username} - Web Browsing ({activity.timestamp.strftime('%Y-%m-%d %H:%M')})"
        self.assertEqual(str(activity), expected)
    
    def test_activity_log_device_ownership_validation(self):
        """Test that device must belong to the user."""
        other_user = User.objects.create_user(username='otheruser', password='pass123')
        other_device = Device.objects.create(
            name='Other Device',
            device_type='tablet',
            mac_address='11:22:33:44:55:66',
            operating_system='ios',
            user=other_user
        )
        
        invalid_data = self.activity_data.copy()
        invalid_data['device'] = other_device
        
        with self.assertRaises(ValidationError):
            ActivityLog.objects.create(**invalid_data)
    
    def test_activity_log_resources_json_validation(self):
        """Test resources_accessed JSON validation."""
        invalid_data = self.activity_data.copy()
        invalid_data['resources_accessed'] = 'invalid json'
        
        with self.assertRaises(ValidationError):
            ActivityLog.objects.create(**invalid_data)
    
    def test_activity_log_duration_properties(self):
        """Test duration property methods."""
        activity = ActivityLog.objects.create(**self.activity_data)
        
        self.assertEqual(activity.duration_minutes, 30.0)
        self.assertEqual(activity.duration_hours, 0.5)
    
    def test_activity_log_resources_methods(self):
        """Test resources list methods."""
        activity = ActivityLog.objects.create(**self.activity_data)
        
        # Test get_resources_list
        resources = activity.get_resources_list()
        self.assertEqual(resources, ["https://example.com", "https://test.com"])
        
        # Test set_resources_list
        new_resources = ["https://newsite.com", "https://another.com"]
        activity.set_resources_list(new_resources)
        self.assertEqual(activity.get_resources_list(), new_resources)
    
    def test_activity_log_productivity_check(self):
        """Test is_productive_activity method."""
        productive_types = ['web_browsing', 'application_usage', 'file_access', 'active']
        non_productive_types = ['login', 'logout', 'idle']
        
        for activity_type in productive_types:
            data = self.activity_data.copy()
            data['activity_type'] = activity_type
            activity = ActivityLog.objects.create(**data)
            self.assertTrue(activity.is_productive_activity())
        
        for activity_type in non_productive_types:
            data = self.activity_data.copy()
            data['activity_type'] = activity_type
            activity = ActivityLog.objects.create(**data)
            self.assertFalse(activity.is_productive_activity())


class PerformanceReportModelTest(TestCase):
    """Test cases for PerformanceReport model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.report_data = {
            'user': self.user,
            'report_type': 'daily',
            'report_date': date.today(),
            'start_date': date.today(),
            'end_date': date.today(),
            'productivity_score': 75.5,
            'attendance_percentage': 90.0,
            'total_active_time': timedelta(hours=6),
            'total_idle_time': timedelta(hours=2),
            'login_count': 3,
            'devices_used': 2
        }
    
    def test_performance_report_creation(self):
        """Test performance report creation with valid data."""
        report = PerformanceReport.objects.create(**self.report_data)
        self.assertEqual(report.user, self.user)
        self.assertEqual(report.report_type, 'daily')
        self.assertEqual(report.productivity_score, 75.5)
        self.assertEqual(report.attendance_percentage, 90.0)
    
    def test_performance_report_str_method(self):
        """Test PerformanceReport string representation."""
        report = PerformanceReport.objects.create(**self.report_data)
        expected = f"{self.user.username} - Daily Report ({report.report_date})"
        self.assertEqual(str(report), expected)
    
    def test_performance_report_date_validation(self):
        """Test date range validation."""
        invalid_data = self.report_data.copy()
        invalid_data['start_date'] = date.today() + timedelta(days=1)
        invalid_data['end_date'] = date.today()
        
        with self.assertRaises(ValidationError):
            PerformanceReport.objects.create(**invalid_data)
    
    def test_performance_report_score_validation(self):
        """Test score range validation."""
        # Test invalid productivity score
        invalid_data = self.report_data.copy()
        invalid_data['productivity_score'] = 150.0
        
        with self.assertRaises(ValidationError):
            PerformanceReport.objects.create(**invalid_data)
        
        # Test invalid attendance percentage
        invalid_data = self.report_data.copy()
        invalid_data['attendance_percentage'] = -10.0
        
        with self.assertRaises(ValidationError):
            PerformanceReport.objects.create(**invalid_data)
    
    def test_performance_report_time_properties(self):
        """Test time property methods."""
        report = PerformanceReport.objects.create(**self.report_data)
        
        self.assertEqual(report.total_time_hours, 8.0)
        self.assertEqual(report.active_time_hours, 6.0)
        self.assertEqual(report.idle_time_hours, 2.0)
        self.assertEqual(report.activity_ratio, 75.0)
    
    def test_performance_report_detailed_metrics(self):
        """Test detailed metrics methods."""
        report = PerformanceReport.objects.create(**self.report_data)
        
        # Test set and get detailed metrics
        metrics = {
            'activity_breakdown': {'web_browsing': 50, 'idle': 30},
            'daily_stats': {'2023-01-01': {'count': 10, 'duration': 3600}}
        }
        report.set_detailed_metrics(metrics)
        retrieved_metrics = report.get_detailed_metrics()
        self.assertEqual(retrieved_metrics, metrics)
    
    def test_performance_report_productivity_calculation(self):
        """Test productivity score calculation method."""
        report = PerformanceReport.objects.create(**self.report_data)
        
        # Test with different values
        report.total_active_time = timedelta(hours=4)
        report.total_idle_time = timedelta(hours=4)
        report.attendance_percentage = 80.0
        report.login_count = 3
        report.devices_used = 1
        
        calculated_score = report.calculate_productivity_score()
        self.assertGreaterEqual(calculated_score, 0.0)
        self.assertLessEqual(calculated_score, 100.0)


class ProductivityCalculatorTest(TestCase):
    """Test cases for ProductivityCalculator utility class."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.device = Device.objects.create(
            name='Test Device',
            device_type='laptop',
            mac_address='00:11:22:33:44:55',
            operating_system='windows',
            user=self.user
        )
        self.calculator = ProductivityCalculator(self.user)
        
        # Create sample activity data
        self.start_date = date.today() - timedelta(days=7)
        self.end_date = date.today()
        
        # Create activities for testing
        for i in range(5):
            ActivityLog.objects.create(
                user=self.user,
                device=self.device,
                activity_type='web_browsing',
                duration=timedelta(hours=1),
                timestamp=timezone.now() - timedelta(days=i)
            )
            ActivityLog.objects.create(
                user=self.user,
                device=self.device,
                activity_type='idle',
                duration=timedelta(minutes=30),
                timestamp=timezone.now() - timedelta(days=i)
            )
    
    def test_productivity_score_calculation(self):
        """Test productivity score calculation."""
        score = self.calculator.calculate_productivity_score(self.start_date, self.end_date)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
    
    def test_attendance_percentage_calculation(self):
        """Test attendance percentage calculation."""
        # Add login activities
        for i in range(3):
            ActivityLog.objects.create(
                user=self.user,
                device=self.device,
                activity_type='login',
                duration=timedelta(seconds=30),
                timestamp=timezone.now() - timedelta(days=i)
            )
        
        attendance = self.calculator.calculate_attendance_percentage(self.start_date, self.end_date)
        self.assertGreaterEqual(attendance, 0.0)
        self.assertLessEqual(attendance, 100.0)
    
    def test_performance_report_generation(self):
        """Test performance report generation."""
        report_date = date.today()
        report = self.calculator.generate_performance_report(report_date, 'daily')
        
        self.assertIsInstance(report, PerformanceReport)
        self.assertEqual(report.user, self.user)
        self.assertEqual(report.report_type, 'daily')
        self.assertEqual(report.report_date, report_date)
        self.assertGreaterEqual(report.productivity_score, 0.0)
        self.assertLessEqual(report.productivity_score, 100.0)
    
    def test_calculator_without_user_raises_error(self):
        """Test that calculator without user raises error for report generation."""
        calculator = ProductivityCalculator()
        
        with self.assertRaises(ValueError):
            calculator.generate_performance_report(date.today())


class ProductivityViewsTest(TestCase):
    """Test cases for productivity views."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        # User profile is created automatically by signal, just set role
        self.user.profile.role = 'student'
        self.user.profile.save()
        
        self.device = Device.objects.create(
            name='Test Device',
            device_type='laptop',
            mac_address='00:11:22:33:44:55',
            operating_system='windows',
            user=self.user
        )
        
        # Create sample activity logs
        for i in range(5):
            ActivityLog.objects.create(
                user=self.user,
                device=self.device,
                activity_type='web_browsing',
                duration=timedelta(hours=1),
                timestamp=timezone.now() - timedelta(days=i)
            )
    
    def test_activity_logs_view_authenticated(self):
        """Test activity logs view for authenticated user."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('productivity:activity_logs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Activity Logs')
    
    def test_activity_logs_view_unauthenticated(self):
        """Test activity logs view redirects unauthenticated users."""
        response = self.client.get(reverse('productivity:activity_logs'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_reports_view_authenticated(self):
        """Test reports view for authenticated user."""
        # Create a sample report
        PerformanceReport.objects.create(
            user=self.user,
            report_type='daily',
            report_date=date.today(),
            start_date=date.today(),
            end_date=date.today(),
            productivity_score=75.0,
            attendance_percentage=90.0
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('productivity:reports'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Productivity Reports')
    
    def test_export_csv_activity_logs(self):
        """Test CSV export for activity logs."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('productivity:export_csv') + '?export_type=activity_logs')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
    
    def test_export_csv_reports(self):
        """Test CSV export for reports."""
        # Create a sample report
        PerformanceReport.objects.create(
            user=self.user,
            report_type='daily',
            report_date=date.today(),
            start_date=date.today(),
            end_date=date.today(),
            productivity_score=75.0,
            attendance_percentage=90.0
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('productivity:export_csv') + '?export_type=reports')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
    
    def test_activity_stats_api(self):
        """Test activity stats API endpoint."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('productivity:activity_stats_api'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('total_activities', data)
        self.assertIn('total_duration_hours', data)
        self.assertIn('activity_breakdown', data)
        self.assertIn('daily_activity', data)
    
    def test_activity_logs_filtering(self):
        """Test activity logs view with filtering."""
        self.client.login(username='testuser', password='testpass123')
        
        # Test activity type filter
        response = self.client.get(reverse('productivity:activity_logs') + '?activity_type=web_browsing')
        self.assertEqual(response.status_code, 200)
        
        # Test date range filter
        start_date = (date.today() - timedelta(days=3)).strftime('%Y-%m-%d')
        end_date = date.today().strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('productivity:activity_logs') + f'?start_date={start_date}&end_date={end_date}'
        )
        self.assertEqual(response.status_code, 200)
    
    def test_reports_filtering(self):
        """Test reports view with filtering."""
        # Create sample reports
        PerformanceReport.objects.create(
            user=self.user,
            report_type='daily',
            report_date=date.today(),
            start_date=date.today(),
            end_date=date.today(),
            productivity_score=75.0,
            attendance_percentage=90.0
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        # Test report type filter
        response = self.client.get(reverse('productivity:reports') + '?report_type=daily')
        self.assertEqual(response.status_code, 200)


class ProductivityUtilsTest(TestCase):
    """Test cases for productivity utility functions."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.device = Device.objects.create(
            name='Test Device',
            device_type='laptop',
            mac_address='00:11:22:33:44:55',
            operating_system='windows',
            user=self.user
        )
    
    def test_generate_sample_activity_data(self):
        """Test sample activity data generation."""
        initial_count = ActivityLog.objects.count()
        
        generate_sample_activity_data(self.user, self.device, days=3)
        
        final_count = ActivityLog.objects.count()
        self.assertGreater(final_count, initial_count)
        
        # Check that activities were created for the user and device
        user_activities = ActivityLog.objects.filter(user=self.user, device=self.device)
        self.assertGreater(user_activities.count(), 0)
    
    def test_weekday_counting(self):
        """Test weekday counting utility."""
        calculator = ProductivityCalculator()
        
        # Test a week with 5 weekdays
        start_date = date(2023, 1, 2)  # Monday
        end_date = date(2023, 1, 6)    # Friday
        weekdays = calculator._count_weekdays(start_date, end_date)
        self.assertEqual(weekdays, 5)
        
        # Test a week including weekend
        start_date = date(2023, 1, 2)  # Monday
        end_date = date(2023, 1, 8)    # Sunday
        weekdays = calculator._count_weekdays(start_date, end_date)
        self.assertEqual(weekdays, 5)
    
    def test_report_date_range_calculation(self):
        """Test report date range calculation."""
        calculator = ProductivityCalculator()
        report_date = date(2023, 1, 15)  # Sunday
        
        # Test daily report
        start, end = calculator._get_report_date_range(report_date, 'daily')
        self.assertEqual(start, report_date)
        self.assertEqual(end, report_date)
        
        # Test weekly report
        start, end = calculator._get_report_date_range(report_date, 'weekly')
        self.assertEqual(start, date(2023, 1, 9))   # Monday of that week
        self.assertEqual(end, date(2023, 1, 15))    # Sunday of that week
        
        # Test monthly report
        start, end = calculator._get_report_date_range(report_date, 'monthly')
        self.assertEqual(start, date(2023, 1, 1))   # First day of month
        self.assertEqual(end, date(2023, 1, 31))    # Last day of month
