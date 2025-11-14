from django.contrib import admin
from .models import Device, DeviceAccessRequest, Notification


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    """
    Admin interface for Device model.
    """
    list_display = [
        'name', 
        'user', 
        'device_type', 
        'operating_system',
        'access_status',
        'compliance_status', 
        'registered_at',
        'last_seen'
    ]
    list_filter = [
        'device_type', 
        'operating_system',
        'access_status',
        'compliance_status', 
        'registered_at'
    ]
    search_fields = [
        'name', 
        'mac_address', 
        'user__username', 
        'user__first_name', 
        'user__last_name'
    ]
    readonly_fields = ['registered_at', 'updated_at']
    
    fieldsets = (
        ('Device Information', {
            'fields': ('name', 'device_type', 'mac_address', 'operating_system')
        }),
        ('Ownership & Status', {
            'fields': ('user', 'registered_by', 'access_status', 'compliance_status')
        }),
        ('Timestamps', {
            'fields': ('registered_at', 'last_seen', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """
        Optimize queryset with select_related for user information.
        """
        return super().get_queryset(request).select_related('user', 'registered_by')


@admin.register(DeviceAccessRequest)
class DeviceAccessRequestAdmin(admin.ModelAdmin):
    """
    Admin interface for DeviceAccessRequest model.
    """
    list_display = [
        'device',
        'requester',
        'status',
        'requested_at',
        'approved_by',
        'approved_at'
    ]
    list_filter = [
        'status',
        'requested_at',
        'approved_at'
    ]
    search_fields = [
        'device__name',
        'requester__username',
        'approved_by__username'
    ]
    readonly_fields = ['requested_at', 'approved_at']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('device', 'requester', 'status')
        }),
        ('Approval Details', {
            'fields': ('approved_by', 'approved_at', 'notes', 'rejection_reason')
        }),
        ('Timestamps', {
            'fields': ('requested_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """
        Optimize queryset with select_related.
        """
        return super().get_queryset(request).select_related(
            'device', 'requester', 'approved_by'
        )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Admin interface for Notification model.
    """
    list_display = [
        'recipient',
        'notification_type',
        'title',
        'is_read',
        'created_at'
    ]
    list_filter = [
        'notification_type',
        'is_read',
        'created_at'
    ]
    search_fields = [
        'recipient__username',
        'title',
        'message'
    ]
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('recipient', 'notification_type', 'title', 'message')
        }),
        ('Related Information', {
            'fields': ('related_request', 'is_read')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """
        Optimize queryset with select_related.
        """
        return super().get_queryset(request).select_related(
            'recipient', 'related_request'
        )