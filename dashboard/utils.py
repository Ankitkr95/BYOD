"""
Dashboard utility functions for data aggregation and calculations.
Provides methods for device compliance overview, session counting, 
productivity summaries, and security alert aggregation.
"""

from django.db.models import Count, Q, Avg, Sum, F
from django.utils import timezone
from datetime import timedelta, date
from django.contrib.auth.models import User

from users.models import UserProfile
from devices.models import Device
from productivity.models import ActivityLog, PerformanceReport
from security.models import AccessControl, SessionTracker


class DashboardDataAggregator:
    """
    Centralized class for dashboard data aggregation methods.
    Provides role-specific data aggregation for admin, teacher, and student dashboards.
    """
    
    def __init__(self, user=None, date_range_days=7):
        self.user = user
        self.date_range_days = date_range_days
        self.today = timezone.now().date()
        self.start_date = self.today - timedelta(days=date_range_days)
    
    def get_device_compliance_overview(self, role_filter=None):
        """
        Get comprehensive device compliance overview.
        
        Args:
            role_filter (str): Filter by user role ('teacher', 'student', 'admin')
            
        Returns:
            dict: Device compliance statistics
        """
        devices_query = Device.objects.all()
        
        if role_filter:
            devices_query = devices_query.filter(user__profile__role=role_filter)
        elif self.user and hasattr(self.user, 'profile') and self.user.profile.role == 'student':
            devices_query = devices_query.filter(user=self.user)
        
        total_devices = devices_query.count()
        compliant_devices = devices_query.filter(compliance_status=True).count()
        non_compliant_devices = total_devices - compliant_devices
        
        compliance_rate = (compliant_devices / total_devices * 100) if total_devices > 0 else 0
        
        # Device type breakdown
        device_types = devices_query.values('device_type').annotate(
            count=Count('id'),
            compliant_count=Count('id', filter=Q(compliance_status=True))
        ).order_by('device_type')
        
        # Recent registrations
        recent_registrations = devices_query.filter(
            registered_at__date__gte=self.start_date
        ).count()
        
        return {
            'total_devices': total_devices,
            'compliant_devices': compliant_devices,
            'non_compliant_devices': non_compliant_devices,
            'compliance_rate': round(compliance_rate, 1),
            'device_types': list(device_types),
            'recent_registrations': recent_registrations,
        }
    
    def get_active_session_counts(self, role_filter=None):
        """
        Get active session counting and statistics.
        
        Args:
            role_filter (str): Filter by user role
            
        Returns:
            dict: Session statistics
        """
        sessions_query = SessionTracker.objects.all()
        
        if role_filter:
            sessions_query = sessions_query.filter(user__profile__role=role_filter)
        elif self.user and hasattr(self.user, 'profile') and self.user.profile.role == 'student':
            sessions_query = sessions_query.filter(user=self.user)
        
        # Current active sessions
        active_sessions = sessions_query.filter(status='active').count()
        
        # Unique active users
        active_users = sessions_query.filter(status='active').values('user').distinct().count()
        
        # Today's sessions
        today_sessions = sessions_query.filter(
            login_time__date=self.today
        ).count()
        
        # Session duration statistics
        completed_sessions = sessions_query.filter(
            logout_time__isnull=False,
            login_time__date__gte=self.start_date
        )
        
        avg_session_duration = None
        if completed_sessions.exists():
            durations = []
            for session in completed_sessions:
                duration = session.logout_time - session.login_time
                durations.append(duration.total_seconds() / 3600)  # Convert to hours
            
            if durations:
                avg_session_duration = sum(durations) / len(durations)
        
        # Peak usage hours (sessions started by hour) - simplified for SQLite compatibility
        try:
            peak_hours = sessions_query.filter(
                login_time__date__gte=self.start_date
            ).extra(
                select={'hour': "strftime('%%H', login_time)"}
            ).values('hour').annotate(
                session_count=Count('id')
            ).order_by('-session_count')[:3]
        except Exception:
            # Fallback if extra() doesn't work
            peak_hours = []
        
        return {
            'active_sessions': active_sessions,
            'active_users': active_users,
            'today_sessions': today_sessions,
            'avg_session_duration_hours': round(avg_session_duration, 2) if avg_session_duration else 0,
            'peak_hours': list(peak_hours),
        }
    
    def get_productivity_summaries(self, role_filter=None):
        """
        Get productivity summaries and metrics.
        
        Args:
            role_filter (str): Filter by user role
            
        Returns:
            dict: Productivity statistics
        """
        reports_query = PerformanceReport.objects.filter(
            report_date__gte=self.start_date
        )
        
        if role_filter:
            reports_query = reports_query.filter(user__profile__role=role_filter)
        elif self.user and hasattr(self.user, 'profile') and self.user.profile.role == 'student':
            reports_query = reports_query.filter(user=self.user)
        
        # Average metrics
        avg_metrics = reports_query.aggregate(
            avg_productivity=Avg('productivity_score'),
            avg_attendance=Avg('attendance_percentage'),
            avg_active_time=Avg('total_active_time'),
        )
        
        # Top performers
        top_performers = reports_query.select_related('user').order_by(
            '-productivity_score'
        )[:5]
        
        # Low performers (need attention)
        low_performers = reports_query.select_related('user').filter(
            productivity_score__lt=60
        ).order_by('productivity_score')[:5]
        
        # Activity trends
        activity_logs = ActivityLog.objects.filter(
            timestamp__date__gte=self.start_date
        )
        
        if role_filter:
            activity_logs = activity_logs.filter(user__profile__role=role_filter)
        elif self.user and hasattr(self.user, 'profile') and self.user.profile.role == 'student':
            activity_logs = activity_logs.filter(user=self.user)
        
        # Daily activity breakdown
        daily_activity = activity_logs.values('timestamp__date').annotate(
            total_duration=Sum('duration'),
            activity_count=Count('id'),
            unique_users=Count('user', distinct=True)
        ).order_by('timestamp__date')
        
        # Most common activity types
        activity_types = activity_logs.values('activity_type').annotate(
            count=Count('id'),
            total_duration=Sum('duration')
        ).order_by('-count')
        
        return {
            'avg_productivity': round(avg_metrics['avg_productivity'] or 0, 1),
            'avg_attendance': round(avg_metrics['avg_attendance'] or 0, 1),
            'avg_active_time_hours': (
                avg_metrics['avg_active_time'].total_seconds() / 3600
            ) if avg_metrics['avg_active_time'] else 0,
            'top_performers': list(top_performers),
            'low_performers': list(low_performers),
            'daily_activity': list(daily_activity),
            'activity_types': list(activity_types),
        }
    
    def get_security_alert_aggregation(self):
        """
        Get security alert aggregation and display data.
        
        Returns:
            dict: Security alert statistics
        """
        # Security violations
        violations = SessionTracker.objects.filter(
            status='violation',
            login_time__date__gte=self.start_date
        )
        
        total_violations = violations.count()
        
        # Violations by user
        violations_by_user = violations.values(
            'user__username'
        ).annotate(
            violation_count=Count('id')
        ).order_by('-violation_count')[:10]
        
        # Violations by device
        violations_by_device = violations.values(
            'device__name', 'device__user__username'
        ).annotate(
            violation_count=Count('id')
        ).order_by('-violation_count')[:10]
        
        # Daily violation trends
        daily_violations = violations.values('login_time__date').annotate(
            count=Count('id')
        ).order_by('login_time__date')
        
        # Expired sessions (potential security concern)
        expired_sessions = SessionTracker.objects.filter(
            status='expired',
            login_time__date__gte=self.start_date
        ).count()
        
        # Concurrent session attempts (security monitoring)
        concurrent_attempts = SessionTracker.objects.filter(
            login_time__date__gte=self.start_date
        ).values('user').annotate(
            concurrent_count=Count('id', filter=Q(status='active'))
        ).filter(concurrent_count__gt=1).count()
        
        # Recent security events
        recent_events = violations.select_related(
            'user', 'device'
        ).order_by('-login_time')[:10]
        
        return {
            'total_violations': total_violations,
            'violations_by_user': list(violations_by_user),
            'violations_by_device': list(violations_by_device),
            'daily_violations': list(daily_violations),
            'expired_sessions': expired_sessions,
            'concurrent_attempts': concurrent_attempts,
            'recent_events': list(recent_events),
        }
    
    def get_user_role_distribution(self):
        """
        Get user role distribution statistics.
        
        Returns:
            dict: User role statistics
        """
        role_distribution = UserProfile.objects.values('role').annotate(
            count=Count('id')
        ).order_by('role')
        
        # Active users by role (have sessions in the date range)
        active_by_role = SessionTracker.objects.filter(
            login_time__date__gte=self.start_date
        ).values('user__profile__role').annotate(
            active_count=Count('user', distinct=True)
        )
        
        return {
            'role_distribution': list(role_distribution),
            'active_by_role': list(active_by_role),
        }
    
    def get_system_health_metrics(self):
        """
        Get overall system health and performance metrics.
        
        Returns:
            dict: System health statistics
        """
        # Database record counts
        total_users = User.objects.count()
        total_devices = Device.objects.count()
        total_activity_logs = ActivityLog.objects.count()
        total_sessions = SessionTracker.objects.count()
        
        # Recent activity (system usage indicator)
        recent_activity_count = ActivityLog.objects.filter(
            timestamp__date__gte=self.start_date
        ).count()
        
        # Data growth trends
        daily_growth = {
            'users': User.objects.filter(
                date_joined__date__gte=self.start_date
            ).count(),
            'devices': Device.objects.filter(
                registered_at__date__gte=self.start_date
            ).count(),
            'activity_logs': ActivityLog.objects.filter(
                timestamp__date__gte=self.start_date
            ).count(),
        }
        
        # System utilization
        avg_daily_sessions = SessionTracker.objects.filter(
            login_time__date__gte=self.start_date
        ).values('login_time__date').annotate(
            daily_count=Count('id')
        ).aggregate(
            avg_sessions=Avg('daily_count')
        )['avg_sessions'] or 0
        
        return {
            'total_users': total_users,
            'total_devices': total_devices,
            'total_activity_logs': total_activity_logs,
            'total_sessions': total_sessions,
            'recent_activity_count': recent_activity_count,
            'daily_growth': daily_growth,
            'avg_daily_sessions': round(avg_daily_sessions, 1),
        }


