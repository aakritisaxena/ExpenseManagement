from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from segments.models import Segment


class Currency(models.Model):
    """Currency model for multi-currency support"""
    code = models.CharField(max_length=3, unique=True, help_text="ISO currency code (e.g., USD, EUR)")
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=5)
    exchange_rate_to_base = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal('1.0'),
        help_text="Exchange rate to base currency"
    )
    is_base_currency = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Currencies'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Expense(models.Model):
    """Main Expense/Invoice model"""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING = 'PENDING', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    date = models.DateField()
    vendor = models.CharField(max_length=200)
    description = models.TextField()
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='expenses'
    )
    amount_in_base_currency = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False
    )
    receipt = models.FileField(
        upload_to='receipts/%Y/%m/',
        null=True,
        blank=True,
        help_text="Upload receipt or invoice image/PDF"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    requires_finance_approval = models.BooleanField(
        default=False,
        help_text="If True, expense requires both manager and finance approval"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.vendor} - ${self.total_amount} ({self.date})"

    def save(self, *args, **kwargs):
        # Calculate amount in base currency
        self.amount_in_base_currency = self.total_amount * self.currency.exchange_rate_to_base
        super().save(*args, **kwargs)

    def clean(self):
        """Validate that segment allocations sum to 100%"""
        super().clean()
        if self.pk:  # Only validate if expense already exists
            total_allocation = sum(
                alloc.percentage for alloc in self.segment_allocations.all()
            )
            if total_allocation != 100 and self.segment_allocations.exists():
                raise ValidationError("Segment allocations must sum to 100%")

    def get_total_allocated_percentage(self):
        """Get total percentage allocated"""
        return sum(alloc.percentage for alloc in self.segment_allocations.all())


class ExpenseSegmentAllocation(models.Model):
    """Multi-segment allocation for expenses"""
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='segment_allocations'
    )
    segment = models.ForeignKey(
        Segment,
        on_delete=models.PROTECT,
        related_name='expense_allocations'
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Percentage of total expense (0.01 to 100.00)"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False
    )
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['expense', 'segment']

    def __str__(self):
        return f"{self.expense} - {self.segment}: {self.percentage}%"

    def save(self, *args, **kwargs):
        # Auto-calculate amount based on percentage
        self.amount = (self.expense.total_amount * self.percentage) / 100
        super().save(*args, **kwargs)
