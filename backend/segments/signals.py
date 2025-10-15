from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from expenses.models import Expense
from .models import Budget
from approvals.models import Notification


@receiver(post_save, sender=Expense)
def check_budget_alerts(sender, instance, created, **kwargs):
    """
    Check if expense pushes budget over threshold and send alerts.
    Requirement: "alert when spending exceeds 80% of budget"
    Following SOLID: Single Responsibility - only handles budget alerts
    """
    # Only check for approved expenses
    if instance.status != 'APPROVED':
        return

    # Check department budget
    if instance.user.department:
        department_budgets = Budget.objects.filter(
            department=instance.user.department,
            start_date__lte=instance.date,
            end_date__gte=instance.date
        )

        for budget in department_budgets:
            if budget.is_over_threshold():
                _create_budget_alert(
                    budget,
                    instance.user.department.manager,
                    f"Department {instance.user.department.name}"
                )

    # Check segment budgets for each allocation
    for allocation in instance.segment_allocations.all():
        segment_budgets = Budget.objects.filter(
            segment=allocation.segment,
            start_date__lte=instance.date,
            end_date__gte=instance.date
        )

        for budget in segment_budgets:
            if budget.is_over_threshold():
                # Notify department manager or finance admins
                if instance.user.department and instance.user.department.manager:
                    _create_budget_alert(
                        budget,
                        instance.user.department.manager,
                        f"Segment {allocation.segment.name}"
                    )
                else:
                    # Notify finance admins
                    from users.models import User
                    finance_admins = User.objects.filter(
                        role=User.Role.FINANCE_ADMIN,
                        is_active=True
                    )
                    for admin in finance_admins:
                        _create_budget_alert(budget, admin, f"Segment {allocation.segment.name}")


def _create_budget_alert(budget, user, entity_name):
    """
    Helper function to create budget alert notification.
    Following DRY: Reusable notification creation
    """
    if not user:
        return

    percentage = budget.get_percentage_used()
    remaining = budget.get_remaining_budget()

    # Only create notification if it doesn't already exist (avoid spam)
    existing = Notification.objects.filter(
        user=user,
        notification_type='BUDGET_ALERT',
        expense=None,  # Budget alerts aren't tied to specific expenses
        created_at__gte=timezone.now() - timezone.timedelta(hours=24)  # Within last 24h
    ).filter(
        message__contains=entity_name
    ).exists()

    if not existing:
        Notification.objects.create(
            user=user,
            notification_type='BUDGET_ALERT',
            title=f'Budget Alert: {entity_name}',
            message=f'{entity_name} budget has reached {percentage:.1f}% of allocated amount. '
                   f'Remaining: ${float(remaining):,.2f} of ${float(budget.allocated_amount):,.2f}.'
        )