def get_dashboard_summary(user, role=None):
    """
    Get a comprehensive dashboard summary for a user.
    
    Args:
        user: Django User object
        role: User role override (optional)
        
    Returns:
        dict: Complete dashboard summary
    """
    aggregator = DashboardDataAggregator(user=user)
    
    user_role = role or (user.profile.role if hasattr(user, 'profile') else 'student')
    
    summary = {
        'user_role': user_role,
        'timestamp': timezone.now(),
    }
    
    if user_role == 'admin':
        summary.update({
            'device_compliance': aggregator.get_device_compliance_overview(),
            'session_stats': aggregator.get_active_session_counts(),
            'productivity': aggregator.get_productivity_summaries(),
            'security_alerts': aggregator.get_security_alert_aggregation(),
            'user_distribution': aggregator.get_user_role_distribution(),
            'system_health': aggregator.get_system_health_metrics(),
        })
    elif user_role == 'teacher':
        summary.update({
            'device_compliance': aggregator.get_device_compliance_overview('student'),
            'session_stats': aggregator.get_active_session_counts('student'),
            'productivity': aggregator.get_productivity_summaries('student'),
        })
    elif user_role == 'student':
        summary.update({
            'device_compliance': aggregator.get_device_compliance_overview(),
            'session_stats': aggregator.get_active_session_counts(),
            'productivity': aggregator.get_productivity_summaries(),
        })
    
    return summary


