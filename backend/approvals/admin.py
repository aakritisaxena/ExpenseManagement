from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.utils import timezone
from .models import Approval, Comment, Notification, AuditLog


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ['expense_display', 'level_display', 'approver', 'status_display', 'approved_at', 'created_at']
    list_filter = ['status', 'level', 'approver', 'created_at']
    search_fields = ['expense__vendor', 'approver__username', 'comments']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    readonly_fields = ['expense', 'approved_at', 'created_at', 'updated_at']
    actions = ['approve_expenses', 'reject_expenses']

    fieldsets = (
        ('Expense Information', {
            'fields': ('expense',),
            'description': 'The expense that requires approval. Click to view full expense details including receipts, segments, and allocation breakdown.'
        }),
        ('Approval Details', {
            'fields': ('approver', 'status', 'comments'),
            'description': 'Provide your approval decision (Pending, Approved, or Rejected) and any comments explaining your decision. Comments will be visible to the employee and other approvers.'
        }),
        ('Timestamps', {
            'fields': ('approved_at', 'created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'Automatically tracked timestamps. "Approved at" is set when status changes from Pending.'
        }),
    )

    def expense_display(self, obj):
        """Display expense details with amount and vendor"""
        return format_html(
            '<strong>{}</strong><br><small style="color: #666;">${} on {}</small>',
            obj.expense.vendor,
            obj.expense.total_amount,
            obj.expense.date
        )
    expense_display.short_description = 'Expense'

    def level_display(self, obj):
        """Display approval level with badge"""
        colors = {
            1: '#2196F3',  # Manager - Blue
            2: '#9C27B0',  # Finance - Purple
        }
        color = colors.get(obj.level, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">Level {}: {}</span>',
            color,
            obj.level,
            obj.get_level_display()
        )
    level_display.short_description = 'Approval Level'

    def status_display(self, obj):
        """Display status with colored badge"""
        colors = {
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

    def get_queryset(self, request):
        """Filter approvals based on user role"""
        qs = super().get_queryset(request)

        # Superuser and Finance Admin see all approvals
        if request.user.is_superuser or request.user.is_finance_admin():
            return qs

        # Managers see their department's approvals
        elif request.user.is_manager():
            if request.user.department:
                return qs.filter(expense__user__department=request.user.department)
            return qs.none()

        # Others see only approvals they made
        else:
            return qs.filter(approver=request.user)

    def has_add_permission(self, request):
        """Only managers and finance admins can add approvals"""
        if request.user.is_manager() or request.user.is_finance_admin():
            return True
        return False

    def has_change_permission(self, request, obj=None):
        """Only managers and finance admins can edit approvals"""
        if request.user.is_manager() or request.user.is_finance_admin():
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Only finance admin and superuser can delete approvals"""
        if request.user.is_superuser or request.user.is_finance_admin():
            return True
        return False

    # Admin Actions for Approve/Reject
    def approve_expenses(self, request, queryset):
        """
        Approve selected expenses.
        Requirement: "As a Manager, I want to approve expenses"
        Following KISS principle: simple, clear action
        """
        # Filter only pending approvals
        pending_approvals = queryset.filter(status='PENDING')

        if not pending_approvals.exists():
            self.message_user(request, 'No pending approvals selected.', level=messages.WARNING)
            return

        approved_count = 0
        for approval in pending_approvals:
            # Check permission: user must be the approver or have admin rights
            if (approval.approver == request.user or
                request.user.is_superuser or
                request.user.is_finance_admin()):

                approval.status = 'APPROVED'
                approval.approved_at = timezone.now()
                approval.save()
                approved_count += 1
            else:
                self.message_user(
                    request,
                    f'You do not have permission to approve expense from {approval.expense.vendor}.',
                    level=messages.WARNING
                )

        if approved_count > 0:
            self.message_user(
                request,
                f'Successfully approved {approved_count} expense(s).',
                level=messages.SUCCESS
            )

    approve_expenses.short_description = '✓ Approve selected expenses'

    def reject_expenses(self, request, queryset):
        """
        Reject selected expenses.
        Requirement: "As a Manager, I want to reject expenses"
        """
        # Filter only pending approvals
        pending_approvals = queryset.filter(status='PENDING')

        if not pending_approvals.exists():
            self.message_user(request, 'No pending approvals selected.', level=messages.WARNING)
            return

        rejected_count = 0
        for approval in pending_approvals:
            # Check permission: user must be the approver or have admin rights
            if (approval.approver == request.user or
                request.user.is_superuser or
                request.user.is_finance_admin()):

                approval.status = 'REJECTED'
                approval.approved_at = timezone.now()
                approval.save()
                rejected_count += 1
            else:
                self.message_user(
                    request,
                    f'You do not have permission to reject expense from {approval.expense.vendor}.',
                    level=messages.WARNING
                )

        if rejected_count > 0:
            self.message_user(
                request,
                f'Successfully rejected {rejected_count} expense(s).',
                level=messages.SUCCESS
            )

    reject_expenses.short_description = '✗ Reject selected expenses'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['expense', 'user', 'text', 'created_at']
    list_filter = ['user']
    search_fields = ['expense__vendor', 'user__username', 'text']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        """Filter comments based on user role"""
        qs = super().get_queryset(request)

        # Superuser and Finance Admin see all comments
        if request.user.is_superuser or request.user.is_finance_admin():
            return qs

        # Managers see their department's comments
        elif request.user.is_manager():
            if request.user.department:
                return qs.filter(expense__user__department=request.user.department)
            return qs.none()

        # Others see only their own comments
        else:
            return qs.filter(user=request.user)

    def has_delete_permission(self, request, obj=None):
        """Only finance admin and superuser can delete comments"""
        if request.user.is_superuser or request.user.is_finance_admin():
            return True
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['notification_icon', 'title_display', 'message_preview', 'status_display', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    actions = ['mark_as_read', 'mark_as_unread']

    def notification_icon(self, obj):
        """Display icon based on notification type"""
        icons = {
            'EXPENSE_SUBMITTED': '📝',
            'EXPENSE_APPROVED': '✅',
            'EXPENSE_REJECTED': '❌',
            'BUDGET_ALERT': '⚠️',
            'COMMENT_ADDED': '💬'
        }
        icon = icons.get(obj.notification_type, '🔔')
        return format_html('<span style="font-size: 20px;">{}</span>', icon)
    notification_icon.short_description = ''

    def title_display(self, obj):
        """Display title with emphasis if unread"""
        if not obj.is_read:
            return format_html('<strong style="color: #2196F3;">{}</strong>', obj.title)
        return format_html('<span style="color: #666;">{}</span>', obj.title)
    title_display.short_description = 'Title'

    def message_preview(self, obj):
        """Show first 80 characters of message"""
        preview = obj.message[:80] + '...' if len(obj.message) > 80 else obj.message
        return format_html('<small>{}</small>', preview)
    message_preview.short_description = 'Message'

    def status_display(self, obj):
        """Display read/unread status"""
        if obj.is_read:
            return format_html('<span style="color: #999;">Read</span>')
        return format_html(
            '<span style="background-color: #2196F3; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">NEW</span>'
        )
    status_display.short_description = 'Status'

    def changelist_view(self, request, extra_context=None):
        """
        Add dashboard with pending items overview.
        Requirement: "overview of all pending items on dashboard"
        """
        extra_context = extra_context or {}

        # Get pending items summary for current user
        if request.user.is_manager() or request.user.is_finance_admin():
            from expenses.models import Expense
            from django.db.models import Count, Sum, Q

            # Pending approvals assigned to this user
            pending_approvals = Approval.objects.filter(
                approver=request.user,
                status='PENDING'
            ).select_related('expense')

            # Unread notifications
            unread_notifications = Notification.objects.filter(
                user=request.user,
                is_read=False
            ).count()

            # Budget alerts (last 7 days)
            budget_alerts = Notification.objects.filter(
                user=request.user,
                notification_type='BUDGET_ALERT',
                created_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count()

            # Pending expenses summary
            if request.user.is_manager() and request.user.department:
                pending_expenses = Expense.objects.filter(
                    user__department=request.user.department,
                    status='PENDING'
                )
            elif request.user.is_finance_admin():
                pending_expenses = Expense.objects.filter(status='PENDING')
            else:
                pending_expenses = Expense.objects.none()

            pending_stats = pending_expenses.aggregate(
                count=Count('id'),
                total=Sum('total_amount')
            )

            extra_context['dashboard_summary'] = {
                'pending_approvals': pending_approvals,
                'pending_approvals_count': pending_approvals.count(),
                'unread_notifications': unread_notifications,
                'budget_alerts': budget_alerts,
                'pending_expenses_count': pending_stats['count'] or 0,
                'pending_expenses_total': f"${float(pending_stats['total'] or 0):,.2f}"
            }

        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        """Users see only their own notifications"""
        qs = super().get_queryset(request)

        # Superuser and Finance Admin see all notifications
        if request.user.is_superuser or request.user.is_finance_admin():
            return qs

        # Everyone else sees only their own notifications
        return qs.filter(user=request.user)

    def has_add_permission(self, request):
        """Only system creates notifications"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Only finance admin and superuser can delete notifications"""
        if request.user.is_superuser or request.user.is_finance_admin():
            return True
        return False

    def mark_as_read(self, request, queryset):
        """Mark selected notifications as read"""
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} notification(s) marked as read.')
    mark_as_read.short_description = 'Mark as read'

    def mark_as_unread(self, request, queryset):
        """Mark selected notifications as unread"""
        updated = queryset.update(is_read=False)
        self.message_user(request, f'{updated} notification(s) marked as unread.')
    mark_as_unread.short_description = 'Mark as unread'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action_type', 'model_name', 'object_id', 'timestamp', 'ip_address']
    list_filter = ['action_type', 'model_name']
    search_fields = ['user__username', 'model_name']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    readonly_fields = ['user', 'action_type', 'model_name', 'object_id', 'changes', 'ip_address', 'timestamp']

    def get_queryset(self, request):
        """Filter audit logs based on user role"""
        qs = super().get_queryset(request)

        # Superuser and Finance Admin see all logs
        if request.user.is_superuser or request.user.is_finance_admin():
            return qs

        # Auditors see all logs (read-only)
        if hasattr(request.user, 'is_auditor') and request.user.is_auditor():
            return qs

        # Managers see their department's logs
        elif request.user.is_manager():
            if request.user.department:
                return qs.filter(user__department=request.user.department)
            return qs.none()

        # Others see only their own logs
        else:
            return qs.filter(user=request.user)

    def has_add_permission(self, request):
        """Only system creates audit logs"""
        return False

    def has_change_permission(self, request, obj=None):
        """Audit logs are read-only"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Only superuser can delete audit logs"""
        return request.user.is_superuser
