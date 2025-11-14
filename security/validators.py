"""
Custom validators for enhanced security and data validation.

This module provides comprehensive validation utilities for the BYOD Security System,
including input sanitization, role-based validation, and security checks.
"""

import re
import html
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.models import User
from django.utils.html import strip_tags


class SecurityValidator:
    """
    Comprehensive security validator for form inputs and data sanitization.
    """
    
    # Allowed HTML tags for rich text fields (if any)
    ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li']
    ALLOWED_ATTRIBUTES = {}
    
    # Common malicious patterns
    MALICIOUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',               # JavaScript protocol
        r'on\w+\s*=',                # Event handlers
        r'data:text/html',           # Data URLs with HTML
        r'vbscript:',                # VBScript protocol
        r'expression\s*\(',          # CSS expressions
        r'@import',                  # CSS imports
        r'<iframe[^>]*>',            # Iframe tags
        r'<object[^>]*>',            # Object tags
        r'<embed[^>]*>',             # Embed tags
    ]
    
    @classmethod
    def sanitize_text_input(cls, value, max_length=None, allow_html=False):
        """
        Sanitize text input to prevent XSS and other attacks.
        
        Args:
            value (str): Input value to sanitize
            max_length (int): Maximum allowed length
            allow_html (bool): Whether to allow safe HTML tags
            
        Returns:
            str: Sanitized value
            
        Raises:
            ValidationError: If input contains malicious content
        """
        if not isinstance(value, str):
            value = str(value)
        
        # Remove null bytes and control characters
        value = value.replace('\x00', '').replace('\r', '')
        
        # Check for malicious patterns
        for pattern in cls.MALICIOUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValidationError(
                    'Input contains potentially malicious content and cannot be processed.'
                )
        
        # Handle HTML content
        if allow_html:
            # For now, just strip all HTML tags even if allow_html is True
            # In production, you might want to install bleach for proper HTML sanitization
            value = strip_tags(value)
            # HTML escape remaining content
            value = html.escape(value)
        else:
            # Strip all HTML tags
            value = strip_tags(value)
            # HTML escape remaining content
            value = html.escape(value)
        
        # Trim whitespace
        value = value.strip()
        
        # Check length
        if max_length and len(value) > max_length:
            raise ValidationError(
                f'Input is too long. Maximum {max_length} characters allowed.'
            )
        
        return value
    
    @classmethod
    def validate_username(cls, username):
        """
        Validate username with security considerations.
        
        Args:
            username (str): Username to validate
            
        Returns:
            str: Cleaned username
            
        Raises:
            ValidationError: If username is invalid
        """
        if not username:
            raise ValidationError('Username is required.')
        
        # Sanitize input
        username = cls.sanitize_text_input(username, max_length=150)
        
        # Check minimum length
        if len(username) < 3:
            raise ValidationError('Username must be at least 3 characters long.')
        
        # Check for valid characters (alphanumeric, underscore, hyphen, dot)
        if not re.match(r'^[a-zA-Z0-9._-]+$', username):
            raise ValidationError(
                'Username can only contain letters, numbers, dots, hyphens, and underscores.'
            )
        
        # Check for reserved usernames
        reserved_usernames = [
            'admin', 'administrator', 'root', 'system', 'test', 'guest',
            'user', 'null', 'undefined', 'api', 'www', 'mail', 'ftp'
        ]
        if username.lower() in reserved_usernames:
            raise ValidationError('This username is reserved and cannot be used.')
        
        # Check for existing username (case-insensitive)
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('A user with this username already exists.')
        
        return username
    
    @classmethod
    def validate_email_address(cls, email):
        """
        Validate email address with additional security checks.
        
        Args:
            email (str): Email address to validate
            
        Returns:
            str: Cleaned email address
            
        Raises:
            ValidationError: If email is invalid
        """
        if not email:
            raise ValidationError('Email address is required.')
        
        # Sanitize input
        email = cls.sanitize_text_input(email, max_length=254).lower()
        
        # Use Django's built-in email validator
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError('Please enter a valid email address.')
        
        # Additional checks for suspicious patterns
        suspicious_patterns = [
            r'\.{2,}',           # Multiple consecutive dots
            r'^\.|\.$',          # Starting or ending with dot
            r'@.*@',             # Multiple @ symbols
            r'[<>"\']',          # Suspicious characters
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, email):
                raise ValidationError('Email address contains invalid characters.')
        
        # Check for disposable email domains (basic list)
        disposable_domains = [
            '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
            'mailinator.com', 'throwaway.email', 'temp-mail.org'
        ]
        
        domain = email.split('@')[1] if '@' in email else ''
        if domain.lower() in disposable_domains:
            raise ValidationError(
                'Disposable email addresses are not allowed. Please use a permanent email address.'
            )
        
        return email
    
    @classmethod
    def validate_device_name(cls, name, user=None):
        """
        Validate device name with security considerations.
        
        Args:
            name (str): Device name to validate
            user (User): User object for uniqueness check
            
        Returns:
            str: Cleaned device name
            
        Raises:
            ValidationError: If device name is invalid
        """
        if not name:
            raise ValidationError('Device name is required.')
        
        # Sanitize input
        name = cls.sanitize_text_input(name, max_length=100)
        
        # Check minimum length
        if len(name) < 2:
            raise ValidationError('Device name must be at least 2 characters long.')
        
        # Check for valid characters (allow more flexibility for device names)
        if not re.match(r'^[a-zA-Z0-9\s._-]+$', name):
            raise ValidationError(
                'Device name can only contain letters, numbers, spaces, dots, hyphens, and underscores.'
            )
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'(admin|root|system|test)',  # Administrative terms
            r'(hack|crack|exploit)',      # Suspicious terms
            r'^\s+|\s+$',                # Leading/trailing spaces
            r'\s{2,}',                   # Multiple spaces
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, name, re.IGNORECASE):
                raise ValidationError(
                    'Device name contains inappropriate content. Please choose a different name.'
                )
        
        return name
    
    @classmethod
    def validate_role_permission(cls, user, required_role):
        """
        Validate if user has required role permission.
        
        Args:
            user (User): User object to check
            required_role (str): Required role for access
            
        Raises:
            ValidationError: If user doesn't have required permission
        """
        if not user or not user.is_authenticated:
            raise ValidationError('Authentication required.')
        
        if not hasattr(user, 'profile'):
            raise ValidationError('User profile not found.')
        
        user_role = user.profile.role
        
        # Define role hierarchy (higher roles can access lower role functions)
        role_hierarchy = {
            'admin': ['admin', 'teacher', 'student'],
            'teacher': ['teacher', 'student'],
            'student': ['student']
        }
        
        allowed_roles = role_hierarchy.get(user_role, [user_role])
        
        if required_role not in allowed_roles:
            raise ValidationError(
                f'Access denied. Required role: {required_role}, your role: {user_role}'
            )
    
    @classmethod
    def validate_json_input(cls, value, max_size=1024):
        """
        Validate and sanitize JSON input.
        
        Args:
            value (str): JSON string to validate
            max_size (int): Maximum size in bytes
            
        Returns:
            dict: Parsed and validated JSON
            
        Raises:
            ValidationError: If JSON is invalid or malicious
        """
        import json
        
        if not value:
            return {}
        
        # Check size
        if len(value.encode('utf-8')) > max_size:
            raise ValidationError(f'JSON data too large. Maximum {max_size} bytes allowed.')
        
        # Check for malicious patterns in JSON string
        for pattern in cls.MALICIOUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValidationError('JSON contains potentially malicious content.')
        
        try:
            data = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValidationError(f'Invalid JSON format: {str(e)}')
        
        # Recursively sanitize string values in JSON
        def sanitize_json_values(obj):
            if isinstance(obj, dict):
                return {k: sanitize_json_values(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize_json_values(item) for item in obj]
            elif isinstance(obj, str):
                return cls.sanitize_text_input(obj, max_length=500)
            else:
                return obj
        
        return sanitize_json_values(data)
    
    @classmethod
    def validate_ip_address(cls, ip_address):
        """
        Validate IP address format and check for suspicious IPs.
        
        Args:
            ip_address (str): IP address to validate
            
        Returns:
            str: Validated IP address
            
        Raises:
            ValidationError: If IP address is invalid
        """
        import ipaddress
        
        if not ip_address:
            raise ValidationError('IP address is required.')
        
        try:
            # Validate IP format
            ip_obj = ipaddress.ip_address(ip_address)
            
            # Check for private/local IPs in production (if needed)
            # This is commented out as local IPs are common in development
            # if ip_obj.is_private and not settings.DEBUG:
            #     raise ValidationError('Private IP addresses are not allowed.')
            
            return str(ip_obj)
            
        except ValueError:
            raise ValidationError('Invalid IP address format.')
    
    @classmethod
    def validate_session_data(cls, session_data):
        """
        Validate session data for security issues.
        
        Args:
            session_data (dict): Session data to validate
            
        Returns:
            dict: Validated session data
            
        Raises:
            ValidationError: If session data is invalid
        """
        if not isinstance(session_data, dict):
            raise ValidationError('Session data must be a dictionary.')
        
        # Check for suspicious keys
        suspicious_keys = [
            'password', 'secret', 'token', 'key', 'admin', 'root'
        ]
        
        for key in session_data.keys():
            if any(suspicious in key.lower() for suspicious in suspicious_keys):
                raise ValidationError(f'Suspicious session key detected: {key}')
        
        # Validate and sanitize string values
        validated_data = {}
        for key, value in session_data.items():
            if isinstance(value, str):
                validated_data[key] = cls.sanitize_text_input(value, max_length=1000)
            elif isinstance(value, (int, float, bool)):
                validated_data[key] = value
            elif value is None:
                validated_data[key] = None
            else:
                # Convert other types to string and sanitize
                validated_data[key] = cls.sanitize_text_input(str(value), max_length=1000)
        
        return validated_data


class MacAddressValidator:
    """
    Enhanced MAC address validator with additional security checks.
    """
    
    @classmethod
    def validate_and_normalize(cls, mac_address):
        """
        Validate and normalize MAC address format.
        
        Args:
            mac_address (str): MAC address to validate
            
        Returns:
            str: Normalized MAC address
            
        Raises:
            ValidationError: If MAC address is invalid
        """
        if not mac_address:
            raise ValidationError('MAC address is required.')
        
        # Remove whitespace and convert to lowercase
        mac_address = mac_address.strip().lower()
        
        # Check for malicious patterns
        if re.search(r'[<>"\']', mac_address):
            raise ValidationError('MAC address contains invalid characters.')
        
        # Remove common separators
        mac_clean = re.sub(r'[:-]', '', mac_address)
        
        # Validate hex characters only
        if not re.match(r'^[0-9a-f]{12}$', mac_clean):
            raise ValidationError(
                'MAC address must contain exactly 12 hexadecimal characters (0-9, A-F).'
            )
        
        # Check for reserved/invalid MAC addresses
        invalid_macs = [
            '000000000000',  # All zeros
            'ffffffffffff',  # All ones (broadcast)
            '010000000000',  # Invalid OUI
        ]
        
        if mac_clean in invalid_macs:
            raise ValidationError('This MAC address is reserved and cannot be used.')
        
        # Check if it's a multicast MAC (first octet's least significant bit)
        first_octet = int(mac_clean[:2], 16)
        if first_octet & 1:
            raise ValidationError('Multicast MAC addresses are not allowed.')
        
        # Format as standard colon-separated format
        formatted_mac = ':'.join([mac_clean[i:i+2] for i in range(0, 12, 2)])
        
        return formatted_mac


class PasswordSecurityValidator:
    """
    Enhanced password security validator.
    """
    
    @classmethod
    def validate_password_strength(cls, password, user=None):
        """
        Validate password strength with comprehensive checks.
        
        Args:
            password (str): Password to validate
            user (User): User object for context-aware validation
            
        Raises:
            ValidationError: If password doesn't meet requirements
        """
        if not password:
            raise ValidationError('Password is required.')
        
        errors = []
        
        # Length check
        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        
        if len(password) > 128:
            errors.append('Password cannot be longer than 128 characters.')
        
        # Character variety checks
        if not re.search(r'[a-z]', password):
            errors.append('Password must contain at least one lowercase letter.')
        
        if not re.search(r'[A-Z]', password):
            errors.append('Password must contain at least one uppercase letter.')
        
        if not re.search(r'\d', password):
            errors.append('Password must contain at least one number.')
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append('Password must contain at least one special character.')
        
        # Common password patterns
        common_patterns = [
            r'123456',
            r'password',
            r'qwerty',
            r'abc123',
            r'admin',
            r'letmein',
        ]
        
        for pattern in common_patterns:
            if re.search(pattern, password, re.IGNORECASE):
                errors.append('Password contains common patterns and is not secure.')
                break
        
        # User-specific checks
        if user:
            user_info = [
                user.username.lower() if user.username else '',
                user.first_name.lower() if user.first_name else '',
                user.last_name.lower() if user.last_name else '',
                user.email.split('@')[0].lower() if user.email else '',
            ]
            
            for info in user_info:
                if info and len(info) > 2 and info in password.lower():
                    errors.append('Password cannot contain your personal information.')
                    break
        
        if errors:
            raise ValidationError(errors)
        
        return password