from django.contrib.auth.models import AbstractUser
from django.db import models


class Department(models.Model):
    """Department or Cost Center model"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, default='DEPT', help_text="Department code (e.g., ENG, MKT, SAL)")
    description = models.TextField(blank=True)
    manager = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_departments',
        limit_choices_to={'role': 'MANAGER'},
        help_text="Department manager"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def get_employee_count(self):
        """Return count of users in this department"""
        return self.users.filter(is_active=True).count()

    def get_manager_name(self):
        """Return manager's name or 'No Manager'"""
        return self.manager.get_full_name() if self.manager else "No Manager"

    def get_total_expenses(self):
        """Get total approved expenses for this department"""
        from expenses.models import Expense
        from decimal import Decimal
        expenses = Expense.objects.filter(
            user__department=self,
            status='APPROVED'
        )
        total = sum((exp.amount_in_base_currency for exp in expenses), Decimal('0.00'))
        return total


class User(AbstractUser):
    """Custom User model with roles and department"""

    class Role(models.TextChoices):
        EMPLOYEE = 'EMPLOYEE', 'Employee'
        MANAGER = 'MANAGER', 'Manager'
        FINANCE_ADMIN = 'FINANCE_ADMIN', 'Finance Admin'
        AUDITOR = 'AUDITOR', 'Auditor'

    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['username']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    def is_manager(self):
        return self.role == self.Role.MANAGER

    def is_finance_admin(self):
        return self.role == self.Role.FINANCE_ADMIN

    def is_auditor(self):
        return self.role == self.Role.AUDITOR
