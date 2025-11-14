from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import UserProfile
from .forms import CustomUserCreationForm, UserProfileForm


class UserProfileModelTest(TestCase):
    """Test cases for UserProfile model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    
    def test_user_profile_creation(self):
        """Test that UserProfile is automatically created when User is created."""
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertIsInstance(self.user.profile, UserProfile)
        self.assertEqual(self.user.profile.role, 'student')  # Default role
    
    def test_user_profile_str_method(self):
        """Test UserProfile string representation."""
        expected = f"{self.user.username} - Student"
        self.assertEqual(str(self.user.profile), expected)
    
    def test_role_properties(self):
        """Test role property methods."""
        profile = self.user.profile
        
        # Test default student role
        self.assertTrue(profile.is_student)
        self.assertFalse(profile.is_teacher)
        self.assertFalse(profile.is_admin)
        
        # Test teacher role
        profile.role = 'teacher'
        profile.save()
        self.assertTrue(profile.is_teacher)
        self.assertFalse(profile.is_student)
        self.assertFalse(profile.is_admin)
        
        # Test admin role
        profile.role = 'admin'
        profile.save()
        self.assertTrue(profile.is_admin)
        self.assertFalse(profile.is_student)
        self.assertFalse(profile.is_teacher)
    
    def test_role_choices(self):
        """Test that role choices are valid."""
        valid_roles = ['teacher', 'student', 'admin']
        for role, _ in UserProfile.ROLE_CHOICES:
            self.assertIn(role, valid_roles)


class CustomUserCreationFormTest(TestCase):
    """Test cases for CustomUserCreationForm."""
    
    def test_form_valid_data(self):
        """Test form with valid data."""
        form_data = {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@example.com',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
            'role': 'teacher'
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_form_save_creates_user_with_profile(self):
        """Test that form save creates user with correct profile role."""
        form_data = {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@example.com',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
            'role': 'teacher'
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        user = form.save()
        self.assertEqual(user.username, 'newuser')
        self.assertEqual(user.first_name, 'New')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertEqual(user.profile.role, 'teacher')
    
    def test_form_password_mismatch(self):
        """Test form validation with password mismatch."""
        form_data = {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@example.com',
            'password1': 'complexpass123',
            'password2': 'differentpass123',
            'role': 'teacher'
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)
    
    def test_form_required_fields(self):
        """Test form validation with missing required fields."""
        form = CustomUserCreationForm(data={})
        self.assertFalse(form.is_valid())
        required_fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'role']
        for field in required_fields:
            self.assertIn(field, form.errors)


class UserProfileFormTest(TestCase):
    """Test cases for UserProfileForm."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    
    def test_form_initialization_with_user_data(self):
        """Test that form initializes with user data."""
        form = UserProfileForm(instance=self.user.profile, user=self.user)
        self.assertEqual(form.fields['first_name'].initial, 'Test')
        self.assertEqual(form.fields['last_name'].initial, 'User')
        self.assertEqual(form.fields['email'].initial, 'test@example.com')
    
    def test_form_save_updates_user_and_profile(self):
        """Test that form save updates both user and profile."""
        form_data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'email': 'updated@example.com',
            'role': 'teacher'
        }
        form = UserProfileForm(data=form_data, instance=self.user.profile, user=self.user)
        self.assertTrue(form.is_valid())
        
        form.save()
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')
        self.assertEqual(self.user.email, 'updated@example.com')
        self.assertEqual(self.user.profile.role, 'teacher')


class AuthenticationViewsTest(TestCase):
    """Test cases for authentication views."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.user.profile.role = 'teacher'
        self.user.profile.save()
    
    def test_signup_view_post_valid(self):
        """Test signup view POST with valid data."""
        form_data = {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@example.com',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
            'role': 'student'
        }
        response = self.client.post(reverse('users:signup'), data=form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful signup
        
        # Check user was created
        self.assertTrue(User.objects.filter(username='newuser').exists())
        new_user = User.objects.get(username='newuser')
        self.assertEqual(new_user.profile.role, 'student')
    
    def test_signup_view_authenticated_user_redirect(self):
        """Test that authenticated users are redirected from signup."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('users:signup'))
        self.assertEqual(response.status_code, 302)  # Should redirect
    
    def test_login_view_post_valid(self):
        """Test login view POST with valid credentials."""
        response = self.client.post(reverse('users:login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after successful login
        
        # Check user is logged in by making another request
        response2 = self.client.get(reverse('users:profile'))
        self.assertEqual(response2.status_code, 200)  # Should access profile successfully
    
    def test_login_view_post_invalid(self):
        """Test login view POST with invalid credentials."""
        response = self.client.post(reverse('users:login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)  # Stay on login page
        
        # Check user is not logged in
        response2 = self.client.get(reverse('users:profile'))
        self.assertEqual(response2.status_code, 302)  # Should redirect to login
    
    def test_profile_view_authenticated(self):
        """Test profile view for authenticated user."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('users:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['profile'], self.user.profile)
    
    def test_profile_view_unauthenticated(self):
        """Test profile view redirects unauthenticated users."""
        response = self.client.get(reverse('users:profile'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_profile_view_post_update(self):
        """Test profile view POST to update profile."""
        self.client.login(username='testuser', password='testpass123')
        form_data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'email': 'updated@example.com',
            'role': 'admin'
        }
        response = self.client.post(reverse('users:profile'), data=form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.profile.role, 'admin')
    
    def test_logout_view(self):
        """Test logout view."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('users:logout'))
        self.assertEqual(response.status_code, 302)  # Redirect after logout
