from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from .models import Device
from .forms import DeviceRegistrationForm, DeviceUpdateForm


class DeviceListView(LoginRequiredMixin, ListView):
    """
    List view for user's devices with pagination and filtering.
    """
    model = Device
    template_name = 'devices/device_list.html'
    context_object_name = 'devices'
    paginate_by = 10
    
    def get_queryset(self):
        """
        Return devices owned by the current user with optional filtering.
        """
        queryset = Device.objects.filter(user=self.request.user).select_related('user')
        
        # Search functionality
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(mac_address__icontains=search_query) |
                Q(device_type__icontains=search_query) |
                Q(operating_system__icontains=search_query)
            )
        
        # Filter by device type
        device_type = self.request.GET.get('device_type', '').strip()
        if device_type:
            queryset = queryset.filter(device_type=device_type)
        
        # Filter by operating system
        operating_system = self.request.GET.get('operating_system', '').strip()
        if operating_system:
            queryset = queryset.filter(operating_system=operating_system)
        
        # Filter by compliance status
        compliance = self.request.GET.get('compliance', '').strip()
        if compliance == 'compliant':
            queryset = queryset.filter(compliance_status=True)
        elif compliance == 'non_compliant':
            queryset = queryset.filter(compliance_status=False)
        
        # Filter by access status
        access_status = self.request.GET.get('access_status', '').strip()
        if access_status:
            queryset = queryset.filter(access_status=access_status)
        
        return queryset.order_by('-registered_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter choices for the template
        context['device_type_choices'] = Device.DEVICE_TYPE_CHOICES
        context['os_choices'] = Device.OS_CHOICES
        context['access_status_choices'] = Device.ACCESS_STATUS_CHOICES
        
        # Preserve current filter values
        context['current_search'] = self.request.GET.get('search', '')
        context['current_device_type'] = self.request.GET.get('device_type', '')
        context['current_os'] = self.request.GET.get('operating_system', '')
        context['current_compliance'] = self.request.GET.get('compliance', '')
        context['current_access_status'] = self.request.GET.get('access_status', '')
        
        # Add device statistics
        user_devices = Device.objects.filter(user=self.request.user)
        context['total_devices'] = user_devices.count()
        context['compliant_devices'] = user_devices.filter(compliance_status=True).count()
        context['non_compliant_devices'] = user_devices.filter(compliance_status=False).count()
        context['pending_devices'] = user_devices.filter(access_status='pending').count()
        context['active_devices'] = user_devices.filter(access_status='active').count()
        context['rejected_devices'] = user_devices.filter(access_status='rejected').count()
        
        return context


class DeviceRegisterView(LoginRequiredMixin, CreateView):
    """
    View for registering a new device.
    """
    model = Device
    form_class = DeviceRegistrationForm
    template_name = 'devices/device_register.html'
    success_url = reverse_lazy('devices:device_list')
    
    def get_form_kwargs(self):
        """
        Pass the current user to the form.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """
        Set the device owner and handle access request creation.
        """
        from devices.services.access_request_manager import AccessRequestManager
        from devices.services.notification_service import NotificationService
        
        # Determine the device owner
        target_user = form.cleaned_data.get('target_user')
        device_owner = target_user if target_user else self.request.user
        
        # Set device owner and registered_by
        form.instance.user = device_owner
        form.instance.registered_by = self.request.user
        
        # Save the device
        self.object = form.save()
        
        # Create access request or auto-approve
        access_request, was_auto_approved = AccessRequestManager.create_request(
            device=self.object,
            requester=device_owner,
            registered_by=self.request.user
        )
        
        # Send notifications if access request was created
        if access_request:
            NotificationService.notify_access_request(access_request)
            messages.success(
                self.request,
                f'Device "{self.object.name}" has been registered. '
                f'Access request is pending approval.'
            )
        else:
            # Auto-approved
            messages.success(
                self.request,
                f'Device "{self.object.name}" has been registered and activated successfully!'
            )
        
        return redirect(self.get_success_url())
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class DeviceDetailView(LoginRequiredMixin, DetailView):
    """
    Detailed view of a specific device.
    """
    model = Device
    template_name = 'devices/device_detail.html'
    context_object_name = 'device'
    
    def get_queryset(self):
        """
        Ensure users can only view their own devices.
        """
        return Device.objects.filter(user=self.request.user)
    
    def get_object(self, queryset=None):
        """
        Get device object with ownership verification.
        """
        obj = super().get_object(queryset)
        if obj.user != self.request.user:
            raise Http404("Device not found.")
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add additional context for the template
        context['can_edit'] = True  # User can always edit their own devices
        
        return context


class DeviceUpdateView(LoginRequiredMixin, UpdateView):
    """
    View for updating device information.
    """
    model = Device
    form_class = DeviceUpdateForm
    template_name = 'devices/device_update.html'
    context_object_name = 'device'
    
    def get_queryset(self):
        """
        Ensure users can only update their own devices.
        """
        return Device.objects.filter(user=self.request.user)
    
    def get_object(self, queryset=None):
        """
        Get device object with ownership verification.
        """
        obj = super().get_object(queryset)
        if obj.user != self.request.user:
            raise Http404("Device not found.")
        return obj
    
    def get_form_kwargs(self):
        """
        Pass the current user to the form.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_success_url(self):
        """
        Redirect to device detail page after successful update.
        """
        return reverse_lazy('devices:device_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Device "{form.instance.name}" has been updated successfully!'
        )
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


@login_required
def device_delete_view(request, pk):
    """
    View for deleting a device (with confirmation).
    """
    device = get_object_or_404(Device, pk=pk, user=request.user)
    
    if request.method == 'POST':
        device_name = device.name
        device.delete()
        messages.success(request, f'Device "{device_name}" has been deleted successfully!')
        return redirect('devices:device_list')
    
    return render(request, 'devices/device_confirm_delete.html', {'device': device})


@login_required
def toggle_compliance_view(request, pk):
    """
    AJAX view for toggling device compliance status.
    """
    device = get_object_or_404(Device, pk=pk, user=request.user)
    
    if request.method == 'POST':
        device.compliance_status = not device.compliance_status
        device.save(update_fields=['compliance_status'])
        
        status_text = 'compliant' if device.compliance_status else 'non-compliant'
        messages.success(
            request,
            f'Device "{device.name}" is now marked as {status_text}.'
        )
    
    return redirect('devices:device_detail', pk=device.pk)



from django.views.generic import FormView
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from .models import DeviceAccessRequest
from .forms import AccessRequestApprovalForm, AccessRequestRejectionForm
from devices.services.access_request_manager import AccessRequestManager
from devices.services.notification_service import NotificationService


def is_approver(user):
    """
    Check if user is a teacher or admin (can approve requests).
    """
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role in ['teacher', 'admin']


@method_decorator(user_passes_test(is_approver), name='dispatch')
class AccessRequestListView(LoginRequiredMixin, ListView):
    """
    List view for pending device access requests.
    """
    model = DeviceAccessRequest
    template_name = 'devices/access_request_list.html'
    context_object_name = 'access_requests'
    paginate_by = 20
    
    def get_queryset(self):
        """
        Return pending requests that the user can approve.
        """
        user = self.request.user
        queryset = DeviceAccessRequest.objects.filter(status='pending').select_related(
            'device', 'requester', 'requester__profile'
        ).order_by('-requested_at')
        
        # Filter based on user role
        if hasattr(user, 'profile'):
            if user.profile.role == 'teacher':
                # Teachers can only see student requests
                queryset = queryset.filter(requester__profile__role='student')
            # Admins can see all requests (no additional filtering)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_count'] = self.get_queryset().count()
        return context


@method_decorator(user_passes_test(is_approver), name='dispatch')
class AccessRequestApproveView(LoginRequiredMixin, FormView):
    """
    View for approving device access requests.
    """
    form_class = AccessRequestApprovalForm
    template_name = 'devices/access_request_approve.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.access_request = get_object_or_404(
            DeviceAccessRequest,
            pk=kwargs.get('pk'),
            status='pending'
        )
        
        # Check if user can approve this request
        if not self.access_request.can_be_approved_by(request.user):
            messages.error(request, "You don't have permission to approve this request.")
            return redirect('devices:access_requests')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['access_request'] = self.access_request
        return context
    
    def form_valid(self, form):
        notes = form.cleaned_data.get('notes', '')
        
        try:
            AccessRequestManager.approve_request(
                self.access_request,
                self.request.user,
                notes
            )
            NotificationService.notify_request_approved(self.access_request)
            
            messages.success(
                self.request,
                f'Access request for "{self.access_request.device.name}" has been approved.'
            )
        except Exception as e:
            messages.error(self.request, str(e))
            return redirect('devices:access_requests')
        
        return redirect('devices:access_requests')
    
    def get_success_url(self):
        return reverse_lazy('devices:access_requests')


