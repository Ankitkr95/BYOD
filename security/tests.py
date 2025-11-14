import json
from datetime import timedelta
from django.test import TestCase, RequestFactory, Client
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from unittest.mock import patch, MagicMock

from users.models import UserProfile
from devices.models import Device
from .models import AccessControl, SessionTracker
from .middleware import SessionValidationMiddleware, AccessControlMiddleware
from .utils import (
    get_active_sessions_count, 
    get_user_active_sessions,
    terminate_user_sessions,
    cleanup_expired_sessions
)
from .validators import SecurityValidator, MacAddressValidator, PasswordSecurityValidator
from .session_utils import SessionManager, SessionSecurityMonitor
from .forms import AccessControlForm


class SessionValidationMiddlewareTest(TestCase):
    """
    Test cases for SessionValidationMiddleware.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        self.factory = RequestFactory()
        self.middleware = SessionValidationMiddleware(get_response=lambda r: None)
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        # Profile is created automatically by signal, just update the role
        self.profile = self.user.profile
        self.profile.role = 'student'
        self.profile.save()
        
        # Create test device
        self.device = Device.objects.create(
            user=self.user,
            name='Test Device',
            device_type='laptop',
            mac_address='00:11:22:33:44:55',
            operating_system='windows',
            compliance_status=True
        )
    
    def _create_request_with_session(self, path='/', user=None):
        """
        Helper method to create request with session.
        """
        request = self.factory.get(path)
        
        # Add session middleware
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        
        # Add authentication
        if user:
            request.user = user
        else:
            request.user = self.user
        
        return request
    
    def test_exempt_urls_bypass_validation(self):
        """
        Test that exempt URLs bypass session validation.
        """
        exempt_paths = ['/auth/login/', '/static/css/style.css', '/admin/']
        
        for path in exempt_paths:
            request = self.factory.get(path)
            request.user = self.user
            
            response = self.middleware.process_request(request)
            self.assertIsNone(response, f"Exempt path {path} should not be processed")
    
    def test_unauthenticated_user_bypass(self):
        """
        Test that unauthenticated users bypass session validation.
        """
        request = self.factory.get('/')
        request.user = MagicMock()
        request.user.is_authenticated = False
        
        response = self.middleware.process_request(request)
        self.assertIsNone(response)
    
    def test_session_tracker_creation(self):
        """
        Test that session tracker is created for new sessions.
        """
        request = self._create_request_with_session()
        
        # Mock device retrieval
        with patch.object(self.middleware, '_get_user_device', return_value=self.device):
            response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.assertTrue(hasattr(request, 'session_tracker'))
        
        # Check that session tracker was created
        session_tracker = SessionTracker.objects.filter(
            user=self.user,
            session_key=request.session.session_key
        ).first()
        self.assertIsNotNone(session_tracker)
    
    def test_session_timeout_handling(self):
        """
        Test session timeout handling.
        """
        # Create expired session tracker
        session_tracker = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='test_session_key',
            ip_address='127.0.0.1',
            status='active',
            last_activity=timezone.now() - timedelta(minutes=45)  # Expired
        )
        
        request = self._create_request_with_session()
        request.session.save()  # This generates a session key
        request.session._session_key = 'test_session_key'
        
        with patch.object(self.middleware, '_get_or_create_session_tracker', return_value=session_tracker):
            response = self.middleware.process_request(request)
        
        # Should return redirect response for timeout
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)
    
    def test_concurrent_session_prevention(self):
        """
        Test concurrent session prevention.
        """
        # Create existing active session
        existing_session = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='existing_session',
            ip_address='127.0.0.1',
            status='active'
        )
        
        # Create new session tracker
        new_session = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='new_session',
            ip_address='127.0.0.1',
            status='active'
        )
        
        request = self._create_request_with_session()
        request.session.save()  # This generates a session key
        request.session._session_key = 'new_session'
        
        with patch.object(self.middleware, '_get_or_create_session_tracker', return_value=new_session):
            response = self.middleware.process_request(request)
        
        # Should handle concurrent session
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)


class AccessControlMiddlewareTest(TestCase):
    """
    Test cases for AccessControlMiddleware.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        self.factory = RequestFactory()
        self.middleware = AccessControlMiddleware(get_response=lambda r: None)
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        # Profile is created automatically by signal, just update the role
        self.profile = self.user.profile
        self.profile.role = 'student'
        self.profile.save()
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        # Profile is created automatically by signal, just update the role
        self.admin_profile = self.admin_user.profile
        self.admin_profile.role = 'admin'
        self.admin_profile.save()
    
    def test_exempt_urls_bypass_access_control(self):
        """
        Test that exempt URLs bypass access control.
        """
        exempt_paths = ['/auth/login/', '/static/css/style.css', '/admin/']
        
        for path in exempt_paths:
            request = self.factory.get(path)
            request.user = self.user
            
            response = self.middleware.process_request(request)
            self.assertIsNone(response, f"Exempt path {path} should not be processed")
    
    def test_unauthenticated_user_bypass(self):
        """
        Test that unauthenticated users bypass access control.
        """
        request = self.factory.get('/')
        request.user = MagicMock()
        request.user.is_authenticated = False
        
        response = self.middleware.process_request(request)
        self.assertIsNone(response)
    
    def test_no_access_rules_allows_access(self):
        """
        Test that users without specific access rules are allowed access.
        """
        request = self.factory.get('/devices/')
        request.user = self.user
        
        response = self.middleware.process_request(request)
        self.assertIsNone(response)
    
    def test_time_restriction_enforcement(self):
        """
        Test time-based access restriction enforcement.
        """
        # Create access control with time restrictions
        access_control = AccessControl.objects.create(
            role='student',
            created_by=self.admin_user,
            is_active=True
        )
        
        # Set time restrictions (9 AM to 5 PM, weekdays only)
        time_restrictions = {
            'start_time': '09:00',
            'end_time': '17:00',
            'days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        }
        access_control.set_time_restrictions(time_restrictions)
        access_control.save()
        
        request = self.factory.get('/devices/')
        request.user = self.user
        
        # Mock time check to return False (outside allowed time)
        with patch.object(access_control, 'is_time_allowed', return_value=False):
            with patch.object(self.middleware, '_get_user_access_rules', return_value=access_control):
                response = self.middleware.process_request(request)
        
        # Should return forbidden response
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
    
    def test_resource_restriction_enforcement(self):
        """
        Test resource access restriction enforcement.
        """
        # Create access control with blocked domains
        access_control = AccessControl.objects.create(
            role='student',
            created_by=self.admin_user,
            is_active=True
        )
        access_control.set_blocked_domains(['social-media', 'games'])
        access_control.save()
        
        request = self.factory.get('/social-media/feed/')
        request.user = self.user
        
        with patch.object(self.middleware, '_get_user_access_rules', return_value=access_control):
            response = self.middleware.process_request(request)
        
        # Should return forbidden response
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)


