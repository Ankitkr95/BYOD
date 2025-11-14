import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count
from django.core.paginator import Paginator
from .models import AccessControl, SessionTracker
from .forms import AccessControlForm


def is_admin_user(user):
    """
    Check if user has admin role.
    """
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_admin


class AdminRequiredMixin(UserPassesTestMixin):
    """
    Mixin to require admin role for access.
    """
    def test_func(self):
        return is_admin_user(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, 'You need administrator privileges to access this page.')
        return redirect('dashboard:home')


class AccessRulesView(AdminRequiredMixin, ListView):
    """
    View for administrators to configure access control rules.
    """
    model = AccessControl
    template_name = 'security/access_rules.html'
    context_object_name = 'access_rules'
    paginate_by = 10
    
    def get_queryset(self):
        """
        Get access control rules with optional filtering.
        """
        queryset = AccessControl.objects.select_related('created_by').order_by('-created_at')
        
        # Filter by role if specified
        role_filter = self.request.GET.get('role')
        if role_filter:
            queryset = queryset.filter(role=role_filter)
        
        # Filter by active status
        active_filter = self.request.GET.get('active')
        if active_filter in ['true', 'false']:
            queryset = queryset.filter(is_active=active_filter == 'true')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """
        Add additional context for the template.
        """
        context = super().get_context_data(**kwargs)
        context['role_choices'] = AccessControl.ROLE_CHOICES
        context['current_role_filter'] = self.request.GET.get('role', '')
        context['current_active_filter'] = self.request.GET.get('active', '')
        return context


