from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count, Q
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import Currency, Expense, ExpenseSegmentAllocation
from approvals.models import Approval, Comment
from decimal import Decimal


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'symbol', 'exchange_rate_to_base', 'is_base_currency']
    list_filter = ['is_base_currency']
    search_fields = ['code', 'name']
    ordering = ['code']

    fieldsets = (
        ('Currency Information', {
            'fields': ('code', 'name', 'symbol'),
            'description': 'Define the currency code (e.g., USD, EUR, GBP), full name, and symbol.'
        }),
        ('Exchange Rate', {
            'fields': ('exchange_rate_to_base', 'is_base_currency'),
            'description': 'Set exchange rate relative to base currency. Check "is_base_currency" if this is the primary currency (rate should be 1.00). Only one currency can be the base currency.'
        }),
    )

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of base currency"""
        if obj and obj.is_base_currency:
            return False
        return super().has_delete_permission(request, obj)


class ExpenseSegmentAllocationInline(admin.TabularInline):
    model = ExpenseSegmentAllocation
    extra = 1
    fields = ['segment', 'segment_description', 'percentage', 'amount', 'notes']
    readonly_fields = ['amount', 'segment_description']

    def segment_description(self, obj):
        """Show segment description"""
        if obj.segment:
            return obj.segment.description or '-'
        return '-'
    segment_description.short_description = 'Category Description'

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        # Add help text
        formset.form.base_fields['percentage'].help_text = 'Enter percentage (e.g., 50 for 50%). Total must equal 100%'

        # Customize segment field to show descriptions
        from segments.models import Segment
        segment_field = formset.form.base_fields.get('segment')
        if segment_field:
            # Create choices with descriptions
            segment_field.queryset = Segment.objects.filter(is_active=True)
            segment_field.help_text = 'Select expense category. Description will appear after selecting.'

        return formset


class ApprovalInline(admin.TabularInline):
    model = Approval
    extra = 0
    fields = ['approver', 'status', 'comments', 'approved_at']
    readonly_fields = ['approved_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        # Only managers and finance admins can add approvals
        if request.user.is_manager() or request.user.is_finance_admin():
            return True
        return False


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ['user', 'text', 'created_at']
    readonly_fields = ['created_at']
    can_delete = False

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields['user'].initial = request.user
        return formset


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = [
        'vendor_display', 'user_display', 'amount_display',
        'currency', 'date', 'status_display', 'allocation_status', 'created_at'
    ]
    list_filter = ['status', 'currency', 'date', 'user__department', 'user__role']
    search_fields = ['vendor', 'description', 'user__username', 'user__email']
    date_hierarchy = 'date'
    ordering = ['-date', '-created_at']
    readonly_fields = ['amount_in_base_currency', 'created_at', 'updated_at', 'total_allocated_display']
    inlines = [ExpenseSegmentAllocationInline, ApprovalInline, CommentInline]
    actions = ['mark_as_pending', 'mark_as_approved', 'mark_as_rejected', 'export_expenses']

    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'date', 'vendor', 'description'),
            'description': 'Enter the basic details of the expense/invoice.'
        }),
        ('Amount & Currency', {
            'fields': ('total_amount', 'currency', 'amount_in_base_currency'),
            'description': 'Specify the amount and currency. Base currency conversion is automatic.'
        }),
        ('Segment Allocation', {
            'fields': ('total_allocated_display',),
            'description': 'Allocate this expense across categories below (must total 100%).'
        }),
        ('Document', {
            'fields': ('receipt',),
            'description': 'Upload receipt or invoice image/PDF for record keeping.'
        }),
        ('Status & Approval', {
            'fields': ('status', 'requires_finance_approval', 'notes'),
            'description': 'Set status and approval requirements. Finance approval adds a second approval level.'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def vendor_display(self, obj):
        """Display vendor with icon"""
        return format_html(
            '<strong>{}</strong>',
            obj.vendor
        )
    vendor_display.short_description = 'Vendor'

    def user_display(self, obj):
        """Display user with department"""
        dept = obj.user.department.name if obj.user.department else 'No Dept'
        return format_html(
            '{}<br><small style="color: #666;">{}</small>',
            obj.user.get_full_name() or obj.user.username,
            dept
        )
    user_display.short_description = 'Submitted By'

    def amount_display(self, obj):
        """Display amount with currency"""
        formatted_amount = f"${float(obj.total_amount):,.2f}"
        return format_html(
            '<strong style="color: #2196F3;">{}</strong>',
            formatted_amount
        )
    amount_display.short_description = 'Amount'

    def status_display(self, obj):
        """Display status with colored badge"""
        colors = {
            'DRAFT': '#999',
            'PENDING': '#ff9800',
            'APPROVED': '#4CAF50',
            'REJECTED': '#f44336'
        }
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'

    def allocation_status(self, obj):
        """Show segment allocation status"""
        total = obj.get_total_allocated_percentage()
        if total == 0:
            return format_html(
                '<span style="color: #f44336;">❌ Not Allocated</span>'
            )
        elif total == 100:
            return format_html(
                '<span style="color: #4CAF50;">✓ 100%</span>'
            )
        else:
            return format_html(
                '<span style="color: #ff9800;">⚠ {}%</span>',
                int(total)
            )
    allocation_status.short_description = 'Allocation'

    def total_allocated_display(self, obj):
        """Display total percentage allocated"""
        if not obj.pk:
            return "Save expense first to allocate segments"

        total = obj.get_total_allocated_percentage()
        if total == 100:
            status = format_html(
                '<span style="color: #4CAF50; font-weight: bold;">✓ Total: 100% (Complete)</span>'
            )
        elif total > 100:
            status = format_html(
                '<span style="color: #f44336; font-weight: bold;">❌ Total: {}% (Over 100%!)</span>',
                int(total)
            )
        elif total > 0:
            status = format_html(
                '<span style="color: #ff9800; font-weight: bold;">⚠ Total: {}% (Must be 100%)</span>',
                int(total)
            )
        else:
            status = format_html(
                '<span style="color: #999; font-weight: bold;">➜ No allocations yet</span>'
            )

        return status
    total_allocated_display.short_description = 'Segment Allocation Status'

    def get_queryset(self, request):
        """Filter expenses based on user role"""
        qs = super().get_queryset(request)

        # Superuser and Finance Admin see everything
        if request.user.is_superuser or request.user.is_finance_admin():
            return qs

        # Managers see their department's expenses
        elif request.user.is_manager():
            if request.user.department:
                return qs.filter(user__department=request.user.department)
            return qs.none()

        # Employees see only their own expenses
        else:
            return qs.filter(user=request.user)

    def has_change_permission(self, request, obj=None):
        """Control who can edit expenses"""
        # Auditors have read-only access
        if hasattr(request.user, 'is_auditor') and request.user.is_auditor():
            return False

        # For specific object, check ownership/department
        if obj:
            # Superuser and Finance Admin can edit all
            if request.user.is_superuser or request.user.is_finance_admin():
                return True

            # Managers can edit their department's expenses
            if request.user.is_manager():
                return obj.user.department == request.user.department

            # Employees can only edit their own expenses
            return obj.user == request.user

        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Control who can delete expenses"""
        # Only Finance Admin and Superuser can delete
        if request.user.is_superuser or (hasattr(request.user, 'is_finance_admin') and request.user.is_finance_admin()):
            return True
        return False

    def save_model(self, request, obj, form, change):
        """
        Custom save with validation and budget warnings.
        Requirement: "warn if expense pushes segment over budget"
        """
        # Set user if creating new expense
        if not change:
            obj.user = request.user

        # Save first to get the object ID
        super().save_model(request, obj, form, change)

        # Check budget warnings (only for pending/draft expenses)
        if obj.status in ['DRAFT', 'PENDING']:
            self._check_budget_warnings(request, obj)

    def _check_budget_warnings(self, request, expense):
        """
        Check if expense would exceed budget and warn user.
        Following KISS: Simple budget check with clear warnings
        """
        from segments.models import Budget

        # Check department budget
        if expense.user.department:
            department_budgets = Budget.objects.filter(
                department=expense.user.department,
                start_date__lte=expense.date,
                end_date__gte=expense.date
            )

            for budget in department_budgets:
                percentage = budget.get_percentage_used()
                if percentage >= budget.alert_threshold_percentage:
                    messages.warning(
                        request,
                        f'⚠️ Department budget warning: {expense.user.department.name} is at '
                        f'{percentage:.1f}% of budget (${float(budget.get_spent_amount()):,.2f} / '
                        f'${float(budget.allocated_amount):,.2f}). '
                        f'Remaining: ${float(budget.get_remaining_budget()):,.2f}'
                    )

        # Check segment budgets
        for allocation in expense.segment_allocations.all():
            segment_budgets = Budget.objects.filter(
                segment=allocation.segment,
                start_date__lte=expense.date,
                end_date__gte=expense.date
            )

            for budget in segment_budgets:
                percentage = budget.get_percentage_used()
                if percentage >= budget.alert_threshold_percentage:
                    messages.warning(
                        request,
                        f'⚠️ Segment budget warning: {allocation.segment.name} is at '
                        f'{percentage:.1f}% of budget (${float(budget.get_spent_amount()):,.2f} / '
                        f'${float(budget.allocated_amount):,.2f}). '
                        f'Remaining: ${float(budget.get_remaining_budget()):,.2f}'
                    )

    def save_formset(self, request, form, formset, change):
        """Save formset and validate segment allocation"""
        instances = formset.save(commit=False)

        # Save all instances
        for instance in instances:
            instance.save()
        formset.save_m2m()

        # Validate total percentage
        expense = form.instance
        total = expense.get_total_allocated_percentage()

        if total > 0 and total != 100:
            messages.warning(
                request,
                f'Warning: Segment allocation totals {int(total)}%. It should be exactly 100%.'
            )
        elif total == 100:
            messages.success(
                request,
                'Segment allocation is complete (100%).'
            )

    def changelist_view(self, request, extra_context=None):
        """
        Add comprehensive analytics to the changelist.
        Requirement: "dashboard showing expenses by segment and department"
        Following DRY: centralized analytics calculation
        """
        extra_context = extra_context or {}

        # Get filtered expense IDs based on user role
        base_qs = super().get_queryset(request)
        expense_ids = list(base_qs.values_list('id', flat=True))

        # Create a fresh queryset for aggregation to avoid annotation conflicts
        queryset = Expense.objects.filter(id__in=expense_ids)

        # Calculate summary statistics by status
        stats = queryset.aggregate(
            total_count=Count('id'),
            sum_total_amount=Sum('total_amount'),
            approved_count=Count('id', filter=Q(status='APPROVED')),
            sum_approved_amount=Sum('total_amount', filter=Q(status='APPROVED')),
            pending_count=Count('id', filter=Q(status='PENDING')),
            sum_pending_amount=Sum('total_amount', filter=Q(status='PENDING')),
            rejected_count=Count('id', filter=Q(status='REJECTED')),
            draft_count=Count('id', filter=Q(status='DRAFT'))
        )

        # Calculate by segment (Top 5)
        segment_stats = ExpenseSegmentAllocation.objects.filter(
            expense_id__in=expense_ids
        ).values(
            'segment__name'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')[:5]

        # Calculate by department (Top 5)
        department_stats = queryset.values(
            'user__department__name'
        ).annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('-total')[:5]

        # Format amounts
        extra_context['summary_stats'] = {
            'total_count': stats['total_count'],
            'total_amount': f"${float(stats['sum_total_amount'] or 0):,.2f}",
            'approved_count': stats['approved_count'],
            'approved_amount': f"${float(stats['sum_approved_amount'] or 0):,.2f}",
            'pending_count': stats['pending_count'],
            'pending_amount': f"${float(stats['sum_pending_amount'] or 0):,.2f}",
            'rejected_count': stats['rejected_count'],
            'draft_count': stats['draft_count']
        }

        # Add segment breakdown
        extra_context['segment_stats'] = [
            {
                'name': item['segment__name'] or 'Unallocated',
                'total': f"${float(item['total'] or 0):,.2f}",
                'count': item['count']
            }
            for item in segment_stats
        ]

        # Add department breakdown
        extra_context['department_stats'] = [
            {
                'name': item['user__department__name'] or 'No Department',
                'total': f"${float(item['total'] or 0):,.2f}",
                'count': item['count']
            }
            for item in department_stats
        ]

        return super().changelist_view(request, extra_context=extra_context)

    # Custom Actions
    def mark_as_pending(self, request, queryset):
        """Mark selected expenses as pending"""
        updated = queryset.update(status='PENDING')
        self.message_user(request, f'{updated} expense(s) marked as Pending.')
    mark_as_pending.short_description = 'Mark as Pending (submit for approval)'

    def mark_as_approved(self, request, queryset):
        """Approve selected expenses"""
        updated = queryset.update(status='APPROVED')
        self.message_user(request, f'{updated} expense(s) approved.')
    mark_as_approved.short_description = 'Approve selected expenses'

    def mark_as_rejected(self, request, queryset):
        """Reject selected expenses"""
        updated = queryset.update(status='REJECTED')
        self.message_user(request, f'{updated} expense(s) rejected.')
    mark_as_rejected.short_description = 'Reject selected expenses'

    def export_expenses(self, request, queryset):
        """Export expenses to CSV"""
        import csv
        from django.http import HttpResponse
        from datetime import datetime

        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type='text/csv')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="expenses_{timestamp}.csv"'

        writer = csv.writer(response)

        # Write header
        writer.writerow([
            'ID', 'Date', 'Vendor', 'Description', 'Amount', 'Currency',
            'Status', 'User', 'Department', 'Segments', 'Created At'
        ])

        # Write data rows
        for expense in queryset:
            segments = ', '.join([
                f"{alloc.segment.name} ({alloc.percentage}%)"
                for alloc in expense.segment_allocations.all()
            ])

            writer.writerow([
                expense.id,
                expense.date,
                expense.vendor,
                expense.description,
                expense.total_amount,
                expense.currency.code,
                expense.get_status_display(),
                expense.user.get_full_name() or expense.user.username,
                expense.user.department.name if expense.user.department else 'N/A',
                segments,
                expense.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])

        self.message_user(request, f'Successfully exported {queryset.count()} expense(s).')
        return response
    export_expenses.short_description = 'Export selected to CSV'


@admin.register(ExpenseSegmentAllocation)
class ExpenseSegmentAllocationAdmin(admin.ModelAdmin):
    list_display = ['expense', 'segment', 'percentage', 'amount']
    list_filter = ['segment']
    search_fields = ['expense__vendor', 'segment__name']
    readonly_fields = ['amount']
    ordering = ['-expense__date']