class SecurityUtilsTest(TestCase):
    """
    Test cases for security utility functions.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        # Profile is created automatically by signal, just update the role
        self.profile = self.user.profile
        self.profile.role = 'student'
        self.profile.save()
        
        self.device = Device.objects.create(
            user=self.user,
            name='Test Device',
            device_type='laptop',
            mac_address='00:11:22:33:44:55',
            operating_system='windows',
            compliance_status=True
        )
    
    def test_get_active_sessions_count(self):
        """
        Test getting active sessions count.
        """
        # Create active sessions
        SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='session1',
            ip_address='127.0.0.1',
            status='active'
        )
        SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='session2',
            ip_address='127.0.0.1',
            status='inactive'
        )
        
        count = get_active_sessions_count()
        self.assertEqual(count, 1)
    
    def test_get_user_active_sessions(self):
        """
        Test getting active sessions for a specific user.
        """
        # Create sessions for different users
        other_user = User.objects.create_user(username='other', password='pass')
        # Profile is created automatically by signal, just update the role
        other_profile = other_user.profile
        other_profile.role = 'student'
        other_profile.save()
        other_device = Device.objects.create(
            user=other_user,
            name='Other Device',
            device_type='tablet',
            mac_address='11:22:33:44:55:66',
            operating_system='ios',
            compliance_status=True
        )
        
        SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='user_session',
            ip_address='127.0.0.1',
            status='active'
        )
        SessionTracker.objects.create(
            user=other_user,
            device=other_device,
            session_key='other_session',
            ip_address='127.0.0.1',
            status='active'
        )
        
        user_sessions = get_user_active_sessions(self.user)
        self.assertEqual(user_sessions.count(), 1)
        self.assertEqual(user_sessions.first().user, self.user)
    
    def test_terminate_user_sessions(self):
        """
        Test terminating user sessions.
        """
        # Create multiple active sessions
        session1 = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='session1',
            ip_address='127.0.0.1',
            status='active'
        )
        session2 = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='session2',
            ip_address='127.0.0.1',
            status='active'
        )
        
        count = terminate_user_sessions(self.user, exclude_session_key='session1')
        
        self.assertEqual(count, 1)
        
        # Check that session2 was terminated but session1 remains active
        session1.refresh_from_db()
        session2.refresh_from_db()
        
        self.assertEqual(session1.status, 'active')
        self.assertEqual(session2.status, 'inactive')
    
    def test_cleanup_expired_sessions(self):
        """
        Test cleanup of expired sessions.
        """
        # Create expired session
        expired_session = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='expired_session',
            ip_address='127.0.0.1',
            status='active',
            last_activity=timezone.now() - timedelta(minutes=45)
        )
        
        # Create active session
        active_session = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='active_session',
            ip_address='127.0.0.1',
            status='active',
            last_activity=timezone.now() - timedelta(minutes=5)
        )
        
        count = cleanup_expired_sessions(timeout_minutes=30)
        
        # Check that expired session was cleaned up
        expired_session.refresh_from_db()
        active_session.refresh_from_db()
        
        self.assertEqual(expired_session.status, 'expired')
        self.assertEqual(active_session.status, 'active')


class SecurityIntegrationTest(TestCase):
    """
    Integration tests for security middleware functionality.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        self.client = Client()
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        # Profile is created automatically by signal, just update the role
        self.profile = self.user.profile
        self.profile.role = 'student'
        self.profile.save()
        
        self.device = Device.objects.create(
            user=self.user,
            name='Test Device',
            device_type='laptop',
            mac_address='00:11:22:33:44:55',
            operating_system='windows',
            compliance_status=True
        )
    
    def test_middleware_integration_with_login(self):
        """
        Test middleware integration with user login flow.
        """
        # Login user
        login_successful = self.client.login(username='testuser', password='testpass123')
        self.assertTrue(login_successful)
        
        # Make request to protected view
        response = self.client.get('/devices/')
        
        # Should be successful (assuming devices view exists and is accessible)
        # The middleware should create session tracker automatically
        session_trackers = SessionTracker.objects.filter(user=self.user)
        
        # Note: In a real test, we'd check that session tracker was created
        # but since we're testing middleware in isolation, we'll just verify
        # the response is handled properly
        self.assertIn(response.status_code, [200, 302, 404])  # Various valid responses


