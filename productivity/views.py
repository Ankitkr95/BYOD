import csv
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Avg
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib.auth.models import User
from .models import ActivityLog, PerformanceReport
from devices.models import Device


class ActivityLogListView(LoginRequiredMixin, ListView):
    """
    List view for activity logs with pagination and filtering.
    Shows activity logs based on user role permissions.
    """
    model = ActivityLog
    template_name = 'productivity/activity_logs.html'
    context_object_name = 'activity_logs'
    paginate_by = 20
    
    def get_queryset(self):
        """
        Return activity logs based on user role and filtering options.
        """
        user = self.request.user
        
        # Base queryset depends on user role
        if hasattr(user, 'profile'):
            if user.profile.is_teacher or user.profile.is_admin:
                # Teachers and admins can see all activity logs
                queryset = ActivityLog.objects.all().select_related('user', 'device')
            else:
                # Students can only see their own activity logs
                queryset = ActivityLog.objects.filter(user=user).select_related('user', 'device')
        else:
            # Default to user's own logs if no profile
            queryset = ActivityLog.objects.filter(user=user).select_related('user', 'device')
        
        # Date filtering
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                queryset = queryset.filter(timestamp__date__gte=start_date)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(timestamp__date__lte=end_date)
            except ValueError:
                pass
        
        # Activity type filtering
        activity_type = self.request.GET.get('activity_type', '').strip()
        if activity_type:
            queryset = queryset.filter(activity_type=activity_type)
        
        # User filtering (for teachers/admins)
        if hasattr(user, 'profile') and (user.profile.is_teacher or user.profile.is_admin):
            user_filter = self.request.GET.get('user_filter', '').strip()
            if user_filter:
                queryset = queryset.filter(
                    Q(user__username__icontains=user_filter) |
                    Q(user__first_name__icontains=user_filter) |
                    Q(user__last_name__icontains=user_filter)
                )
        
        # Device filtering
        device_filter = self.request.GET.get('device_filter', '').strip()
        if device_filter:
            queryset = queryset.filter(device__name__icontains=device_filter)
        
        return queryset.order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter choices
        context['activity_type_choices'] = ActivityLog.ACTIVITY_TYPE_CHOICES
        
        # Preserve current filter values
        context['current_start_date'] = self.request.GET.get('start_date', '')
        context['current_end_date'] = self.request.GET.get('end_date', '')
        context['current_activity_type'] = self.request.GET.get('activity_type', '')
        context['current_user_filter'] = self.request.GET.get('user_filter', '')
        context['current_device_filter'] = self.request.GET.get('device_filter', '')
        
        # Add user role information
        user = self.request.user
        context['can_view_all_users'] = (
            hasattr(user, 'profile') and 
            (user.profile.is_teacher or user.profile.is_admin)
        )
        
        # Add summary statistics
        queryset = self.get_queryset()
        context['total_logs'] = queryset.count()
        context['total_duration'] = queryset.aggregate(
            total=Sum('duration')
        )['total'] or timedelta(0)
        
        # Activity type breakdown
        activity_breakdown = queryset.values('activity_type').annotate(
            count=Count('id'),
            total_duration=Sum('duration')
        ).order_by('-count')
        context['activity_breakdown'] = activity_breakdown
        
        return context


