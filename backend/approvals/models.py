from django.db import models
from django.conf import settings
from expenses.models import Expense


class Approval(models.Model):
    """
    Approval tracking for expenses.
    Supports multi-level approval workflow (e.g., Manager -> Finance Admin)
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    class ApprovalLevel(models.IntegerChoices):
        MANAGER = 1, 'Manager Approval'
        FINANCE = 2, 'Finance Approval'

    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='approvals'
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='approvals_made'
    )
    level = models.IntegerField(
        choices=ApprovalLevel.choices,
        default=ApprovalLevel.MANAGER,
        help_text="Approval level in the hierarchy"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    comments = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['level', '-created_at']
        unique_together = ['expense', 'level']

    def __str__(self):
        return f"{self.expense} - Level {self.level} ({self.get_status_display()})"


class Comment(models.Model):
    """Comments on expenses for discussion"""
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='expense_comments'
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user} on {self.expense}"


class Notification(models.Model):
    """In-app notifications"""

    class NotificationType(models.TextChoices):
        EXPENSE_SUBMITTED = 'EXPENSE_SUBMITTED', 'Expense Submitted'
        EXPENSE_APPROVED = 'EXPENSE_APPROVED', 'Expense Approved'
        EXPENSE_REJECTED = 'EXPENSE_REJECTED', 'Expense Rejected'
        BUDGET_ALERT = 'BUDGET_ALERT', 'Budget Alert'
        COMMENT_ADDED = 'COMMENT_ADDED', 'Comment Added'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user}"


class AuditLog(models.Model):
    """Audit log for tracking all actions"""

    class ActionType(models.TextChoices):
        CREATE = 'CREATE', 'Created'
        UPDATE = 'UPDATE', 'Updated'
        DELETE = 'DELETE', 'Deleted'
        APPROVE = 'APPROVE', 'Approved'
        REJECT = 'REJECT', 'Rejected'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs'
    )
    action_type = models.CharField(
        max_length=20,
        choices=ActionType.choices
    )
    model_name = models.CharField(max_length=50)
    object_id = models.IntegerField()
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} {self.action_type} {self.model_name} #{self.object_id}"