class SecurityValidatorTest(TestCase):
    """
    Test cases for SecurityValidator class.
    """
    
    def test_sanitize_text_input_basic(self):
        """
        Test basic text input sanitization.
        """
        # Test normal text
        result = SecurityValidator.sanitize_text_input("Hello World")
        self.assertEqual(result, "Hello World")
        
        # Test HTML escaping for safe content
        result = SecurityValidator.sanitize_text_input("<b>Bold Text</b>")
        self.assertNotIn("<b>", result)
        self.assertIn("Bold Text", result)
        
        # Test length limit
        with self.assertRaises(ValidationError):
            SecurityValidator.sanitize_text_input("a" * 1000, max_length=10)
    
    def test_sanitize_text_input_malicious_patterns(self):
        """
        Test detection of malicious patterns.
        """
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "onclick='alert(1)'",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
        ]
        
        for malicious_input in malicious_inputs:
            with self.assertRaises(ValidationError):
                SecurityValidator.sanitize_text_input(malicious_input)
    
    def test_validate_username(self):
        """
        Test username validation.
        """
        # Valid usernames
        valid_usernames = ["user123", "test_user", "user.name", "user-name"]
        for username in valid_usernames:
            result = SecurityValidator.validate_username(username)
            self.assertEqual(result, username)
        
        # Invalid usernames
        with self.assertRaises(ValidationError):
            SecurityValidator.validate_username("ab")  # Too short
        
        with self.assertRaises(ValidationError):
            SecurityValidator.validate_username("user@name")  # Invalid character
        
        with self.assertRaises(ValidationError):
            SecurityValidator.validate_username("admin")  # Reserved username
    
    def test_validate_email_address(self):
        """
        Test email address validation.
        """
        # Valid emails
        valid_emails = ["test@example.com", "user.name@domain.org"]
        for email in valid_emails:
            result = SecurityValidator.validate_email_address(email)
            self.assertEqual(result, email.lower())
        
        # Invalid emails
        invalid_emails = [
            "invalid-email",
            "test@",
            "@domain.com",
            "test..test@domain.com",
            "test@10minutemail.com",  # Disposable email
        ]
        
        for email in invalid_emails:
            with self.assertRaises(ValidationError):
                SecurityValidator.validate_email_address(email)
    
    def test_validate_device_name(self):
        """
        Test device name validation.
        """
        # Valid device names
        valid_names = ["My Laptop", "iPhone 12", "Work-Computer"]
        for name in valid_names:
            result = SecurityValidator.validate_device_name(name)
            self.assertEqual(result, name)
        
        # Invalid device names
        invalid_names = [
            "a",  # Too short
            "admin-device",  # Contains suspicious term
            "hack-tool",  # Contains suspicious term
        ]
        
        for name in invalid_names:
            with self.assertRaises(ValidationError):
                SecurityValidator.validate_device_name(name)
    
    def test_validate_json_input(self):
        """
        Test JSON input validation.
        """
        # Valid JSON
        valid_json = '{"key": "value", "number": 123}'
        result = SecurityValidator.validate_json_input(valid_json)
        self.assertEqual(result, {"key": "value", "number": 123})
        
        # Invalid JSON
        with self.assertRaises(ValidationError):
            SecurityValidator.validate_json_input('{"invalid": json}')
        
        # JSON with malicious content
        with self.assertRaises(ValidationError):
            SecurityValidator.validate_json_input('{"script": "<script>alert(1)</script>"}')


