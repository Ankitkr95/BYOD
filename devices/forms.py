from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import Device, validate_mac_address
from security.validators import SecurityValidator, MacAddressValidator


class DeviceRegistrationForm(forms.ModelForm):
    """
    Form for registering a new device with validation.
    """
    
    target_user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-input',
        }),
        label='Register Device For',
        help_text='Admin: Select user to register device for'
    )
    
    class Meta:
        model = Device
        fields = ['name', 'device_type', 'mac_address', 'operating_system']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., John\'s MacBook Pro',
                'maxlength': 100,
            }),
            'device_type': forms.Select(attrs={
                'class': 'form-input',
            }),
            'mac_address': forms.TextInput(attrs={
                'class': 'form-input font-mono',
                'placeholder': 'XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX',
                'maxlength': 17,
            }),
            'operating_system': forms.Select(attrs={
                'class': 'form-input',
            }),
        }
        help_texts = {
            'name': 'Choose a descriptive name to easily identify this device',
            'mac_address': 'Enter your device\'s MAC address. You can find this in your network settings.',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Show target_user field only for admins
        if not self.user or not hasattr(self.user, 'profile') or self.user.profile.role != 'admin':
            self.fields.pop('target_user', None)
        else:
            # For admins, populate target_user choices
            self.fields['target_user'].queryset = User.objects.filter(
                profile__isnull=False
            ).select_related('profile').order_by('username')
        
        # Make all fields required except target_user
        for field_name, field in self.fields.items():
            if field_name != 'target_user':
                field.required = True
            
        # Add custom labels
        self.fields['name'].label = 'Device Name'
        self.fields['device_type'].label = 'Device Type'
        self.fields['mac_address'].label = 'MAC Address'
        self.fields['operating_system'].label = 'Operating System'
    
    def clean_name(self):
        """
        Validate device name for uniqueness per user and content.
        """
        name = self.cleaned_data.get('name', '').strip()
        
        # Use enhanced security validator
        name = SecurityValidator.validate_device_name(name, self.user)
        
        # Check for uniqueness per user (if user is available)
        if self.user:
            existing_device = Device.objects.filter(
                user=self.user, 
                name__iexact=name
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_device.exists():
                raise ValidationError(
                    f'You already have a device named "{name}". Please choose a different name.'
                )
        
        return name
    
    def clean_mac_address(self):
        """
        Validate MAC address format and uniqueness.
        """
        mac_address = self.cleaned_data.get('mac_address', '').strip()
        
        if not mac_address:
            raise ValidationError('MAC address is required.')
        
        # Use enhanced MAC address validator
        try:
            normalized_mac = MacAddressValidator.validate_and_normalize(mac_address)
        except ValidationError as e:
            raise ValidationError(str(e))
        
        # Check for uniqueness across all users
        existing_device = Device.objects.filter(
            mac_address=normalized_mac
        ).exclude(pk=self.instance.pk if self.instance else None)
        
        if existing_device.exists():
            raise ValidationError(
                'A device with this MAC address is already registered. '
                'Each device must have a unique MAC address.'
            )
        
        return normalized_mac
    
    def clean_device_type(self):
        """
        Validate device type selection.
        """
        device_type = self.cleaned_data.get('device_type')
        
        if not device_type:
            raise ValidationError('Please select a device type.')
        
        # Validate against allowed choices
        valid_choices = [choice[0] for choice in Device.DEVICE_TYPE_CHOICES if choice[0]]
        if device_type not in valid_choices:
            raise ValidationError('Please select a valid device type.')
        
        return device_type
    
    def clean_operating_system(self):
        """
        Validate operating system selection.
        """
        operating_system = self.cleaned_data.get('operating_system')
        
        if not operating_system:
            raise ValidationError('Please select an operating system.')
        
        # Validate against allowed choices
        valid_choices = [choice[0] for choice in Device.OS_CHOICES if choice[0]]
        if operating_system not in valid_choices:
            raise ValidationError('Please select a valid operating system.')
        
        return operating_system
    
    def clean(self):
        """
        Perform cross-field validation and role-based permissions.
        """
        cleaned_data = super().clean()
        device_type = cleaned_data.get('device_type')
        operating_system = cleaned_data.get('operating_system')
        target_user = cleaned_data.get('target_user')
        
        # Role-based validation
        if self.user and hasattr(self.user, 'profile'):
            user_role = self.user.profile.role
            
            # Teachers cannot register devices for students
            if user_role == 'teacher' and target_user:
                if hasattr(target_user, 'profile') and target_user.profile.role == 'student':
                    raise ValidationError(
                        "Teachers cannot register devices for students. "
                        "Students must register their own devices."
                    )
            
            # Students cannot register devices for others
            if user_role == 'student' and target_user and target_user != self.user:
                raise ValidationError(
                    "Students can only register devices for themselves."
                )
        
        # Validate OS compatibility with device type (basic validation)
        if device_type and operating_system:
            # Mobile devices shouldn't have desktop OS
            if device_type == 'smartphone' and operating_system in ['windows', 'macos', 'linux']:
                raise ValidationError(
                    'Smartphones typically don\'t run desktop operating systems. '
                    'Please verify your selections.'
                )
            
            # Desktop/laptop devices shouldn't have mobile OS
            if device_type in ['desktop', 'laptop'] and operating_system in ['ios', 'android']:
                raise ValidationError(
                    'Desktop and laptop computers typically don\'t run mobile operating systems. '
                    'Please verify your selections.'
                )
        
        return cleaned_data


class DeviceUpdateForm(forms.ModelForm):
    """
    Form for updating existing device information.
    """
    
    class Meta:
        model = Device
        fields = ['name', 'device_type', 'mac_address', 'operating_system']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., John\'s MacBook Pro',
                'maxlength': 100,
            }),
            'device_type': forms.Select(attrs={
                'class': 'form-input',
            }),
            'mac_address': forms.TextInput(attrs={
                'class': 'form-input font-mono',
                'placeholder': 'XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX',
                'maxlength': 17,
            }),
            'operating_system': forms.Select(attrs={
                'class': 'form-input',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make all fields required
        for field_name, field in self.fields.items():
            field.required = True
            
        # Add custom labels
        self.fields['name'].label = 'Device Name'
        self.fields['device_type'].label = 'Device Type'
        self.fields['mac_address'].label = 'MAC Address'
        self.fields['operating_system'].label = 'Operating System'
    
    def clean_name(self):
        """
        Validate device name for uniqueness per user and content.
        """
        name = self.cleaned_data.get('name', '').strip()
        
        # Use enhanced security validator
        name = SecurityValidator.validate_device_name(name, self.user)
        
        # Check for uniqueness per user (excluding current device)
        if self.user and self.instance:
            existing_device = Device.objects.filter(
                user=self.user, 
                name__iexact=name
            ).exclude(pk=self.instance.pk)
            
            if existing_device.exists():
                raise ValidationError(
                    f'You already have a device named "{name}". Please choose a different name.'
                )
        
        return name
    
    def clean_mac_address(self):
        """
        Validate MAC address format and uniqueness.
        """
        mac_address = self.cleaned_data.get('mac_address', '').strip()
        
        if not mac_address:
            raise ValidationError('MAC address is required.')
        
        # Use enhanced MAC address validator
        try:
            normalized_mac = MacAddressValidator.validate_and_normalize(mac_address)
        except ValidationError as e:
            raise ValidationError(str(e))
        
        # Check for uniqueness across all users (excluding current device)
        existing_device = Device.objects.filter(
            mac_address=normalized_mac
        ).exclude(pk=self.instance.pk if self.instance else None)
        
        if existing_device.exists():
            raise ValidationError(
                'A device with this MAC address is already registered. '
                'Each device must have a unique MAC address.'
            )
        
        return normalized_mac
    
    def clean_device_type(self):
        """
        Validate device type selection.
        """
        device_type = self.cleaned_data.get('device_type')
        
        if not device_type:
            raise ValidationError('Please select a device type.')
        
        # Validate against allowed choices
        valid_choices = [choice[0] for choice in Device.DEVICE_TYPE_CHOICES if choice[0]]
        if device_type not in valid_choices:
            raise ValidationError('Please select a valid device type.')
        
        return device_type
    
    def clean_operating_system(self):
        """
        Validate operating system selection.
        """
        operating_system = self.cleaned_data.get('operating_system')
        
        if not operating_system:
            raise ValidationError('Please select an operating system.')
        
        # Validate against allowed choices
        valid_choices = [choice[0] for choice in Device.OS_CHOICES if choice[0]]
        if operating_system not in valid_choices:
            raise ValidationError('Please select a valid operating system.')
        
        return operating_system
    
    def clean(self):
        """
        Perform cross-field validation.
        """
        cleaned_data = super().clean()
        device_type = cleaned_data.get('device_type')
        operating_system = cleaned_data.get('operating_system')
        
        # Validate OS compatibility with device type (basic validation)
        if device_type and operating_system:
            # Mobile devices shouldn't have desktop OS
            if device_type == 'smartphone' and operating_system in ['windows', 'macos', 'linux']:
                raise ValidationError(
                    'Smartphones typically don\'t run desktop operating systems. '
                    'Please verify your selections.'
                )
            
            # Desktop/laptop devices shouldn't have mobile OS
            if device_type in ['desktop', 'laptop'] and operating_system in ['ios', 'android']:
                raise ValidationError(
                    'Desktop and laptop computers typically don\'t run mobile operating systems. '
                    'Please verify your selections.'
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """
        Override save to handle MAC address changes.
        """
        device = super().save(commit=False)
        
        # If MAC address changed, reset compliance status for re-verification
        if self.instance and self.instance.pk:
            # Get the original MAC address from the database
            original_device = Device.objects.get(pk=self.instance.pk)
            if original_device.mac_address != device.mac_address:
                device.compliance_status = False
        
        if commit:
            device.save()
        
        return device


class DeviceFilterForm(forms.Form):
    """
    Form for filtering devices in the device list view.
    """
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Search by name, MAC address, type...',
        }),
        label='Search'
    )
    
    device_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + Device.DEVICE_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-input',
        }),
        label='Device Type'
    )
    
    operating_system = forms.ChoiceField(
        required=False,
        choices=[('', 'All OS')] + Device.OS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-input',
        }),
        label='Operating System'
    )
    
    compliance = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Status'),
            ('compliant', 'Compliant'),
            ('non_compliant', 'Non-Compliant'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-input',
        }),
        label='Compliance Status'
    )


class AccessRequestApprovalForm(forms.Form):
    """
    Form for approving device access requests.
    """
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'placeholder': 'Optional notes about the approval...',
            'rows': 3,
        }),
        label='Approval Notes',
        help_text='Optional notes about the approval'
    )


class AccessRequestRejectionForm(forms.Form):
    """
    Form for rejecting device access requests.
    """
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'placeholder': 'Please provide a reason for rejection...',
            'rows': 4,
        }),
        label='Rejection Reason',
        help_text='Please provide a reason for rejection'
    )
    
    def clean_reason(self):
        """
        Validate that reason is not empty.
        """
        reason = self.cleaned_data.get('reason', '').strip()
        if not reason:
            raise ValidationError('Rejection reason is required.')
        return reason
