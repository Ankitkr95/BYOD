import json
from django import forms
from django.core.exceptions import ValidationError
from .models import AccessControl, SessionTracker, validate_json_list, validate_time_restrictions
from .validators import SecurityValidator


class AccessControlForm(forms.ModelForm):
    """
    Form for creating and editing access control rules.
    """
    
    # Custom fields for better user experience
    allowed_domains_list = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Enter allowed domains, one per line\nExample:\nexample.com\ngoogle.com\neducation.gov'
        }),
        required=False,
        help_text="Enter allowed domains, one per line. Leave empty to allow all domains (except blocked ones)."
    )
    
    blocked_domains_list = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Enter blocked domains, one per line\nExample:\nfacebook.com\ntwitter.com\ngaming-site.com'
        }),
        required=False,
        help_text="Enter blocked domains, one per line. These will be blocked regardless of allowed domains."
    )
    
    # Time restriction fields
    enable_time_restrictions = forms.BooleanField(
        required=False,
        help_text="Enable time-based access restrictions"
    )
    
    start_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time'}),
        help_text="Start time for allowed access"
    )
    
    end_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time'}),
        help_text="End time for allowed access"
    )
    
    allowed_days = forms.MultipleChoiceField(
        choices=[
            ('monday', 'Monday'),
            ('tuesday', 'Tuesday'),
            ('wednesday', 'Wednesday'),
            ('thursday', 'Thursday'),
            ('friday', 'Friday'),
            ('saturday', 'Saturday'),
            ('sunday', 'Sunday'),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select days when access is allowed"
    )
    
    class Meta:
        model = AccessControl
        fields = ['role', 'is_active']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing existing instance, populate custom fields
        if self.instance and self.instance.pk:
            # Populate domain lists
            allowed_domains = self.instance.get_allowed_domains()
            if allowed_domains:
                self.fields['allowed_domains_list'].initial = '\n'.join(allowed_domains)
            
            blocked_domains = self.instance.get_blocked_domains()
            if blocked_domains:
                self.fields['blocked_domains_list'].initial = '\n'.join(blocked_domains)
            
            # Populate time restrictions
            time_restrictions = self.instance.get_time_restrictions()
            if time_restrictions:
                self.fields['enable_time_restrictions'].initial = True
                
                if 'start_time' in time_restrictions:
                    self.fields['start_time'].initial = time_restrictions['start_time']
                
                if 'end_time' in time_restrictions:
                    self.fields['end_time'].initial = time_restrictions['end_time']
                
                if 'days' in time_restrictions:
                    self.fields['allowed_days'].initial = [day.lower() for day in time_restrictions['days']]
    
    def clean_allowed_domains_list(self):
        """
        Clean and validate allowed domains list.
        """
        domains_text = self.cleaned_data.get('allowed_domains_list', '')
        if not domains_text.strip():
            return []
        
        # Sanitize input
        domains_text = SecurityValidator.sanitize_text_input(domains_text, max_length=5000)
        domains = [domain.strip() for domain in domains_text.split('\n') if domain.strip()]
        
        # Enhanced domain validation
        validated_domains = []
        for domain in domains:
            # Sanitize each domain
            domain = SecurityValidator.sanitize_text_input(domain, max_length=253)
            
            # Validate domain format
            if not self._is_valid_domain(domain):
                raise ValidationError(f'Invalid domain format: {domain}')
            
            # Check for suspicious patterns
            if self._is_suspicious_domain(domain):
                raise ValidationError(f'Suspicious domain detected: {domain}')
            
            validated_domains.append(domain.lower())
        
        return validated_domains
    
    def clean_blocked_domains_list(self):
        """
        Clean and validate blocked domains list.
        """
        domains_text = self.cleaned_data.get('blocked_domains_list', '')
        if not domains_text.strip():
            return []
        
        # Sanitize input
        domains_text = SecurityValidator.sanitize_text_input(domains_text, max_length=5000)
        domains = [domain.strip() for domain in domains_text.split('\n') if domain.strip()]
        
        # Enhanced domain validation
        validated_domains = []
        for domain in domains:
            # Sanitize each domain
            domain = SecurityValidator.sanitize_text_input(domain, max_length=253)
            
            # Validate domain format
            if not self._is_valid_domain(domain):
                raise ValidationError(f'Invalid domain format: {domain}')
            
            validated_domains.append(domain.lower())
        
        return validated_domains
    
    def clean(self):
        """
        Perform cross-field validation.
        """
        cleaned_data = super().clean()
        
        # Validate time restrictions
        enable_time = cleaned_data.get('enable_time_restrictions')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if enable_time:
            if not start_time or not end_time:
                raise ValidationError('Both start time and end time are required when time restrictions are enabled.')
            
            if start_time >= end_time:
                raise ValidationError('Start time must be before end time.')
        
        # Check for domain conflicts
        allowed_domains = cleaned_data.get('allowed_domains_list', [])
        blocked_domains = cleaned_data.get('blocked_domains_list', [])
        
        if allowed_domains and blocked_domains:
            conflicts = set(allowed_domains) & set(blocked_domains)
            if conflicts:
                raise ValidationError(f'Domains cannot be both allowed and blocked: {", ".join(conflicts)}')
        
        return cleaned_data
    
    def save(self, commit=True):
        """
        Save the form data to the model instance.
        """
        instance = super().save(commit=False)
        
        # Convert domain lists to JSON
        allowed_domains = self.cleaned_data.get('allowed_domains_list', [])
        blocked_domains = self.cleaned_data.get('blocked_domains_list', [])
        
        instance.set_allowed_domains(allowed_domains)
        instance.set_blocked_domains(blocked_domains)
        
        # Handle time restrictions
        time_restrictions = {}
        if self.cleaned_data.get('enable_time_restrictions'):
            start_time = self.cleaned_data.get('start_time')
            end_time = self.cleaned_data.get('end_time')
            allowed_days = self.cleaned_data.get('allowed_days', [])
            
            if start_time and end_time:
                time_restrictions['start_time'] = start_time.strftime('%H:%M')
                time_restrictions['end_time'] = end_time.strftime('%H:%M')
            
            if allowed_days:
                time_restrictions['days'] = allowed_days
        
        instance.set_time_restrictions(time_restrictions)
        
        if commit:
            instance.save()
        
        return instance
    
    def _is_valid_domain(self, domain):
        """
        Enhanced domain validation.
        """
        import re
        
        # Basic domain pattern (simplified)
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        
        if not re.match(domain_pattern, domain):
            return False
        
        # Check length
        if len(domain) > 253:
            return False
        
        # Check for valid TLD
        parts = domain.split('.')
        if len(parts) < 2:
            return False
        
        # Check for consecutive dots or hyphens
        if '..' in domain or '--' in domain:
            return False
        
        # Check for domains starting or ending with hyphen
        if domain.startswith('-') or domain.endswith('-'):
            return False
        
        return True
    
    def _is_suspicious_domain(self, domain):
        """
        Check for suspicious domain patterns.
        """
        import re
        
        # Suspicious patterns
        suspicious_patterns = [
            r'(admin|root|system|test)',  # Administrative terms
            r'(hack|crack|exploit|malware)',  # Malicious terms
            r'(phish|scam|fraud)',  # Phishing terms
            r'^\d+\.\d+\.\d+\.\d+$',  # IP addresses
            r'(localhost|127\.0\.0\.1)',  # Local addresses
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, domain, re.IGNORECASE):
                return True
        
        # Check for suspicious TLDs (basic list)
        suspicious_tlds = ['.tk', '.ml', '.ga', '.cf', '.bit']
        for tld in suspicious_tlds:
            if domain.endswith(tld):
                return True
        
        return False


class SessionFilterForm(forms.Form):
    """
    Form for filtering session data.
    """
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + list(SessionTracker.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    user = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by username',
            'class': 'form-control'
        })
    )
    
    device = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by device name',
            'class': 'form-control'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    
    def clean_user(self):
        """
        Sanitize user search input.
        """
        user = self.cleaned_data.get('user')
        if user:
            return SecurityValidator.sanitize_text_input(user, max_length=150)
        return user
    
    def clean_device(self):
        """
        Sanitize device search input.
        """
        device = self.cleaned_data.get('device')
        if device:
            return SecurityValidator.sanitize_text_input(device, max_length=100)
        return device
    
    def clean(self):
        """
        Validate date range and other cross-field validation.
        """
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError('Start date must be before or equal to end date.')
        
        # Validate date range is not too large (performance consideration)
        if date_from and date_to:
            date_diff = (date_to - date_from).days
            if date_diff > 365:
                raise ValidationError('Date range cannot exceed 365 days.')
        
        return cleaned_data


class SecurityAlertFilterForm(forms.Form):
    """
    Form for filtering security alerts.
    """
    severity = forms.ChoiceField(
        choices=[
            ('', 'All Severities'),
            ('high', 'High (5+ violations)'),
            ('medium', 'Medium (2-4 violations)'),
            ('low', 'Low (1 violation)'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date = forms.ChoiceField(
        choices=[
            ('', 'All Time'),
            ('today', 'Today'),
            ('week', 'Last 7 Days'),
            ('month', 'Last 30 Days'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )