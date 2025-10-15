from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from decimal import Decimal
from datetime import date
from .models import Approval, Comment, Notification, AuditLog
from expenses.models import Expense, Currency
from users.models import Department

User = get_user_model()


class ApprovalModelTest(TestCase):
    """Test cases for Approval model"""

    def setUp(self):
        """Set up test data"""
        self.department = Department.objects.create(
            name='Engineering',
            code='ENG'
        )

        self.employee = User.objects.create_user(
            username='employee',
            email='employee@test.com',
            password='testpass123',
            role=User.Role.EMPLOYEE,
            department=self.department
        )

        self.manager = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123',
            role=User.Role.MANAGER,
            department=self.department
        )

        self.finance_admin = User.objects.create_user(
            username='finance',
            email='finance@test.com',
            password='testpass123',
            role=User.Role.FINANCE_ADMIN
        )

        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            exchange_rate_to_base=Decimal('1.000000'),
            is_base_currency=True
        )

        self.expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Amazon',
            description='Office supplies',
            total_amount=Decimal('500.00'),
            currency=self.usd
        )

    def test_approval_creation(self):
        """Test approval can be created successfully"""
        approval = Approval.objects.create(
            expense=self.expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER,
            status=Approval.Status.PENDING
        )

        self.assertEqual(approval.expense, self.expense)
        self.assertEqual(approval.approver, self.manager)
        self.assertEqual(approval.level, Approval.ApprovalLevel.MANAGER)
        self.assertEqual(approval.status, Approval.Status.PENDING)

    def test_approval_str_method(self):
        """Test approval string representation"""
        approval = Approval.objects.create(
            expense=self.expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER
        )

        expected = f"{self.expense} - Level {Approval.ApprovalLevel.MANAGER} (Pending)"
        self.assertEqual(str(approval), expected)

    def test_approval_default_status(self):
        """Test default status is PENDING"""
        approval = Approval.objects.create(
            expense=self.expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER
        )

        self.assertEqual(approval.status, Approval.Status.PENDING)

    def test_all_approval_statuses(self):
        """Test all approval statuses"""
        statuses = [
            Approval.Status.PENDING,
            Approval.Status.APPROVED,
            Approval.Status.REJECTED
        ]

        for i, status in enumerate(statuses):
            expense = Expense.objects.create(
                user=self.employee,
                date=date.today(),
                vendor=f'Vendor {i}',
                description='Test',
                total_amount=Decimal('100.00'),
                currency=self.usd
            )

            approval = Approval.objects.create(
                expense=expense,
                approver=self.manager,
                level=Approval.ApprovalLevel.MANAGER,
                status=status
            )
            self.assertEqual(approval.status, status)

    def test_approval_levels(self):
        """Test approval levels"""
        manager_approval = Approval.objects.create(
            expense=self.expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER
        )

        finance_approval = Approval.objects.create(
            expense=self.expense,
            approver=self.finance_admin,
            level=Approval.ApprovalLevel.FINANCE
        )

        self.assertEqual(manager_approval.level, Approval.ApprovalLevel.MANAGER)
        self.assertEqual(finance_approval.level, Approval.ApprovalLevel.FINANCE)

    def test_approval_unique_together(self):
        """Test that expense-level combination must be unique"""
        Approval.objects.create(
            expense=self.expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER
        )

        with self.assertRaises(IntegrityError):
            Approval.objects.create(
                expense=self.expense,
                approver=self.manager,
                level=Approval.ApprovalLevel.MANAGER
            )

    def test_approval_with_comments(self):
        """Test approval can have comments"""
        approval = Approval.objects.create(
            expense=self.expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER,
            comments='Looks good, approved'
        )

        self.assertEqual(approval.comments, 'Looks good, approved')

    def test_approval_ordering(self):
        """Test approvals are ordered by level and created_at"""
        manager_approval = Approval.objects.create(
            expense=self.expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER
        )

        finance_approval = Approval.objects.create(
            expense=self.expense,
            approver=self.finance_admin,
            level=Approval.ApprovalLevel.FINANCE
        )

        approvals = Approval.objects.all()
        # Manager approval (level 1) should come before Finance (level 2)
        self.assertEqual(approvals[0], manager_approval)
        self.assertEqual(approvals[1], finance_approval)