def calculate_compliance_trend(days=30):
    """
    Calculate device compliance trend over time.
    
    Args:
        days (int): Number of days to analyze
        
    Returns:
        list: Daily compliance rates
    """
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    compliance_trend = []
    current_date = start_date
    
    while current_date <= end_date:
        # Get devices registered up to this date
        devices_up_to_date = Device.objects.filter(
            registered_at__date__lte=current_date
        )
        
        total_devices = devices_up_to_date.count()
        compliant_devices = devices_up_to_date.filter(
            compliance_status=True
        ).count()
        
        compliance_rate = (
            compliant_devices / total_devices * 100
        ) if total_devices > 0 else 0
        
        compliance_trend.append({
            'date': current_date,
            'total_devices': total_devices,
            'compliant_devices': compliant_devices,
            'compliance_rate': round(compliance_rate, 1),
        })
        
        current_date += timedelta(days=1)
    
    return compliance_trend


def get_productivity_insights(user_role='student', days=7):
    """
    Get productivity insights and recommendations.
    
    Args:
        user_role (str): Role to analyze
        days (int): Number of days to analyze
        
    Returns:
        dict: Productivity insights
    """
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    reports = PerformanceReport.objects.filter(
        user__profile__role=user_role,
        report_date__gte=start_date
    )
    
    if not reports.exists():
        return {
            'insights': [],
            'recommendations': ['No data available for analysis'],
        }
    
    insights = []
    recommendations = []
    
    # Analyze productivity trends
    avg_productivity = reports.aggregate(
        avg=Avg('productivity_score')
    )['avg'] or 0
    
    if avg_productivity < 60:
        insights.append(f"Average productivity is below target ({avg_productivity:.1f}%)")
        recommendations.append("Consider reviewing study habits and time management")
    elif avg_productivity > 80:
        insights.append(f"Excellent productivity performance ({avg_productivity:.1f}%)")
        recommendations.append("Maintain current study patterns")
    
    # Analyze attendance patterns
    avg_attendance = reports.aggregate(
        avg=Avg('attendance_percentage')
    )['avg'] or 0
    
    if avg_attendance < 80:
        insights.append(f"Attendance could be improved ({avg_attendance:.1f}%)")
        recommendations.append("Focus on consistent daily participation")
    
    # Analyze activity patterns
    low_activity_days = reports.filter(
        total_active_time__lt=timedelta(hours=2)
    ).count()
    
    if low_activity_days > days * 0.3:  # More than 30% of days
        insights.append("Several days with low activity detected")
        recommendations.append("Aim for more consistent daily engagement")
    
    return {
        'insights': insights,
        'recommendations': recommendations,
        'avg_productivity': round(avg_productivity, 1),
        'avg_attendance': round(avg_attendance, 1),
    }