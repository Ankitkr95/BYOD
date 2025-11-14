"""
Session management utilities for concurrent session prevention and cleanup.

This module provides utilities for managing user sessions, preventing concurrent
sessions, and handling session cleanup operations.
"""

import logging
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from .models import SessionTracker


logger = logging.getLogger(__name__)


class SessionManager:
    """
    Utility class for managing user sessions and preventing concurrent access.
    """
    
    # Cache timeout for session data (in seconds)
    CACHE_TIMEOUT = 300  # 5 minutes
    
    # Maximum concurrent sessions per user (configurable via settings)
    MAX_CONCURRENT_SESSIONS = getattr(settings, 'MAX_CONCURRENT_SESSIONS', 1)
    
    @classmethod
    def get_active_sessions_for_user(cls, user):
        """
        Get all active sessions for a specific user.
        
        Args:
            user (User): User object
            
        Returns:
            QuerySet: Active SessionTracker objects for the user
        """
        return SessionTracker.objects.filter(
            user=user,
            status='active',
            logout_time__isnull=True
        ).select_related('device')
    
    @classmethod
    def get_session_count_for_user(cls, user):
        """
        Get the count of active sessions for a user.
        
        Args:
            user (User): User object
            
        Returns:
            int: Number of active sessions
        """
        cache_key = f"session_count_{user.id}"
        count = cache.get(cache_key)
        
        if count is None:
            count = cls.get_active_sessions_for_user(user).count()
            cache.set(cache_key, count, timeout=cls.CACHE_TIMEOUT)
        
        return count
    
    @classmethod
    def can_create_new_session(cls, user):
        """
        Check if a user can create a new session based on concurrent session limits.
        
        Args:
            user (User): User object
            
        Returns:
            bool: True if user can create a new session, False otherwise
        """
        if not user or not user.is_authenticated:
            return False
        
        active_sessions = cls.get_session_count_for_user(user)
        return active_sessions < cls.MAX_CONCURRENT_SESSIONS
    
    @classmethod
    def end_oldest_session_for_user(cls, user, reason='new_session_limit'):
        """
        End the oldest active session for a user to make room for a new one.
        
        Args:
            user (User): User object
            reason (str): Reason for ending the session
            
        Returns:
            bool: True if a session was ended, False otherwise
        """
        try:
            oldest_session = cls.get_active_sessions_for_user(user).order_by('login_time').first()
            
            if oldest_session:
                oldest_session.end_session(reason)
                
                # Also invalidate the Django session
                try:
                    django_session = Session.objects.get(session_key=oldest_session.session_key)
                    django_session.delete()
                except Session.DoesNotExist:
                    pass
                
                # Clear cache
                cls._clear_user_session_cache(user)
                
                logger.info(f"Ended oldest session for user {user.username}: {oldest_session.session_key}")
                return True
                
        except Exception as e:
            logger.error(f"Error ending oldest session for user {user.username}: {e}")
        
        return False
    
    @classmethod
    def end_all_sessions_for_user(cls, user, reason='admin_action', exclude_session=None):
        """
        End all active sessions for a user.
        
        Args:
            user (User): User object
            reason (str): Reason for ending sessions
            exclude_session (str): Session key to exclude from termination
            
        Returns:
            int: Number of sessions ended
        """
        try:
            active_sessions = cls.get_active_sessions_for_user(user)
            
            if exclude_session:
                active_sessions = active_sessions.exclude(session_key=exclude_session)
            
            ended_count = 0
            
            with transaction.atomic():
                for session_tracker in active_sessions:
                    session_tracker.end_session(reason)
                    
                    # Also invalidate the Django session
                    try:
                        django_session = Session.objects.get(session_key=session_tracker.session_key)
                        django_session.delete()
                    except Session.DoesNotExist:
                        pass
                    
                    ended_count += 1
            
            # Clear cache
            cls._clear_user_session_cache(user)
            
            logger.info(f"Ended {ended_count} sessions for user {user.username}")
            return ended_count
            
        except Exception as e:
            logger.error(f"Error ending sessions for user {user.username}: {e}")
            return 0
    
    @classmethod
    def handle_concurrent_session_attempt(cls, user, current_session_key):
        """
        Handle a concurrent session attempt based on system configuration.
        
        Args:
            user (User): User object
            current_session_key (str): Current session key
            
        Returns:
            tuple: (allowed, message) - whether session is allowed and message
        """
        if cls.can_create_new_session(user):
            return True, "Session allowed"
        
        # Check system policy for handling concurrent sessions
        concurrent_policy = getattr(settings, 'CONCURRENT_SESSION_POLICY', 'deny')
        
        if concurrent_policy == 'allow':
            # Allow unlimited concurrent sessions
            return True, "Multiple sessions allowed"
        
        elif concurrent_policy == 'replace_oldest':
            # End the oldest session and allow new one
            if cls.end_oldest_session_for_user(user):
                return True, "Oldest session terminated, new session allowed"
            else:
                return False, "Failed to terminate oldest session"
        
        else:  # 'deny' (default)
            # Deny new session
            return False, "Multiple sessions not allowed. Please log out from other devices first."
    
    @classmethod
    def create_session_notification(cls, user, session_tracker, notification_type):
        """
        Create a notification for session-related events.
        
        Args:
            user (User): User object
            session_tracker (SessionTracker): Session tracker object
            notification_type (str): Type of notification
        """
        try:
            # Store notification in cache for display to user
            cache_key = f"session_notification_{user.id}"
            
            notification_data = {
                'type': notification_type,
                'message': cls._get_notification_message(notification_type, session_tracker),
                'timestamp': timezone.now().isoformat(),
                'session_info': {
                    'device_name': session_tracker.device.name if session_tracker.device else 'Unknown',
                    'ip_address': session_tracker.ip_address,
                    'login_time': session_tracker.login_time.isoformat(),
                }
            }
            
            # Store for 1 hour
            cache.set(cache_key, notification_data, timeout=3600)
            
        except Exception as e:
            logger.error(f"Error creating session notification: {e}")
    
    @classmethod
    def get_session_notification(cls, user):
        """
        Get pending session notification for a user.
        
        Args:
            user (User): User object
            
        Returns:
            dict: Notification data or None
        """
        cache_key = f"session_notification_{user.id}"
        return cache.get(cache_key)
    
    @classmethod
    def clear_session_notification(cls, user):
        """
        Clear session notification for a user.
        
        Args:
            user (User): User object
        """
        cache_key = f"session_notification_{user.id}"
        cache.delete(cache_key)
    
    @classmethod
    def cleanup_expired_sessions(cls, timeout_minutes=None):
        """
        Clean up expired sessions and session trackers.
        
        Args:
            timeout_minutes (int): Session timeout in minutes
            
        Returns:
            dict: Cleanup statistics
        """
        if timeout_minutes is None:
            timeout_minutes = getattr(settings, 'SESSION_TIMEOUT_MINUTES', 30)
        
        cutoff_time = timezone.now() - timedelta(minutes=timeout_minutes)
        
        try:
            # Find expired session trackers
            expired_sessions = SessionTracker.objects.filter(
                status='active',
                last_activity__lt=cutoff_time
            )
            
            expired_count = 0
            django_sessions_cleaned = 0
            
            with transaction.atomic():
                for session_tracker in expired_sessions:
                    # End the session tracker
                    session_tracker.end_session('timeout')
                    expired_count += 1
                    
                    # Clean up Django session
                    try:
                        django_session = Session.objects.get(session_key=session_tracker.session_key)
                        django_session.delete()
                        django_sessions_cleaned += 1
                    except Session.DoesNotExist:
                        pass
            
            # Clean up orphaned Django sessions (sessions without trackers)
            orphaned_sessions = Session.objects.filter(
                expire_date__lt=timezone.now()
            )
            orphaned_count = orphaned_sessions.count()
            orphaned_sessions.delete()
            
            # Clear all session count caches
            cls._clear_all_session_caches()
            
            stats = {
                'expired_session_trackers': expired_count,
                'django_sessions_cleaned': django_sessions_cleaned,
                'orphaned_sessions_cleaned': orphaned_count,
                'total_cleaned': expired_count + orphaned_count
            }
            
            logger.info(f"Session cleanup completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")
            return {'error': str(e)}
    
    @classmethod
    def get_session_statistics(cls):
        """
        Get comprehensive session statistics.
        
        Returns:
            dict: Session statistics
        """
        try:
            now = timezone.now()
            today = now.date()
            
            stats = {
                'total_active_sessions': SessionTracker.objects.filter(
                    status='active',
                    logout_time__isnull=True
                ).count(),
                
                'total_sessions_today': SessionTracker.objects.filter(
                    login_time__date=today
                ).count(),
                
                'unique_users_today': SessionTracker.objects.filter(
                    login_time__date=today
                ).values('user').distinct().count(),
                
                'violations_today': SessionTracker.objects.filter(
                    login_time__date=today,
                    violation_count__gt=0
                ).count(),
                
                'concurrent_violations_today': SessionTracker.objects.filter(
                    login_time__date=today,
                    violations__contains='concurrent_session'
                ).count(),
                
                'average_session_duration': cls._calculate_average_session_duration(),
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting session statistics: {e}")
            return {}
    
    @classmethod
    def _get_notification_message(cls, notification_type, session_tracker):
        """
        Get notification message based on type.
        """
        messages = {
            'concurrent_session_denied': 'Login attempt denied. You already have an active session on another device.',
            'session_terminated': 'Your session was terminated due to a new login from another device.',
            'session_timeout': 'Your session expired due to inactivity.',
            'admin_logout': 'Your session was terminated by an administrator.',
        }
        
        return messages.get(notification_type, 'Session notification')
    
    @classmethod
    def _clear_user_session_cache(cls, user):
        """
        Clear session-related cache for a specific user.
        """
        cache_keys = [
            f"session_count_{user.id}",
            f"session_notification_{user.id}",
        ]
        
        for key in cache_keys:
            cache.delete(key)
    
    @classmethod
    def _clear_all_session_caches(cls):
        """
        Clear all session-related caches.
        """
        # This is a simplified approach - in production, you might want
        # to use cache versioning or more sophisticated cache management
        try:
            cache.clear()
        except Exception as e:
            logger.error(f"Error clearing session caches: {e}")
    
    @classmethod
    def _calculate_average_session_duration(cls):
        """
        Calculate average session duration for completed sessions.
        """
        try:
            from django.db.models import Avg, F
            
            # Calculate for sessions completed in the last 7 days
            week_ago = timezone.now() - timedelta(days=7)
            
            avg_duration = SessionTracker.objects.filter(
                logout_time__isnull=False,
                login_time__gte=week_ago
            ).aggregate(
                avg_duration=Avg(F('logout_time') - F('login_time'))
            )['avg_duration']
            
            if avg_duration:
                return int(avg_duration.total_seconds() / 60)  # Return in minutes
            
        except Exception as e:
            logger.error(f"Error calculating average session duration: {e}")
        
        return 0


class SessionSecurityMonitor:
    """
    Monitor for detecting suspicious session activities.
    """
    
    @classmethod
    def detect_suspicious_activity(cls, session_tracker):
        """
        Detect suspicious activity patterns in a session.
        
        Args:
            session_tracker (SessionTracker): Session to analyze
            
        Returns:
            list: List of detected suspicious activities
        """
        suspicious_activities = []
        
        try:
            # Check for rapid login attempts
            if cls._has_rapid_login_attempts(session_tracker.user):
                suspicious_activities.append('rapid_login_attempts')
            
            # Check for unusual IP address patterns
            if cls._has_unusual_ip_pattern(session_tracker):
                suspicious_activities.append('unusual_ip_pattern')
            
            # Check for session duration anomalies
            if cls._has_unusual_session_duration(session_tracker):
                suspicious_activities.append('unusual_session_duration')
            
            # Check for excessive violations
            if session_tracker.violation_count > 5:
                suspicious_activities.append('excessive_violations')
            
        except Exception as e:
            logger.error(f"Error detecting suspicious activity: {e}")
        
        return suspicious_activities
    
    @classmethod
    def _has_rapid_login_attempts(cls, user):
        """
        Check for rapid login attempts from the same user.
        """
        try:
            # Check for more than 5 login attempts in the last 10 minutes
            ten_minutes_ago = timezone.now() - timedelta(minutes=10)
            
            recent_sessions = SessionTracker.objects.filter(
                user=user,
                login_time__gte=ten_minutes_ago
            ).count()
            
            return recent_sessions > 5
            
        except Exception:
            return False
    
    @classmethod
    def _has_unusual_ip_pattern(cls, session_tracker):
        """
        Check for unusual IP address patterns.
        """
        try:
            # Check if user has logged in from different IP addresses recently
            recent_ips = SessionTracker.objects.filter(
                user=session_tracker.user,
                login_time__gte=timezone.now() - timedelta(hours=24)
            ).values_list('ip_address', flat=True).distinct()
            
            # Flag if more than 3 different IPs in 24 hours
            return len(recent_ips) > 3
            
        except Exception:
            return False
    
    @classmethod
    def _has_unusual_session_duration(cls, session_tracker):
        """
        Check for unusual session duration patterns.
        """
        try:
            # If session is still active and has been running for more than 12 hours
            if session_tracker.status == 'active':
                duration = timezone.now() - session_tracker.login_time
                return duration.total_seconds() > 12 * 3600  # 12 hours
            
        except Exception:
            pass
        
        return False