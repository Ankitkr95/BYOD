"""
Notification views for managing user notifications.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from devices.models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    """
    Display user notifications.
    """
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        """
        Return notifications for the current user.
        """
        return Notification.objects.filter(
            recipient=self.request.user
        ).select_related(
            'related_request', 'related_request__device'
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_notifications = self.get_queryset()
        context['unread_count'] = user_notifications.filter(is_read=False).count()
        context['total_count'] = user_notifications.count()
        return context


@login_required
@require_http_methods(["GET"])
def notification_badge_view(request):
    """
    AJAX endpoint to return unread notification count.
    """
    unread_count = Notification.get_unread_count(request.user)
    return JsonResponse({'unread_count': unread_count})


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, pk):
    """
    Mark a notification as read.
    """
    notification = get_object_or_404(
        Notification,
        pk=pk,
        recipient=request.user
    )
    notification.mark_as_read()
    
    # Return JSON response for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    # Redirect for regular requests
    return redirect('notifications:list')


@login_required
@require_http_methods(["POST"])
def mark_all_read(request):
    """
    Mark all notifications as read for the current user.
    """
    Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(is_read=True)
    
    # Return JSON response for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    # Redirect for regular requests
    return redirect('notifications:list')
