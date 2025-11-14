import json
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from devices.models import Device


def validate_json_list(value):
    """
    Validate that the value is a valid JSON list.
    """
    if not value:
        return []
    
    try:
        data = json.loads(value) if isinstance(value, str) else value
        if not isinstance(data, list):
            raise ValidationError('Value must be a JSON list.')
        return data
    except (json.JSONDecodeError, TypeError):
        raise ValidationError('Invalid JSON format.')


def validate_time_restrictions(value):
    """
    Validate time restrictions JSON format.
    Expected format: {"start_time": "09:00", "end_time": "17:00", "days": ["monday", "tuesday", ...]}
    """
    if not value:
        return {}
    
    try:
        data = json.loads(value) if isinstance(value, str) else value
        if not isinstance(data, dict):
            raise ValidationError('Time restrictions must be a JSON object.')
        
        # Validate required fields if present
        if 'start_time' in data or 'end_time' in data:
            if not all(key in data for key in ['start_time', 'end_time']):
                raise ValidationError('Both start_time and end_time must be provided.')
        
        return data
    except (json.JSONDecodeError, TypeError):
        raise ValidationError('Invalid JSON format for time restrictions.')


class AccessControl(models.Model):
    """
    Model for managing role-based access control rules.
    Defines what domains and resources different user roles can access.
    """
    
    ROLE_CHOICES = [
        ('teacher', 'Teacher'),
        ('student', 'Student'),
        ('admin', 'Administrator'),
    ]
    
    # Role this access control applies to
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        help_text="User role this access control applies to"
    )
    
    # Domain access control (stored as JSON lists)
    allowed_domains = models.TextField(
        blank=True,
        default='[]',
        help_text="JSON list of allowed domains for this role"
    )
    blocked_domains = models.TextField(
        blank=True,
        default='[]',
        help_text="JSON list of blocked domains for this role"
    )
    
    # Time-based restrictions (stored as JSON object)
    time_restrictions = models.TextField(
        blank=True,
        default='{}',
        help_text="JSON object with time-based access restrictions"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_access_rules',
        help_text="Administrator who created this rule"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this access control rule is active"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this rule was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this rule was last updated"
    )
    
    class Meta:
        verbose_name = 'Access Control Rule'
        verbose_name_plural = 'Access Control Rules'
        ordering = ['-created_at']
        unique_together = ['role']  # One active rule per role
    
    def __str__(self):
        return f"Access Control for {self.get_role_display()}"
    
    def clean(self):
        """
        Custom validation for AccessControl model.
        """
        super().clean()
        
        # Validate JSON fields
        try:
            validate_json_list(self.allowed_domains)
        except ValidationError as e:
            raise ValidationError({'allowed_domains': f'Invalid allowed domains: {e}'})
        
        try:
            validate_json_list(self.blocked_domains)
        except ValidationError as e:
            raise ValidationError({'blocked_domains': f'Invalid blocked domains: {e}'})
        
        try:
            validate_time_restrictions(self.time_restrictions)
        except ValidationError as e:
            raise ValidationError({'time_restrictions': f'Invalid time restrictions: {e}'})
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure validation and handle unique constraint.
        """
        self.full_clean()
        
        # If this is an active rule, deactivate other rules for the same role
        if self.is_active:
            AccessControl.objects.filter(role=self.role, is_active=True).exclude(pk=self.pk).update(is_active=False)
        
        super().save(*args, **kwargs)
    
    def get_allowed_domains(self):
        """
        Return allowed domains as a Python list.
        """
        try:
            return json.loads(self.allowed_domains) if self.allowed_domains else []
        except json.JSONDecodeError:
            return []
    
    def set_allowed_domains(self, domains_list):
        """
        Set allowed domains from a Python list.
        """
        self.allowed_domains = json.dumps(domains_list)
    
    def get_blocked_domains(self):
        """
        Return blocked domains as a Python list.
        """
        try:
            return json.loads(self.blocked_domains) if self.blocked_domains else []
        except json.JSONDecodeError:
            return []
    
    def set_blocked_domains(self, domains_list):
        """
        Set blocked domains from a Python list.
        """
        self.blocked_domains = json.dumps(domains_list)
    
    def get_time_restrictions(self):
        """
        Return time restrictions as a Python dict.
        """
        try:
            return json.loads(self.time_restrictions) if self.time_restrictions else {}
        except json.JSONDecodeError:
            return {}
    
    def set_time_restrictions(self, restrictions_dict):
        """
        Set time restrictions from a Python dict.
        """
        self.time_restrictions = json.dumps(restrictions_dict)
    
    def is_domain_allowed(self, domain):
        """
        Check if a domain is allowed for this role.
        """
        allowed = self.get_allowed_domains()
        blocked = self.get_blocked_domains()
        
        # If domain is explicitly blocked, deny access
        if domain in blocked:
            return False
        
        # If no allowed domains specified, allow all (except blocked)
        if not allowed:
            return True
        
        # Check if domain is in allowed list
        return domain in allowed
    
    def is_time_allowed(self, current_time=None):
        """
        Check if current time is within allowed time restrictions.
        """
        if current_time is None:
            current_time = timezone.now()
        
        restrictions = self.get_time_restrictions()
        if not restrictions:
            return True
        
        # Check day restrictions
        if 'days' in restrictions:
            current_day = current_time.strftime('%A').lower()
            if current_day not in [day.lower() for day in restrictions['days']]:
                return False
        
        # Check time restrictions
        if 'start_time' in restrictions and 'end_time' in restrictions:
            current_time_str = current_time.strftime('%H:%M')
            if not (restrictions['start_time'] <= current_time_str <= restrictions['end_time']):
                return False
        
        return True


class SessionTracker(models.Model):
    """
    Model for tracking user sessions and monitoring network activity.
    Provides real-time session monitoring and security event logging.
    """
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
        ('violation', 'Security Violation'),
    ]
    
    # Session identification
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='session_tracks',
        help_text="User associated with this session"
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='session_tracks',
        help_text="Device used for this session"
    )
    session_key = models.CharField(
        max_length=40,
        unique=True,
        help_text="Django session key"
    )
    
    # Session timing
    login_time = models.DateTimeField(
        auto_now_add=True,
        help_text="When the session started"
    )
    logout_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the session ended"
    )
    last_activity = models.DateTimeField(
        default=timezone.now,
        help_text="Last recorded activity in this session"
    )
    
    # Network information
    ip_address = models.GenericIPAddressField(
        help_text="IP address of the session"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="Browser user agent string"
    )
    
    # Session status and metadata
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Current status of the session"
    )
    violation_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of security violations in this session"
    )
    violation_details = models.TextField(
        blank=True,
        help_text="JSON string containing violation details"
    )
    
    class Meta:
        verbose_name = 'Session Tracker'
        verbose_name_plural = 'Session Trackers'
        ordering = ['-login_time']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['device', 'status']),
            models.Index(fields=['session_key']),
            models.Index(fields=['login_time']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.device.name} ({self.status})"
    
    def clean(self):
        """
        Custom validation for SessionTracker model.
        """
        super().clean()
        
        # Validate that logout_time is after login_time if both are set
        if self.logout_time and self.login_time and self.logout_time < self.login_time:
            raise ValidationError({'logout_time': 'Logout time cannot be before login time.'})
        
        # Validate violation_details is valid JSON if provided
        if self.violation_details:
            try:
                json.loads(self.violation_details)
            except json.JSONDecodeError:
                raise ValidationError({'violation_details': 'Violation details must be valid JSON.'})
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure validation.
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def duration(self):
        """
        Calculate session duration.
        """
        end_time = self.logout_time or timezone.now()
        return end_time - self.login_time
    
    @property
    def is_active(self):
        """
        Check if session is currently active.
        """
        return self.status == 'active' and self.logout_time is None
    
    @property
    def time_since_last_activity(self):
        """
        Calculate time since last activity.
        """
        return timezone.now() - self.last_activity
    
    def update_activity(self):
        """
        Update last activity timestamp.
        """
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
    
    def end_session(self, reason='logout'):
        """
        End the session with specified reason.
        """
        self.logout_time = timezone.now()
        if reason == 'violation':
            self.status = 'violation'
        elif reason == 'timeout':
            self.status = 'expired'
        else:
            self.status = 'inactive'
        
        self.save(update_fields=['logout_time', 'status'])
    
    def add_violation(self, violation_type, details=None):
        """
        Record a security violation for this session.
        """
        self.violation_count += 1
        
        # Update violation details
        try:
            current_violations = json.loads(self.violation_details) if self.violation_details else []
        except json.JSONDecodeError:
            current_violations = []
        
        violation_record = {
            'type': violation_type,
            'timestamp': timezone.now().isoformat(),
            'details': details or {}
        }
        current_violations.append(violation_record)
        
        self.violation_details = json.dumps(current_violations)
        self.save(update_fields=['violation_count', 'violation_details'])
    
    def get_violations(self):
        """
        Return violations as a Python list.
        """
        try:
            return json.loads(self.violation_details) if self.violation_details else []
        except json.JSONDecodeError:
            return []
    
    def is_session_expired(self, timeout_minutes=30):
        """
        Check if session has expired based on inactivity.
        """
        if self.status != 'active':
            return True
        
        inactive_duration = self.time_since_last_activity
        return inactive_duration.total_seconds() > (timeout_minutes * 60)
    
    @classmethod
    def get_active_sessions(cls):
        """
        Get all currently active sessions.
        """
        return cls.objects.filter(status='active', logout_time__isnull=True)
    
    @classmethod
    def get_user_active_sessions(cls, user):
        """
        Get active sessions for a specific user.
        """
        return cls.get_active_sessions().filter(user=user)
    
    @classmethod
    def cleanup_expired_sessions(cls, timeout_minutes=30):
        """
        Mark expired sessions as expired.
        """
        cutoff_time = timezone.now() - timezone.timedelta(minutes=timeout_minutes)
        expired_sessions = cls.objects.filter(
            status='active',
            last_activity__lt=cutoff_time,
            logout_time__isnull=True
        )
        
        for session in expired_sessions:
            session.end_session('timeout')
        
        return expired_sessions.count()