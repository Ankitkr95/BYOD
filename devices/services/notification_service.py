"""
Notification Service
Handles creation and delivery of notifications for device access requests.
"""
import logging
from devices.models import Notification, DeviceAccessRequest

logger = logging.getLogger('devices.notifications')


class NotificationService:
    """
    Handle creation and delivery of notifications.
    """
    
    @staticmethod
    def notify_access_request(request):
        """
        Send notifications to eligible approvers when request is created.
        
        Args:
            request: DeviceAccessRequest instance
        """
        eligible_approvers = request.get_eligible_approvers()
        
        title = f"New Device Access Request from {request.requester.get_full_name() or request.requester.username}"
        message = (
            f"{request.requester.get_full_name() or request.requester.username} "
            f"has requested access for device '{request.device.name}' "
            f"({request.device.get_device_type_display()})."
        )
        
        notifications_created = 0
        for approver in eligible_approvers:
            Notification.objects.create(
                recipient=approver,
                notification_type='access_request',
                title=title,
                message=message,
                related_request=request
            )
            notifications_created += 1
        
        logger.info(
            f"Created {notifications_created} notifications for access request {request.id}"
        )
    
    @staticmethod
    def notify_request_approved(request):
        """
        Notify device owner when request is approved.
        
        Args:
            request: DeviceAccessRequest instance
        """
        approver_name = request.approved_by.get_full_name() or request.approved_by.username
        
        title = "Device Access Request Approved"
        message = (
            f"Your device '{request.device.name}' has been approved by {approver_name}. "
            f"You can now use this device on the network."
        )
        
        if request.notes:
            message += f"\n\nNotes: {request.notes}"
        
        Notification.objects.create(
            recipient=request.requester,
            notification_type='request_approved',
            title=title,
            message=message,
            related_request=request
        )
        
        logger.info(
            f"Sent approval notification to user {request.requester.id} "
            f"for request {request.id}"
        )
    
    @staticmethod
    def notify_request_rejected(request, reason):
        """
        Notify device owner when request is rejected.
        
        Args:
            request: DeviceAccessRequest instance
            reason: Rejection reason
        """
        approver_name = request.approved_by.get_full_name() or request.approved_by.username
        
        title = "Device Access Request Rejected"
        message = (
            f"Your device '{request.device.name}' access request has been rejected by {approver_name}."
        )
        
        if reason:
            message += f"\n\nReason: {reason}"
        
        Notification.objects.create(
            recipient=request.requester,
            notification_type='request_rejected',
            title=title,
            message=message,
            related_request=request
        )
        
        logger.info(
            f"Sent rejection notification to user {request.requester.id} "
            f"for request {request.id}"
        )
    
    @staticmethod
    def get_unread_count(user):
        """
        Get count of unread notifications for user.
        
        Args:
            user: User instance
        
        Returns:
            int: Count of unread notifications
        """
        return Notification.get_unread_count(user)
