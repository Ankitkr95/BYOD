from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import UserProfile
from security.validators import SecurityValidator, PasswordSecurityValidator


class CustomUserCreationForm(UserCreationForm):
    """
    Custom user registration form with role selection.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your email address'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your first name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your last name'
        })
    )
    role = forms.ChoiceField(
        choices=UserProfile.ROLE_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'role')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes to inherited fields
        self.fields['username'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Choose a username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Enter a secure password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Confirm your password'
        })
    
    def clean_username(self):
        """
        Validate username with enhanced security checks.
        """
        username = self.cleaned_data.get('username')
        return SecurityValidator.validate_username(username)
    
    def clean_email(self):
        """
        Validate email with enhanced security checks.
        """
        email = self.cleaned_data.get('email')
        return SecurityValidator.validate_email_address(email)
    
    def clean_first_name(self):
        """
        Sanitize first name input.
        """
        first_name = self.cleaned_data.get('first_name')
        return SecurityValidator.sanitize_text_input(first_name, max_length=30)
    
    def clean_last_name(self):
        """
        Sanitize last name input.
        """
        last_name = self.cleaned_data.get('last_name')
        return SecurityValidator.sanitize_text_input(last_name, max_length=30)
    
    def clean_role(self):
        """
        Validate role selection.
        """
        role = self.cleaned_data.get('role')
        valid_roles = [choice[0] for choice in UserProfile.ROLE_CHOICES]
        
        if role not in valid_roles:
            raise ValidationError('Please select a valid role.')
        
        return role
    
    def clean_password1(self):
        """
        Validate password strength.
        """
        password1 = self.cleaned_data.get('password1')
        if password1:
            # Get user data for context-aware validation
            username = self.cleaned_data.get('username')
            email = self.cleaned_data.get('email')
            first_name = self.cleaned_data.get('first_name')
            last_name = self.cleaned_data.get('last_name')
            
            # Create a temporary user object for validation
            temp_user = User(
                username=username or '',
                email=email or '',
                first_name=first_name or '',
                last_name=last_name or ''
            )
            
            PasswordSecurityValidator.validate_password_strength(password1, temp_user)
        
        return password1
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Update the user's profile with the selected role
            user.profile.role = self.cleaned_data['role']
            user.profile.save()
        
        return user


class UserProfileForm(forms.ModelForm):
    """
    Form for editing user profile information.
    """
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your first name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your last name'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your email address'
        })
    )
    
    class Meta:
        model = UserProfile
        fields = ('role',)
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'})
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
    
    def clean_first_name(self):
        """
        Sanitize first name input.
        """
        first_name = self.cleaned_data.get('first_name')
        return SecurityValidator.sanitize_text_input(first_name, max_length=30)
    
    def clean_last_name(self):
        """
        Sanitize last name input.
        """
        last_name = self.cleaned_data.get('last_name')
        return SecurityValidator.sanitize_text_input(last_name, max_length=30)
    
    def clean_email(self):
        """
        Validate email with enhanced security checks.
        """
        email = self.cleaned_data.get('email')
        validated_email = SecurityValidator.validate_email_address(email)
        
        # Check if email is already taken by another user
        if self.user:
            existing_user = User.objects.filter(email=validated_email).exclude(pk=self.user.pk)
            if existing_user.exists():
                raise ValidationError('A user with this email address already exists.')
        
        return validated_email
    
    def clean_role(self):
        """
        Validate role change permissions.
        """
        role = self.cleaned_data.get('role')
        
        if not role:
            raise ValidationError('Role selection is required.')
        
        # Check if user has permission to change role
        if self.user and hasattr(self.user, 'profile'):
            current_role = self.user.profile.role
            
            # Only admins can change roles, and students cannot become admins directly
            if current_role != 'admin' and role != current_role:
                raise ValidationError('You do not have permission to change your role.')
            
            # Prevent admins from demoting themselves (security measure)
            if current_role == 'admin' and role != 'admin':
                admin_count = UserProfile.objects.filter(role='admin').count()
                if admin_count <= 1:
                    raise ValidationError(
                        'Cannot change role. At least one administrator must remain in the system.'
                    )
        
        return role
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            
            if commit:
                self.user.save()
                profile.save()
        
        return profile