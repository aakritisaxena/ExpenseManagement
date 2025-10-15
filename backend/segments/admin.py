from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.db.models import Count
from .models import Segment, Budget


@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'description_preview', 'usage_count_display', 'department_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'departments']
    search_fields = ['name', 'description']
    filter_horizontal = ['departments']
    ordering = ['name']
    actions = ['activate_segments', 'deactivate_segments']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description'),
            'description': 'Define the segment name and description. Segments are categories for expense allocation (e.g., Project A, Marketing Campaign, R&D). Employees will see this when allocating expenses across multiple segments.'
        }),
        ('Department Access', {
            'fields': ('departments',),
            'description': 'Select which departments can use this segment. Leave empty to allow all departments. This helps control which teams can allocate expenses to specific projects or initiatives.'
        }),
        ('Status', {
            'fields': ('is_active',),
            'description': 'Inactive segments will not be available for new expense allocations, but existing allocations remain intact. Use this instead of deletion to preserve historical data.'
        }),
    )

    def description_preview(self, obj):
        """Show first 50 chars of description"""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return format_html('<span style="color: #999;">No description</span>')
    description_preview.short_description = 'Description'

    def usage_count_display(self, obj):
        """Display how many times this segment is used in allocations"""
        count = obj.get_usage_count()
        if count == 0:
            return format_html('<span style="color: #999;">Not used</span>')
        elif count < 10:
            return format_html('<span style="color: #4CAF50;">{} allocations</span>', count)
        else:
            return format_html('<span style="color: #2196F3; font-weight: bold;">{} allocations</span>', count)
    usage_count_display.short_description = 'Usage'

    def department_count(self, obj):
        """Display number of departments this segment is assigned to"""
        count = obj.departments.count()
        if count == 0:
            return format_html('<span style="color: #999;">All departments</span>')
        return format_html('<span>{} departments</span>', count)
    department_count.short_description = 'Departments'

    def get_queryset(self, request):
        """Optimize queryset with annotations"""
        qs = super().get_queryset(request)
        qs = qs.annotate(
            allocation_count=Count('expense_allocations')
        )
        return qs

    def has_change_permission(self, request, obj=None):
        """Only Finance Admin and Superuser can edit segments"""
        if request.user.is_superuser or request.user.is_finance_admin():
            return True
        return False

    def has_add_permission(self, request):
        """Only Finance Admin and Superuser can add segments"""
        if request.user.is_superuser or request.user.is_finance_admin():
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Only Superuser can delete segments"""
        return request.user.is_superuser

    def delete_model(self, request, obj):
        """
        Override delete to check if segment is in use.
        Following requirements: handle existing expenses appropriately.
        """
        if obj.is_in_use():
            usage_count = obj.get_usage_count()
            messages.error(
                request,
                f'Cannot delete segment "{obj.name}" because it is being used in {usage_count} expense allocation(s). '
                f'Please deactivate it instead or reassign the expenses first.'
            )
            return

        # Safe to delete
        super().delete_model(request, obj)
        messages.success(request, f'Segment "{obj.name}" was successfully deleted.')

    def delete_queryset(self, request, queryset):
        """
        Override bulk delete to check if any segments are in use.
        """
        segments_in_use = []
        segments_safe_to_delete = []

        for segment in queryset:
            if segment.is_in_use():
                segments_in_use.append(f"{segment.name} ({segment.get_usage_count()} allocations)")
            else:
                segments_safe_to_delete.append(segment)

        # Delete safe segments
        if segments_safe_to_delete:
            count = len(segments_safe_to_delete)
            for segment in segments_safe_to_delete:
                segment.delete()
            messages.success(request, f'Successfully deleted {count} segment(s).')

        # Warn about segments in use
        if segments_in_use:
            messages.error(
                request,
                f'Could not delete the following segments because they are in use: {", ".join(segments_in_use)}. '
                f'Please deactivate them instead or reassign the expenses first.'
            )

    # Admin Actions
    def activate_segments(self, request, queryset):
        """Activate selected segments"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} segment(s) activated successfully.')
    activate_segments.short_description = 'Activate selected segments'

    def deactivate_segments(self, request, queryset):
        """
        Deactivate selected segments (safer than deletion).
        Inactive segments won't be available for NEW allocations but existing ones remain.
        """
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{updated} segment(s) deactivated successfully. '
            f'They will not be available for new expense allocations.'
        )
    deactivate_segments.short_description = 'Deactivate selected segments (safe alternative to deletion)'


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = [
        'budget_name', 'allocated_amount_display', 'spent_amount_display',
        'remaining_display', 'usage_bar', 'period_type', 'date_range', 'threshold_display'
    ]
    list_filter = ['period_type', 'segment', 'department', 'start_date']
    search_fields = ['segment__name', 'department__name']
    date_hierarchy = 'start_date'
    ordering = ['-start_date']

    fieldsets = (
        ('Budget Target', {
            'fields': ('segment', 'department', 'allocated_amount'),
            'description': 'Assign budget to either a segment (e.g., Project A) or department (e.g., Engineering), but not both. This allows tracking spending limits for specific initiatives or teams.'
        }),
        ('Period', {
            'fields': ('period_type', 'start_date', 'end_date'),
            'description': 'Define the budget period (Monthly, Quarterly, Yearly, or Custom). The system will track expenses within this date range and calculate remaining budget.'
        }),
        ('Alerts', {
            'fields': ('alert_threshold_percentage',),
            'description': 'Set alert threshold percentage (default 80%). Managers and Finance Admins will receive notifications when spending exceeds this percentage of the allocated budget. Alerts are sent once per 24 hours to avoid spam.'
        }),
    )

    def budget_name(self, obj):
        """Display budget entity with icon"""
        entity = obj.segment or obj.department
        icon = '📊' if obj.segment else '🏢'
        return format_html(
            '{} <strong>{}</strong>',
            icon,
            entity
        )
    budget_name.short_description = 'Budget For'

    def allocated_amount_display(self, obj):
        """Display allocated amount"""
        amount = float(obj.allocated_amount)
        return format_html(
            '<span style="color: #666; font-weight: bold;">${}</span>',
            f'{amount:,.2f}'
        )
    allocated_amount_display.short_description = 'Allocated'

    def spent_amount_display(self, obj):
        """Display spent amount"""
        spent = float(obj.get_spent_amount())
        return format_html(
            '<span style="color: #f44336; font-weight: bold;">${}</span>',
            f'{spent:,.2f}'
        )
    spent_amount_display.short_description = 'Spent'

    def remaining_display(self, obj):
        """Display remaining amount"""
        remaining = float(obj.get_remaining_budget())
        color = '#4CAF50' if remaining > 0 else '#f44336'
        return format_html(
            '<span style="color: {}; font-weight: bold;">${}</span>',
            color,
            f'{remaining:,.2f}'
        )
    remaining_display.short_description = 'Remaining'

    def usage_bar(self, obj):
        """
        Display visual budget usage bar.
        Requirement: "view remaining budget" with visual indicator
        """
        percentage = obj.get_percentage_used()

        # Determine color based on threshold
        if percentage >= obj.alert_threshold_percentage:
            color = '#f44336'  # Red - over threshold
        elif percentage >= obj.alert_threshold_percentage * 0.75:
            color = '#ff9800'  # Orange - approaching threshold
        else:
            color = '#4CAF50'  # Green - safe

        # Cap at 100% for display
        display_percentage = min(percentage, 100)

        return format_html(
            '<div style="width: 120px; background: #eee; border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; height: 20px; border-radius: 3px; display: flex; align-items: center; justify-content: center; color: white; font-size: 11px; font-weight: bold;">'
            '{}'
            '</div>'
            '</div>',
            display_percentage,
            color,
            f'{percentage:.0f}%'
        )
    usage_bar.short_description = 'Usage'

    def date_range(self, obj):
        """Display date range"""
        return format_html(
            '<small>{} to {}</small>',
            obj.start_date.strftime('%b %d, %Y'),
            obj.end_date.strftime('%b %d, %Y')
        )
    date_range.short_description = 'Period'

    def threshold_display(self, obj):
        """Display threshold with indicator"""
        if obj.is_over_threshold():
            return format_html(
                '<span style="color: #f44336; font-weight: bold;">⚠️ {}% (EXCEEDED)</span>',
                obj.alert_threshold_percentage
            )
        return format_html(
            '<span style="color: #666;">{}%</span>',
            obj.alert_threshold_percentage
        )
    threshold_display.short_description = 'Alert Threshold'

    def has_add_permission(self, request):
        """Only Finance Admin and Superuser can add budgets"""
        if request.user.is_superuser or request.user.is_finance_admin():
            return True
        return False

    def has_change_permission(self, request, obj=None):
        """Only Finance Admin and Superuser can edit budgets"""
        if request.user.is_superuser or request.user.is_finance_admin():
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Only Superuser can delete budgets"""
        return request.user.is_superuser
