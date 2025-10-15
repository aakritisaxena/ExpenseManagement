"""
Integration tests for Expense Management System
Tests workflows that span multiple apps and models
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date, timedelta

from users.models import Department, User
from segments.models import Segment, Budget
from expenses.models import Currency, Expense, ExpenseSegmentAllocation
from approvals.models import Approval, Comment, Notification, AuditLog

User = get_user_model()


class ExpenseSubmissionWorkflowTest(TestCase):
    """Test the complete expense submission workflow"""

    def setUp(self):
        """Set up test data for expense submission"""
        # Create departments
        self.eng_dept = Department.objects.create(
            name='Engineering',
            code='ENG'
        )

        # Create users
        self.employee = User.objects.create_user(
            username='employee1',
            email='employee@test.com',
            password='testpass123',
            role=User.Role.EMPLOYEE,
            department=self.eng_dept,
            first_name='John',
            last_name='Doe'
        )

        self.manager = User.objects.create_user(
            username='manager1',
            email='manager@test.com',
            password='testpass123',
            role=User.Role.MANAGER,
            department=self.eng_dept
        )

        # Create currency
        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            exchange_rate_to_base=Decimal('1.000000'),
            is_base_currency=True
        )

        # Create segments
        self.travel_segment = Segment.objects.create(
            name='Travel',
            description='Travel expenses'
        )

        self.meals_segment = Segment.objects.create(
            name='Meals',
            description='Meal expenses'
        )

    def test_complete_expense_submission(self):
        """Test creating an expense with segment allocations"""
        # Create expense
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='United Airlines',
            description='Business trip to NYC',
            total_amount=Decimal('1000.00'),
            currency=self.usd,
            status=Expense.Status.PENDING
        )

        # Verify expense was created
        self.assertIsNotNone(expense.id)
        self.assertEqual(expense.user, self.employee)
        self.assertEqual(expense.amount_in_base_currency, Decimal('1000.00'))

        # Add segment allocations
        travel_allocation = ExpenseSegmentAllocation.objects.create(
            expense=expense,
            segment=self.travel_segment,
            percentage=Decimal('70.00'),
            notes='Flight tickets'
        )

        meals_allocation = ExpenseSegmentAllocation.objects.create(
            expense=expense,
            segment=self.meals_segment,
            percentage=Decimal('30.00'),
            notes='Airport meals'
        )

        # Verify allocations
        self.assertEqual(expense.segment_allocations.count(), 2)
        self.assertEqual(travel_allocation.amount, Decimal('700.00'))
        self.assertEqual(meals_allocation.amount, Decimal('300.00'))
        self.assertEqual(expense.get_total_allocated_percentage(), Decimal('100.00'))

    def test_expense_with_multiple_currencies(self):
        """Test expense submission with foreign currency"""
        # Create EUR currency
        eur = Currency.objects.create(
            code='EUR',
            name='Euro',
            symbol='€',
            exchange_rate_to_base=Decimal('1.100000')
        )

        # Create expense in EUR
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='European Vendor',
            description='Conference registration',
            total_amount=Decimal('500.00'),
            currency=eur
        )

        # Verify currency conversion
        self.assertEqual(expense.total_amount, Decimal('500.00'))
        self.assertEqual(expense.amount_in_base_currency, Decimal('550.00'))  # 500 * 1.1


class ApprovalWorkflowTest(TestCase):
    """Test the approval workflow from submission to approval"""

    def setUp(self):
        """Set up test data for approval workflow"""
        self.dept = Department.objects.create(name='Sales', code='SAL')

        self.employee = User.objects.create_user(
            username='employee',
            email='employee@test.com',
            password='testpass123',
            role=User.Role.EMPLOYEE,
            department=self.dept
        )

        self.manager = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123',
            role=User.Role.MANAGER,
            department=self.dept
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
            is_base_currency=True
        )

    def test_single_level_approval_workflow(self):
        """Test basic approval workflow with manager approval only"""
        # Employee submits expense
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Office Supplies Inc',
            description='Office supplies',
            total_amount=Decimal('200.00'),
            currency=self.usd,
            status=Expense.Status.PENDING
        )

        # Create manager approval
        approval = Approval.objects.create(
            expense=expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER,
            status=Approval.Status.PENDING
        )

        # Verify approval is pending
        self.assertEqual(approval.status, Approval.Status.PENDING)
        self.assertEqual(expense.approvals.count(), 1)

        # Manager approves
        approval.status = Approval.Status.APPROVED
        approval.comments = 'Approved - valid business expense'
        approval.save()

        # Update expense status
        expense.status = Expense.Status.APPROVED
        expense.save()

        # Verify approval
        approval.refresh_from_db()
        expense.refresh_from_db()
        self.assertEqual(approval.status, Approval.Status.APPROVED)
        self.assertEqual(expense.status, Expense.Status.APPROVED)

    def test_multi_level_approval_workflow(self):
        """Test multi-level approval with manager and finance"""
        # Employee submits large expense requiring finance approval
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Tech Equipment',
            description='New laptops for team',
            total_amount=Decimal('15000.00'),
            currency=self.usd,
            status=Expense.Status.PENDING,
            requires_finance_approval=True
        )

        # Create manager approval
        manager_approval = Approval.objects.create(
            expense=expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER,
            status=Approval.Status.PENDING
        )

        # Create finance approval
        finance_approval = Approval.objects.create(
            expense=expense,
            approver=self.finance_admin,
            level=Approval.ApprovalLevel.FINANCE,
            status=Approval.Status.PENDING
        )

        # Manager approves first
        manager_approval.status = Approval.Status.APPROVED
        manager_approval.comments = 'Team needs new equipment'
        manager_approval.save()

        # Expense still pending until finance approves
        expense.status = Expense.Status.PENDING
        expense.save()

        # Finance approves
        finance_approval.status = Approval.Status.APPROVED
        finance_approval.comments = 'Budget available, approved'
        finance_approval.save()

        # Now expense can be fully approved
        expense.status = Expense.Status.APPROVED
        expense.save()

        # Verify both approvals
        self.assertEqual(expense.approvals.count(), 2)
        self.assertEqual(
            expense.approvals.filter(status=Approval.Status.APPROVED).count(),
            2
        )

    def test_rejection_workflow(self):
        """Test expense rejection workflow"""
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Personal Vendor',
            description='Personal expense',
            total_amount=Decimal('500.00'),
            currency=self.usd,
            status=Expense.Status.PENDING
        )

        approval = Approval.objects.create(
            expense=expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER,
            status=Approval.Status.PENDING
        )

        # Manager rejects
        approval.status = Approval.Status.REJECTED
        approval.comments = 'This appears to be a personal expense'
        approval.save()

        expense.status = Expense.Status.REJECTED
        expense.save()

        # Verify rejection
        self.assertEqual(approval.status, Approval.Status.REJECTED)
        self.assertEqual(expense.status, Expense.Status.REJECTED)


class BudgetTrackingIntegrationTest(TestCase):
    """Test budget tracking with expenses"""

    def setUp(self):
        """Set up test data for budget tracking"""
        self.dept = Department.objects.create(name='Marketing', code='MKT')

        self.user = User.objects.create_user(
            username='marketer',
            email='marketer@test.com',
            password='testpass123',
            department=self.dept
        )

        self.segment = Segment.objects.create(
            name='Advertising',
            description='Advertising expenses'
        )

        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_base_currency=True
        )

        # Create budget
        self.budget = Budget.objects.create(
            segment=self.segment,
            allocated_amount=Decimal('10000.00'),
            period_type=Budget.PeriodType.MONTHLY,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            alert_threshold_percentage=80
        )

    def test_budget_tracking_with_expenses(self):
        """Test that budget tracks expenses correctly"""
        # Initially no spending
        self.assertEqual(self.budget.get_spent_amount(), 0)
        self.assertEqual(self.budget.get_remaining_budget(), Decimal('10000.00'))
        self.assertEqual(self.budget.get_percentage_used(), 0)

        # Create and approve expense 1
        expense1 = Expense.objects.create(
            user=self.user,
            date=date.today(),
            vendor='Google Ads',
            description='Online advertising',
            total_amount=Decimal('3000.00'),
            currency=self.usd,
            status=Expense.Status.APPROVED
        )

        ExpenseSegmentAllocation.objects.create(
            expense=expense1,
            segment=self.segment,
            percentage=Decimal('100.00')
        )

        # Check budget after first expense
        spent = self.budget.get_spent_amount()
        self.assertEqual(spent, Decimal('3000.00'))
        self.assertEqual(self.budget.get_remaining_budget(), Decimal('7000.00'))
        self.assertEqual(self.budget.get_percentage_used(), 30.0)
        self.assertFalse(self.budget.is_over_threshold())

        # Create and approve expense 2
        expense2 = Expense.objects.create(
            user=self.user,
            date=date.today(),
            vendor='Facebook Ads',
            description='Social media advertising',
            total_amount=Decimal('6000.00'),
            currency=self.usd,
            status=Expense.Status.APPROVED
        )

        ExpenseSegmentAllocation.objects.create(
            expense=expense2,
            segment=self.segment,
            percentage=Decimal('100.00')
        )

        # Check budget after second expense
        total_spent = self.budget.get_spent_amount()
        self.assertEqual(total_spent, Decimal('9000.00'))
        self.assertEqual(self.budget.get_remaining_budget(), Decimal('1000.00'))
        self.assertEqual(self.budget.get_percentage_used(), 90.0)
        self.assertTrue(self.budget.is_over_threshold())  # Over 80%

    def test_budget_with_partial_allocations(self):
        """Test budget tracking with partial segment allocations"""
        expense = Expense.objects.create(
            user=self.user,
            date=date.today(),
            vendor='Mixed Vendor',
            description='Multiple categories',
            total_amount=Decimal('1000.00'),
            currency=self.usd,
            status=Expense.Status.APPROVED
        )

        # Only 50% allocated to this segment
        ExpenseSegmentAllocation.objects.create(
            expense=expense,
            segment=self.segment,
            percentage=Decimal('50.00')
        )

        # Only $500 should count toward budget
        self.assertEqual(self.budget.get_spent_amount(), Decimal('500.00'))
        self.assertEqual(self.budget.get_percentage_used(), 5.0)


class MultiSegmentAllocationTest(TestCase):
    """Test complex multi-segment allocation scenarios"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='user',
            email='user@test.com',
            password='testpass123'
        )

        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_base_currency=True
        )

        self.travel = Segment.objects.create(name='Travel')
        self.meals = Segment.objects.create(name='Meals')
        self.lodging = Segment.objects.create(name='Lodging')

    def test_three_way_split(self):
        """Test expense split across three segments"""
        expense = Expense.objects.create(
            user=self.user,
            date=date.today(),
            vendor='Conference',
            description='Annual conference expenses',
            total_amount=Decimal('3000.00'),
            currency=self.usd
        )

        # Split: 50% travel, 30% lodging, 20% meals
        travel_alloc = ExpenseSegmentAllocation.objects.create(
            expense=expense,
            segment=self.travel,
            percentage=Decimal('50.00')
        )

        lodging_alloc = ExpenseSegmentAllocation.objects.create(
            expense=expense,
            segment=self.lodging,
            percentage=Decimal('30.00')
        )

        meals_alloc = ExpenseSegmentAllocation.objects.create(
            expense=expense,
            segment=self.meals,
            percentage=Decimal('20.00')
        )

        # Verify amounts
        self.assertEqual(travel_alloc.amount, Decimal('1500.00'))
        self.assertEqual(lodging_alloc.amount, Decimal('900.00'))
        self.assertEqual(meals_alloc.amount, Decimal('600.00'))
        self.assertEqual(expense.get_total_allocated_percentage(), Decimal('100.00'))

        # Verify total equals expense amount
        total = (travel_alloc.amount + lodging_alloc.amount + meals_alloc.amount)
        self.assertEqual(total, expense.total_amount)


