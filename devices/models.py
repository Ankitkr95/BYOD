import re
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone


def validate_mac_address(value):
    """
    Validate MAC address format (XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX).
    """
    # Remove any whitespace
    value = value.strip()
    
    # Check for valid MAC address patterns
    mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
    
    if not re.match(mac_pattern, value):
        raise ValidationError(
            'MAC address must be in format XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX'
        )
    
    return value.upper().replace('-', ':')


class Device(models.Model):
    """
    Model for managing user devices in BYOD environment.
    Tracks device information, compliance status, and user relationships.
    """
    
    DEVICE_TYPE_CHOICES = [
        ('laptop', 'Laptop'),
        ('tablet', 'Tablet'),
        ('smartphone', 'Smartphone'),
        ('desktop', 'Desktop'),
        ('other', 'Other'),
    ]
    
    OS_CHOICES = [
        ('windows', 'Windows'),
        ('macos', 'macOS'),
        ('linux', 'Linux'),
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('other', 'Other'),
    ]
    
    # Basic device information
    name = models.CharField(
        max_length=100,
        help_text="Device name (e.g., 'John's MacBook Pro')"
    )
    device_type = models.CharField(
        max_length=20,
        choices=DEVICE_TYPE_CHOICES,
        help_text="Type of device"
    )
    mac_address = models.CharField(
        max_length=17,
        unique=True,
        validators=[validate_mac_address],
        help_text="MAC address in format XX:XX:XX:XX:XX:XX"
    )
    operating_system = models.CharField(
        max_length=20,
        choices=OS_CHOICES,
        help_text="Operating system of the device"
    )
    
    # Compliance and status tracking
    compliance_status = models.BooleanField(
        default=False,
        help_text="Whether device meets security requirements"
    )
    
    # Access status tracking
    ACCESS_STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]
    access_status = models.CharField(
        max_length=20,
        choices=ACCESS_STATUS_CHOICES,
        default='pending',
        help_text="Current access status of the device"
    )
    
    # Relationships
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='devices',
        help_text="Owner of the device"
    )
    registered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='registered_devices',
        help_text="User who registered this device"
    )
    
    # Timestamps
    registered_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the device was first registered"
    )
    last_seen = models.DateTimeField(
        default=timezone.now,
        help_text="Last time device was active on network"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last time device information was updated"
    )
    
    class Meta:
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'
        ordering = ['-registered_at']
        unique_together = ['user', 'name']  # User can't have duplicate device names
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"
    
    def clean(self):
        """
        Custom validation for the Device model.
        """
        super().clean()
        
        # Normalize MAC address format
        if self.mac_address:
            self.mac_address = validate_mac_address(self.mac_address)
        
        # Validate device name is not empty after stripping
        if self.name and not self.name.strip():
            raise ValidationError({'name': 'Device name cannot be empty or just whitespace.'})
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure validation is run.
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_compliant(self):
        """
        Check if device is compliant with security requirements.
        """
        return self.compliance_status
    
    @property
    def days_since_registration(self):
        """
        Calculate days since device was registered.
        """
        return (timezone.now() - self.registered_at).days
    
    @property
    def days_since_last_seen(self):
        """
        Calculate days since device was last seen.
        """
        return (timezone.now() - self.last_seen).days
    
    def update_last_seen(self):
        """
        Update the last_seen timestamp to current time.
        """
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])
    
    def set_compliance_status(self, status, save=True):
        """
        Update compliance status with optional save.
        """
        self.compliance_status = status
        if save:
            self.save(update_fields=['compliance_status'])
    
    def get_device_info(self):
        """
        Return formatted device information string.
        """
        return f"{self.get_device_type_display()} - {self.get_operating_system_display()}"
    
    def grant_access(self):
        """
        Change device status to 'active'.
        """
        self.access_status = 'active'
        self.save(update_fields=['access_status'])
    
    def revoke_access(self):
        """
        Change device status to 'suspended'.
        """
        self.access_status = 'suspended'
        self.save(update_fields=['access_status'])
    
    def requires_approval(self):
        """
        Check if device needs approval based on registration context.
        """
        return self.access_status == 'pending'


