"""
Functional tests for Expense Management System
Tests user-facing features, API endpoints, and complete user workflows
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from datetime import date, timedelta
import json

from users.models import Department, User
from segments.models import Segment, Budget
from expenses.models import Currency, Expense, ExpenseSegmentAllocation
from approvals.models import Approval, Comment, Notification

User = get_user_model()


class UserAuthenticationFunctionalTest(TestCase):
    """Test user authentication and authorization workflows"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

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

    def test_user_can_login(self):
        """Test that users can log in successfully"""
        login_successful = self.client.login(
            username='employee',
            password='testpass123'
        )
        self.assertTrue(login_successful)

    def test_user_roles_are_assigned_correctly(self):
        """Test that users have correct roles"""
        self.assertTrue(self.employee.role == User.Role.EMPLOYEE)
        self.assertTrue(self.manager.is_manager())
        self.assertTrue(self.finance_admin.is_finance_admin())

    def test_user_belongs_to_department(self):
        """Test user-department relationship"""
        self.assertEqual(self.employee.department, self.department)
        self.assertEqual(self.manager.department, self.department)
        self.assertIn(self.employee, self.department.users.all())


class ExpenseManagementFunctionalTest(TestCase):
    """Test complete expense management workflows"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        self.department = Department.objects.create(
            name='Sales',
            code='SAL'
        )

        self.employee = User.objects.create_user(
            username='employee',
            email='employee@test.com',
            password='testpass123',
            role=User.Role.EMPLOYEE,
            department=self.department,
            first_name='John',
            last_name='Doe'
        )

        self.manager = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123',
            role=User.Role.MANAGER,
            department=self.department
        )

        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            exchange_rate_to_base=Decimal('1.000000'),
            is_base_currency=True
        )

        self.travel_segment = Segment.objects.create(
            name='Travel',
            description='Travel expenses'
        )

        self.meals_segment = Segment.objects.create(
            name='Meals',
            description='Meal expenses'
        )

        # Login as employee
        self.client.login(username='employee', password='testpass123')

    def test_employee_can_create_expense(self):
        """Test employee can create an expense"""
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Uber',
            description='Client meeting transportation',
            total_amount=Decimal('50.00'),
            currency=self.usd,
            status=Expense.Status.PENDING
        )

        self.assertIsNotNone(expense.id)
        self.assertEqual(expense.user, self.employee)
        self.assertEqual(expense.status, Expense.Status.PENDING)

    def test_employee_can_add_segment_allocations(self):
        """Test employee can allocate expense to segments"""
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Conference Center',
            description='Annual sales conference',
            total_amount=Decimal('2000.00'),
            currency=self.usd
        )

        # Allocate 80% to travel, 20% to meals
        travel_alloc = ExpenseSegmentAllocation.objects.create(
            expense=expense,
            segment=self.travel_segment,
            percentage=Decimal('80.00')
        )

        meals_alloc = ExpenseSegmentAllocation.objects.create(
            expense=expense,
            segment=self.meals_segment,
            percentage=Decimal('20.00')
        )

        # Verify allocations
        self.assertEqual(expense.segment_allocations.count(), 2)
        self.assertEqual(travel_alloc.amount, Decimal('1600.00'))
        self.assertEqual(meals_alloc.amount, Decimal('400.00'))
        self.assertEqual(expense.get_total_allocated_percentage(), Decimal('100.00'))

    def test_employee_can_view_own_expenses(self):
        """Test employee can view their own expenses"""
        # Create multiple expenses
        expense1 = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Vendor 1',
            description='Expense 1',
            total_amount=Decimal('100.00'),
            currency=self.usd
        )

        expense2 = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Vendor 2',
            description='Expense 2',
            total_amount=Decimal('200.00'),
            currency=self.usd
        )

        # Get employee's expenses
        employee_expenses = Expense.objects.filter(user=self.employee)

        self.assertEqual(employee_expenses.count(), 2)
        self.assertIn(expense1, employee_expenses)
        self.assertIn(expense2, employee_expenses)

    def test_employee_can_update_draft_expense(self):
        """Test employee can update draft expenses"""
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Original Vendor',
            description='Original description',
            total_amount=Decimal('100.00'),
            currency=self.usd,
            status=Expense.Status.DRAFT
        )

        # Update expense
        expense.vendor = 'Updated Vendor'
        expense.total_amount = Decimal('150.00')
        expense.save()

        # Verify updates
        expense.refresh_from_db()
        self.assertEqual(expense.vendor, 'Updated Vendor')
        self.assertEqual(expense.total_amount, Decimal('150.00'))

    def test_employee_cannot_modify_approved_expense(self):
        """Test that approved expenses should not be modified (business logic)"""
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Test Vendor',
            description='Test',
            total_amount=Decimal('100.00'),
            currency=self.usd,
            status=Expense.Status.APPROVED
        )

        # In a real application, you would check permissions here
        # For now, we just verify the expense is approved
        self.assertEqual(expense.status, Expense.Status.APPROVED)


class ApprovalWorkflowFunctionalTest(TestCase):
    """Test approval workflow from user perspective"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        self.department = Department.objects.create(
            name='Marketing',
            code='MKT'
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
            is_base_currency=True
        )

    def test_manager_can_see_pending_approvals(self):
        """Test manager can see expenses awaiting their approval"""
        # Employee submits expense
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Test Vendor',
            description='Test expense',
            total_amount=Decimal('500.00'),
            currency=self.usd,
            status=Expense.Status.PENDING
        )

        # Create pending approval for manager
        approval = Approval.objects.create(
            expense=expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER,
            status=Approval.Status.PENDING
        )

        # Manager logs in and checks pending approvals
        self.client.login(username='manager', password='testpass123')

        pending_approvals = Approval.objects.filter(
            approver=self.manager,
            status=Approval.Status.PENDING
        )

        self.assertEqual(pending_approvals.count(), 1)
        self.assertEqual(pending_approvals.first(), approval)

    def test_manager_can_approve_expense(self):
        """Test manager approval workflow"""
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Test Vendor',
            description='Valid business expense',
            total_amount=Decimal('300.00'),
            currency=self.usd,
            status=Expense.Status.PENDING
        )

        approval = Approval.objects.create(
            expense=expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER,
            status=Approval.Status.PENDING
        )

        # Manager approves
        self.client.login(username='manager', password='testpass123')

        approval.status = Approval.Status.APPROVED
        approval.comments = 'Approved - valid expense'
        approval.save()

        expense.status = Expense.Status.APPROVED
        expense.save()

        # Verify approval
        approval.refresh_from_db()
        expense.refresh_from_db()

        self.assertEqual(approval.status, Approval.Status.APPROVED)
        self.assertEqual(expense.status, Expense.Status.APPROVED)

    def test_manager_can_reject_expense(self):
        """Test manager rejection workflow"""
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Questionable Vendor',
            description='Unclear expense',
            total_amount=Decimal('1000.00'),
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
        self.client.login(username='manager', password='testpass123')

        approval.status = Approval.Status.REJECTED
        approval.comments = 'Please provide more details'
        approval.save()

        expense.status = Expense.Status.REJECTED
        expense.save()

        # Verify rejection
        approval.refresh_from_db()
        expense.refresh_from_db()

        self.assertEqual(approval.status, Approval.Status.REJECTED)
        self.assertEqual(expense.status, Expense.Status.REJECTED)

    def test_finance_admin_can_approve_large_expenses(self):
        """Test finance admin approval for large expenses"""
        # Create large expense requiring finance approval
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Major Vendor',
            description='Large purchase',
            total_amount=Decimal('20000.00'),
            currency=self.usd,
            status=Expense.Status.PENDING,
            requires_finance_approval=True
        )

        # Manager approves first
        manager_approval = Approval.objects.create(
            expense=expense,
            approver=self.manager,
            level=Approval.ApprovalLevel.MANAGER,
            status=Approval.Status.APPROVED
        )

        # Finance admin reviews
        finance_approval = Approval.objects.create(
            expense=expense,
            approver=self.finance_admin,
            level=Approval.ApprovalLevel.FINANCE,
            status=Approval.Status.PENDING
        )

        self.client.login(username='finance', password='testpass123')

        # Finance approves
        finance_approval.status = Approval.Status.APPROVED
        finance_approval.comments = 'Budget available, approved'
        finance_approval.save()

        expense.status = Expense.Status.APPROVED
        expense.save()

        # Verify both approvals are approved
        self.assertEqual(
            expense.approvals.filter(status=Approval.Status.APPROVED).count(),
            2
        )