@method_decorator(user_passes_test(is_approver), name='dispatch')
class AccessRequestRejectView(LoginRequiredMixin, FormView):
    """
    View for rejecting device access requests.
    """
    form_class = AccessRequestRejectionForm
    template_name = 'devices/access_request_reject.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.access_request = get_object_or_404(
            DeviceAccessRequest,
            pk=kwargs.get('pk'),
            status='pending'
        )
        
        # Check if user can reject this request
        if not self.access_request.can_be_approved_by(request.user):
            messages.error(request, "You don't have permission to reject this request.")
            return redirect('devices:access_requests')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['access_request'] = self.access_request
        return context
    
    def form_valid(self, form):
        reason = form.cleaned_data.get('reason', '')
        
        try:
            AccessRequestManager.reject_request(
                self.access_request,
                self.request.user,
                reason
            )
            NotificationService.notify_request_rejected(self.access_request, reason)
            
            messages.success(
                self.request,
                f'Access request for "{self.access_request.device.name}" has been rejected.'
            )
        except Exception as e:
            messages.error(self.request, str(e))
            return redirect('devices:access_requests')
        
        return redirect('devices:access_requests')
    
    def get_success_url(self):
        return reverse_lazy('devices:access_requests')


class MyAccessRequestsView(LoginRequiredMixin, ListView):
    """
    View for users to track their own device access requests.
    """
    model = DeviceAccessRequest
    template_name = 'devices/my_access_requests.html'
    context_object_name = 'access_requests'
    paginate_by = 20
    
    def get_queryset(self):
        """
        Return access requests for the current user's devices.
        """
        return DeviceAccessRequest.objects.filter(
            requester=self.request.user
        ).select_related(
            'device', 'approved_by'
        ).order_by('-requested_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_requests = self.get_queryset()
        context['pending_count'] = user_requests.filter(status='pending').count()
        context['approved_count'] = user_requests.filter(status='approved').count()
        context['rejected_count'] = user_requests.filter(status='rejected').count()
        return context