class CommentModelTest(TestCase):
    """Test cases for Comment model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            exchange_rate_to_base=Decimal('1.000000'),
            is_base_currency=True
        )

        self.expense = Expense.objects.create(
            user=self.user,
            date=date.today(),
            vendor='Amazon',
            description='Office supplies',
            total_amount=Decimal('500.00'),
            currency=self.usd
        )

    def test_comment_creation(self):
        """Test comment can be created successfully"""
        comment = Comment.objects.create(
            expense=self.expense,
            user=self.user,
            text='This is a test comment'
        )

        self.assertEqual(comment.expense, self.expense)
        self.assertEqual(comment.user, self.user)
        self.assertEqual(comment.text, 'This is a test comment')

    def test_comment_str_method(self):
        """Test comment string representation"""
        comment = Comment.objects.create(
            expense=self.expense,
            user=self.user,
            text='Test comment'
        )

        expected = f"Comment by {self.user} on {self.expense}"
        self.assertEqual(str(comment), expected)

    def test_multiple_comments_on_expense(self):
        """Test multiple comments can be added to an expense"""
        user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='testpass123'
        )

        comment1 = Comment.objects.create(
            expense=self.expense,
            user=self.user,
            text='First comment'
        )

        comment2 = Comment.objects.create(
            expense=self.expense,
            user=user2,
            text='Second comment'
        )

        self.assertEqual(self.expense.comments.count(), 2)

    def test_comment_ordering(self):
        """Test comments are ordered by created_at ascending"""
        comment1 = Comment.objects.create(
            expense=self.expense,
            user=self.user,
            text='First comment'
        )

        comment2 = Comment.objects.create(
            expense=self.expense,
            user=self.user,
            text='Second comment'
        )

        comments = Comment.objects.all()
        # First comment should be first
        self.assertEqual(comments[0], comment1)
        self.assertEqual(comments[1], comment2)


class NotificationModelTest(TestCase):
    """Test cases for Notification model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            exchange_rate_to_base=Decimal('1.000000'),
            is_base_currency=True
        )

        self.expense = Expense.objects.create(
            user=self.user,
            date=date.today(),
            vendor='Amazon',
            description='Office supplies',
            total_amount=Decimal('500.00'),
            currency=self.usd
        )

    def test_notification_creation(self):
        """Test notification can be created successfully"""
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_SUBMITTED,
            title='Expense Submitted',
            message='Your expense has been submitted for approval',
            expense=self.expense
        )

        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.notification_type, Notification.NotificationType.EXPENSE_SUBMITTED)
        self.assertEqual(notification.title, 'Expense Submitted')
        self.assertFalse(notification.is_read)

    def test_notification_str_method(self):
        """Test notification string representation"""
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_APPROVED,
            title='Expense Approved',
            message='Your expense has been approved'
        )

        expected = f"Expense Approved - {self.user}"
        self.assertEqual(str(notification), expected)

    def test_all_notification_types(self):
        """Test all notification types"""
        notification_types = [
            Notification.NotificationType.EXPENSE_SUBMITTED,
            Notification.NotificationType.EXPENSE_APPROVED,
            Notification.NotificationType.EXPENSE_REJECTED,
            Notification.NotificationType.BUDGET_ALERT,
            Notification.NotificationType.COMMENT_ADDED
        ]

        for notif_type in notification_types:
            notification = Notification.objects.create(
                user=self.user,
                notification_type=notif_type,
                title=f'Test {notif_type}',
                message='Test message'
            )
            self.assertEqual(notification.notification_type, notif_type)

    def test_notification_default_is_read(self):
        """Test default is_read is False"""
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_SUBMITTED,
            title='Test',
            message='Test message'
        )

        self.assertFalse(notification.is_read)

    def test_notification_without_expense(self):
        """Test notification can exist without expense"""
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.BUDGET_ALERT,
            title='Budget Alert',
            message='Budget threshold exceeded'
        )

        self.assertIsNone(notification.expense)

    def test_notification_ordering(self):
        """Test notifications are ordered by created_at descending"""
        notification1 = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_SUBMITTED,
            title='First',
            message='First notification'
        )

        notification2 = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_APPROVED,
            title='Second',
            message='Second notification'
        )

        notifications = Notification.objects.all()
        # Most recent should be first
        self.assertEqual(notifications[0], notification2)
        self.assertEqual(notifications[1], notification1)


