from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.db.models import Count, Q, Avg, Sum
from django.utils import timezone
from datetime import timedelta, date
from django.contrib.auth.models import User

from users.models import UserProfile
from devices.models import Device, DeviceAccessRequest
from productivity.models import ActivityLog, PerformanceReport
from security.models import AccessControl, SessionTracker
from .utils import DashboardDataAggregator, get_dashboard_summary, get_productivity_insights


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Main dashboard view with role-based content aggregation.
    Displays different data based on user role (teacher, student, admin).
    """
    template_name = 'dashboard/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        user_profile = getattr(user, 'profile', None)
        
        if not user_profile:
            # Create profile if it doesn't exist
            user_profile = UserProfile.objects.create(user=user)
        
        # Common context for all roles
        context.update({
            'user_role': user_profile.role,
            'current_date': timezone.now().date(),
        })
        
        # Role-specific data aggregation
        if user_profile.is_admin:
            context.update(self._get_admin_dashboard_data())
        elif user_profile.is_teacher:
            context.update(self._get_teacher_dashboard_data())
        elif user_profile.is_student:
            context.update(self._get_student_dashboard_data(user))
        
        return context
    
    def _get_admin_dashboard_data(self):
        """
        Aggregate data for administrator dashboard using utility functions.
        """
        aggregator = DashboardDataAggregator()
        
        # Get comprehensive data using utility functions
        device_data = aggregator.get_device_compliance_overview()
        session_data = aggregator.get_active_session_counts()
        security_data = aggregator.get_security_alert_aggregation()
        system_health = aggregator.get_system_health_metrics()
        
        # Get recent activity for display
        week_ago = timezone.now().date() - timedelta(days=7)
        recent_registrations = Device.objects.filter(
            registered_at__date__gte=week_ago
        ).select_related('user').order_by('-registered_at')[:5]
        
        recent_violations = SessionTracker.objects.filter(
            status='violation',
            login_time__date__gte=week_ago
        ).select_related('user', 'device').order_by('-login_time')[:5]
        
        # Get pending access requests for admins
        pending_requests = DeviceAccessRequest.objects.filter(
            status='pending'
        ).select_related('device', 'requester', 'requester__profile').order_by('-requested_at')[:10]
        
        pending_count = DeviceAccessRequest.objects.filter(status='pending').count()
        
        return {
            'total_users': system_health['total_users'],
            'active_users_today': session_data['active_users'],
            'total_devices': device_data['total_devices'],
            'compliant_devices': device_data['compliant_devices'],
            'compliance_rate': device_data['compliance_rate'],
            'active_sessions': session_data['active_sessions'],
            'total_sessions_today': session_data['today_sessions'],
            'security_violations': security_data['total_violations'],
            'recent_registrations': recent_registrations,
            'recent_violations': recent_violations,
            'pending_access_requests': pending_requests,
            'pending_requests_count': pending_count,
        }
    
    def _get_teacher_dashboard_data(self):
        """
        Aggregate data for teacher dashboard using utility functions.
        """
        aggregator = DashboardDataAggregator()
        
        # Get student-specific data
        device_data = aggregator.get_device_compliance_overview('student')
        session_data = aggregator.get_active_session_counts('student')
        productivity_data = aggregator.get_productivity_summaries('student')
        
        # Student count
        total_students = UserProfile.objects.filter(role='student').count()
        
        # Recent student activity
        week_ago = timezone.now().date() - timedelta(days=7)
        recent_activity = ActivityLog.objects.filter(
            timestamp__date__gte=week_ago,
            user__profile__role='student'
        ).select_related('user', 'device').order_by('-timestamp')[:10]
        
        # Get pending student access requests for teachers
        pending_requests = DeviceAccessRequest.objects.filter(
            status='pending',
            requester__profile__role='student'
        ).select_related('device', 'requester').order_by('-requested_at')[:10]
        
        pending_count = DeviceAccessRequest.objects.filter(
            status='pending',
            requester__profile__role='student'
        ).count()
        
        return {
            'total_students': total_students,
            'active_students_today': session_data['active_users'],
            'total_student_devices': device_data['total_devices'],
            'student_compliance_rate': device_data['compliance_rate'],
            'avg_productivity': productivity_data['avg_productivity'],
            'avg_attendance': productivity_data['avg_attendance'],
            'recent_activity': recent_activity,
            'top_students': productivity_data['top_performers'],
            'pending_access_requests': pending_requests,
            'pending_requests_count': pending_count,
        }
    
    def _get_student_dashboard_data(self, user):
        """
        Aggregate data for student dashboard using utility functions.
        """
        aggregator = DashboardDataAggregator(user=user)
        
        # Get personal data
        device_data = aggregator.get_device_compliance_overview()
        session_data = aggregator.get_active_session_counts()
        productivity_data = aggregator.get_productivity_summaries()
        
        # Personal activity and performance
        week_ago = timezone.now().date() - timedelta(days=7)
        recent_activity = ActivityLog.objects.filter(
            user=user,
            timestamp__date__gte=week_ago
        ).order_by('-timestamp')[:10]
        
        total_activity_time = ActivityLog.objects.filter(
            user=user,
            timestamp__date__gte=week_ago
        ).aggregate(
            total_time=Sum('duration')
        )['total_time'] or timedelta(0)
        
        latest_report = PerformanceReport.objects.filter(
            user=user
        ).order_by('-report_date').first()
        
        recent_sessions = SessionTracker.objects.filter(
            user=user,
            login_time__date__gte=week_ago
        ).select_related('device').order_by('-login_time')[:5]
        
        # Get productivity insights
        insights = get_productivity_insights('student', days=7)
        
        # Get student's own access requests
        my_access_requests = DeviceAccessRequest.objects.filter(
            requester=user
        ).select_related('device', 'approved_by').order_by('-requested_at')[:5]
        
        pending_requests_count = DeviceAccessRequest.objects.filter(
            requester=user,
            status='pending'
        ).count()
        
        return {
            'total_devices': device_data['total_devices'],
            'compliant_devices': device_data['compliant_devices'],
            'recent_activity': recent_activity,
            'total_activity_hours': total_activity_time.total_seconds() / 3600,
            'latest_report': latest_report,
            'recent_sessions': recent_sessions,
            'weekly_activity': productivity_data['daily_activity'],
            'productivity_insights': insights,
            'my_access_requests': my_access_requests,
            'pending_requests_count': pending_requests_count,
        }


class StatsAPIView(LoginRequiredMixin, TemplateView):
    """
    JSON API endpoint for real-time dashboard updates.
    Returns role-appropriate statistics in JSON format.
    """
    
    def get(self, request, *args, **kwargs):
        user = request.user
        user_profile = getattr(user, 'profile', None)
        
        if not user_profile:
            return JsonResponse({'error': 'User profile not found'}, status=404)
        
        # Get real-time statistics based on role
        if user_profile.is_admin:
            stats = self._get_admin_stats()
        elif user_profile.is_teacher:
            stats = self._get_teacher_stats()
        elif user_profile.is_student:
            stats = self._get_student_stats(user)
        else:
            stats = {}
        
        stats['timestamp'] = timezone.now().isoformat()
        return JsonResponse(stats)
    
    def _get_admin_stats(self):
        """
        Real-time statistics for administrators.
        """
        active_sessions = SessionTracker.objects.filter(status='active').count()
        total_users_online = SessionTracker.objects.filter(
            status='active'
        ).values('user').distinct().count()
        
        recent_violations = SessionTracker.objects.filter(
            status='violation',
            login_time__date=timezone.now().date()
        ).count()
        
        device_compliance = Device.objects.aggregate(
            total=Count('id'),
            compliant=Count('id', filter=Q(compliance_status=True))
        )
        
        compliance_rate = (
            device_compliance['compliant'] / device_compliance['total'] * 100
        ) if device_compliance['total'] > 0 else 0
        
        return {
            'active_sessions': active_sessions,
            'users_online': total_users_online,
            'recent_violations': recent_violations,
            'compliance_rate': round(compliance_rate, 1),
            'total_devices': device_compliance['total'],
        }
    
    def _get_teacher_stats(self):
        """
        Real-time statistics for teachers.
        """
        active_students = SessionTracker.objects.filter(
            status='active',
            user__profile__role='student'
        ).values('user').distinct().count()
        
        student_sessions = SessionTracker.objects.filter(
            status='active',
            user__profile__role='student'
        ).count()
        
        return {
            'active_students': active_students,
            'student_sessions': student_sessions,
        }
    
    def _get_student_stats(self, user):
        """
        Real-time statistics for students.
        """
        active_session = SessionTracker.objects.filter(
            user=user,
            status='active'
        ).first()
        
        today_activity = ActivityLog.objects.filter(
            user=user,
            timestamp__date=timezone.now().date()
        ).aggregate(
            total_time=Sum('duration'),
            activity_count=Count('id')
        )
        
        session_duration = None
        if active_session:
            session_duration = (timezone.now() - active_session.login_time).total_seconds() / 3600
        
        return {
            'has_active_session': bool(active_session),
            'session_duration_hours': round(session_duration, 2) if session_duration else 0,
            'today_activity_hours': (
                today_activity['total_time'].total_seconds() / 3600
            ) if today_activity['total_time'] else 0,
            'today_activity_count': today_activity['activity_count'] or 0,
        }


@login_required
def dashboard_home(request):
    """
    Simple function-based view that redirects to the class-based dashboard.
    This can be used as the main entry point.
    """
    return DashboardView.as_view()(request)