class DeviceAccessRequest(models.Model):
    """
    Model for tracking device access requests and their approval status.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='access_requests',
        help_text="The device requesting access"
    )
    requester = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='device_access_requests',
        help_text="User who registered the device"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current status of the access request"
    )
    requested_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the access request was created"
    )
    
    # Approval tracking
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_requests',
        help_text="User who approved or rejected the request"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the request was approved or rejected"
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection if applicable"
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the request"
    )
    
    class Meta:
        verbose_name = 'Device Access Request'
        verbose_name_plural = 'Device Access Requests'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status', 'requested_at']),
            models.Index(fields=['requester', 'status']),
            models.Index(fields=['device']),
        ]
    
    def __str__(self):
        return f"Access Request for {self.device.name} by {self.requester.username}"
    
    def approve(self, approver, notes=''):
        """
        Approve the request and grant device access.
        """
        from django.core.exceptions import PermissionDenied
        
        if not self.can_be_approved_by(approver):
            raise PermissionDenied("You cannot approve this request")
        
        if self.status != 'pending':
            raise ValidationError("This request has already been processed")
        
        self.status = 'approved'
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.notes = notes
        self.save()
        
        # Grant access to the device
        self.device.grant_access()
    
    def reject(self, approver, reason=''):
        """
        Reject the request.
        """
        from django.core.exceptions import PermissionDenied
        
        if not self.can_be_approved_by(approver):
            raise PermissionDenied("You cannot reject this request")
        
        if self.status != 'pending':
            raise ValidationError("This request has already been processed")
        
        self.status = 'rejected'
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.rejection_reason = reason
        self.save()
        
        # Update device status
        self.device.access_status = 'rejected'
        self.device.save(update_fields=['access_status'])
    
    def can_be_approved_by(self, user):
        """
        Check if user has permission to approve this request.
        """
        if not hasattr(user, 'profile'):
            return False
        
        # User cannot approve their own request
        if user == self.requester:
            return False
        
        requester_role = self.requester.profile.role
        approver_role = user.profile.role
        
        # Admin can approve all requests
        if approver_role == 'admin':
            return True
        
        # Teacher can approve student requests only
        if approver_role == 'teacher' and requester_role == 'student':
            return True
        
        return False
    
    def get_eligible_approvers(self):
        """
        Return queryset of users who can approve this request.
        """
        from users.models import UserProfile
        
        requester_role = self.requester.profile.role
        
        if requester_role == 'student':
            # Students' requests can be approved by teachers and admins
            return User.objects.filter(
                profile__role__in=['teacher', 'admin']
            )
        elif requester_role == 'teacher':
            # Teachers' requests can only be approved by admins
            return User.objects.filter(profile__role='admin')
        
        return User.objects.none()


class Notification(models.Model):
    """
    Model for storing and managing user notifications.
    """
    NOTIFICATION_TYPES = [
        ('access_request', 'Device Access Request'),
        ('request_approved', 'Request Approved'),
        ('request_rejected', 'Request Rejected'),
    ]
    
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="User who receives this notification"
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        help_text="Type of notification"
    )
    title = models.CharField(
        max_length=200,
        help_text="Notification title"
    )
    message = models.TextField(
        help_text="Notification message content"
    )
    related_request = models.ForeignKey(
        DeviceAccessRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text="Related access request if applicable"
    )
    
    is_read = models.BooleanField(
        default=False,
        help_text="Whether the notification has been read"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the notification was created"
    )
    
    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', 'created_at']),
            models.Index(fields=['related_request']),
        ]
    
    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"
    
    def mark_as_read(self):
        """
        Mark notification as read.
        """
        self.is_read = True
        self.save(update_fields=['is_read'])
    
    @classmethod
    def get_unread_count(cls, user):
        """
        Get count of unread notifications for user.
        """
        return cls.objects.filter(recipient=user, is_read=False).count()
