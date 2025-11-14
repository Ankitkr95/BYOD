from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json

from users.models import UserProfile
from devices.models import Device
from productivity.models import ActivityLog, PerformanceReport
from security.models import SessionTracker
from .utils import DashboardDataAggregator, get_productivity_insights
from .views import DashboardView, StatsAPIView


class DashboardViewTestCase(TestCase):
    """
    Test cases for dashboard views and role-based content filtering.
    """
    
    def setUp(self):
        """Set up test data for dashboard tests."""
        self.client = Client()
        
        # Create test users with different roles
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='testpass123'
        )
        self.admin_profile = UserProfile.objects.get(user=self.admin_user)
        self.admin_profile.role = 'admin'
        self.admin_profile.save()
        
        self.student_user = User.objects.create_user(
            username='student_test',
            email='student@test.com',
            password='testpass123'
        )
        self.student_profile = UserProfile.objects.get(user=self.student_user)
        self.student_profile.role = 'student'
        self.student_profile.save()
        
        # Create test device
        self.device1 = Device.objects.create(
            name='Test Laptop',
            device_type='laptop',
            mac_address='AA:BB:CC:DD:EE:FF',
            operating_system='windows',
            compliance_status=True,
            user=self.student_user
        )
    
    def test_dashboard_view_requires_login(self):
        """Test that dashboard view requires authentication."""
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_admin_dashboard_access(self):
        """Test admin user can access dashboard with admin content."""
        self.client.login(username='admin_test', password='testpass123')
        response = self.client.get(reverse('dashboard:home'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
        self.assertEqual(response.context['user_role'], 'admin')
    
    def test_student_dashboard_access(self):
        """Test student user can access dashboard with student content."""
        self.client.login(username='student_test', password='testpass123')
        response = self.client.get(reverse('dashboard:home'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
        self.assertEqual(response.context['user_role'], 'student')


class StatsAPIViewTestCase(TestCase):
    """
    Test cases for real-time dashboard statistics API.
    """
    
    def setUp(self):
        """Set up test data for API tests."""
        self.client = Client()
        
        # Create test user
        self.user = User.objects.create_user(
            username='api_test',
            email='api@test.com',
            password='testpass123'
        )
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.role = 'admin'
        self.profile.save()
    
    def test_stats_api_requires_login(self):
        """Test that stats API requires authentication."""
        response = self.client.get(reverse('dashboard:stats_api'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_stats_api_returns_json(self):
        """Test that stats API returns JSON response."""
        self.client.login(username='api_test', password='testpass123')
        response = self.client.get(reverse('dashboard:stats_api'))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = json.loads(response.content)
        self.assertIn('timestamp', data)


class DashboardDataAggregatorTestCase(TestCase):
    """
    Test cases for dashboard data aggregation utility functions.
    """
    
    def setUp(self):
        """Set up test data for aggregation tests."""
        # Create test user
        self.student_user = User.objects.create_user(
            username='student_agg',
            email='student_agg@test.com',
            password='testpass123'
        )
        self.student_profile = UserProfile.objects.get(user=self.student_user)
        self.student_profile.role = 'student'
        self.student_profile.save()
        
        # Create test devices
        self.compliant_device = Device.objects.create(
            name='Compliant Device',
            device_type='laptop',
            mac_address='AA:BB:CC:DD:EE:22',
            operating_system='windows',
            compliance_status=True,
            user=self.student_user
        )
        
        self.non_compliant_device = Device.objects.create(
            name='Non-Compliant Device',
            device_type='tablet',
            mac_address='11:22:33:44:55:77',
            operating_system='android',
            compliance_status=False,
            user=self.student_user
        )
    
    def test_device_compliance_overview(self):
        """Test device compliance overview aggregation."""
        aggregator = DashboardDataAggregator()
        result = aggregator.get_device_compliance_overview()
        
        self.assertEqual(result['total_devices'], 2)
        self.assertEqual(result['compliant_devices'], 1)
        self.assertEqual(result['non_compliant_devices'], 1)
        self.assertEqual(result['compliance_rate'], 50.0)
        self.assertIsInstance(result['device_types'], list)
    
    def test_productivity_summaries(self):
        """Test productivity summaries aggregation."""
        aggregator = DashboardDataAggregator()
        result = aggregator.get_productivity_summaries()
        
        # Should handle empty data gracefully
        self.assertIsInstance(result['avg_productivity'], (int, float))
        self.assertIsInstance(result['avg_attendance'], (int, float))
        self.assertIsInstance(result['top_performers'], list)


class DashboardUtilityFunctionsTestCase(TestCase):
    """
    Test cases for dashboard utility functions.
    """
    
    def setUp(self):
        """Set up test data for utility function tests."""
        self.user = User.objects.create_user(
            username='util_test',
            email='util@test.com',
            password='testpass123'
        )
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.role = 'student'
        self.profile.save()
        
        # Create performance report for insights
        self.report = PerformanceReport.objects.create(
            user=self.user,
            report_type='daily',
            report_date=timezone.now().date(),
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            productivity_score=45.0,  # Low score for testing
            attendance_percentage=70.0,  # Low attendance for testing
            total_active_time=timedelta(hours=1),  # Low activity for testing
            login_count=1,
            devices_used=1
        )
    
    def test_get_productivity_insights(self):
        """Test productivity insights generation."""
        insights = get_productivity_insights('student', days=7)
        
        self.assertIn('insights', insights)
        self.assertIn('recommendations', insights)
        self.assertIn('avg_productivity', insights)
        self.assertIn('avg_attendance', insights)
    
    def test_productivity_insights_with_no_data(self):
        """Test productivity insights when no data is available."""
        insights = get_productivity_insights('teacher', days=7)  # Different role with no data
        
        self.assertEqual(insights['insights'], [])
        self.assertIn('No data available', insights['recommendations'][0])


class DashboardIntegrationTestCase(TestCase):
    """
    Integration tests for complete dashboard workflows.
    """
    
    def setUp(self):
        """Set up test data for integration tests."""
        self.admin = User.objects.create_user('admin_int', 'admin_int@test.com', 'pass123')
        UserProfile.objects.filter(user=self.admin).update(role='admin')
    
    def test_complete_dashboard_workflow_admin(self):
        """Test complete dashboard workflow for admin user."""
        self.client.login(username='admin_int', password='pass123')
        
        # Test dashboard page
        dashboard_response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(dashboard_response.status_code, 200)
        
        # Test stats API
        stats_response = self.client.get(reverse('dashboard:stats_api'))
        self.assertEqual(stats_response.status_code, 200)
        
        stats_data = json.loads(stats_response.content)
        self.assertIn('timestamp', stats_data)
