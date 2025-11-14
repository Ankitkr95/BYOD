"""
Utility functions for security middleware and session management.
"""

import logging
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.core.cache import cache
from .models import SessionTracker


logger = logging.getLogger(__name__)


def get_active_sessions_count():
    """
    Get count of currently active sessions.
    """
    try:
        return SessionTracker.objects.filter(
            status='active',
            logout_time__isnull=True
        ).count()
    except Exception as e:
        logger.error(f"Error getting active sessions count: {e}")
        return 0


def get_user_active_sessions(user):
    """
    Get active sessions for a specific user.
    """
    try:
        return SessionTracker.objects.filter(
            user=user,
            status='active',
            logout_time__isnull=True
        )
    except Exception as e:
        logger.error(f"Error getting user active sessions: {e}")
        return SessionTracker.objects.none()


def terminate_user_sessions(user, exclude_session_key=None):
    """
    Terminate all active sessions for a user.
    
    Args:
        user: User object
        exclude_session_key: Session key to exclude from termination
    """
    try:
        sessions = get_user_active_sessions(user)
        
        if exclude_session_key:
            sessions = sessions.exclude(session_key=exclude_session_key)
        
        count = 0
        for session in sessions:
            session.end_session('admin_action')
            
            # Also delete the Django session
            try:
                Session.objects.filter(session_key=session.session_key).delete()
            except Exception:
                pass  # Session might already be deleted
            
            count += 1
        
        logger.info(f"Terminated {count} sessions for user {user.username}")
        return count
        
    except Exception as e:
        logger.error(f"Error terminating user sessions: {e}")
        return 0


def check_concurrent_sessions(user, current_session_key):
    """
    Check if user has concurrent active sessions.
    
    Args:
        user: User object
        current_session_key: Current session key to exclude from check
        
    Returns:
        bool: True if concurrent sessions exist
    """
    try:
        concurrent_sessions = SessionTracker.objects.filter(
            user=user,
            status='active',
            logout_time__isnull=True
        ).exclude(session_key=current_session_key)
        
        return concurrent_sessions.exists()
        
    except Exception as e:
        logger.error(f"Error checking concurrent sessions: {e}")
        return False


def cleanup_expired_sessions(timeout_minutes=30):
    """
    Cleanup expired sessions based on timeout.
    
    Args:
        timeout_minutes: Session timeout in minutes
        
    Returns:
        int: Number of sessions cleaned up
    """
    try:
        cutoff_time = timezone.now() - timezone.timedelta(minutes=timeout_minutes)
        
        expired_sessions = SessionTracker.objects.filter(
            status='active',
            last_activity__lt=cutoff_time,
            logout_time__isnull=True
        )
        
        count = 0
        for session in expired_sessions:
            session.end_session('timeout')
            count += 1
        
        # Also cleanup Django sessions
        django_expired = Session.objects.filter(expire_date__lt=timezone.now())
        django_count = django_expired.count()
        django_expired.delete()
        
        logger.info(f"Cleaned up {count} session trackers and {django_count} Django sessions")
        return count + django_count
        
    except Exception as e:
        logger.error(f"Error cleaning up expired sessions: {e}")
        return 0


def get_session_statistics():
    """
    Get comprehensive session statistics.
    
    Returns:
        dict: Session statistics
    """
    try:
        now = timezone.now()
        today = now.date()
        
        stats = {
            'active_sessions': SessionTracker.objects.filter(
                status='active',
                logout_time__isnull=True
            ).count(),
            'total_sessions_today': SessionTracker.objects.filter(
                login_time__date=today
            ).count(),
            'violations_today': SessionTracker.objects.filter(
                login_time__date=today,
                violation_count__gt=0
            ).count(),
            'unique_users_today': SessionTracker.objects.filter(
                login_time__date=today
            ).values('user').distinct().count(),
            'expired_sessions': SessionTracker.objects.filter(
                status='expired'
            ).count(),
            'terminated_sessions': SessionTracker.objects.filter(
                status='terminated'
            ).count(),
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting session statistics: {e}")
        return {}


def cache_user_activity(user_id, activity_data, timeout=300):
    """
    Cache user activity data for performance.
    
    Args:
        user_id: User ID
        activity_data: Activity data dictionary
        timeout: Cache timeout in seconds
    """
    try:
        cache_key = f"user_activity_{user_id}"
        cache.set(cache_key, activity_data, timeout=timeout)
    except Exception as e:
        logger.error(f"Error caching user activity: {e}")


def get_cached_user_activity(user_id):
    """
    Get cached user activity data.
    
    Args:
        user_id: User ID
        
    Returns:
        dict: Cached activity data or None
    """
    try:
        cache_key = f"user_activity_{user_id}"
        return cache.get(cache_key)
    except Exception as e:
        logger.error(f"Error getting cached user activity: {e}")
        return None


def log_security_event(event_type, user, details, severity='info'):
    """
    Log security events with structured data.
    
    Args:
        event_type: Type of security event
        user: User object
        details: Event details dictionary
        severity: Event severity (info, warning, error)
    """
    try:
        log_data = {
            'event_type': event_type,
            'user': user.username if user else 'anonymous',
            'user_id': user.id if user else None,
            'details': details,
            'timestamp': timezone.now().isoformat()
        }
        
        log_message = f"Security Event: {event_type} - User: {log_data['user']} - Details: {details}"
        
        if severity == 'error':
            logger.error(log_message, extra=log_data)
        elif severity == 'warning':
            logger.warning(log_message, extra=log_data)
        else:
            logger.info(log_message, extra=log_data)
            
    except Exception as e:
        logger.error(f"Error logging security event: {e}")


def validate_session_security(request):
    """
    Validate session security parameters.
    
    Args:
        request: Django request object
        
    Returns:
        dict: Validation results
    """
    try:
        results = {
            'valid': True,
            'issues': []
        }
        
        # Check if session exists
        if not request.session.session_key:
            results['valid'] = False
            results['issues'].append('No session key')
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            results['valid'] = False
            results['issues'].append('User not authenticated')
        
        # Check session age
        if hasattr(request, 'session_tracker'):
            session_tracker = request.session_tracker
            session_age = timezone.now() - session_tracker.login_time
            
            if session_age.total_seconds() > (8 * 60 * 60):  # 8 hours
                results['issues'].append('Session too old')
        
        # Check for suspicious activity
        if hasattr(request, 'session_tracker'):
            session_tracker = request.session_tracker
            if session_tracker.violation_count > 5:
                results['valid'] = False
                results['issues'].append('Too many violations')
        
        return results
        
    except Exception as e:
        logger.error(f"Error validating session security: {e}")
        return {'valid': False, 'issues': ['Validation error']}