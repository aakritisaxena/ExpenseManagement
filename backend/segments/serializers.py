from rest_framework import serializers
from .models import Segment, Budget
from users.models import Department


class SegmentSerializer(serializers.ModelSerializer):
    department_names = serializers.SerializerMethodField()

    class Meta:
        model = Segment
        fields = ['id', 'name', 'description', 'departments', 'department_names', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def get_department_names(self, obj):
        return [dept.name for dept in obj.departments.all()]


class BudgetSerializer(serializers.ModelSerializer):
    segment_name = serializers.CharField(source='segment.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    spent_amount = serializers.SerializerMethodField()
    remaining_budget = serializers.SerializerMethodField()
    percentage_used = serializers.SerializerMethodField()
    is_over_threshold = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = [
            'id', 'segment', 'segment_name', 'department', 'department_name',
            'allocated_amount', 'period_type', 'start_date', 'end_date',
            'alert_threshold_percentage', 'spent_amount', 'remaining_budget',
            'percentage_used', 'is_over_threshold', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_spent_amount(self, obj):
        return float(obj.get_spent_amount())

    def get_remaining_budget(self, obj):
        return float(obj.get_remaining_budget())

    def get_percentage_used(self, obj):
        return round(obj.get_percentage_used(), 2)

    def get_is_over_threshold(self, obj):
        return obj.is_over_threshold()

    def validate(self, attrs):
        if attrs.get('segment') and attrs.get('department'):
            raise serializers.ValidationError("Budget can be for either segment or department, not both.")
        if not attrs.get('segment') and not attrs.get('department'):
            raise serializers.ValidationError("Budget must be for either segment or department.")
        if attrs['end_date'] <= attrs['start_date']:
            raise serializers.ValidationError("End date must be after start date.")
        return attrs
