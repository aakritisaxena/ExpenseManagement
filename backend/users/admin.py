from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import User, Department


class UserInline(admin.TabularInline):
    """Inline display of users in a department"""
    model = User
    fields = ['username', 'email', 'first_name', 'last_name', 'role', 'is_active']
    readonly_fields = ['username', 'email']
    extra = 0
    can_delete = False
    show_change_link = True


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'code', 'manager_display', 'employee_count',
        'total_expenses_display', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'description', 'manager__username']
    ordering = ['name']
    inlines = [UserInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description'),
            'description': 'Enter department name and unique code. The code is used for reporting and identification purposes.'
        }),
        ('Management', {
            'fields': ('manager', 'is_active'),
            'description': 'Assign a manager who will approve expenses for this department. Inactive departments cannot submit new expenses.'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'Automatically tracked timestamps for audit purposes.'
        }),
    )

    readonly_fields = ['created_at', 'updated_at']

    def manager_display(self, obj):
        """Display manager with badge"""
        if obj.manager:
            return format_html(
                '<span style="background-color: #4CAF50; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
                obj.manager.get_full_name() or obj.manager.username
            )
        return format_html(
            '<span style="background-color: #ff9800; color: white; padding: 3px 8px; border-radius: 3px;">No Manager</span>'
        )
    manager_display.short_description = 'Manager'

    def employee_count(self, obj):
        """Display count of active employees"""
        count = obj.get_employee_count()
        color = '#4CAF50' if count > 0 else '#999'
        return format_html(
            '<span style="font-weight: bold; color: {};">{} employees</span>',
            color, count
        )
    employee_count.short_description = 'Team Size'

    def total_expenses_display(self, obj):
        """Display total expenses for this department"""
        total = obj.get_total_expenses()
        # Convert Decimal to float for formatting
        total_float = float(total) if total else 0.0
        # Format the number as a string first
        formatted_total = f"${total_float:,.2f}"
        return format_html(
            '<span style="color: #2196F3; font-weight: bold;">{}</span>',
            formatted_total
        )
    total_expenses_display.short_description = 'Total Expenses'

    def get_queryset(self, request):
        """Optimize queryset with annotations and role-based filtering"""
        qs = super().get_queryset(request)
        qs = qs.annotate(
            active_user_count=Count('users', filter=Q(users__is_active=True))
        )

        # Managers see only their department
        if request.user.is_manager() and not request.user.is_superuser:
            if request.user.department:
                return qs.filter(id=request.user.department.id)
            return qs.none()

        return qs

    def has_change_permission(self, request, obj=None):
        """Control who can edit departments"""
        # Only Finance Admin and Superuser can edit departments
        if request.user.is_superuser or request.user.is_finance_admin():
            return True
        return False

    def has_add_permission(self, request):
        """Control who can add departments"""
        # Only Finance Admin and Superuser can add departments
        if request.user.is_superuser or request.user.is_finance_admin():
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Control who can delete departments"""
        # Only Superuser can delete departments
        return request.user.is_superuser

    actions = ['activate_departments', 'deactivate_departments', 'export_department_report']

    def activate_departments(self, request, queryset):
        """Activate selected departments"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} department(s) activated successfully.')
    activate_departments.short_description = 'Activate selected departments'

    def deactivate_departments(self, request, queryset):
        """Deactivate selected departments"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} department(s) deactivated successfully.')
    deactivate_departments.short_description = 'Deactivate selected departments'

    def export_department_report(self, request, queryset):
        """Export department report to CSV"""
        import csv
        from django.http import HttpResponse
        from datetime import datetime

        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type='text/csv')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="departments_{timestamp}.csv"'

        writer = csv.writer(response)

        # Write header
        writer.writerow([
            'ID', 'Name', 'Code', 'Manager', 'Employee Count',
            'Total Expenses', 'Active', 'Created At'
        ])

        # Write data rows
        for dept in queryset:
            total_expenses = dept.get_total_expenses()

            writer.writerow([
                dept.id,
                dept.name,
                dept.code,
                dept.manager.get_full_name() if dept.manager else 'N/A',
                dept.get_employee_count(),
                f"${float(total_expenses):,.2f}",
                'Yes' if dept.is_active else 'No',
                dept.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])

        self.message_user(request, f'Successfully exported {queryset.count()} department(s).')
        return response
    export_department_report.short_description = 'Export department report to CSV'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'department', 'is_active']
    list_filter = ['role', 'department', 'is_active', 'is_staff']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['username']
    actions = ['impersonate_user_action']

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('role', 'department', 'phone'),
            'description': 'Assign user role and department. Role determines permissions: Employee (submit), Manager (approve L1), Finance Admin (approve L2, manage budgets), Auditor (read-only access).'
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('email', 'role', 'department', 'phone'),
            'description': 'Set the user role and department assignment. Ensure email is provided for notifications.'
        }),
    )

    def get_queryset(self, request):
        """Filter users based on role"""
        qs = super().get_queryset(request)

        # Superuser and Finance Admin see all users
        if request.user.is_superuser or request.user.is_finance_admin():
            return qs

        # Managers see only their department's users
        if request.user.is_manager():
            if request.user.department:
                return qs.filter(department=request.user.department)
            return qs.none()

        # Employees see only themselves
        return qs.filter(id=request.user.id)

    def has_change_permission(self, request, obj=None):
        """Control who can edit users"""
        # Only Finance Admin and Superuser can edit users
        if request.user.is_superuser or request.user.is_finance_admin():
            return True
        return False

    def has_add_permission(self, request):
        """Control who can add users"""
        # Only Finance Admin and Superuser can add users
        if request.user.is_superuser or request.user.is_finance_admin():
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Control who can delete users"""
        # Only Superuser can delete users
        return request.user.is_superuser

    def impersonate_user_action(self, request, queryset):
        """
        Admin action to impersonate selected user.
        Only works for single user selection.
        """
        # Only superusers can impersonate
        if not request.user.is_superuser:
            self.message_user(request, 'Only superadmins can impersonate users.', level=messages.ERROR)
            return

        # Only allow impersonating one user at a time
        if queryset.count() != 1:
            self.message_user(
                request,
                'Please select exactly one user to impersonate.',
                level=messages.WARNING
            )
            return

        user_to_impersonate = queryset.first()

        # Don't allow impersonating yourself
        if user_to_impersonate.id == request.user.id:
            self.message_user(request, 'You cannot impersonate yourself.', level=messages.WARNING)
            return

        # Store impersonation in session
        request.session['impersonate_id'] = user_to_impersonate.id
        request.session['real_user_id'] = request.user.id

        self.message_user(
            request,
            f'You are now viewing the system as: {user_to_impersonate.get_full_name() or user_to_impersonate.username} '
            f'({user_to_impersonate.get_role_display()}). Use the "Stop Impersonation" button to return.',
            level=messages.SUCCESS
        )

    impersonate_user_action.short_description = 'Impersonate selected user (Superadmin only)'