class ReportsView(LoginRequiredMixin, ListView):
    """
    View for displaying productivity reports and analytics.
    """
    model = PerformanceReport
    template_name = 'productivity/reports.html'
    context_object_name = 'reports'
    paginate_by = 10
    
    def get_queryset(self):
        """
        Return performance reports based on user role and filtering.
        """
        user = self.request.user
        
        # Base queryset depends on user role
        if hasattr(user, 'profile'):
            if user.profile.is_teacher or user.profile.is_admin:
                # Teachers and admins can see all reports
                queryset = PerformanceReport.objects.all().select_related('user')
            else:
                # Students can only see their own reports
                queryset = PerformanceReport.objects.filter(user=user).select_related('user')
        else:
            # Default to user's own reports if no profile
            queryset = PerformanceReport.objects.filter(user=user).select_related('user')
        
        # Report type filtering
        report_type = self.request.GET.get('report_type', '').strip()
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        # Date range filtering
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                queryset = queryset.filter(report_date__gte=start_date)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(report_date__lte=end_date)
            except ValueError:
                pass
        
        # User filtering (for teachers/admins)
        if hasattr(user, 'profile') and (user.profile.is_teacher or user.profile.is_admin):
            user_filter = self.request.GET.get('user_filter', '').strip()
            if user_filter:
                queryset = queryset.filter(
                    Q(user__username__icontains=user_filter) |
                    Q(user__first_name__icontains=user_filter) |
                    Q(user__last_name__icontains=user_filter)
                )
        
        return queryset.order_by('-report_date', '-generated_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter choices
        context['report_type_choices'] = PerformanceReport.REPORT_TYPE_CHOICES
        
        # Preserve current filter values
        context['current_report_type'] = self.request.GET.get('report_type', '')
        context['current_start_date'] = self.request.GET.get('start_date', '')
        context['current_end_date'] = self.request.GET.get('end_date', '')
        context['current_user_filter'] = self.request.GET.get('user_filter', '')
        
        # Add user role information
        user = self.request.user
        context['can_view_all_users'] = (
            hasattr(user, 'profile') and 
            (user.profile.is_teacher or user.profile.is_admin)
        )
        
        # Add summary statistics
        queryset = self.get_queryset()
        if queryset.exists():
            context['avg_productivity_score'] = queryset.aggregate(
                avg=Avg('productivity_score')
            )['avg'] or 0
            context['avg_attendance'] = queryset.aggregate(
                avg=Avg('attendance_percentage')
            )['avg'] or 0
            context['total_reports'] = queryset.count()
        else:
            context['avg_productivity_score'] = 0
            context['avg_attendance'] = 0
            context['total_reports'] = 0
        
        return context


class ExportCSVView(LoginRequiredMixin, ListView):
    """
    View for exporting activity logs and reports to CSV format.
    """
    
    def get(self, request, *args, **kwargs):
        """
        Handle CSV export based on export_type parameter.
        """
        export_type = request.GET.get('export_type', 'activity_logs')
        
        if export_type == 'activity_logs':
            return self.export_activity_logs()
        elif export_type == 'reports':
            return self.export_reports()
        else:
            messages.error(request, 'Invalid export type specified.')
            return redirect('productivity:reports')
    
    def export_activity_logs(self):
        """
        Export activity logs to CSV.
        """
        user = self.request.user
        
        # Get queryset based on user permissions
        if hasattr(user, 'profile') and (user.profile.is_teacher or user.profile.is_admin):
            queryset = ActivityLog.objects.all().select_related('user', 'device')
        else:
            queryset = ActivityLog.objects.filter(user=user).select_related('user', 'device')
        
        # Apply same filters as ActivityLogListView
        queryset = self.apply_activity_filters(queryset)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="activity_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Timestamp', 'User', 'Device', 'Activity Type', 
            'Duration (minutes)', 'Resources Accessed', 'IP Address'
        ])
        
        for log in queryset:
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.user.username,
                log.device.name,
                log.get_activity_type_display(),
                round(log.duration_minutes, 2),
                ', '.join(log.get_resources_list()) if log.get_resources_list() else '',
                log.ip_address or ''
            ])
        
        return response
    
    def export_reports(self):
        """
        Export performance reports to CSV.
        """
        user = self.request.user
        
        # Get queryset based on user permissions
        if hasattr(user, 'profile') and (user.profile.is_teacher or user.profile.is_admin):
            queryset = PerformanceReport.objects.all().select_related('user')
        else:
            queryset = PerformanceReport.objects.filter(user=user).select_related('user')
        
        # Apply same filters as ReportsView
        queryset = self.apply_report_filters(queryset)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="performance_reports_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'User', 'Report Type', 'Report Date', 'Productivity Score', 
            'Attendance %', 'Active Time (hours)', 'Idle Time (hours)', 
            'Login Count', 'Devices Used', 'Generated At'
        ])
        
        for report in queryset:
            writer.writerow([
                report.user.username,
                report.get_report_type_display(),
                report.report_date.strftime('%Y-%m-%d'),
                round(report.productivity_score, 2),
                round(report.attendance_percentage, 2),
                round(report.active_time_hours, 2),
                round(report.idle_time_hours, 2),
                report.login_count,
                report.devices_used,
                report.generated_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    
    def apply_activity_filters(self, queryset):
        """
        Apply the same filters as ActivityLogListView.
        """
        # Date filtering
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                queryset = queryset.filter(timestamp__date__gte=start_date)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(timestamp__date__lte=end_date)
            except ValueError:
                pass
        
        # Activity type filtering
        activity_type = self.request.GET.get('activity_type', '').strip()
        if activity_type:
            queryset = queryset.filter(activity_type=activity_type)
        
        # User filtering (for teachers/admins)
        user = self.request.user
        if hasattr(user, 'profile') and (user.profile.is_teacher or user.profile.is_admin):
            user_filter = self.request.GET.get('user_filter', '').strip()
            if user_filter:
                queryset = queryset.filter(
                    Q(user__username__icontains=user_filter) |
                    Q(user__first_name__icontains=user_filter) |
                    Q(user__last_name__icontains=user_filter)
                )
        
        return queryset.order_by('-timestamp')
    
    def apply_report_filters(self, queryset):
        """
        Apply the same filters as ReportsView.
        """
        # Report type filtering
        report_type = self.request.GET.get('report_type', '').strip()
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        # Date range filtering
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                queryset = queryset.filter(report_date__gte=start_date)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(report_date__lte=end_date)
            except ValueError:
                pass
        
        # User filtering (for teachers/admins)
        user = self.request.user
        if hasattr(user, 'profile') and (user.profile.is_teacher or user.profile.is_admin):
            user_filter = self.request.GET.get('user_filter', '').strip()
            if user_filter:
                queryset = queryset.filter(
                    Q(user__username__icontains=user_filter) |
                    Q(user__first_name__icontains=user_filter) |
                    Q(user__last_name__icontains=user_filter)
                )
        
        return queryset.order_by('-report_date', '-generated_at')


@login_required
def activity_stats_api(request):
    """
    JSON API endpoint for activity statistics (for AJAX requests).
    """
    user = request.user
    
    # Get date range from request
    days = int(request.GET.get('days', 7))  # Default to last 7 days
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Base queryset based on user permissions
    if hasattr(user, 'profile') and (user.profile.is_teacher or user.profile.is_admin):
        queryset = ActivityLog.objects.filter(
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        )
    else:
        queryset = ActivityLog.objects.filter(
            user=user,
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        )
    
    # Calculate statistics
    stats = {
        'total_activities': queryset.count(),
        'total_duration_hours': 0,
        'activity_breakdown': {},
        'daily_activity': {}
    }
    
    # Total duration
    total_duration = queryset.aggregate(total=Sum('duration'))['total']
    if total_duration:
        stats['total_duration_hours'] = round(total_duration.total_seconds() / 3600, 2)
    
    # Activity type breakdown
    activity_breakdown = queryset.values('activity_type').annotate(
        count=Count('id'),
        total_duration=Sum('duration')
    )
    
    for item in activity_breakdown:
        activity_type = item['activity_type']
        duration_hours = 0
        if item['total_duration']:
            duration_hours = round(item['total_duration'].total_seconds() / 3600, 2)
        
        stats['activity_breakdown'][activity_type] = {
            'count': item['count'],
            'duration_hours': duration_hours
        }
    
    # Daily activity (for charts)
    daily_activities = queryset.extra(
        select={'day': 'date(timestamp)'}
    ).values('day').annotate(
        count=Count('id'),
        total_duration=Sum('duration')
    ).order_by('day')
    
    for item in daily_activities:
        day = item['day'] if isinstance(item['day'], str) else item['day'].strftime('%Y-%m-%d')
        duration_hours = 0
        if item['total_duration']:
            duration_hours = round(item['total_duration'].total_seconds() / 3600, 2)
        
        stats['daily_activity'][day] = {
            'count': item['count'],
            'duration_hours': duration_hours
        }
    
    return JsonResponse(stats)