class AuditLogModelTest(TestCase):
    """Test cases for AuditLog model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

    def test_audit_log_creation(self):
        """Test audit log can be created successfully"""
        audit_log = AuditLog.objects.create(
            user=self.user,
            action_type=AuditLog.ActionType.CREATE,
            model_name='Expense',
            object_id=1,
            changes={'status': 'PENDING'},
            ip_address='192.168.1.1'
        )

        self.assertEqual(audit_log.user, self.user)
        self.assertEqual(audit_log.action_type, AuditLog.ActionType.CREATE)
        self.assertEqual(audit_log.model_name, 'Expense')
        self.assertEqual(audit_log.object_id, 1)
        self.assertEqual(audit_log.changes, {'status': 'PENDING'})
        self.assertEqual(audit_log.ip_address, '192.168.1.1')

    def test_audit_log_str_method(self):
        """Test audit log string representation"""
        audit_log = AuditLog.objects.create(
            user=self.user,
            action_type=AuditLog.ActionType.UPDATE,
            model_name='Expense',
            object_id=5
        )

        expected = f"{self.user} UPDATE Expense #5"
        self.assertEqual(str(audit_log), expected)

    def test_all_action_types(self):
        """Test all action types"""
        action_types = [
            AuditLog.ActionType.CREATE,
            AuditLog.ActionType.UPDATE,
            AuditLog.ActionType.DELETE,
            AuditLog.ActionType.APPROVE,
            AuditLog.ActionType.REJECT
        ]

        for action_type in action_types:
            audit_log = AuditLog.objects.create(
                user=self.user,
                action_type=action_type,
                model_name='Expense',
                object_id=1
            )
            self.assertEqual(audit_log.action_type, action_type)

    def test_audit_log_without_ip_address(self):
        """Test audit log can be created without IP address"""
        audit_log = AuditLog.objects.create(
            user=self.user,
            action_type=AuditLog.ActionType.CREATE,
            model_name='Expense',
            object_id=1
        )

        self.assertIsNone(audit_log.ip_address)

    def test_audit_log_default_changes(self):
        """Test default changes is empty dict"""
        audit_log = AuditLog.objects.create(
            user=self.user,
            action_type=AuditLog.ActionType.DELETE,
            model_name='Expense',
            object_id=1
        )

        self.assertEqual(audit_log.changes, {})

    def test_audit_log_with_changes(self):
        """Test audit log can store changes as JSON"""
        changes = {
            'old_value': 'PENDING',
            'new_value': 'APPROVED',
            'field': 'status'
        }

        audit_log = AuditLog.objects.create(
            user=self.user,
            action_type=AuditLog.ActionType.UPDATE,
            model_name='Expense',
            object_id=1,
            changes=changes
        )

        self.assertEqual(audit_log.changes, changes)

    def test_audit_log_ordering(self):
        """Test audit logs are ordered by timestamp descending"""
        log1 = AuditLog.objects.create(
            user=self.user,
            action_type=AuditLog.ActionType.CREATE,
            model_name='Expense',
            object_id=1
        )

        log2 = AuditLog.objects.create(
            user=self.user,
            action_type=AuditLog.ActionType.UPDATE,
            model_name='Expense',
            object_id=1
        )

        logs = AuditLog.objects.all()
        # Most recent should be first
        self.assertEqual(logs[0], log2)
        self.assertEqual(logs[1], log1)

    def test_audit_log_with_null_user(self):
        """Test audit log can exist with null user (for system actions)"""
        audit_log = AuditLog.objects.create(
            user=None,
            action_type=AuditLog.ActionType.CREATE,
            model_name='Expense',
            object_id=1
        )

        self.assertIsNone(audit_log.user)