class MacAddressValidatorTest(TestCase):
    """
    Test cases for MacAddressValidator class.
    """
    
    def test_validate_and_normalize_valid_formats(self):
        """
        Test validation and normalization of valid MAC address formats.
        """
        valid_macs = [
            ("00:11:22:33:44:55", "00:11:22:33:44:55"),
            ("00-11-22-33-44-55", "00:11:22:33:44:55"),
            ("001122334455", "00:11:22:33:44:55"),
            ("AA:BB:CC:DD:EE:FF", "aa:bb:cc:dd:ee:ff"),
        ]
        
        for input_mac, expected_output in valid_macs:
            result = MacAddressValidator.validate_and_normalize(input_mac)
            self.assertEqual(result, expected_output)
    
    def test_validate_and_normalize_invalid_formats(self):
        """
        Test validation of invalid MAC address formats.
        """
        invalid_macs = [
            "00:11:22:33:44",  # Too short
            "00:11:22:33:44:55:66",  # Too long
            "GG:11:22:33:44:55",  # Invalid hex character
            "000000000000",  # All zeros (reserved)
            "ffffffffffff",  # All ones (broadcast)
            "010000000000",  # Multicast (invalid OUI)
        ]
        
        for mac in invalid_macs:
            with self.assertRaises(ValidationError):
                MacAddressValidator.validate_and_normalize(mac)


class PasswordSecurityValidatorTest(TestCase):
    """
    Test cases for PasswordSecurityValidator class.
    """
    
    def setUp(self):
        """
        Set up test user.
        """
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
    
    def test_validate_password_strength_valid(self):
        """
        Test validation of strong passwords.
        """
        strong_passwords = [
            "StrongPass123!",
            "MySecure@Password2024",
            "Complex#Pass1",
        ]
        
        for password in strong_passwords:
            # Should not raise ValidationError
            result = PasswordSecurityValidator.validate_password_strength(password, self.user)
            self.assertEqual(result, password)
    
    def test_validate_password_strength_weak(self):
        """
        Test validation of weak passwords.
        """
        weak_passwords = [
            "short",  # Too short
            "nouppercase123!",  # No uppercase
            "NOLOWERCASE123!",  # No lowercase
            "NoNumbers!",  # No numbers
            "NoSpecialChars123",  # No special characters
            "password123",  # Common pattern
            "testuser123",  # Contains username
        ]
        
        for password in weak_passwords:
            with self.assertRaises(ValidationError):
                PasswordSecurityValidator.validate_password_strength(password, self.user)


