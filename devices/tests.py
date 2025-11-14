from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from .models import Device, validate_mac_address
from .forms import DeviceRegistrationForm, DeviceUpdateForm


class DeviceModelTest(TestCase):
    """Test cases for Device model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.device_data = {
            'name': 'Test Laptop',
            'device_type': 'laptop',
            'mac_address': '00:11:22:33:44:55',
            'operating_system': 'windows',
            'user': self.user
        }
    
    def test_device_creation(self):
        """Test device creation with valid data."""
        device = Device.objects.create(**self.device_data)
        self.assertEqual(device.name, 'Test Laptop')
        self.assertEqual(device.device_type, 'laptop')
        self.assertEqual(device.mac_address, '00:11:22:33:44:55')
        self.assertEqual(device.operating_system, 'windows')
        self.assertEqual(device.user, self.user)
        self.assertFalse(device.compliance_status)  # Default is False
    
    def test_device_str_method(self):
        """Test Device string representation."""
        device = Device.objects.create(**self.device_data)
        expected = f"{device.name} ({self.user.username})"
        self.assertEqual(str(device), expected)
    
    def test_mac_address_validation_valid_formats(self):
        """Test MAC address validation with valid formats."""
        valid_macs = [
            '00:11:22:33:44:55',
            '00-11-22-33-44-55',
            'AA:BB:CC:DD:EE:FF',
            'aa:bb:cc:dd:ee:ff'
        ]
        
        for mac in valid_macs:
            normalized = validate_mac_address(mac)
            self.assertEqual(len(normalized), 17)
            self.assertTrue(':' in normalized)
            self.assertEqual(normalized.upper(), normalized)
    
    def test_mac_address_validation_invalid_formats(self):
        """Test MAC address validation with invalid formats."""
        invalid_macs = [
            '00:11:22:33:44',  # Too short
            '00:11:22:33:44:55:66',  # Too long
            '00-11-22-33-44',  # Mixed format, too short
            'invalid_mac',  # Invalid characters
            '00:GG:22:33:44:55',  # Invalid hex characters
            '',  # Empty string
        ]
        
        for mac in invalid_macs:
            with self.assertRaises(ValidationError):
                validate_mac_address(mac)
    
    def test_device_unique_mac_address(self):
        """Test that MAC addresses must be unique."""
        Device.objects.create(**self.device_data)
        
        # Try to create another device with same MAC address
        user2 = User.objects.create_user(username='user2', password='pass123')
        device_data2 = self.device_data.copy()
        device_data2['user'] = user2
        device_data2['name'] = 'Another Device'
        
        with self.assertRaises(ValidationError):
            Device.objects.create(**device_data2)
    
    def test_device_unique_name_per_user(self):
        """Test that device names must be unique per user."""
        Device.objects.create(**self.device_data)
        
        # Try to create another device with same name for same user
        device_data2 = self.device_data.copy()
        device_data2['mac_address'] = '11:22:33:44:55:66'
        
        with self.assertRaises(ValidationError):
            Device.objects.create(**device_data2)
    
    def test_device_properties(self):
        """Test device property methods."""
        device = Device.objects.create(**self.device_data)
        
        # Test is_compliant property
        self.assertFalse(device.is_compliant)
        device.compliance_status = True
        device.save()
        self.assertTrue(device.is_compliant)
        
        # Test days_since_registration
        self.assertEqual(device.days_since_registration, 0)
        
        # Test days_since_last_seen
        self.assertEqual(device.days_since_last_seen, 0)
    
    def test_device_methods(self):
        """Test device utility methods."""
        device = Device.objects.create(**self.device_data)
        
        # Test set_compliance_status
        device.set_compliance_status(True)
        self.assertTrue(device.compliance_status)
        
        # Test get_device_info
        info = device.get_device_info()
        self.assertIn('Laptop', info)
        self.assertIn('Windows', info)
        
        # Test update_last_seen
        original_last_seen = device.last_seen
        device.update_last_seen()
        device.refresh_from_db()
        self.assertGreaterEqual(device.last_seen, original_last_seen)


class DeviceRegistrationFormTest(TestCase):
    """Test cases for DeviceRegistrationForm."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.valid_form_data = {
            'name': 'Test Device',
            'device_type': 'laptop',
            'mac_address': '00:11:22:33:44:55',
            'operating_system': 'windows'
        }
    
    def test_form_valid_data(self):
        """Test form with valid data."""
        form = DeviceRegistrationForm(data=self.valid_form_data, user=self.user)
        self.assertTrue(form.is_valid())
    
    def test_form_required_fields(self):
        """Test form validation with missing required fields."""
        form = DeviceRegistrationForm(data={}, user=self.user)
        self.assertFalse(form.is_valid())
        required_fields = ['name', 'device_type', 'mac_address', 'operating_system']
        for field in required_fields:
            self.assertIn(field, form.errors)
    
    def test_form_mac_address_validation(self):
        """Test MAC address validation in form."""
        # Invalid MAC address
        invalid_data = self.valid_form_data.copy()
        invalid_data['mac_address'] = 'invalid_mac'
        form = DeviceRegistrationForm(data=invalid_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('mac_address', form.errors)
    
    def test_form_duplicate_mac_address(self):
        """Test form validation with duplicate MAC address."""
        # Create existing device
        Device.objects.create(
            name='Existing Device',
            device_type='laptop',
            mac_address='00:11:22:33:44:55',
            operating_system='windows',
            user=self.user
        )
        
        # Try to create form with same MAC
        form = DeviceRegistrationForm(data=self.valid_form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('mac_address', form.errors)
    
    def test_form_duplicate_device_name(self):
        """Test form validation with duplicate device name for same user."""
        # Create existing device
        Device.objects.create(
            name='Test Device',
            device_type='laptop',
            mac_address='11:22:33:44:55:66',
            operating_system='windows',
            user=self.user
        )
        
        # Try to create form with same name
        form = DeviceRegistrationForm(data=self.valid_form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_form_device_os_compatibility(self):
        """Test form validation for device type and OS compatibility."""
        # Smartphone with desktop OS
        invalid_data = self.valid_form_data.copy()
        invalid_data['device_type'] = 'smartphone'
        invalid_data['operating_system'] = 'windows'
        form = DeviceRegistrationForm(data=invalid_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        
        # Desktop with mobile OS
        invalid_data['device_type'] = 'desktop'
        invalid_data['operating_system'] = 'ios'
        form = DeviceRegistrationForm(data=invalid_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)


class DeviceUpdateFormTest(TestCase):
    """Test cases for DeviceUpdateForm."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.device = Device.objects.create(
            name='Original Device',
            device_type='laptop',
            mac_address='00:11:22:33:44:55',
            operating_system='windows',
            user=self.user,
            compliance_status=True
        )
        self.update_data = {
            'name': 'Updated Device',
            'device_type': 'laptop',
            'mac_address': '11:22:33:44:55:66',
            'operating_system': 'macos'
        }
    
    def test_form_update_valid_data(self):
        """Test form update with valid data."""
        form = DeviceUpdateForm(
            data=self.update_data,
            instance=self.device,
            user=self.user
        )
        self.assertTrue(form.is_valid())
    
    def test_form_mac_address_change_resets_compliance(self):
        """Test that changing MAC address resets compliance status."""
        # Ensure original device has compliance status True
        self.device.compliance_status = True
        self.device.save()
        
        # Verify the MAC address is actually different
        self.assertNotEqual(self.device.mac_address, self.update_data['mac_address'])
        
        form = DeviceUpdateForm(
            data=self.update_data,
            instance=self.device,
            user=self.user
        )
        self.assertTrue(form.is_valid())
        
        updated_device = form.save()
        self.assertFalse(updated_device.compliance_status)  # Should be reset
    
    def test_form_same_mac_address_keeps_compliance(self):
        """Test that keeping same MAC address preserves compliance status."""
        update_data = self.update_data.copy()
        update_data['mac_address'] = self.device.mac_address  # Keep same MAC
        
        form = DeviceUpdateForm(
            data=update_data,
            instance=self.device,
            user=self.user
        )
        self.assertTrue(form.is_valid())
        
        updated_device = form.save()
        self.assertTrue(updated_device.compliance_status)  # Should be preserved


class DeviceViewsTest(TestCase):
    """Test cases for device views."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.device = Device.objects.create(
            name='Test Device',
            device_type='laptop',
            mac_address='00:11:22:33:44:55',
            operating_system='windows',
            user=self.user
        )
    
    def test_device_list_view_authenticated(self):
        """Test device list view for authenticated user."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('devices:device_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Device')
    
    def test_device_list_view_unauthenticated(self):
        """Test device list view redirects unauthenticated users."""
        response = self.client.get(reverse('devices:device_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_device_register_view_get(self):
        """Test device registration view GET."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('devices:device_register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Register New Device')
    
    def test_device_register_view_post_valid(self):
        """Test device registration view POST with valid data."""
        self.client.login(username='testuser', password='testpass123')
        form_data = {
            'name': 'New Device',
            'device_type': 'tablet',
            'mac_address': '11:22:33:44:55:66',
            'operating_system': 'ios'
        }
        response = self.client.post(reverse('devices:device_register'), data=form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful registration
        
        # Check device was created
        self.assertTrue(Device.objects.filter(name='New Device', user=self.user).exists())
    
    def test_device_detail_view_owner(self):
        """Test device detail view for device owner."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('devices:device_detail', kwargs={'pk': self.device.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['device'], self.device)
    
    def test_device_detail_view_non_owner(self):
        """Test device detail view for non-owner returns 404."""
        other_user = User.objects.create_user(username='otheruser', password='pass123')
        self.client.login(username='otheruser', password='pass123')
        response = self.client.get(reverse('devices:device_detail', kwargs={'pk': self.device.pk}))
        self.assertEqual(response.status_code, 404)
    
    def test_device_update_view_get(self):
        """Test device update view GET."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('devices:device_update', kwargs={'pk': self.device.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Device')
    
    def test_device_update_view_post_valid(self):
        """Test device update view POST with valid data."""
        self.client.login(username='testuser', password='testpass123')
        form_data = {
            'name': 'Updated Device Name',
            'device_type': 'laptop',
            'mac_address': '11:22:33:44:55:66',
            'operating_system': 'macos'
        }
        response = self.client.post(
            reverse('devices:device_update', kwargs={'pk': self.device.pk}),
            data=form_data
        )
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        
        # Check device was updated
        self.device.refresh_from_db()
        self.assertEqual(self.device.name, 'Updated Device Name')
        self.assertEqual(self.device.operating_system, 'macos')
    
    def test_device_delete_view_get(self):
        """Test device delete confirmation view GET."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('devices:device_delete', kwargs={'pk': self.device.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Delete Device')
    
    def test_device_delete_view_post(self):
        """Test device delete view POST."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('devices:device_delete', kwargs={'pk': self.device.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect after deletion
        
        # Check device was deleted
        self.assertFalse(Device.objects.filter(pk=self.device.pk).exists())
    
    def test_toggle_compliance_view(self):
        """Test toggle compliance status view."""
        self.client.login(username='testuser', password='testpass123')
        original_status = self.device.compliance_status
        
        response = self.client.post(reverse('devices:toggle_compliance', kwargs={'pk': self.device.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect after toggle
        
        # Check compliance status was toggled
        self.device.refresh_from_db()
        self.assertEqual(self.device.compliance_status, not original_status)
    
    def test_device_list_filtering(self):
        """Test device list view with filtering."""
        # Create additional devices for filtering
        Device.objects.create(
            name='Android Phone',
            device_type='smartphone',
            mac_address='22:33:44:55:66:77',
            operating_system='android',
            user=self.user,
            compliance_status=True
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        # Test device type filter
        response = self.client.get(reverse('devices:device_list') + '?device_type=smartphone')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Android Phone')
        self.assertNotContains(response, 'Test Device')
        
        # Test compliance filter
        response = self.client.get(reverse('devices:device_list') + '?compliance=compliant')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Android Phone')
        self.assertNotContains(response, 'Test Device')
        
        # Test search filter
        response = self.client.get(reverse('devices:device_list') + '?search=Android')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Android Phone')
        self.assertNotContains(response, 'Test Device')