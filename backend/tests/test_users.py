from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from decimal import Decimal
from users.models import Department, User

User = get_user_model()


class DepartmentModelTest(TestCase):
    """Test cases for Department model"""

    def setUp(self):
        """Set up test data"""
        self.manager = User.objects.create_user(
            username='manager1',
            email='manager@test.com',
            password='testpass123',
            role=User.Role.MANAGER,
            first_name='John',
            last_name='Manager'
        )

        self.department = Department.objects.create(
            name='Engineering',
            code='ENG',
            description='Engineering Department',
            manager=self.manager
        )

    def test_department_creation(self):
        """Test department can be created successfully"""
        self.assertEqual(self.department.name, 'Engineering')
        self.assertEqual(self.department.code, 'ENG')
        self.assertEqual(self.department.manager, self.manager)
        self.assertTrue(self.department.is_active)

    def test_department_str_method(self):
        """Test department string representation"""
        self.assertEqual(str(self.department), 'Engineering (ENG)')

    def test_department_unique_name(self):
        """Test that department name must be unique"""
        with self.assertRaises(IntegrityError):
            Department.objects.create(
                name='Engineering',
                code='ENG2'
            )

    def test_department_unique_code(self):
        """Test that department code must be unique"""
        with self.assertRaises(IntegrityError):
            Department.objects.create(
                name='Engineering 2',
                code='ENG'
            )

    def test_get_employee_count(self):
        """Test getting employee count in department"""
        # Create employees in the department
        User.objects.create_user(
            username='emp1',
            email='emp1@test.com',
            password='testpass123',
            department=self.department
        )
        User.objects.create_user(
            username='emp2',
            email='emp2@test.com',
            password='testpass123',
            department=self.department
        )

        # Create inactive employee (should not be counted)
        inactive_user = User.objects.create_user(
            username='emp3',
            email='emp3@test.com',
            password='testpass123',
            department=self.department
        )
        inactive_user.is_active = False
        inactive_user.save()

        self.assertEqual(self.department.get_employee_count(), 2)

    def test_get_manager_name(self):
        """Test getting manager name"""
        self.assertEqual(self.department.get_manager_name(), 'John Manager')

        # Test department without manager
        dept_no_manager = Department.objects.create(
            name='Marketing',
            code='MKT'
        )
        self.assertEqual(dept_no_manager.get_manager_name(), 'No Manager')

    def test_get_total_expenses(self):
        """Test getting total approved expenses for department"""
        # Initial total should be 0
        total = self.department.get_total_expenses()
        self.assertEqual(total, Decimal('0.00'))


class UserModelTest(TestCase):
    """Test cases for User model"""

    def setUp(self):
        """Set up test data"""
        self.department = Department.objects.create(
            name='Sales',
            code='SAL'
        )

    def test_user_creation(self):
        """Test user can be created successfully"""
        user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            role=User.Role.EMPLOYEE,
            department=self.department,
            phone='1234567890'
        )

        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@test.com')
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        self.assertEqual(user.department, self.department)
        self.assertTrue(user.check_password('testpass123'))

    def test_user_str_method(self):
        """Test user string representation"""
        user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            role=User.Role.EMPLOYEE
        )

        self.assertEqual(str(user), 'Test User (Employee)')

    def test_user_str_method_without_name(self):
        """Test user string representation without full name"""
        user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            role=User.Role.MANAGER
        )

        self.assertEqual(str(user), 'testuser (Manager)')

    def test_unique_email(self):
        """Test that email must be unique"""
        User.objects.create_user(
            username='user1',
            email='same@test.com',
            password='testpass123'
        )

        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username='user2',
                email='same@test.com',
                password='testpass123'
            )

    def test_default_role_is_employee(self):
        """Test that default role is EMPLOYEE"""
        user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

        self.assertEqual(user.role, User.Role.EMPLOYEE)

    def test_is_manager_method(self):
        """Test is_manager method"""
        manager = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123',
            role=User.Role.MANAGER
        )
        employee = User.objects.create_user(
            username='employee',
            email='employee@test.com',
            password='testpass123',
            role=User.Role.EMPLOYEE
        )

        self.assertTrue(manager.is_manager())
        self.assertFalse(employee.is_manager())

    def test_is_finance_admin_method(self):
        """Test is_finance_admin method"""
        finance_admin = User.objects.create_user(
            username='finance',
            email='finance@test.com',
            password='testpass123',
            role=User.Role.FINANCE_ADMIN
        )
        employee = User.objects.create_user(
            username='employee',
            email='employee@test.com',
            password='testpass123',
            role=User.Role.EMPLOYEE
        )

        self.assertTrue(finance_admin.is_finance_admin())
        self.assertFalse(employee.is_finance_admin())

    def test_is_auditor_method(self):
        """Test is_auditor method"""
        auditor = User.objects.create_user(
            username='auditor',
            email='auditor@test.com',
            password='testpass123',
            role=User.Role.AUDITOR
        )
        employee = User.objects.create_user(
            username='employee',
            email='employee@test.com',
            password='testpass123',
            role=User.Role.EMPLOYEE
        )

        self.assertTrue(auditor.is_auditor())
        self.assertFalse(employee.is_auditor())

    def test_all_user_roles(self):
        """Test all available user roles"""
        roles = [
            User.Role.EMPLOYEE,
            User.Role.MANAGER,
            User.Role.FINANCE_ADMIN,
            User.Role.AUDITOR
        ]

        for role in roles:
            user = User.objects.create_user(
                username=f'user_{role}',
                email=f'{role}@test.com',
                password='testpass123',
                role=role
            )
            self.assertEqual(user.role, role)

    def test_user_department_relationship(self):
        """Test user-department relationship"""
        user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            department=self.department
        )

        self.assertEqual(user.department, self.department)
        self.assertIn(user, self.department.users.all())

    def test_user_can_exist_without_department(self):
        """Test that user can exist without a department"""
        user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

        self.assertIsNone(user.department)
