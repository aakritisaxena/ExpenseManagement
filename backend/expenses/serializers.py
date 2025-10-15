from rest_framework import serializers
from .models import Currency, Expense, ExpenseSegmentAllocation
from segments.models import Segment


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'symbol', 'exchange_rate_to_base', 'is_base_currency', 'updated_at']
        read_only_fields = ['updated_at']


class ExpenseSegmentAllocationSerializer(serializers.ModelSerializer):
    segment_name = serializers.CharField(source='segment.name', read_only=True)

    class Meta:
        model = ExpenseSegmentAllocation
        fields = ['id', 'segment', 'segment_name', 'percentage', 'amount', 'notes']
        read_only_fields = ['amount']


class ExpenseSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    segment_allocations = ExpenseSegmentAllocationSerializer(many=True, required=False)
    total_allocated_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = [
            'id', 'user', 'user_name', 'date', 'vendor', 'description',
            'total_amount', 'currency', 'currency_code', 'amount_in_base_currency',
            'receipt', 'status', 'notes', 'segment_allocations',
            'total_allocated_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'amount_in_base_currency', 'created_at', 'updated_at']

    def get_total_allocated_percentage(self, obj):
        return float(obj.get_total_allocated_percentage())

    def validate_segment_allocations(self, value):
        """Validate that segment allocations sum to 100%"""
        if value:
            total = sum(float(alloc.get('percentage', 0)) for alloc in value)
            if abs(total - 100) > 0.01:  # Allow small floating point errors
                raise serializers.ValidationError(f"Segment allocations must sum to 100%, got {total}%")
        return value

    def create(self, validated_data):
        segment_allocations_data = validated_data.pop('segment_allocations', [])
        validated_data['user'] = self.context['request'].user
        expense = Expense.objects.create(**validated_data)

        # Create segment allocations
        for allocation_data in segment_allocations_data:
            ExpenseSegmentAllocation.objects.create(expense=expense, **allocation_data)

        return expense

    def update(self, instance, validated_data):
        segment_allocations_data = validated_data.pop('segment_allocations', None)

        # Update expense fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update segment allocations if provided
        if segment_allocations_data is not None:
            instance.segment_allocations.all().delete()
            for allocation_data in segment_allocations_data:
                ExpenseSegmentAllocation.objects.create(expense=instance, **allocation_data)

        return instance


class ExpenseDetailSerializer(ExpenseSerializer):
    """Detailed expense serializer with all related information"""
    user_details = serializers.SerializerMethodField()
    currency_details = CurrencySerializer(source='currency', read_only=True)

    class Meta(ExpenseSerializer.Meta):
        fields = ExpenseSerializer.Meta.fields + ['user_details', 'currency_details']

    def get_user_details(self, obj):
        return {
            'id': obj.user.id,
            'username': obj.user.username,
            'full_name': obj.user.get_full_name(),
            'email': obj.user.email,
            'department': obj.user.department.name if obj.user.department else None
        }


class ExpenseCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating expenses"""
    segment_allocations = ExpenseSegmentAllocationSerializer(many=True)

    class Meta:
        model = Expense
        fields = [
            'date', 'vendor', 'description', 'total_amount', 'currency',
            'receipt', 'status', 'notes', 'segment_allocations'
        ]

    def validate_segment_allocations(self, value):
        """Validate that segment allocations sum to 100%"""
        if not value:
            raise serializers.ValidationError("At least one segment allocation is required.")

        total = sum(float(alloc.get('percentage', 0)) for alloc in value)
        if abs(total - 100) > 0.01:
            raise serializers.ValidationError(f"Segment allocations must sum to 100%, got {total}%")
        return value

    def create(self, validated_data):
        segment_allocations_data = validated_data.pop('segment_allocations')
        validated_data['user'] = self.context['request'].user
        expense = Expense.objects.create(**validated_data)

        for allocation_data in segment_allocations_data:
            ExpenseSegmentAllocation.objects.create(expense=expense, **allocation_data)

        return expense

    def update(self, instance, validated_data):
        segment_allocations_data = validated_data.pop('segment_allocations', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if segment_allocations_data:
            instance.segment_allocations.all().delete()
            for allocation_data in segment_allocations_data:
                ExpenseSegmentAllocation.objects.create(expense=instance, **allocation_data)

        return instance
