from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from decimal import Decimal
from datetime import date, timedelta
from .models import Segment, Budget
from users.models import Department

User = get_user_model()


class SegmentModelTest(TestCase):
    """Test cases for Segment model"""

    def setUp(self):
        """Set up test data"""
        self.department = Department.objects.create(
            name='Engineering',
            code='ENG'
        )

        self.segment = Segment.objects.create(
            name='Travel',
            description='Travel expenses'
        )

    def test_segment_creation(self):
        """Test segment can be created successfully"""
        self.assertEqual(self.segment.name, 'Travel')
        self.assertEqual(self.segment.description, 'Travel expenses')
        self.assertTrue(self.segment.is_active)

    def test_segment_str_method(self):
        """Test segment string representation"""
        self.assertEqual(str(self.segment), 'Travel')

    def test_segment_unique_name(self):
        """Test that segment name must be unique"""
        with self.assertRaises(IntegrityError):
            Segment.objects.create(name='Travel')

    def test_segment_department_relationship(self):
        """Test segment can be associated with departments"""
        self.segment.departments.add(self.department)

        self.assertIn(self.department, self.segment.departments.all())
        self.assertIn(self.segment, self.department.segments.all())

    def test_segment_multiple_departments(self):
        """Test segment can be associated with multiple departments"""
        dept2 = Department.objects.create(name='Marketing', code='MKT')

        self.segment.departments.add(self.department, dept2)

        self.assertEqual(self.segment.departments.count(), 2)

    def test_is_in_use_method(self):
        """Test is_in_use method"""
        # Initially not in use
        self.assertFalse(self.segment.is_in_use())

    def test_get_usage_count_method(self):
        """Test get_usage_count method"""
        # Initially usage count is 0
        self.assertEqual(self.segment.get_usage_count(), 0)

    def test_segment_without_departments(self):
        """Test segment can exist without departments (available to all)"""
        all_segment = Segment.objects.create(
            name='General',
            description='General expenses'
        )

        self.assertEqual(all_segment.departments.count(), 0)


class BudgetModelTest(TestCase):
    """Test cases for Budget model"""

    def setUp(self):
        """Set up test data"""
        self.department = Department.objects.create(
            name='Engineering',
            code='ENG'
        )

        self.segment = Segment.objects.create(
            name='Travel',
            description='Travel expenses'
        )

        self.start_date = date.today()
        self.end_date = self.start_date + timedelta(days=30)

        self.budget = Budget.objects.create(
            segment=self.segment,
            allocated_amount=Decimal('10000.00'),
            period_type=Budget.PeriodType.MONTHLY,
            start_date=self.start_date,
            end_date=self.end_date,
            alert_threshold_percentage=80
        )

    def test_budget_creation(self):
        """Test budget can be created successfully"""
        self.assertEqual(self.budget.segment, self.segment)
        self.assertEqual(self.budget.allocated_amount, Decimal('10000.00'))
        self.assertEqual(self.budget.period_type, Budget.PeriodType.MONTHLY)
        self.assertEqual(self.budget.alert_threshold_percentage, 80)

    def test_budget_str_method(self):
        """Test budget string representation"""
        expected = f"Travel Budget: $10000.00 (MONTHLY)"
        self.assertEqual(str(self.budget), expected)

    def test_budget_for_department(self):
        """Test budget can be created for department"""
        dept_budget = Budget.objects.create(
            department=self.department,
            allocated_amount=Decimal('50000.00'),
            period_type=Budget.PeriodType.QUARTERLY,
            start_date=self.start_date,
            end_date=self.end_date
        )

        self.assertEqual(dept_budget.department, self.department)
        self.assertIsNone(dept_budget.segment)

    def test_budget_period_types(self):
        """Test all budget period types"""
        period_types = [
            Budget.PeriodType.MONTHLY,
            Budget.PeriodType.QUARTERLY,
            Budget.PeriodType.YEARLY
        ]

        for period_type in period_types:
            budget = Budget.objects.create(
                segment=self.segment,
                allocated_amount=Decimal('5000.00'),
                period_type=period_type,
                start_date=self.start_date,
                end_date=self.end_date
            )
            self.assertEqual(budget.period_type, period_type)

    def test_get_spent_amount(self):
        """Test get_spent_amount method"""
        # Initially spent amount should be 0
        spent = self.budget.get_spent_amount()
        self.assertEqual(spent, 0)

    def test_get_remaining_budget(self):
        """Test get_remaining_budget method"""
        remaining = self.budget.get_remaining_budget()
        expected = self.budget.allocated_amount - self.budget.get_spent_amount()
        self.assertEqual(remaining, expected)

    def test_get_percentage_used(self):
        """Test get_percentage_used method"""
        # With no expenses, percentage should be 0
        percentage = self.budget.get_percentage_used()
        self.assertEqual(percentage, 0)

    def test_get_percentage_used_with_zero_allocation(self):
        """Test get_percentage_used with zero allocated amount"""
        zero_budget = Budget.objects.create(
            segment=self.segment,
            allocated_amount=Decimal('0.00'),
            period_type=Budget.PeriodType.MONTHLY,
            start_date=self.start_date,
            end_date=self.end_date
        )

        percentage = zero_budget.get_percentage_used()
        self.assertEqual(percentage, 0)

    def test_is_over_threshold(self):
        """Test is_over_threshold method"""
        # With no expenses, should not be over threshold
        self.assertFalse(self.budget.is_over_threshold())

    def test_default_alert_threshold(self):
        """Test default alert threshold is 80"""
        budget = Budget.objects.create(
            segment=self.segment,
            allocated_amount=Decimal('5000.00'),
            period_type=Budget.PeriodType.MONTHLY,
            start_date=self.start_date,
            end_date=self.end_date
        )

        self.assertEqual(budget.alert_threshold_percentage, 80)

    def test_custom_alert_threshold(self):
        """Test setting custom alert threshold"""
        budget = Budget.objects.create(
            segment=self.segment,
            allocated_amount=Decimal('5000.00'),
            period_type=Budget.PeriodType.MONTHLY,
            start_date=self.start_date,
            end_date=self.end_date,
            alert_threshold_percentage=90
        )

        self.assertEqual(budget.alert_threshold_percentage, 90)

    def test_budget_ordering(self):
        """Test budgets are ordered by start_date descending"""
        # Create another budget with earlier start date
        earlier_date = self.start_date - timedelta(days=60)
        earlier_budget = Budget.objects.create(
            segment=self.segment,
            allocated_amount=Decimal('5000.00'),
            period_type=Budget.PeriodType.MONTHLY,
            start_date=earlier_date,
            end_date=earlier_date + timedelta(days=30)
        )

        budgets = Budget.objects.all()
        # Most recent budget should be first
        self.assertEqual(budgets[0], self.budget)
        self.assertEqual(budgets[1], earlier_budget)

    def test_budget_with_both_segment_and_department(self):
        """Test budget can have both segment and department"""
        budget = Budget.objects.create(
            segment=self.segment,
            department=self.department,
            allocated_amount=Decimal('3000.00'),
            period_type=Budget.PeriodType.MONTHLY,
            start_date=self.start_date,
            end_date=self.end_date
        )

        self.assertEqual(budget.segment, self.segment)
        self.assertEqual(budget.department, self.department)
