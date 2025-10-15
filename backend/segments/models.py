from django.db import models
from users.models import Department


class Segment(models.Model):
    """
    Segment (Category) model for expense categorization.
    Examples: Travel, Marketing, Research, Operations, etc.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name='segments',
        help_text="Departments that can use this segment. Leave empty for all departments."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def is_in_use(self):
        """Check if this segment is being used in any expense allocations"""
        return self.expense_allocations.exists()

    def get_usage_count(self):
        """Get count of expense allocations using this segment"""
        return self.expense_allocations.count()


class Budget(models.Model):
    """Budget allocation for segments or departments"""

    class PeriodType(models.TextChoices):
        MONTHLY = 'MONTHLY', 'Monthly'
        QUARTERLY = 'QUARTERLY', 'Quarterly'
        YEARLY = 'YEARLY', 'Yearly'

    segment = models.ForeignKey(
        Segment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='budgets'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='budgets'
    )
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2)
    period_type = models.CharField(
        max_length=20,
        choices=PeriodType.choices,
        default=PeriodType.MONTHLY
    )
    start_date = models.DateField()
    end_date = models.DateField()
    alert_threshold_percentage = models.IntegerField(
        default=80,
        help_text="Alert when spending exceeds this percentage"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        entity = self.segment or self.department
        return f"{entity} Budget: ${self.allocated_amount} ({self.period_type})"

    def get_spent_amount(self):
        """Calculate total spent against this budget"""
        # Will be implemented after Expense model
        from expenses.models import Expense, ExpenseSegmentAllocation

        if self.segment:
            allocations = ExpenseSegmentAllocation.objects.filter(
                segment=self.segment,
                expense__status='APPROVED',
                expense__date__range=[self.start_date, self.end_date]
            )
            return sum(allocation.amount for allocation in allocations)
        elif self.department:
            expenses = Expense.objects.filter(
                user__department=self.department,
                status='APPROVED',
                date__range=[self.start_date, self.end_date]
            )
            return sum(expense.total_amount for expense in expenses)
        return 0

    def get_remaining_budget(self):
        """Calculate remaining budget"""
        return self.allocated_amount - self.get_spent_amount()

    def get_percentage_used(self):
        """Calculate percentage of budget used"""
        if self.allocated_amount == 0:
            return 0
        return (self.get_spent_amount() / self.allocated_amount) * 100

    def is_over_threshold(self):
        """Check if spending exceeds alert threshold"""
        return self.get_percentage_used() >= self.alert_threshold_percentage