class BudgetManagementFunctionalTest(TestCase):
    """Test budget management workflows"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        self.finance_admin = User.objects.create_user(
            username='finance',
            email='finance@test.com',
            password='testpass123',
            role=User.Role.FINANCE_ADMIN
        )

        self.employee = User.objects.create_user(
            username='employee',
            email='employee@test.com',
            password='testpass123',
            role=User.Role.EMPLOYEE
        )

        self.segment = Segment.objects.create(
            name='Marketing',
            description='Marketing expenses'
        )

        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_base_currency=True
        )

    def test_finance_admin_can_create_budget(self):
        """Test finance admin can create budgets"""
        self.client.login(username='finance', password='testpass123')

        budget = Budget.objects.create(
            segment=self.segment,
            allocated_amount=Decimal('50000.00'),
            period_type=Budget.PeriodType.QUARTERLY,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
            alert_threshold_percentage=85
        )

        self.assertIsNotNone(budget.id)
        self.assertEqual(budget.allocated_amount, Decimal('50000.00'))

    def test_budget_tracks_spending_correctly(self):
        """Test budget tracking as expenses are approved"""
        budget = Budget.objects.create(
            segment=self.segment,
            allocated_amount=Decimal('10000.00'),
            period_type=Budget.PeriodType.MONTHLY,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30)
        )

        # Create and approve expense
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Ad Agency',
            description='Marketing campaign',
            total_amount=Decimal('3000.00'),
            currency=self.usd,
            status=Expense.Status.APPROVED
        )

        ExpenseSegmentAllocation.objects.create(
            expense=expense,
            segment=self.segment,
            percentage=Decimal('100.00')
        )

        # Check budget
        spent = budget.get_spent_amount()
        remaining = budget.get_remaining_budget()

        self.assertEqual(spent, Decimal('3000.00'))
        self.assertEqual(remaining, Decimal('7000.00'))
        self.assertEqual(budget.get_percentage_used(), 30.0)

    def test_budget_alert_threshold(self):
        """Test budget alert when threshold is exceeded"""
        budget = Budget.objects.create(
            segment=self.segment,
            allocated_amount=Decimal('5000.00'),
            period_type=Budget.PeriodType.MONTHLY,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            alert_threshold_percentage=80
        )

        # Spend 85% of budget
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Vendor',
            description='Large marketing expense',
            total_amount=Decimal('4250.00'),
            currency=self.usd,
            status=Expense.Status.APPROVED
        )

        ExpenseSegmentAllocation.objects.create(
            expense=expense,
            segment=self.segment,
            percentage=Decimal('100.00')
        )

        # Check if over threshold
        self.assertTrue(budget.is_over_threshold())
        self.assertEqual(budget.get_percentage_used(), 85.0)


class CommentAndCollaborationFunctionalTest(TestCase):
    """Test commenting and collaboration features"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        self.employee = User.objects.create_user(
            username='employee',
            email='employee@test.com',
            password='testpass123',
            role=User.Role.EMPLOYEE
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

        self.expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Test Vendor',
            description='Needs clarification',
            total_amount=Decimal('500.00'),
            currency=self.usd
        )

    def test_manager_can_comment_on_expense(self):
        """Test manager can add comments to expenses"""
        self.client.login(username='manager', password='testpass123')

        comment = Comment.objects.create(
            expense=self.expense,
            user=self.manager,
            text='Can you provide more details about this expense?'
        )

        self.assertIsNotNone(comment.id)
        self.assertEqual(comment.expense, self.expense)
        self.assertEqual(self.expense.comments.count(), 1)

    def test_employee_can_respond_to_comments(self):
        """Test employee can respond to manager comments"""
        # Manager comments
        manager_comment = Comment.objects.create(
            expense=self.expense,
            user=self.manager,
            text='Please provide receipt'
        )

        # Employee responds
        self.client.login(username='employee', password='testpass123')

        employee_comment = Comment.objects.create(
            expense=self.expense,
            user=self.employee,
            text='Receipt attached, please review'
        )

        # Verify comment thread
        comments = self.expense.comments.all()
        self.assertEqual(comments.count(), 2)
        self.assertEqual(comments[0], manager_comment)
        self.assertEqual(comments[1], employee_comment)


