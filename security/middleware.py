"""
Custom middleware for BYOD Security System.

This module contains middleware classes for session validation, activity tracking,
access control enforcement, and security monitoring.
"""

import json
import logging
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from .models import SessionTracker, AccessControl
from .session_utils import SessionManager, SessionSecurityMonitor
from devices.models import Device


logger = logging.getLogger(__name__)


class SessionValidationMiddleware(MiddlewareMixin):
    """
    Middleware for session validation, activity tracking, and timeout management.
    
    This middleware:
    - Tracks user sessions and device usage
    - Enforces session timeouts
    - Prevents concurrent sessions
    - Logs user activity for security monitoring
    """
    
    # Session timeout in minutes (configurable via settings)
    SESSION_TIMEOUT = getattr(settings, 'SESSION_TIMEOUT_MINUTES', 30)
    
    # URLs that don't require session validation
    EXEMPT_URLS = [
        '/auth/login/',
        '/auth/logout/',
        '/auth/signup/',
        '/admin/',
        '/static/',
        '/media/',
    ]
    
    def process_request(self, request):
        """
        Process incoming requests for session validation and activity tracking.
        """
        # Skip validation for exempt URLs
        if self._is_exempt_url(request.path):
            return None
        
        # Skip validation for unauthenticated users
        if not request.user.is_authenticated:
            return None
        
        # Get or create session tracker
        session_tracker = self._get_or_create_session_tracker(request)
        if not session_tracker:
            return None
        
        # Check for session timeout
        if self._is_session_expired(session_tracker):
            return self._handle_session_timeout(request, session_tracker)
        
        # Check for concurrent sessions
        if self._has_concurrent_sessions(request.user, request.session.session_key):
            return self._handle_concurrent_session(request, session_tracker)
        
        # Update activity tracking
        self._update_activity_tracking(request, session_tracker)
        
        # Monitor for suspicious activity
        self._monitor_suspicious_activity(request, session_tracker)
        
        return None
    
    def process_response(self, request, response):
        """
        Process responses to log additional activity data.
        """
        # Skip processing for exempt URLs or unauthenticated users
        if (self._is_exempt_url(request.path) or 
            not request.user.is_authenticated):
            return response
        
        # Log response status for security monitoring
        if hasattr(request, 'session_tracker'):
            self._log_response_activity(request, response)
        
        return response
    
    def _is_exempt_url(self, path):
        """
        Check if URL is exempt from session validation.
        """
        return any(path.startswith(exempt) for exempt in self.EXEMPT_URLS)
    
    def _get_or_create_session_tracker(self, request):
        """
        Get existing session tracker or create a new one.
        """
        try:
            # Try to get existing session tracker
            session_tracker = SessionTracker.objects.select_related('user', 'device').get(
                session_key=request.session.session_key,
                status='active'
            )
            
            # Store in request for later use
            request.session_tracker = session_tracker
            return session_tracker
            
        except SessionTracker.DoesNotExist:
            # Create new session tracker if this is a new session
            return self._create_new_session_tracker(request)
        except Exception as e:
            logger.error(f"Error getting session tracker: {e}")
            return None
    
    def _create_new_session_tracker(self, request):
        """
        Create a new session tracker for the current session.
        """
        try:
            # Get user's primary device or create a default one
            device = self._get_user_device(request)
            if not device:
                return None
            
            # Create session tracker
            session_tracker = SessionTracker.objects.create(
                user=request.user,
                device=device,
                session_key=request.session.session_key,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                status='active'
            )
            
            request.session_tracker = session_tracker
            logger.info(f"Created new session tracker for user {request.user.username}")
            return session_tracker
            
        except Exception as e:
            logger.error(f"Error creating session tracker: {e}")
            return None
    
    def _get_user_device(self, request):
        """
        Get the user's device for session tracking.
        """
        try:
            # Try to get device from session or user's primary device
            device_id = request.session.get('device_id')
            if device_id:
                return Device.objects.get(id=device_id, user=request.user)
            
            # Get user's first registered device
            device = Device.objects.filter(user=request.user).first()
            if device:
                request.session['device_id'] = device.id
                return device
            
            # Create a default device if none exists
            return Device.objects.create(
                user=request.user,
                name=f"Default Device - {request.user.username}",
                device_type='laptop',
                mac_address='00:00:00:00:00:00',  # Placeholder MAC
                operating_system='Unknown',
                compliance_status=False
            )
            
        except Exception as e:
            logger.error(f"Error getting user device: {e}")
            return None
    
    def _get_client_ip(self, request):
        """
        Get the client's IP address from request.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _is_session_expired(self, session_tracker):
        """
        Check if the session has expired due to inactivity.
        """
        if not session_tracker:
            return False
        
        inactive_duration = timezone.now() - session_tracker.last_activity
        return inactive_duration.total_seconds() > (self.SESSION_TIMEOUT * 60)
    
    def _has_concurrent_sessions(self, user, current_session_key):
        """
        Check if user has concurrent active sessions using SessionManager.
        """
        try:
            # Use SessionManager for more sophisticated concurrent session handling
            active_sessions = SessionManager.get_active_sessions_for_user(user).exclude(
                session_key=current_session_key
            )
            
            return active_sessions.exists()
            
        except Exception as e:
            logger.error(f"Error checking concurrent sessions: {e}")
            return False
    
    def _handle_session_timeout(self, request, session_tracker):
        """
        Handle session timeout by logging out user and ending session.
        """
        try:
            # End the session tracker
            session_tracker.end_session('timeout')
            
            # Log the timeout event
            logger.info(f"Session timeout for user {request.user.username}")
            
            # Logout user and redirect to login
            logout(request)
            
            # Return redirect response
            if self._is_ajax_request(request):
                return JsonResponse({
                    'error': 'Session expired',
                    'redirect': reverse('users:login')
                }, status=401)
            else:
                return redirect('users:login')
                
        except Exception as e:
            logger.error(f"Error handling session timeout: {e}")
            return None
    
    def _handle_concurrent_session(self, request, session_tracker):
        """
        Handle concurrent session using SessionManager policies.
        """
        try:
            # Use SessionManager to handle concurrent session attempt
            allowed, message = SessionManager.handle_concurrent_session_attempt(
                request.user, 
                request.session.session_key
            )
            
            if allowed:
                # Session is allowed, continue normally
                return None
            
            # Session not allowed - handle based on policy
            session_tracker.add_violation(
                'concurrent_session',
                {'message': message}
            )
            
            # Create notification for user
            SessionManager.create_session_notification(
                request.user,
                session_tracker,
                'concurrent_session_denied'
            )
            
            # End the current session
            session_tracker.end_session('violation')
            
            # Log the violation
            logger.warning(f"Concurrent session denied for user {request.user.username}: {message}")
            
            # Logout user
            logout(request)
            
            # Return appropriate response
            if self._is_ajax_request(request):
                return JsonResponse({
                    'error': message,
                    'redirect': reverse('users:login')
                }, status=403)
            else:
                return redirect('users:login')
                
        except Exception as e:
            logger.error(f"Error handling concurrent session: {e}")
            return None
    
    def _update_activity_tracking(self, request, session_tracker):
        """
        Update session activity tracking.
        """
        try:
            # Update last activity timestamp
            session_tracker.update_activity()
            
            # Cache activity data for performance
            cache_key = f"user_activity_{request.user.id}"
            activity_data = {
                'last_seen': timezone.now().isoformat(),
                'path': request.path,
                'method': request.method,
                'ip_address': self._get_client_ip(request)
            }
            cache.set(cache_key, activity_data, timeout=300)  # 5 minutes
            
        except Exception as e:
            logger.error(f"Error updating activity tracking: {e}")
    
    def _log_response_activity(self, request, response):
        """
        Log response activity for security monitoring.
        """
        try:
            # Log suspicious response codes
            if response.status_code in [403, 404, 500]:
                session_tracker = request.session_tracker
                session_tracker.add_violation(
                    'suspicious_response',
                    {
                        'status_code': response.status_code,
                        'path': request.path,
                        'method': request.method
                    }
                )
                
        except Exception as e:
            logger.error(f"Error logging response activity: {e}")
    
    def _monitor_suspicious_activity(self, request, session_tracker):
        """
        Monitor session for suspicious activity patterns.
        """
        try:
            suspicious_activities = SessionSecurityMonitor.detect_suspicious_activity(session_tracker)
            
            if suspicious_activities:
                # Log suspicious activities
                for activity in suspicious_activities:
                    session_tracker.add_violation(
                        activity,
                        {
                            'detected_at': timezone.now().isoformat(),
                            'path': request.path,
                            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200]
                        }
                    )
                
                logger.warning(
                    f"Suspicious activity detected for user {request.user.username}: "
                    f"{', '.join(suspicious_activities)}"
                )
                
        except Exception as e:
            logger.error(f"Error monitoring suspicious activity: {e}")
    
    def _is_ajax_request(self, request):
        """
        Check if request is an AJAX request (replacement for deprecated is_ajax()).
        """
        return (
            request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest' or
            request.content_type == 'application/json' or
            'application/json' in request.META.get('HTTP_ACCEPT', '')
        )


class AccessControlMiddleware(MiddlewareMixin):
    """
    Middleware for enforcing role-based access control and resource restrictions.
    
    This middleware:
    - Enforces role-based access control rules
    - Blocks access to restricted domains/resources
    - Validates time-based access restrictions
    - Logs access violations
    """
    
    # URLs that don't require access control
    EXEMPT_URLS = [
        '/auth/',
        '/admin/',
        '/static/',
        '/media/',
        '/dashboard/',
        '/devices/',
        '/productivity/',
        '/security/',
        '/health/',
        '/ready/',
        '/alive/',
        '/stats/',
    ]
    
    # Cache timeout for access control rules (in seconds)
    CACHE_TIMEOUT = 300  # 5 minutes
    
    def process_request(self, request):
        """
        Process requests to enforce access control rules.
        """
        # Skip access control for exempt URLs
        if self._is_exempt_url(request.path):
            return None
        
        # Skip for unauthenticated users (handled by authentication middleware)
        if not request.user.is_authenticated:
            return None
        
        # Get user's access control rules
        access_rules = self._get_user_access_rules(request.user)
        if not access_rules:
            return None
        
        # Check time-based restrictions
        if not self._is_time_allowed(access_rules):
            return self._handle_time_restriction_violation(request, access_rules)
        
        # Check resource access restrictions
        if not self._is_resource_allowed(request, access_rules):
            return self._handle_resource_restriction_violation(request, access_rules)
        
        return None
    
    def _is_exempt_url(self, path):
        """
        Check if URL is exempt from access control.
        """
        return any(path.startswith(exempt) for exempt in self.EXEMPT_URLS)
    
    def _get_user_access_rules(self, user):
        """
        Get access control rules for the user's role.
        """
        try:
            # Get user role
            if not hasattr(user, 'profile'):
                return None
            
            user_role = user.profile.role
            
            # Try to get from cache first
            cache_key = f"access_rules_{user_role}"
            access_rules = cache.get(cache_key)
            
            if access_rules is None:
                # Get from database
                try:
                    access_rules = AccessControl.objects.get(
                        role=user_role,
                        is_active=True
                    )
                    # Cache the rules
                    cache.set(cache_key, access_rules, timeout=self.CACHE_TIMEOUT)
                except AccessControl.DoesNotExist:
                    # No specific rules for this role, allow all access
                    return None
            
            return access_rules
            
        except Exception as e:
            logger.error(f"Error getting access rules: {e}")
            return None
    
    def _is_time_allowed(self, access_rules):
        """
        Check if current time is within allowed time restrictions.
        """
        try:
            return access_rules.is_time_allowed()
        except Exception as e:
            logger.error(f"Error checking time restrictions: {e}")
            return True  # Allow access if check fails
    
    def _is_resource_allowed(self, request, access_rules):
        """
        Check if the requested resource is allowed based on access rules.
        This should only apply to external domain requests, not internal app URLs.
        """
        try:
            # For now, we'll only control external domain access
            # Internal application URLs should always be allowed
            # This middleware is primarily for controlling external web access
            
            # Check if this is an external domain request
            # (This would be implemented when we add proxy/filtering functionality)
            
            # For internal application URLs, always allow access
            return True
            
        except Exception as e:
            logger.error(f"Error checking resource access: {e}")
            return True  # Allow access if check fails
    
    def _extract_resource_from_request(self, request):
        """
        Extract resource/domain information from request.
        """
        try:
            # For now, we'll use the URL path as the resource
            # In a more advanced implementation, this could parse
            # actual domain requests or API endpoints
            path = request.path.strip('/')
            
            # Extract the main app/resource from URL
            if path:
                resource_parts = path.split('/')
                if resource_parts:
                    return resource_parts[0]  # First part of URL path
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting resource: {e}")
            return None
    
    def _handle_time_restriction_violation(self, request, access_rules):
        """
        Handle time-based access restriction violations.
        """
        try:
            # Log the violation
            self._log_access_violation(
                request,
                'time_restriction',
                f"Access outside allowed time for role {access_rules.role}"
            )
            
            # Return forbidden response
            if self._is_ajax_request(request):
                return JsonResponse({
                    'error': 'Access not allowed at this time',
                    'message': 'Your role has time-based access restrictions'
                }, status=403)
            else:
                return HttpResponseForbidden(
                    "Access not allowed at this time. Your role has time-based restrictions."
                )
                
        except Exception as e:
            logger.error(f"Error handling time restriction violation: {e}")
            return None
    
    def _handle_resource_restriction_violation(self, request, access_rules):
        """
        Handle resource access restriction violations.
        """
        try:
            # Log the violation
            resource = self._extract_resource_from_request(request)
            self._log_access_violation(
                request,
                'resource_restriction',
                f"Access to restricted resource '{resource}' for role {access_rules.role}"
            )
            
            # Return forbidden response
            if self._is_ajax_request(request):
                return JsonResponse({
                    'error': 'Access to this resource is not allowed',
                    'message': 'Your role does not have permission to access this resource'
                }, status=403)
            else:
                return HttpResponseForbidden(
                    "Access to this resource is not allowed for your role."
                )
                
        except Exception as e:
            logger.error(f"Error handling resource restriction violation: {e}")
            return None
    
    def _log_access_violation(self, request, violation_type, details):
        """
        Log access control violations to session tracker.
        """
        try:
            # Get session tracker if available
            if hasattr(request, 'session_tracker') and request.session_tracker:
                request.session_tracker.add_violation(
                    violation_type,
                    {
                        'details': details,
                        'path': request.path,
                        'method': request.method,
                        'ip_address': self._get_client_ip(request),
                        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200]
                    }
                )
            
            # Also log to Django logger
            logger.warning(f"Access violation: {details} - User: {request.user.username}")
            
        except Exception as e:
            logger.error(f"Error logging access violation: {e}")
    
    def _get_client_ip(self, request):
        """
        Get the client's IP address from request.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _is_ajax_request(self, request):
        """
        Check if request is an AJAX request (replacement for deprecated is_ajax()).
        """
        return (
            request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest' or
            request.content_type == 'application/json' or
            'application/json' in request.META.get('HTTP_ACCEPT', '')
        )


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers to responses.
    
    This middleware adds various security headers to enhance application security.
    """
    
    def process_response(self, request, response):
        """
        Add security headers to response.
        """
        # Content Security Policy
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        
        # X-Frame-Options (prevent clickjacking)
        response['X-Frame-Options'] = 'DENY'
        
        # X-Content-Type-Options (prevent MIME sniffing)
        response['X-Content-Type-Options'] = 'nosniff'
        
        # X-XSS-Protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy
        response['Permissions-Policy'] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "speaker=()"
        )
        
        return response