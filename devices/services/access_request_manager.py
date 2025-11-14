"""
Access Request Manager Service
Handles business logic for device access requests and approvals.
"""
import logging
from django.contrib.auth.models import User
from django.utils import timezone
from devices.models import Device, DeviceAccessRequest

logger = logging.getLogger('devices.access_requests')


class AccessRequestManager:
    """
    Centralized business logic for handling device access requests.
    """
    
    @staticmethod
    def create_request(device, requester, registered_by=None):
        """
        Create access request and handle auto-approval logic.
        
        Args:
            device: Device instance
            requester: User who owns the device
            registered_by: User who registered the device (defaults to requester)
        
        Returns:
            tuple: (DeviceAccessRequest instance, was_auto_approved boolean)
        """
        if registered_by is None:
            registered_by = requester
        
        # Check if should auto-approve
        if AccessRequestManager.should_auto_approve(device, requester, registered_by):
            # Auto-approve: set device to active, no access request needed
            device.access_status = 'active'
            device.save(update_fields=['access_status'])
            
            logger.info(
                f"Auto-approved device {device.id} for user {requester.id} "
                f"(registered by {registered_by.id})"
            )
            
            return None, True
        
        # Create access request
        access_request = DeviceAccessRequest.objects.create(
            device=device,
            requester=requester,
            status='pending'
        )
        
        logger.info(
            f"Created access request {access_request.id} for device {device.id} "
            f"by user {requester.id}"
        )
        
        return access_request, False
    
    @staticmethod
    def should_auto_approve(device, requester, registered_by):
        """
        Determine if device should be auto-approved based on roles.
        
        Rules:
        - Teacher registering own device: auto-approve
        - Admin registering any device: auto-approve
        - Student registering device: requires approval
        - Teacher registering for student: not allowed (handled in form validation)
        
        Args:
            device: Device instance
            requester: User who owns the device
            registered_by: User who registered the device
        
        Returns:
            bool: True if should auto-approve, False otherwise
        """
        if not hasattr(registered_by, 'profile'):
            return False
        
        registered_by_role = registered_by.profile.role
        
        # Admin registering any device: auto-approve
        if registered_by_role == 'admin':
            return True
        
        # Teacher registering own device: auto-approve
        if registered_by_role == 'teacher' and registered_by == requester:
            return True
        
        # All other cases require approval
        return False
    
    @staticmethod
    def get_eligible_approvers(request):
        """
        Return users who can approve this request based on requester role.
        
        Args:
            request: DeviceAccessRequest instance
        
        Returns:
            QuerySet: Users who can approve this request
        """
        if not hasattr(request.requester, 'profile'):
            return User.objects.none()
        
        requester_role = request.requester.profile.role
        
        if requester_role == 'student':
            # Students' requests can be approved by teachers and admins
            return User.objects.filter(
                profile__role__in=['teacher', 'admin']
            )
        elif requester_role == 'teacher':
            # Teachers' requests can only be approved by admins
            return User.objects.filter(profile__role='admin')
        
        return User.objects.none()
    
    @staticmethod
    def approve_request(request, approver, notes=''):
        """
        Approve request, grant device access, send notifications.
        
        Args:
            request: DeviceAccessRequest instance
            approver: User approving the request
            notes: Optional notes about the approval
        
        Raises:
            PermissionDenied: If approver doesn't have permission
            ValidationError: If request is not in pending status
        """
        from django.core.exceptions import PermissionDenied, ValidationError
        
        if not request.can_be_approved_by(approver):
            logger.warning(
                f"Unauthorized approval attempt: User {approver.id} tried to approve "
                f"request {request.id} without permission"
            )
            raise PermissionDenied("You don't have permission to approve this request")
        
        if request.status != 'pending':
            raise ValidationError("This request has already been processed")
        
        # Approve the request
        request.approve(approver, notes)
        
        logger.info(
            f"Request {request.id} approved by user {approver.id} "
            f"for device {request.device.id}"
        )
    
    @staticmethod
    def reject_request(request, approver, reason=''):
        """
        Reject request and notify requester.
        
        Args:
            request: DeviceAccessRequest instance
            approver: User rejecting the request
            reason: Reason for rejection
        
        Raises:
            PermissionDenied: If approver doesn't have permission
            ValidationError: If request is not in pending status
        """
        from django.core.exceptions import PermissionDenied, ValidationError
        
        if not request.can_be_approved_by(approver):
            logger.warning(
                f"Unauthorized rejection attempt: User {approver.id} tried to reject "
                f"request {request.id} without permission"
            )
            raise PermissionDenied("You don't have permission to reject this request")
        
        if request.status != 'pending':
            raise ValidationError("This request has already been processed")
        
        # Reject the request
        request.reject(approver, reason)
        
        logger.info(
            f"Request {request.id} rejected by user {approver.id} "
            f"for device {request.device.id}. Reason: {reason}"
        )
