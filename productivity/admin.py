from django.contrib import admin
from django.utils.html import format_html
from .models import ActivityLog, PerformanceReport


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """
    Admin interface for ActivityLog model.
    """
    list_display = [
        'user', 'device', 'activity_type', 'duration_display', 
        'timestamp', 'session_id'
    ]
    list_filter = [
        'activity_type', 'timestamp', 'user__profile__role'
    ]
    search_fields = [
        'user__username', 'user__first_name', 'user__last_name',
        'device__name', 'session_id', 'ip_address'
    ]
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'device', 'activity_type', 'duration')
        }),
        ('Session Details', {
            'fields': ('timestamp', 'session_id', 'ip_address')
        }),
        ('Resources', {
            'fields': ('resources_accessed',),
            'classes': ('collapse',)
        }),
    )
    
    def duration_display(self, obj):
        """Display duration in a human-readable format."""
        if obj.duration_minutes < 60:
            return f"{obj.duration_minutes:.1f}m"
        else:
            return f"{obj.duration_hours:.1f}h"
    duration_display.short_description = 'Duration'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user', 'device')


@admin.register(PerformanceReport)
class PerformanceReportAdmin(admin.ModelAdmin):
    """
    Admin interface for PerformanceReport model.
    """
    list_display = [
        'user', 'report_type', 'report_date', 'productivity_score_display',
        'attendance_percentage_display', 'generated_at'
    ]
    list_filter = [
        'report_type', 'report_date', 'user__profile__role', 'generated_at'
    ]
    search_fields = [
        'user__username', 'user__first_name', 'user__last_name'
    ]
    readonly_fields = ['generated_at', 'updated_at']
    date_hierarchy = 'report_date'
    ordering = ['-report_date', '-generated_at']
    
    fieldsets = (
        ('Report Information', {
            'fields': ('user', 'report_type', 'report_date', 'start_date', 'end_date')
        }),
        ('Performance Metrics', {
            'fields': ('productivity_score', 'attendance_percentage')
        }),
        ('Time Metrics', {
            'fields': ('total_active_time', 'total_idle_time')
        }),
        ('Activity Metrics', {
            'fields': ('login_count', 'devices_used')
        }),
        ('Detailed Data', {
            'fields': ('detailed_metrics',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('generated_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def productivity_score_display(self, obj):
        """Display productivity score with color coding."""
        score = obj.productivity_score
        if score >= 80:
            color = 'green'
        elif score >= 60:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, score
        )
    productivity_score_display.short_description = 'Productivity Score'
    
    def attendance_percentage_display(self, obj):
        """Display attendance percentage with color coding."""
        attendance = obj.attendance_percentage
        if attendance >= 90:
            color = 'green'
        elif attendance >= 70:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, attendance
        )
    attendance_percentage_display.short_description = 'Attendance %'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user')
