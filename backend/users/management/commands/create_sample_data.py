from django.core.management.base import BaseCommand
from users.models import User, Department
from segments.models import Segment, Budget
from expenses.models import Currency, Expense, ExpenseSegmentAllocation
from datetime import date, timedelta
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Create sample data for testing the Expense Management System'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Creating sample data...'))

        # Create Departments
        self.stdout.write('Creating departments...')
        departments_data = [
            {'name': 'Engineering', 'code': 'ENG', 'description': 'Software and Hardware Engineering'},
            {'name': 'Marketing', 'code': 'MKT', 'description': 'Marketing and Communications'},
            {'name': 'Sales', 'code': 'SAL', 'description': 'Sales and Business Development'},
            {'name': 'Finance', 'code': 'FIN', 'description': 'Finance and Accounting'},
            {'name': 'Human Resources', 'code': 'HR', 'description': 'Human Resources and Recruitment'},
        ]

        departments = {}
        for dept_data in departments_data:
            dept, created = Department.objects.get_or_create(
                code=dept_data['code'],
                defaults={'name': dept_data['name'], 'description': dept_data['description']}
            )
            departments[dept_data['code']] = dept
            status = 'created' if created else 'already exists'
            self.stdout.write(f'  - {dept.name}: {status}')

        # Create Users
        self.stdout.write('\nCreating users...')
        users_data = [
            # Managers
            {'username': 'john_manager', 'email': 'john@company.com', 'first_name': 'John', 'last_name': 'Smith',
             'role': 'MANAGER', 'dept': 'ENG'},
            {'username': 'sarah_manager', 'email': 'sarah@company.com', 'first_name': 'Sarah', 'last_name': 'Johnson',
             'role': 'MANAGER', 'dept': 'MKT'},
            {'username': 'mike_manager', 'email': 'mike@company.com', 'first_name': 'Mike', 'last_name': 'Davis',
             'role': 'MANAGER', 'dept': 'SAL'},

            # Finance Admin
            {'username': 'alice_finance', 'email': 'alice@company.com', 'first_name': 'Alice', 'last_name': 'Williams',
             'role': 'FINANCE_ADMIN', 'dept': 'FIN'},

            # Employees - Engineering
            {'username': 'bob_dev', 'email': 'bob@company.com', 'first_name': 'Bob', 'last_name': 'Brown',
             'role': 'EMPLOYEE', 'dept': 'ENG'},
            {'username': 'charlie_dev', 'email': 'charlie@company.com', 'first_name': 'Charlie', 'last_name': 'Wilson',
             'role': 'EMPLOYEE', 'dept': 'ENG'},
            {'username': 'diana_dev', 'email': 'diana@company.com', 'first_name': 'Diana', 'last_name': 'Martinez',
             'role': 'EMPLOYEE', 'dept': 'ENG'},

            # Employees - Marketing
            {'username': 'emma_marketing', 'email': 'emma@company.com', 'first_name': 'Emma', 'last_name': 'Garcia',
             'role': 'EMPLOYEE', 'dept': 'MKT'},
            {'username': 'frank_marketing', 'email': 'frank@company.com', 'first_name': 'Frank', 'last_name': 'Rodriguez',
             'role': 'EMPLOYEE', 'dept': 'MKT'},

            # Employees - Sales
            {'username': 'grace_sales', 'email': 'grace@company.com', 'first_name': 'Grace', 'last_name': 'Lee',
             'role': 'EMPLOYEE', 'dept': 'SAL'},
            {'username': 'henry_sales', 'email': 'henry@company.com', 'first_name': 'Henry', 'last_name': 'Taylor',
             'role': 'EMPLOYEE', 'dept': 'SAL'},
        ]

        users = {}
        for user_data in users_data:
            dept_code = user_data.pop('dept')
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    **user_data,
                    'department': departments[dept_code]
                }
            )
            if created:
                user.set_password('password123')
                user.save()
            users[user.username] = user
            status = 'created' if created else 'already exists'
            self.stdout.write(f'  - {user.username} ({user.get_role_display()}): {status}')

        # Assign managers to departments
        self.stdout.write('\nAssigning managers to departments...')
        departments['ENG'].manager = users['john_manager']
        departments['ENG'].save()
        self.stdout.write(f'  - Engineering: John Smith')

        departments['MKT'].manager = users['sarah_manager']
        departments['MKT'].save()
        self.stdout.write(f'  - Marketing: Sarah Johnson')

        departments['SAL'].manager = users['mike_manager']
        departments['SAL'].save()
        self.stdout.write(f'  - Sales: Mike Davis')

        # Create Segments (Categories)
        self.stdout.write('\nCreating expense segments...')
        segments_data = [
            {'name': 'Travel', 'description': 'Business travel expenses including flights, hotels, and transportation'},
            {'name': 'Meals & Entertainment', 'description': 'Client meetings, team lunches, and business entertainment'},
            {'name': 'Office Supplies', 'description': 'Stationery, equipment, and office necessities'},
            {'name': 'Software & Tools', 'description': 'Software licenses, SaaS subscriptions, and development tools'},
            {'name': 'Marketing', 'description': 'Advertising, events, campaigns, and promotional materials'},
            {'name': 'Training & Development', 'description': 'Courses, conferences, and professional development'},
            {'name': 'Equipment', 'description': 'Computer hardware, furniture, and office equipment'},
        ]

        segments = {}
        for seg_data in segments_data:
            seg, created = Segment.objects.get_or_create(
                name=seg_data['name'],
                defaults={'description': seg_data['description']}
            )
            segments[seg.name] = seg
            status = 'created' if created else 'already exists'
            self.stdout.write(f'  - {seg.name}: {status}')

        # Create Currency
        self.stdout.write('\nCreating currencies...')
        usd, created = Currency.objects.get_or_create(
            code='USD',
            defaults={
                'name': 'US Dollar',
                'symbol': '$',
                'exchange_rate_to_base': Decimal('1.0'),
                'is_base_currency': True
            }
        )
        self.stdout.write(f'  - USD (US Dollar): {"created" if created else "already exists"}')

        # Create Budgets
        self.stdout.write('\nCreating department budgets...')
        today = date.today()
        budget_data = [
            {'segment': 'Travel', 'dept': 'ENG', 'amount': 50000},
            {'segment': 'Software & Tools', 'dept': 'ENG', 'amount': 100000},
            {'segment': 'Marketing', 'dept': 'MKT', 'amount': 150000},
            {'segment': 'Travel', 'dept': 'SAL', 'amount': 75000},
        ]

        for budget_info in budget_data:
            budget, created = Budget.objects.get_or_create(
                segment=segments[budget_info['segment']],
                department=departments[budget_info['dept']],
                start_date=date(today.year, today.month, 1),
                defaults={
                    'allocated_amount': budget_info['amount'],
                    'period_type': 'MONTHLY',
                    'end_date': date(today.year, today.month + 1, 1) if today.month < 12 else date(today.year + 1, 1, 1),
                    'alert_threshold_percentage': 80
                }
            )
            status = 'created' if created else 'already exists'
            self.stdout.write(f'  - {budget_info["dept"]} - {budget_info["segment"]}: ${budget_info["amount"]:,} ({status})')

        self.stdout.write(self.style.SUCCESS('\n✅ Sample data created successfully!'))
        self.stdout.write(self.style.SUCCESS('\nYou can now login to the admin panel with:'))
        self.stdout.write(self.style.SUCCESS('  Username: admin'))
        self.stdout.write(self.style.SUCCESS('  Password: admin123'))
        self.stdout.write(self.style.SUCCESS('\nOr use any sample user:'))
        self.stdout.write(self.style.SUCCESS('  Username: john_manager (or any other username)'))
        self.stdout.write(self.style.SUCCESS('  Password: password123'))
