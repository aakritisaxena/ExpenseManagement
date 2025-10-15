from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from datetime import date
from .models import Currency, Expense, ExpenseSegmentAllocation
from segments.models import Segment
from users.models import Department

User = get_user_model()


class CurrencyModelTest(TestCase):
    """Test cases for Currency model"""

    def setUp(self):
        """Set up test data"""
        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            exchange_rate_to_base=Decimal('1.000000'),
            is_base_currency=True
        )

    def test_currency_creation(self):
        """Test currency can be created successfully"""
        self.assertEqual(self.usd.code, 'USD')
        self.assertEqual(self.usd.name, 'US Dollar')
        self.assertEqual(self.usd.symbol, '$')
        self.assertEqual(self.usd.exchange_rate_to_base, Decimal('1.000000'))
        self.assertTrue(self.usd.is_base_currency)

    def test_currency_str_method(self):
        """Test currency string representation"""
        self.assertEqual(str(self.usd), 'USD - US Dollar')

    def test_currency_unique_code(self):
        """Test that currency code must be unique"""
        with self.assertRaises(IntegrityError):
            Currency.objects.create(
                code='USD',
                name='US Dollar 2',
                symbol='$'
            )

    def test_multiple_currencies(self):
        """Test creating multiple currencies with exchange rates"""
        eur = Currency.objects.create(
            code='EUR',
            name='Euro',
            symbol='€',
            exchange_rate_to_base=Decimal('1.100000'),
            is_base_currency=False
        )

        gbp = Currency.objects.create(
            code='GBP',
            name='British Pound',
            symbol='£',
            exchange_rate_to_base=Decimal('1.250000'),
            is_base_currency=False
        )

        self.assertEqual(Currency.objects.count(), 3)
        self.assertEqual(eur.exchange_rate_to_base, Decimal('1.100000'))
        self.assertEqual(gbp.exchange_rate_to_base, Decimal('1.250000'))

    def test_default_exchange_rate(self):
        """Test default exchange rate is 1.0"""
        inr = Currency.objects.create(
            code='INR',
            name='Indian Rupee',
            symbol='₹'
        )

        self.assertEqual(inr.exchange_rate_to_base, Decimal('1.0'))

    def test_default_is_base_currency(self):
        """Test default is_base_currency is False"""
        eur = Currency.objects.create(
            code='EUR',
            name='Euro',
            symbol='€'
        )

        self.assertFalse(eur.is_base_currency)


class ExpenseModelTest(TestCase):
    """Test cases for Expense model"""

    def setUp(self):
        """Set up test data"""
        self.department = Department.objects.create(
            name='Engineering',
            code='ENG'
        )

        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            department=self.department
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
            total_amount=Decimal('150.00'),
            currency=self.usd,
            status=Expense.Status.PENDING
        )

    def test_expense_creation(self):
        """Test expense can be created successfully"""
        self.assertEqual(self.expense.user, self.user)
        self.assertEqual(self.expense.vendor, 'Amazon')
        self.assertEqual(self.expense.total_amount, Decimal('150.00'))
        self.assertEqual(self.expense.currency, self.usd)
        self.assertEqual(self.expense.status, Expense.Status.PENDING)

    def test_expense_str_method(self):
        """Test expense string representation"""
        expected = f"Amazon - $150.00 ({date.today()})"
        self.assertEqual(str(self.expense), expected)

    def test_expense_auto_calculate_base_currency(self):
        """Test that amount_in_base_currency is auto-calculated"""
        # For USD with exchange rate 1.0, should be same as total_amount
        self.assertEqual(self.expense.amount_in_base_currency, Decimal('150.00'))

        # Create expense with different currency
        eur = Currency.objects.create(
            code='EUR',
            name='Euro',
            symbol='€',
            exchange_rate_to_base=Decimal('1.100000')
        )

        eur_expense = Expense.objects.create(
            user=self.user,
            date=date.today(),
            vendor='Vendor',
            description='Test',
            total_amount=Decimal('100.00'),
            currency=eur
        )

        # 100 EUR * 1.1 = 110 in base currency
        self.assertEqual(eur_expense.amount_in_base_currency, Decimal('110.00'))

    def test_expense_default_status(self):
        """Test default status is PENDING"""
        expense = Expense.objects.create(
            user=self.user,
            date=date.today(),
            vendor='Test Vendor',
            description='Test',
            total_amount=Decimal('100.00'),
            currency=self.usd
        )

        self.assertEqual(expense.status, Expense.Status.PENDING)

    def test_all_expense_statuses(self):
        """Test all expense statuses"""
        statuses = [
            Expense.Status.DRAFT,
            Expense.Status.PENDING,
            Expense.Status.APPROVED,
            Expense.Status.REJECTED
        ]

        for status in statuses:
            expense = Expense.objects.create(
                user=self.user,
                date=date.today(),
                vendor=f'Vendor {status}',
                description='Test',
                total_amount=Decimal('100.00'),
                currency=self.usd,
                status=status
            )
            self.assertEqual(expense.status, status)

    def test_expense_requires_finance_approval(self):
        """Test requires_finance_approval field"""
        self.assertFalse(self.expense.requires_finance_approval)

        expensive = Expense.objects.create(
            user=self.user,
            date=date.today(),
            vendor='Big Vendor',
            description='Large purchase',
            total_amount=Decimal('10000.00'),
            currency=self.usd,
            requires_finance_approval=True
        )

        self.assertTrue(expensive.requires_finance_approval)

    def test_get_total_allocated_percentage(self):
        """Test get_total_allocated_percentage method"""
        # Initially should be 0
        self.assertEqual(self.expense.get_total_allocated_percentage(), 0)

    def test_expense_ordering(self):
        """Test expenses are ordered by date and created_at descending"""
        earlier_expense = Expense.objects.create(
            user=self.user,
            date=date.today(),
            vendor='Earlier',
            description='Test',
            total_amount=Decimal('50.00'),
            currency=self.usd
        )

        expenses = Expense.objects.all()
        # Most recent should be first
        self.assertEqual(expenses[0], earlier_expense)