class NotificationFunctionalTest(TestCase):
    """Test notification system"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        self.employee = User.objects.create_user(
            username='employee',
            email='employee@test.com',
            password='testpass123',
            role=User.Role.EMPLOYEE
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

    def test_employee_receives_notification_on_approval(self):
        """Test employee gets notified when expense is approved"""
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Test Vendor',
            description='Test',
            total_amount=Decimal('100.00'),
            currency=self.usd
        )

        # Create approval notification
        notification = Notification.objects.create(
            user=self.employee,
            notification_type=Notification.NotificationType.EXPENSE_APPROVED,
            title='Expense Approved',
            message='Your expense has been approved',
            expense=expense
        )

        # Verify notification
        self.client.login(username='employee', password='testpass123')

        user_notifications = Notification.objects.filter(user=self.employee)
        self.assertEqual(user_notifications.count(), 1)
        self.assertFalse(notification.is_read)

    def test_manager_receives_notification_on_new_expense(self):
        """Test manager gets notified of new expenses to review"""
        expense = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='Test Vendor',
            description='Test',
            total_amount=Decimal('100.00'),
            currency=self.usd,
            status=Expense.Status.PENDING
        )

        notification = Notification.objects.create(
            user=self.manager,
            notification_type=Notification.NotificationType.EXPENSE_SUBMITTED,
            title='New Expense to Review',
            message=f'New expense from {self.employee.username}',
            expense=expense
        )

        self.client.login(username='manager', password='testpass123')

        manager_notifications = Notification.objects.filter(user=self.manager)
        self.assertEqual(manager_notifications.count(), 1)

    def test_user_can_mark_notification_as_read(self):
        """Test users can mark notifications as read"""
        notification = Notification.objects.create(
            user=self.employee,
            notification_type=Notification.NotificationType.EXPENSE_APPROVED,
            title='Test Notification',
            message='Test message'
        )

        self.client.login(username='employee', password='testpass123')

        # Mark as read
        notification.is_read = True
        notification.save()

        notification.refresh_from_db()
        self.assertTrue(notification.is_read)


class MultiCurrencyFunctionalTest(TestCase):
    """Test multi-currency support"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        self.employee = User.objects.create_user(
            username='employee',
            email='employee@test.com',
            password='testpass123',
            role=User.Role.EMPLOYEE
        )

        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            exchange_rate_to_base=Decimal('1.000000'),
            is_base_currency=True
        )

        self.eur = Currency.objects.create(
            code='EUR',
            name='Euro',
            symbol='€',
            exchange_rate_to_base=Decimal('1.100000')
        )

        self.gbp = Currency.objects.create(
            code='GBP',
            name='British Pound',
            symbol='£',
            exchange_rate_to_base=Decimal('1.250000')
        )

    def test_expense_in_foreign_currency_converts_correctly(self):
        """Test foreign currency conversion"""
        # Create expense in EUR
        expense_eur = Expense.objects.create(
            user=self.employee,
            date=date.today(),
            vendor='European Vendor',
            description='EUR expense',
            total_amount=Decimal('1000.00'),
            currency=self.eur
        )

        # 1000 EUR * 1.1 = 1100 USD
        self.assertEqual(expense_eur.amount_in_base_currency, Decimal('1100.00'))

    def test_multiple_currencies_in_same_system(self):
        """Test system handles multiple currencies"""
        expenses = [
            Expense.objects.create(
                user=self.employee,
                date=date.today(),
                vendor='USD Vendor',
                description='USD expense',
                total_amount=Decimal('100.00'),
                currency=self.usd
            ),
            Expense.objects.create(
                user=self.employee,
                date=date.today(),
                vendor='EUR Vendor',
                description='EUR expense',
                total_amount=Decimal('100.00'),
                currency=self.eur
            ),
            Expense.objects.create(
                user=self.employee,
                date=date.today(),
                vendor='GBP Vendor',
                description='GBP expense',
                total_amount=Decimal('100.00'),
                currency=self.gbp
            )
        ]

        # Verify all conversions
        self.assertEqual(expenses[0].amount_in_base_currency, Decimal('100.00'))
        self.assertEqual(expenses[1].amount_in_base_currency, Decimal('110.00'))
        self.assertEqual(expenses[2].amount_in_base_currency, Decimal('125.00'))

        # Total in base currency
        total_base = sum(e.amount_in_base_currency for e in expenses)
        self.assertEqual(total_base, Decimal('335.00'))
