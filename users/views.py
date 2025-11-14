from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import CustomUserCreationForm, UserProfileForm
from .models import UserProfile


class CustomLoginView(LoginView):
    """
    Custom login view with role-based redirection.
    """
    template_name = 'users/login.html'
    redirect_authenticated_user = True
    
    def dispatch(self, request, *args, **kwargs):
        # Redirect authenticated users to dashboard
        if request.user.is_authenticated:
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_success_url(self):
        # Redirect to dashboard after successful login
        return reverse_lazy('dashboard:home')
    
    def form_valid(self, form):
        # Clean up any existing sessions for this user before logging in
        user = form.get_user()
        
        # Import here to avoid circular imports
        from security.models import SessionTracker
        from django.contrib.sessions.models import Session
        
        # End all active sessions for this user
        active_sessions = SessionTracker.objects.filter(
            user=user,
            status='active',
            logout_time__isnull=True
        )
        
        for session_tracker in active_sessions:
            session_tracker.end_session('new_login')
            # Also delete the Django session
            try:
                Session.objects.filter(session_key=session_tracker.session_key).delete()
            except:
                pass
        
        messages.success(self.request, f'Welcome back, {form.get_user().first_name or form.get_user().username}!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Invalid username or password. Please try again.')
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    """
    Custom logout view with success message.
    """
    next_page = reverse_lazy('home')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.success(request, 'You have been successfully logged out.')
        return super().dispatch(request, *args, **kwargs)


class SignupView(CreateView):
    """
    User registration view with role selection.
    """
    form_class = CustomUserCreationForm
    template_name = 'users/signup.html'
    success_url = reverse_lazy('users:login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.save()
        messages.success(
            self.request, 
            f'Account created successfully! Welcome, {user.first_name or user.username}. You can now log in.'
        )
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def dispatch(self, request, *args, **kwargs):
        # Redirect authenticated users to dashboard
        if request.user.is_authenticated:
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)


class ProfileView(LoginRequiredMixin, DetailView):
    """
    User profile view showing user information and connected devices.
    """
    model = UserProfile
    template_name = 'users/profile.html'
    context_object_name = 'profile'
    
    def get_object(self):
        return self.request.user.profile
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add user's devices to context (will be available once devices app is implemented)
        context['user_devices'] = []  # Placeholder for now
        context['form'] = UserProfileForm(instance=self.object, user=self.request.user)
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle profile updates."""
        self.object = self.get_object()
        form = UserProfileForm(request.POST, instance=self.object, user=request.user)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('users:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
            context = self.get_context_data()
            context['form'] = form
            return self.render_to_response(context)