class ExpenseSegmentAllocationModelTest(TestCase):
    """Test cases for ExpenseSegmentAllocation model"""

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
            total_amount=Decimal('1000.00'),
            currency=self.usd
        )

        self.travel_segment = Segment.objects.create(
            name='Travel',
            description='Travel expenses'
        )

        self.meals_segment = Segment.objects.create(
            name='Meals',
            description='Meal expenses'
        )

    def test_allocation_creation(self):
        """Test expense segment allocation can be created"""
        allocation = ExpenseSegmentAllocation.objects.create(
            expense=self.expense,
            segment=self.travel_segment,
            percentage=Decimal('30.00')
        )

        self.assertEqual(allocation.expense, self.expense)
        self.assertEqual(allocation.segment, self.travel_segment)
        self.assertEqual(allocation.percentage, Decimal('30.00'))

    def test_allocation_auto_calculate_amount(self):
        """Test that amount is auto-calculated from percentage"""
        allocation = ExpenseSegmentAllocation.objects.create(
            expense=self.expense,
            segment=self.travel_segment,
            percentage=Decimal('30.00')
        )

        # 30% of 1000 = 300
        self.assertEqual(allocation.amount, Decimal('300.00'))

    def test_allocation_str_method(self):
        """Test allocation string representation"""
        allocation = ExpenseSegmentAllocation.objects.create(
            expense=self.expense,
            segment=self.travel_segment,
            percentage=Decimal('30.00')
        )

        expected = f"{self.expense} - Travel: 30.00%"
        self.assertEqual(str(allocation), expected)

    def test_multiple_allocations(self):
        """Test creating multiple allocations for one expense"""
        alloc1 = ExpenseSegmentAllocation.objects.create(
            expense=self.expense,
            segment=self.travel_segment,
            percentage=Decimal('30.00')
        )

        alloc2 = ExpenseSegmentAllocation.objects.create(
            expense=self.expense,
            segment=self.meals_segment,
            percentage=Decimal('70.00')
        )

        self.assertEqual(self.expense.segment_allocations.count(), 2)
        self.assertEqual(alloc1.amount, Decimal('300.00'))
        self.assertEqual(alloc2.amount, Decimal('700.00'))

    def test_allocation_unique_together(self):
        """Test that expense-segment combination must be unique"""
        ExpenseSegmentAllocation.objects.create(
            expense=self.expense,
            segment=self.travel_segment,
            percentage=Decimal('30.00')
        )

        with self.assertRaises(IntegrityError):
            ExpenseSegmentAllocation.objects.create(
                expense=self.expense,
                segment=self.travel_segment,
                percentage=Decimal('40.00')
            )

    def test_allocation_with_notes(self):
        """Test allocation can have notes"""
        allocation = ExpenseSegmentAllocation.objects.create(
            expense=self.expense,
            segment=self.travel_segment,
            percentage=Decimal('100.00'),
            notes='Full amount for business travel'
        )

        self.assertEqual(allocation.notes, 'Full amount for business travel')

    def test_allocation_percentage_calculation(self):
        """Test various percentage calculations"""
        test_cases = [
            (Decimal('25.00'), Decimal('250.00')),
            (Decimal('50.00'), Decimal('500.00')),
            (Decimal('75.50'), Decimal('755.00')),
            (Decimal('100.00'), Decimal('1000.00'))
        ]

        for percentage, expected_amount in test_cases:
            allocation = ExpenseSegmentAllocation.objects.create(
                expense=self.expense,
                segment=Segment.objects.create(name=f'Segment {percentage}'),
                percentage=percentage
            )
            self.assertEqual(allocation.amount, expected_amount)

    def test_get_total_allocated_percentage_with_allocations(self):
        """Test get_total_allocated_percentage with allocations"""
        ExpenseSegmentAllocation.objects.create(
            expense=self.expense,
            segment=self.travel_segment,
            percentage=Decimal('30.00')
        )

        ExpenseSegmentAllocation.objects.create(
            expense=self.expense,
            segment=self.meals_segment,
            percentage=Decimal('70.00')
        )

        total_percentage = self.expense.get_total_allocated_percentage()
        self.assertEqual(total_percentage, Decimal('100.00'))