class AccessRuleCreateView(AdminRequiredMixin, CreateView):
    """
    View for creating new access control rules.
    """
    model = AccessControl
    form_class = AccessControlForm
    template_name = 'security/access_rule_form.html'
    success_url = reverse_lazy('security:access_rules')
    
    def form_valid(self, form):
        """
        Set created_by to current user.
        """
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Access rule for {form.instance.get_role_display()} created successfully.')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        """
        Handle form validation errors.
        """
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class AccessRuleUpdateView(AdminRequiredMixin, UpdateView):
    """
    View for updating existing access control rules.
    """
    model = AccessControl
    form_class = AccessControlForm
    template_name = 'security/access_rule_form.html'
    success_url = reverse_lazy('security:access_rules')
    
    def form_valid(self, form):
        """
        Handle successful form submission.
        """
        messages.success(self.request, f'Access rule for {form.instance.get_role_display()} updated successfully.')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        """
        Handle form validation errors.
        """
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class AccessRuleDeleteView(AdminRequiredMixin, DeleteView):
    """
    View for deleting access control rules.
    """
    model = AccessControl
    template_name = 'security/access_rule_confirm_delete.html'
    success_url = reverse_lazy('security:access_rules')
    
    def delete(self, request, *args, **kwargs):
        """
        Handle deletion with success message.
        """
        obj = self.get_object()
        messages.success(request, f'Access rule for {obj.get_role_display()} deleted successfully.')
        return super().delete(request, *args, **kwargs)


class SessionMonitorView(AdminRequiredMixin, ListView):
    """
    View for real-time session monitoring.
    """
    model = SessionTracker
    template_name = 'security/session_monitor.html'
    context_object_name = 'sessions'
    paginate_by = 20
    
    def get_queryset(self):
        """
        Get session data with optional filtering.
        """
        queryset = SessionTracker.objects.select_related('user', 'device').order_by('-login_time')
        
        # Filter by status
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by user
        user_filter = self.request.GET.get('user')
        if user_filter:
            queryset = queryset.filter(user__username__icontains=user_filter)
        
        # Filter by device
        device_filter = self.request.GET.get('device')
        if device_filter:
            queryset = queryset.filter(device__name__icontains=device_filter)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(login_time__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(login_time__date__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """
        Add additional context for the template.
        """
        context = super().get_context_data(**kwargs)
        
        # Session statistics
        context['total_sessions'] = SessionTracker.objects.count()
        context['active_sessions'] = SessionTracker.get_active_sessions().count()
        context['sessions_today'] = SessionTracker.objects.filter(
            login_time__date=timezone.now().date()
        ).count()
        context['violations_today'] = SessionTracker.objects.filter(
            login_time__date=timezone.now().date(),
            violation_count__gt=0
        ).count()
        
        # Filter values for form
        context['status_choices'] = SessionTracker.STATUS_CHOICES
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'user': self.request.GET.get('user', ''),
            'device': self.request.GET.get('device', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
        }
        
        return context


@login_required
@user_passes_test(is_admin_user)
def session_detail_view(request, session_id):
    """
    Detailed view of a specific session.
    """
    session = get_object_or_404(SessionTracker, id=session_id)
    
    context = {
        'session': session,
        'violations': session.get_violations(),
        'is_expired': session.is_session_expired(),
    }
    
    return render(request, 'security/session_detail.html', context)


@login_required
@user_passes_test(is_admin_user)
def end_session_view(request, session_id):
    """
    End a specific session.
    """
    if request.method == 'POST':
        session = get_object_or_404(SessionTracker, id=session_id)
        
        if session.is_active:
            session.end_session('admin_action')
            messages.success(request, f'Session for {session.user.username} ended successfully.')
        else:
            messages.warning(request, 'Session is already inactive.')
    
    return redirect('security:session_monitor')


class SecurityAlertsView(AdminRequiredMixin, ListView):
    """
    View for security violation notifications and alerts.
    """
    model = SessionTracker
    template_name = 'security/security_alerts.html'
    context_object_name = 'alerts'
    paginate_by = 15
    
    def get_queryset(self):
        """
        Get sessions with security violations.
        """
        queryset = SessionTracker.objects.filter(
            Q(violation_count__gt=0) | Q(status='violation')
        ).select_related('user', 'device').order_by('-login_time')
        
        # Filter by severity (based on violation count)
        severity_filter = self.request.GET.get('severity')
        if severity_filter == 'high':
            queryset = queryset.filter(violation_count__gte=5)
        elif severity_filter == 'medium':
            queryset = queryset.filter(violation_count__range=(2, 4))
        elif severity_filter == 'low':
            queryset = queryset.filter(violation_count=1)
        
        # Filter by date
        date_filter = self.request.GET.get('date')
        if date_filter == 'today':
            queryset = queryset.filter(login_time__date=timezone.now().date())
        elif date_filter == 'week':
            week_ago = timezone.now() - timezone.timedelta(days=7)
            queryset = queryset.filter(login_time__gte=week_ago)
        elif date_filter == 'month':
            month_ago = timezone.now() - timezone.timedelta(days=30)
            queryset = queryset.filter(login_time__gte=month_ago)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """
        Add alert statistics to context.
        """
        context = super().get_context_data(**kwargs)
        
        # Alert statistics
        context['total_alerts'] = self.get_queryset().count()
        context['high_severity'] = self.get_queryset().filter(violation_count__gte=5).count()
        context['medium_severity'] = self.get_queryset().filter(violation_count__range=(2, 4)).count()
        context['low_severity'] = self.get_queryset().filter(violation_count=1).count()
        
        # Recent alerts (last 24 hours)
        yesterday = timezone.now() - timezone.timedelta(days=1)
        context['recent_alerts'] = self.get_queryset().filter(login_time__gte=yesterday).count()
        
        # Filter values
        context['current_filters'] = {
            'severity': self.request.GET.get('severity', ''),
            'date': self.request.GET.get('date', ''),
        }
        
        return context


@login_required
@user_passes_test(is_admin_user)
def session_stats_api(request):
    """
    API endpoint for real-time session statistics.
    """
    stats = {
        'active_sessions': SessionTracker.get_active_sessions().count(),
        'total_sessions_today': SessionTracker.objects.filter(
            login_time__date=timezone.now().date()
        ).count(),
        'violations_today': SessionTracker.objects.filter(
            login_time__date=timezone.now().date(),
            violation_count__gt=0
        ).count(),
        'users_online': SessionTracker.get_active_sessions().values('user').distinct().count(),
    }
    
    return JsonResponse(stats)


@login_required
@user_passes_test(is_admin_user)
def cleanup_expired_sessions(request):
    """
    Manual cleanup of expired sessions.
    """
    if request.method == 'POST':
        timeout_minutes = int(request.POST.get('timeout_minutes', 30))
        
        from .session_utils import SessionManager
        stats = SessionManager.cleanup_expired_sessions(timeout_minutes)
        
        if 'error' in stats:
            messages.error(request, f'Cleanup failed: {stats["error"]}')
        else:
            messages.success(
                request, 
                f'Cleaned up {stats["total_cleaned"]} expired sessions '
                f'({stats["expired_session_trackers"]} trackers, '
                f'{stats["orphaned_sessions_cleaned"]} orphaned sessions).'
            )
    
    return redirect('security:session_monitor')


@login_required
@user_passes_test(is_admin_user)
def manage_user_sessions(request, user_id):
    """
    Manage sessions for a specific user.
    """
    from django.contrib.auth.models import User
    from .session_utils import SessionManager
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'end_all':
            count = SessionManager.end_all_sessions_for_user(user, 'admin_action')
            messages.success(request, f'Ended {count} sessions for user {user.username}.')
        
        elif action == 'end_session':
            session_id = request.POST.get('session_id')
            session_tracker = get_object_or_404(SessionTracker, id=session_id, user=user)
            session_tracker.end_session('admin_action')
            messages.success(request, f'Ended session for user {user.username}.')
    
    # Get user's active sessions
    active_sessions = SessionManager.get_active_sessions_for_user(user)
    
    context = {
        'target_user': user,
        'active_sessions': active_sessions,
        'session_count': active_sessions.count(),
    }
    
    return render(request, 'security/manage_user_sessions.html', context)


@login_required
@user_passes_test(is_admin_user)
def session_statistics_api(request):
    """
    API endpoint for session statistics.
    """
    from .session_utils import SessionManager
    
    stats = SessionManager.get_session_statistics()
    return JsonResponse(stats)


def csrf_failure(request, reason=""):
    """
    Custom CSRF failure view with user-friendly error message.
    """
    from django.shortcuts import render
    from django.http import HttpResponseForbidden
    import logging
    
    logger = logging.getLogger('security.middleware')
    logger.warning(f'CSRF failure for user {request.user} from IP {request.META.get("REMOTE_ADDR")}: {reason}')
    
    context = {
        'reason': reason,
        'user': request.user if request.user.is_authenticated else None,
    }
    
    return HttpResponseForbidden(
        render(request, 'security/csrf_failure.html', context).content
    )