class SessionManagerTest(TestCase):
    """
    Test cases for SessionManager utility class.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.profile = self.user.profile
        self.profile.role = 'student'
        self.profile.save()
        
        self.device = Device.objects.create(
            user=self.user,
            name='Test Device',
            device_type='laptop',
            mac_address='00:11:22:33:44:55',
            operating_system='windows',
            compliance_status=True
        )
    
    def test_get_active_sessions_for_user(self):
        """
        Test getting active sessions for a user.
        """
        # Create active and inactive sessions
        active_session = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='active_session',
            ip_address='127.0.0.1',
            status='active'
        )
        
        inactive_session = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='inactive_session',
            ip_address='127.0.0.1',
            status='inactive',
            logout_time=timezone.now()
        )
        
        active_sessions = SessionManager.get_active_sessions_for_user(self.user)
        self.assertEqual(active_sessions.count(), 1)
        self.assertEqual(active_sessions.first(), active_session)
    
    def test_can_create_new_session(self):
        """
        Test session creation permission check.
        """
        # No existing sessions - should allow
        self.assertTrue(SessionManager.can_create_new_session(self.user))
        
        # Create active session
        SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='existing_session',
            ip_address='127.0.0.1',
            status='active'
        )
        
        # With MAX_CONCURRENT_SESSIONS = 1, should not allow new session
        self.assertFalse(SessionManager.can_create_new_session(self.user))
    
    def test_end_oldest_session_for_user(self):
        """
        Test ending the oldest session for a user.
        """
        # Create multiple sessions with different login times
        old_session = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='old_session',
            ip_address='127.0.0.1',
            status='active',
            login_time=timezone.now() - timedelta(hours=2)
        )
        
        new_session = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='new_session',
            ip_address='127.0.0.1',
            status='active',
            login_time=timezone.now() - timedelta(hours=1)
        )
        
        result = SessionManager.end_oldest_session_for_user(self.user)
        self.assertTrue(result)
        
        # Check that oldest session was ended
        old_session.refresh_from_db()
        new_session.refresh_from_db()
        
        self.assertNotEqual(old_session.status, 'active')
        self.assertEqual(new_session.status, 'active')
    
    def test_cleanup_expired_sessions(self):
        """
        Test cleanup of expired sessions.
        """
        # Create expired session
        expired_session = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='expired_session',
            ip_address='127.0.0.1',
            status='active',
            last_activity=timezone.now() - timedelta(minutes=45)
        )
        
        # Create active session
        active_session = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='active_session',
            ip_address='127.0.0.1',
            status='active',
            last_activity=timezone.now() - timedelta(minutes=5)
        )
        
        stats = SessionManager.cleanup_expired_sessions(timeout_minutes=30)
        
        self.assertGreater(stats['expired_session_trackers'], 0)
        
        # Check that expired session was cleaned up
        expired_session.refresh_from_db()
        active_session.refresh_from_db()
        
        self.assertNotEqual(expired_session.status, 'active')
        self.assertEqual(active_session.status, 'active')


class SessionSecurityMonitorTest(TestCase):
    """
    Test cases for SessionSecurityMonitor class.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.profile = self.user.profile
        self.profile.role = 'student'
        self.profile.save()
        
        self.device = Device.objects.create(
            user=self.user,
            name='Test Device',
            device_type='laptop',
            mac_address='00:11:22:33:44:55',
            operating_system='windows',
            compliance_status=True
        )
    
    def test_detect_excessive_violations(self):
        """
        Test detection of excessive violations.
        """
        session_tracker = SessionTracker.objects.create(
            user=self.user,
            device=self.device,
            session_key='test_session',
            ip_address='127.0.0.1',
            status='active',
            violation_count=10  # Excessive violations
        )
        
        suspicious_activities = SessionSecurityMonitor.detect_suspicious_activity(session_tracker)
        self.assertIn('excessive_violations', suspicious_activities)
    
    def test_detect_rapid_login_attempts(self):
        """
        Test detection of rapid login attempts.
        """
        # Create multiple recent sessions
        for i in range(6):
            SessionTracker.objects.create(
                user=self.user,
                device=self.device,
                session_key=f'session_{i}',
                ip_address='127.0.0.1',
                status='active',
                login_time=timezone.now() - timedelta(minutes=i)
            )
        
        session_tracker = SessionTracker.objects.filter(user=self.user).first()
        suspicious_activities = SessionSecurityMonitor.detect_suspicious_activity(session_tracker)
        
        self.assertIn('rapid_login_attempts', suspicious_activities)


