from django.core.management.base import BaseCommand
from users.models import User
from segments.models import Segment
from expenses.models import Currency, Expense, ExpenseSegmentAllocation
from datetime import date, timedelta
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Create sample expenses for testing'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Creating sample expenses...'))

        # Get required data
        try:
            usd = Currency.objects.get(code='USD')
            segments = list(Segment.objects.all())
            users = list(User.objects.filter(role='EMPLOYEE'))

            if not segments:
                self.stdout.write(self.style.ERROR('No segments found! Run create_sample_data first.'))
                return

            if not users:
                self.stdout.write(self.style.ERROR('No employees found! Run create_sample_data first.'))
                return

        except Currency.DoesNotExist:
            self.stdout.write(self.style.ERROR('USD currency not found! Run create_sample_data first.'))
            return

        # Sample expense data
        expense_templates = [
            {
                'vendor': 'Delta Airlines',
                'description': 'Flight to client meeting in San Francisco',
                'amount': 450.00,
                'segments': [{'name': 'Travel', 'percentage': 100}]
            },
            {
                'vendor': 'Hilton Hotel',
                'description': 'Hotel stay for tech conference (3 nights)',
                'amount': 720.00,
                'segments': [{'name': 'Travel', 'percentage': 60}, {'name': 'Training & Development', 'percentage': 40}]
            },
            {
                'vendor': 'AWS',
                'description': 'Cloud services monthly subscription',
                'amount': 1250.00,
                'segments': [{'name': 'Software & Tools', 'percentage': 100}]
            },
            {
                'vendor': 'Starbucks',
                'description': 'Client lunch meeting',
                'amount': 45.50,
                'segments': [{'name': 'Meals & Entertainment', 'percentage': 100}]
            },
            {
                'vendor': 'Google Ads',
                'description': 'Q1 Digital marketing campaign',
                'amount': 5000.00,
                'segments': [{'name': 'Marketing', 'percentage': 100}]
            },
            {
                'vendor': 'Office Depot',
                'description': 'Office supplies and stationery',
                'amount': 156.75,
                'segments': [{'name': 'Office Supplies', 'percentage': 100}]
            },
            {
                'vendor': 'Apple Store',
                'description': 'MacBook Pro for new developer',
                'amount': 2399.00,
                'segments': [{'name': 'Equipment', 'percentage': 100}]
            },
            {
                'vendor': 'Udemy',
                'description': 'Python and Django training courses for team',
                'amount': 199.99,
                'segments': [{'name': 'Training & Development', 'percentage': 100}]
            },
            {
                'vendor': 'Uber',
                'description': 'Transportation to airport and client office',
                'amount': 85.00,
                'segments': [{'name': 'Travel', 'percentage': 100}]
            },
            {
                'vendor': 'Zoom',
                'description': 'Video conferencing subscription',
                'amount': 149.90,
                'segments': [{'name': 'Software & Tools', 'percentage': 100}]
            },
            {
                'vendor': 'FedEx',
                'description': 'Shipping product samples to clients',
                'amount': 67.50,
                'segments': [{'name': 'Marketing', 'percentage': 60}, {'name': 'Office Supplies', 'percentage': 40}]
            },
            {
                'vendor': 'LinkedIn Ads',
                'description': 'B2B lead generation campaign',
                'amount': 3500.00,
                'segments': [{'name': 'Marketing', 'percentage': 100}]
            },
            {
                'vendor': 'Restaurant Le Bernardin',
                'description': 'Dinner with key client and prospects',
                'amount': 380.00,
                'segments': [{'name': 'Meals & Entertainment', 'percentage': 100}]
            },
            {
                'vendor': 'GitHub',
                'description': 'Enterprise plan for development team',
                'amount': 450.00,
                'segments': [{'name': 'Software & Tools', 'percentage': 100}]
            },
            {
                'vendor': 'Staples',
                'description': 'Printer paper and toner cartridges',
                'amount': 234.50,
                'segments': [{'name': 'Office Supplies', 'percentage': 100}]
            },
        ]

        created_count = 0
        for template in expense_templates:
            # Pick a random user
            user = random.choice(users)

            # Random date in the last 30 days
            days_ago = random.randint(1, 30)
            expense_date = date.today() - timedelta(days=days_ago)

            # Random status
            statuses = ['PENDING', 'PENDING', 'APPROVED', 'DRAFT']  # More pending than others
            status = random.choice(statuses)

            # Create expense
            expense = Expense.objects.create(
                user=user,
                date=expense_date,
                vendor=template['vendor'],
                description=template['description'],
                total_amount=Decimal(str(template['amount'])),
                currency=usd,
                status=status
            )

            # Create segment allocations
            for seg_alloc in template['segments']:
                try:
                    segment = Segment.objects.get(name=seg_alloc['name'])
                    ExpenseSegmentAllocation.objects.create(
                        expense=expense,
                        segment=segment,
                        percentage=Decimal(str(seg_alloc['percentage']))
                    )
                except Segment.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"  Segment '{seg_alloc['name']}' not found, skipping"))

            created_count += 1
            self.stdout.write(f"  ✓ {expense.vendor} - ${expense.total_amount} ({expense.get_status_display()})")

        self.stdout.write(self.style.SUCCESS(f'\n✅ Created {created_count} sample expenses!'))
        self.stdout.write(self.style.SUCCESS('\nYou can view them at: http://127.0.0.1:8000/admin/expenses/expense/'))
