import json
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from devices.models import Device


class ActivityLog(models.Model):
    """
    Model for tracking user activity and device usage.
    Records user actions, duration, and resources accessed during sessions.
    """
    
    ACTIVITY_TYPE_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('web_browsing', 'Web Browsing'),
        ('application_usage', 'Application Usage'),
        ('file_access', 'File Access'),
        ('idle', 'Idle Time'),
        ('active', 'Active Usage'),
        ('other', 'Other'),
    ]
    
    # Relationships
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activity_logs',
        help_text="User who performed the activity"
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='activity_logs',
        help_text="Device used for the activity"
    )
    
    # Activity details
    activity_type = models.CharField(
        max_length=20,
        choices=ACTIVITY_TYPE_CHOICES,
        help_text="Type of activity performed"
    )
    duration = models.DurationField(
        help_text="Duration of the activity"
    )
    resources_accessed = models.TextField(
        blank=True,
        help_text="JSON formatted list of resources accessed (URLs, applications, files)"
    )
    
    # Metadata
    timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="When the activity occurred"
    )
    session_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Session identifier for grouping related activities"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address from which activity originated"
    )
    
    class Meta:
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['device', 'timestamp']),
            models.Index(fields=['activity_type', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"
    
    def clean(self):
        """
        Custom validation for ActivityLog model.
        """
        super().clean()
        
        # Validate that device belongs to the user
        if self.device and self.user and self.device.user != self.user:
            raise ValidationError({
                'device': 'Device must belong to the specified user.'
            })
        
        # Validate resources_accessed is valid JSON if provided
        if self.resources_accessed:
            try:
                json.loads(self.resources_accessed)
            except json.JSONDecodeError:
                raise ValidationError({
                    'resources_accessed': 'Resources accessed must be valid JSON format.'
                })
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure validation is run.
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def duration_minutes(self):
        """
        Return duration in minutes as a float.
        """
        return self.duration.total_seconds() / 60
    
    @property
    def duration_hours(self):
        """
        Return duration in hours as a float.
        """
        return self.duration.total_seconds() / 3600
    
    def get_resources_list(self):
        """
        Parse and return resources_accessed as a Python list.
        """
        if not self.resources_accessed:
            return []
        try:
            return json.loads(self.resources_accessed)
        except json.JSONDecodeError:
            return []
    
    def set_resources_list(self, resources_list):
        """
        Set resources_accessed from a Python list.
        """
        self.resources_accessed = json.dumps(resources_list)
    
    def is_productive_activity(self):
        """
        Determine if this activity type is considered productive.
        """
        productive_activities = ['web_browsing', 'application_usage', 'file_access', 'active']
        return self.activity_type in productive_activities


class PerformanceReport(models.Model):
    """
    Model for storing aggregated performance metrics and productivity reports.
    Generated periodically to track user productivity and engagement.
    """
    
    REPORT_TYPE_CHOICES = [
        ('daily', 'Daily Report'),
        ('weekly', 'Weekly Report'),
        ('monthly', 'Monthly Report'),
        ('custom', 'Custom Period Report'),
    ]
    
    # Relationships
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='performance_reports',
        help_text="User for whom the report is generated"
    )
    
    # Report metadata
    report_type = models.CharField(
        max_length=20,
        choices=REPORT_TYPE_CHOICES,
        default='daily',
        help_text="Type of performance report"
    )
    report_date = models.DateField(
        help_text="Date for which the report is generated"
    )
    start_date = models.DateField(
        help_text="Start date of the reporting period"
    )
    end_date = models.DateField(
        help_text="End date of the reporting period"
    )
    
    # Performance metrics
    productivity_score = models.FloatField(
        default=0.0,
        help_text="Calculated productivity score (0-100)"
    )
    attendance_percentage = models.FloatField(
        default=0.0,
        help_text="Attendance percentage for the period"
    )
    total_active_time = models.DurationField(
        default=timezone.timedelta(0),
        help_text="Total active time during the period"
    )
    total_idle_time = models.DurationField(
        default=timezone.timedelta(0),
        help_text="Total idle time during the period"
    )
    
    # Activity breakdown
    login_count = models.IntegerField(
        default=0,
        help_text="Number of login sessions"
    )
    devices_used = models.IntegerField(
        default=0,
        help_text="Number of different devices used"
    )
    
    # Additional metrics (stored as JSON)
    detailed_metrics = models.TextField(
        blank=True,
        help_text="JSON formatted detailed metrics and breakdowns"
    )
    
    # Timestamps
    generated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the report was generated"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last time the report was updated"
    )
    
    class Meta:
        verbose_name = 'Performance Report'
        verbose_name_plural = 'Performance Reports'
        ordering = ['-report_date', '-generated_at']
        unique_together = ['user', 'report_type', 'report_date']
        indexes = [
            models.Index(fields=['user', 'report_date']),
            models.Index(fields=['report_type', 'report_date']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_report_type_display()} ({self.report_date})"
    
    def clean(self):
        """
        Custom validation for PerformanceReport model.
        """
        super().clean()
        
        # Validate date range
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({
                'end_date': 'End date must be after start date.'
            })
        
        # Validate productivity score range
        if self.productivity_score < 0 or self.productivity_score > 100:
            raise ValidationError({
                'productivity_score': 'Productivity score must be between 0 and 100.'
            })
        
        # Validate attendance percentage range
        if self.attendance_percentage < 0 or self.attendance_percentage > 100:
            raise ValidationError({
                'attendance_percentage': 'Attendance percentage must be between 0 and 100.'
            })
        
        # Validate detailed_metrics is valid JSON if provided
        if self.detailed_metrics:
            try:
                json.loads(self.detailed_metrics)
            except json.JSONDecodeError:
                raise ValidationError({
                    'detailed_metrics': 'Detailed metrics must be valid JSON format.'
                })
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure validation is run.
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def total_time_hours(self):
        """
        Return total time (active + idle) in hours.
        """
        total_time = self.total_active_time + self.total_idle_time
        return total_time.total_seconds() / 3600
    
    @property
    def active_time_hours(self):
        """
        Return active time in hours.
        """
        return self.total_active_time.total_seconds() / 3600
    
    @property
    def idle_time_hours(self):
        """
        Return idle time in hours.
        """
        return self.total_idle_time.total_seconds() / 3600
    
    @property
    def activity_ratio(self):
        """
        Calculate ratio of active time to total time.
        """
        total_seconds = (self.total_active_time + self.total_idle_time).total_seconds()
        if total_seconds == 0:
            return 0.0
        return (self.total_active_time.total_seconds() / total_seconds) * 100
    
    def get_detailed_metrics(self):
        """
        Parse and return detailed_metrics as a Python dictionary.
        """
        if not self.detailed_metrics:
            return {}
        try:
            return json.loads(self.detailed_metrics)
        except json.JSONDecodeError:
            return {}
    
    def set_detailed_metrics(self, metrics_dict):
        """
        Set detailed_metrics from a Python dictionary.
        """
        self.detailed_metrics = json.dumps(metrics_dict)
    
    def calculate_productivity_score(self):
        """
        Calculate productivity score based on activity patterns.
        This is a basic implementation that can be enhanced with more sophisticated algorithms.
        """
        if self.total_time_hours == 0:
            return 0.0
        
        # Base score from activity ratio (40% weight)
        activity_score = self.activity_ratio * 0.4
        
        # Attendance bonus (30% weight)
        attendance_score = self.attendance_percentage * 0.3
        
        # Login frequency score (20% weight) - optimal range is 2-5 logins per day
        login_score = 0
        if self.login_count >= 2:
            login_score = min(20, self.login_count * 4)  # Cap at 20 points
        
        # Device usage consistency (10% weight) - using 1-2 devices is optimal
        device_score = 0
        if self.devices_used == 1:
            device_score = 10
        elif self.devices_used == 2:
            device_score = 8
        elif self.devices_used > 2:
            device_score = max(0, 10 - (self.devices_used - 2) * 2)
        
        total_score = activity_score + attendance_score + login_score + device_score
        return min(100.0, max(0.0, total_score))  # Ensure score is between 0-100