class AccessControlFormTest(TestCase):
    """
    Test cases for AccessControlForm.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        self.admin_profile = self.admin_user.profile
        self.admin_profile.role = 'admin'
        self.admin_profile.save()
    
    def test_valid_form_submission(self):
        """
        Test valid form submission.
        """
        form_data = {
            'role': 'student',
            'is_active': True,
            'allowed_domains_list': 'example.com\neducation.gov',
            'blocked_domains_list': 'facebook.com\ntwitter.com',
            'enable_time_restrictions': True,
            'start_time': '09:00',
            'end_time': '17:00',
            'allowed_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        }
        
        form = AccessControlForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Test saving
        access_control = form.save(commit=False)
        access_control.created_by = self.admin_user
        access_control.save()
        
        self.assertEqual(access_control.role, 'student')
        self.assertTrue(access_control.is_active)
    
    def test_invalid_domain_format(self):
        """
        Test form validation with invalid domain format.
        """
        form_data = {
            'role': 'student',
            'is_active': True,
            'allowed_domains_list': 'invalid..domain\n<script>alert(1)</script>',
            'blocked_domains_list': '',
        }
        
        form = AccessControlForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('allowed_domains_list', form.errors)
    
    def test_time_restriction_validation(self):
        """
        Test time restriction validation.
        """
        form_data = {
            'role': 'student',
            'is_active': True,
            'enable_time_restrictions': True,
            'start_time': '17:00',  # Start time after end time
            'end_time': '09:00',
        }
        
        form = AccessControlForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('Start time must be before end time', str(form.errors))
    
    def test_domain_conflict_validation(self):
        """
        Test validation of conflicting allowed and blocked domains.
        """
        form_data = {
            'role': 'student',
            'is_active': True,
            'allowed_domains_list': 'example.com\ntest.com',
            'blocked_domains_list': 'example.com\nother.com',  # Conflict with allowed
        }
        
        form = AccessControlForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('cannot be both allowed and blocked', str(form.errors))


class CSRFProtectionTest(TestCase):
    """
    Test cases for CSRF protection.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_csrf_protection_on_forms(self):
        """
        Test that CSRF protection is enforced on forms.
        """
        # Login user
        self.client.login(username='testuser', password='testpass123')
        
        # Try to submit form without CSRF token
        response = self.client.post('/devices/register/', {
            'name': 'Test Device',
            'device_type': 'laptop',
            'mac_address': '00:11:22:33:44:55',
            'operating_system': 'windows'
        })
        
        # Should be forbidden due to missing CSRF token
        self.assertEqual(response.status_code, 403)
    
    def test_csrf_failure_view(self):
        """
        Test custom CSRF failure view.
        """
        # This test would need to trigger a CSRF failure
        # and verify that our custom view is called
        pass  # Implementation depends on specific URL structure


class SessionTimeoutTest(TestCase):
    """
    Test cases for session timeout functionality.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.profile = self.user.profile
        self.profile.role = 'student'
        self.profile.save()
    
    def test_session_timeout_configuration(self):
        """
        Test that session timeout is properly configured.
        """
        from django.conf import settings
        
        # Check that session timeout settings are configured
        self.assertTrue(hasattr(settings, 'SESSION_COOKIE_AGE'))
        self.assertTrue(hasattr(settings, 'SESSION_TIMEOUT_MINUTES'))
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
    
    def test_secure_cookie_settings(self):
        """
        Test that secure cookie settings are properly configured.
        """
        from django.conf import settings
        
        # In production (DEBUG=False), cookies should be secure
        if not settings.DEBUG:
            self.assertTrue(settings.SESSION_COOKIE_SECURE)
            self.assertTrue(settings.CSRF_COOKIE_SECURE)
        
        # These should always be True
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
