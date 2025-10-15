from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from expenses.models import Expense
from .models import Approval, Notification, AuditLog


@receiver(post_save, sender=Approval)
def update_expense_on_approval(sender, instance, created, **kwargs):
    """Update expense status when approval is approved/rejected"""
    # Skip if this is a recursive save (updating approved_at)
    update_fields = kwargs.get('update_fields')
    if update_fields and 'approved_at' in update_fields:
        return

    if not created and instance.status in ['APPROVED', 'REJECTED']:
        expense = instance.expense
        expense.status = instance.status
        # Mark expense to skip audit logging (handled by approval log)
        expense._skip_audit_log = True
        expense.save()

        # Update approved_at timestamp
        if instance.status == 'APPROVED' and not instance.approved_at:
            instance.approved_at = timezone.now()
            instance.save(update_fields=['approved_at'])

        # Create notification for expense submitter
        notification_type = 'EXPENSE_APPROVED' if instance.status == 'APPROVED' else 'EXPENSE_REJECTED'
        title = f"Expense {instance.status.title()}"
        message = f"Your expense from {expense.vendor} for ${expense.total_amount} has been {instance.status.lower()} by {instance.approver.get_full_name() or instance.approver.username}."

        Notification.objects.create(
            user=expense.user,
            notification_type=notification_type,
            title=title,
            message=message,
            expense=expense
        )


@receiver(post_save, sender=Expense)
def create_approval_on_submission(sender, instance, created, **kwargs):
    """
    Auto-create Approval record(s) when expense is submitted.
    Requirement: "after I submit an expense, it's sent automatically to my Manager"
    Supports multi-level approval: Manager -> Finance Admin
    """
    if created and instance.status == 'PENDING':
        # Get department manager
        if instance.user.department and instance.user.department.manager:
            manager = instance.user.department.manager

            # Create Level 1 approval (Manager)
            Approval.objects.create(
                expense=instance,
                approver=manager,
                level=Approval.ApprovalLevel.MANAGER,
                status='PENDING'
            )

            # Notify department manager
            Notification.objects.create(
                user=manager,
                notification_type='EXPENSE_SUBMITTED',
                title='New Expense Submitted',
                message=f"{instance.user.get_full_name() or instance.user.username} submitted an expense from {instance.vendor} for ${instance.total_amount}.",
                expense=instance
            )

            # If finance approval is required, create Level 2 approval
            if instance.requires_finance_approval:
                # Find a finance admin to assign to
                from users.models import User
                finance_admins = User.objects.filter(role=User.Role.FINANCE_ADMIN, is_active=True)
                if finance_admins.exists():
                    # Assign to first finance admin (can be made more sophisticated)
                    finance_admin = finance_admins.first()

                    Approval.objects.create(
                        expense=instance,
                        approver=finance_admin,
                        level=Approval.ApprovalLevel.FINANCE,
                        status='PENDING'
                    )

                    # Notify finance admin too
                    Notification.objects.create(
                        user=finance_admin,
                        notification_type='EXPENSE_SUBMITTED',
                        title='Finance Approval Required',
                        message=f"Expense from {instance.vendor} for ${instance.total_amount} requires finance approval.",
                        expense=instance
                    )


@receiver(post_save, sender=Expense)
def log_expense_changes(sender, instance, created, **kwargs):
    """Log expense creation and updates to audit log"""
    # Skip if expense is being updated by approval workflow
    if hasattr(instance, '_skip_audit_log') and instance._skip_audit_log:
        return

    action_type = 'CREATE' if created else 'UPDATE'

    AuditLog.objects.create(
        user=instance.user,
        action_type=action_type,
        model_name='Expense',
        object_id=instance.id,
        changes={
            'vendor': instance.vendor,
            'total_amount': str(instance.total_amount),
            'status': instance.status,
            'date': str(instance.date)
        }
    )


@receiver(post_save, sender=Approval)
def log_approval_actions(sender, instance, created, **kwargs):
    """Log approval actions to audit log"""
    # Skip if this is a recursive save (updating approved_at)
    update_fields = kwargs.get('update_fields')
    if update_fields and 'approved_at' in update_fields:
        return

    if not created and instance.status in ['APPROVED', 'REJECTED']:
        action_type = 'APPROVE' if instance.status == 'APPROVED' else 'REJECT'

        AuditLog.objects.create(
            user=instance.approver,
            action_type=action_type,
            model_name='Expense',
            object_id=instance.expense.id,
            changes={
                'expense_vendor': instance.expense.vendor,
                'approval_status': instance.status,
                'comments': instance.comments
            }
        )
