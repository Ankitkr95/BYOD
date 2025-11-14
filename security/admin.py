from django.contrib import admin
from django.utils.html import format_html
from .models import AccessControl, SessionTracker


@admin.register(AccessControl)
class AccessControlAdmin(admin.ModelAdmin):
    """
    Admin interface for AccessControl model.
    """
    list_display = ['role', 'is_active', 'created_by', 'created_at', 'updated_at']
    list_filter = ['role', 'is_active', 'created_at']
    search_fields = ['role', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('role', 'is_active', 'created_by')
        }),
        ('Domain Access Control', {
            'fields': ('allowed_domains', 'blocked_domains'),
            'description': 'Enter domains as JSON lists, e.g., ["example.com", "google.com"]'
        }),
        ('Time Restrictions', {
            'fields': ('time_restrictions',),
            'description': 'Enter time restrictions as JSON object, e.g., {"start_time": "09:00", "end_time": "17:00", "days": ["monday", "tuesday"]}'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """
        Set created_by to current user if not set.
        """
        if not change:  # Only for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SessionTracker)
class SessionTrackerAdmin(admin.ModelAdmin):
    """
    Admin interface for SessionTracker model.
    """
    list_display = ['user', 'device', 'status', 'login_time', 'logout_time', 'duration_display', 'violation_count']
    list_filter = ['status', 'login_time', 'device__device_type', 'violation_count']
    search_fields = ['user__username', 'device__name', 'ip_address', 'session_key']
    readonly_fields = ['login_time', 'duration_display', 'time_since_last_activity_display']
    date_hierarchy = 'login_time'
    
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'device', 'session_key', 'status')
        }),
        ('Timing', {
            'fields': ('login_time', 'logout_time', 'last_activity', 'duration_display', 'time_since_last_activity_display')
        }),
        ('Network Information', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Security', {
            'fields': ('violation_count', 'violation_details'),
            'classes': ('collapse',)
        }),
    )
    
    def duration_display(self, obj):
        """
        Display session duration in a readable format.
        """
        duration = obj.duration
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    duration_display.short_description = 'Duration'
    
    def time_since_last_activity_display(self, obj):
        """
        Display time since last activity in a readable format.
        """
        time_diff = obj.time_since_last_activity
        if time_diff.total_seconds() < 60:
            return f"{int(time_diff.total_seconds())} seconds ago"
        elif time_diff.total_seconds() < 3600:
            return f"{int(time_diff.total_seconds() // 60)} minutes ago"
        else:
            return f"{int(time_diff.total_seconds() // 3600)} hours ago"
    time_since_last_activity_display.short_description = 'Last Activity'
    
    actions = ['end_selected_sessions', 'mark_as_violation']
    
    def end_selected_sessions(self, request, queryset):
        """
        End selected active sessions.
        """
        count = 0
        for session in queryset.filter(status='active'):
            session.end_session('admin_action')
            count += 1
        
        self.message_user(request, f'Successfully ended {count} sessions.')
    end_selected_sessions.short_description = 'End selected sessions'
    
    def mark_as_violation(self, request, queryset):
        """
        Mark selected sessions as security violations.
        """
        count = queryset.update(status='violation')
        self.message_user(request, f'Marked {count} sessions as violations.')
    mark_as_violation.short_description = 'Mark as security violation'