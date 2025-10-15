from rest_framework import serializers
from django.utils import timezone
from .models import Approval, Comment, Notification, AuditLog
from expenses.models import Expense


class ApprovalSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(source='approver.get_full_name', read_only=True)
    expense_details = serializers.SerializerMethodField()

    class Meta:
        model = Approval
        fields = [
            'id', 'expense', 'expense_details', 'approver', 'approver_name',
            'status', 'comments', 'approved_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['approver', 'approved_at', 'created_at', 'updated_at']

    def get_expense_details(self, obj):
        return {
            'id': obj.expense.id,
            'vendor': obj.expense.vendor,
            'total_amount': str(obj.expense.total_amount),
            'date': obj.expense.date,
            'submitter': obj.expense.user.get_full_name()
        }


class ApprovalActionSerializer(serializers.Serializer):
    """Serializer for approve/reject actions"""
    status = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])
    comments = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        instance.status = validated_data['status']
        instance.comments = validated_data.get('comments', instance.comments)
        instance.approved_at = timezone.now()
        instance.save()

        # Update expense status
        instance.expense.status = validated_data['status']
        instance.expense.save()

        return instance


class CommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'expense', 'user', 'user_name', 'text', 'created_at', 'updated_at']
        read_only_fields = ['user', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'notification_type', 'title', 'message',
            'expense', 'is_read', 'created_at'
        ]
        read_only_fields = ['user', 'created_at']


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'action_type', 'model_name',
            'object_id', 'changes', 'ip_address', 'timestamp'
        ]
        read_only_fields = ['user', 'action_type', 'model_name', 'object_id', 'changes', 'ip_address', 'timestamp']