class NotificationAndAuditTest(TestCase):
    """Test notification and audit log creation"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='user',
            email='user@test.com',
            password='testpass123'
        )

        self.manager = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123',
            role=User.Role.MANAGER
        )

        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_base_currency=True
        )

    def test_notification_creation_workflow(self):
        """Test creating notifications for expense workflow"""
        # Create expense
        expense = Expense.objects.create(
            user=self.user,
            date=date.today(),
            vendor='Test Vendor',
            description='Test expense',
            total_amount=Decimal('100.00'),
            currency=self.usd
        )

        # Create notification for employee
        employee_notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_SUBMITTED,
            title='Expense Submitted',
            message='Your expense has been submitted for approval',
            expense=expense
        )

        # Create notification for manager
        manager_notification = Notification.objects.create(
            user=self.manager,
            notification_type=Notification.NotificationType.EXPENSE_SUBMITTED,
            title='New Expense to Review',
            message=f'{self.user.get_full_name() or self.user.username} submitted an expense',
            expense=expense
        )

        # Verify notifications
        self.assertEqual(Notification.objects.count(), 2)
        self.assertFalse(employee_notification.is_read)
        self.assertFalse(manager_notification.is_read)

        # Approve expense
        approval = Approval.objects.create(
            expense=expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER,
            status=Approval.Status.APPROVED
        )

        # Create approval notification
        approval_notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.EXPENSE_APPROVED,
            title='Expense Approved',
            message=f'Your expense has been approved by {self.manager.username}',
            expense=expense
        )

        self.assertEqual(Notification.objects.filter(user=self.user).count(), 2)

    def test_audit_log_creation(self):
        """Test audit log creation for various actions"""
        # Create expense
        expense = Expense.objects.create(
            user=self.user,
            date=date.today(),
            vendor='Test Vendor',
            description='Test expense',
            total_amount=Decimal('100.00'),
            currency=self.usd
        )

        # Log expense creation
        create_log = AuditLog.objects.create(
            user=self.user,
            action_type=AuditLog.ActionType.CREATE,
            model_name='Expense',
            object_id=expense.id,
            changes={'amount': '100.00', 'vendor': 'Test Vendor'},
            ip_address='127.0.0.1'
        )

        # Update expense
        expense.total_amount = Decimal('150.00')
        expense.save()

        # Log expense update
        update_log = AuditLog.objects.create(
            user=self.user,
            action_type=AuditLog.ActionType.UPDATE,
            model_name='Expense',
            object_id=expense.id,
            changes={
                'field': 'total_amount',
                'old_value': '100.00',
                'new_value': '150.00'
            },
            ip_address='127.0.0.1'
        )

        # Approve expense
        approval = Approval.objects.create(
            expense=expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER,
            status=Approval.Status.APPROVED
        )

        # Log approval
        approve_log = AuditLog.objects.create(
            user=self.manager,
            action_type=AuditLog.ActionType.APPROVE,
            model_name='Expense',
            object_id=expense.id,
            changes={'approver': self.manager.username, 'level': 'MANAGER'},
            ip_address='127.0.0.1'
        )

        # Verify audit trail - check that our manually created logs exist
        logs = AuditLog.objects.filter(model_name='Expense', object_id=expense.id)
        self.assertGreaterEqual(logs.count(), 3)  # At least 3 logs
        self.assertGreaterEqual(logs.filter(action_type=AuditLog.ActionType.CREATE).count(), 1)
        self.assertGreaterEqual(logs.filter(action_type=AuditLog.ActionType.UPDATE).count(), 1)
        self.assertGreaterEqual(logs.filter(action_type=AuditLog.ActionType.APPROVE).count(), 1)

        # Verify specific logs we created
        self.assertIn(create_log, logs)
        self.assertIn(update_log, logs)
        self.assertIn(approve_log, logs)


class CommentWorkflowTest(TestCase):
    """Test comment and discussion workflow"""

    def setUp(self):
        """Set up test data"""
        self.employee = User.objects.create_user(
            username='employee',
            email='employee@test.com',
            password='testpass123'
        )

        self.manager = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123',
            role=User.Role.MANAGER
        )

        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_base_currency=True
        )

    def test_comment_discussion(self):
        """Test comment discussion on expense"""
        # Create expense
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Unclear Vendor',
            description='Needs clarification',
            total_amount=Decimal('500.00'),
            currency=self.usd
        )

        # Manager asks for clarification
        manager_comment = Comment.objects.create(
            expense=expense,
            user=self.manager,
            text='Can you provide more details about this expense?'
        )

        # Employee responds
        employee_comment = Comment.objects.create(
            expense=expense,
            user=self.employee,
            text='This was for the client meeting supplies as discussed in our last standup'
        )

        # Manager follows up
        manager_followup = Comment.objects.create(
            expense=expense,
            user=self.manager,
            text='Thanks for clarifying. Approved.'
        )

        # Verify comment thread
        comments = expense.comments.all()
        self.assertEqual(comments.count(), 3)
        self.assertEqual(comments[0], manager_comment)
        self.assertEqual(comments[1], employee_comment)
        self.assertEqual(comments[2], manager_followup)
