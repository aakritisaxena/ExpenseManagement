# Invoice & Expense Segmentation App

A full-stack expense management system with multi-segment allocation built with Django (Python) and React.

## 🚀 Quick Start

### Backend (Django)

**Server Status:** ✅ Running at http://127.0.0.1:8000

**Admin Panel:** http://127.0.0.1:8000/admin

**Admin Credentials:**
- Username: `admin`
- Password: `admin123`

**Start Server:**
```bash
cd backend
source ../venv/bin/activate
python manage.py runserver
```

## 📊 Features Implemented

### ✅ Backend (Django REST Framework)
- [x] Custom User model with 4 roles (Employee, Manager, Finance Admin, Auditor)
- [x] Department/Cost Center management
- [x] Segment (Category) management
- [x] Multi-segment expense allocation (split by percentage)
- [x] Multi-currency support with auto-conversion
- [x] Budget tracking with alert thresholds
- [x] Approval workflow system
- [x] Comments on expenses
- [x] In-app notifications
- [x] Complete audit logging
- [x] Django Admin panel (fully configured)
- [x] DRF Serializers for all models

### 🔜 To Do (Next Steps)
- [ ] ViewSets and API endpoints
- [ ] JWT authentication (login/register)
- [ ] Role-based permissions
- [ ] React frontend setup
- [ ] API integration
- [ ] Dashboard with charts
- [ ] Email notifications

## 🗂️ Database Models

### Users App
- **User**: Custom auth user with roles and department
- **Department**: Cost centers/departments

### Segments App
- **Segment**: Expense categories (Travel, Marketing, etc.)
- **Budget**: Budget allocation per segment/department

### Expenses App
- **Currency**: Multi-currency support
- **Expense**: Main expense/invoice model
- **ExpenseSegmentAllocation**: Split expenses across segments

### Approvals App
- **Approval**: Expense approval tracking
- **Comment**: Discussion on expenses
- **Notification**: In-app notifications
- **AuditLog**: Complete audit trail

## 🔧 Tech Stack

**Backend:**
- Python 3.9
- Django 4.2.9
- Django REST Framework
- Simple JWT (authentication)
- SQLite (development) / PostgreSQL (production)

**Frontend (Coming):**
- React with TypeScript
- Vite
- Tailwind CSS
- React Query
- Recharts (for analytics)

## 📝 Django Admin Panel

The Django Admin panel is fully configured and ready to use! You can:
- Manage users and assign roles
- Create departments
- Create segments (expense categories)
- Set up budgets with alerts
- View all expenses with segment breakdowns
- Track approvals and comments
- Monitor notifications
- View complete audit logs

## 🎯 2-Week Development Plan

**Week 1: Core MVP**
- Days 1-2: ✅ Backend foundation & models
- Days 3-4: API endpoints & authentication
- Days 5-6: React setup & expense submission
- Day 7: Approval workflow UI

**Week 2: Advanced Features**
- Days 8-9: Budgeting & alerts
- Days 10-11: Analytics dashboard
- Days 12-13: Notifications & polish
- Day 14: Testing & deployment

## 🔐 User Roles

1. **Employee**: Submit expenses, view own submissions
2. **Manager**: Approve team expenses, view department budgets
3. **Finance Admin**: Configure segments, budgets, run reports
4. **Auditor**: View audit logs, read-only access

## 💡 Key Features

### Multi-Segment Allocation
Split any expense across multiple categories:
- Example: $1000 expense → 30% Travel ($300) + 70% Meals ($700)
- Validation ensures allocations = 100%

### Budget Tracking
- Set budgets per segment or department
- Alert thresholds (default 80%)
- Real-time spent/remaining calculations

### Approval Workflow
- Automatic routing to manager
- Multi-level approval hierarchies
- Comments and discussions

## 📂 Project Structure

```
ExpenseManagement/
├── backend/
│   ├── expense_manager/    # Django project settings
│   ├── users/              # User & Department
│   ├── segments/           # Segments & Budgets
│   ├── expenses/           # Expenses & Currency
│   ├── approvals/          # Approvals & Notifications
│   ├── manage.py
│   └── db.sqlite3
├── venv/                   # Virtual environment
└── README.md
```

## 🚦 Current Status

**Progress:** Day 1-2 Backend Foundation Complete! 🎉

The backend foundation is solid with:
- 8 database models
- Complete admin panel
- All serializers ready
- Database migrations applied

Next up: Creating API endpoints and starting the React frontend!
