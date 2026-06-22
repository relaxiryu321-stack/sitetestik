from datetime import date, time, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from hr.models import (
    AbsenceType,
    AuditAction,
    AuditLog,
    Department,
    DocumentCategory,
    Employee,
    EmployeeDocument,
    EmployeeStatus,
    LeaveRequest,
    Notification,
    Position,
    RequestStatus,
    User,
    UserRole,
    WorkLog,
)
from hr.services import create_audit_log


class Command(BaseCommand):
    help = 'Populate the database with deterministic demo data for all major entities.'

    demo_password = 'DemoPass123!'

    def handle(self, *args, **options):
        with transaction.atomic():
            seed_stats = self.seed_demo_data()

        self.stdout.write(self.style.SUCCESS('Demo data created/updated successfully.'))
        self.stdout.write(f'Password for all demo users: {self.demo_password}')
        for key, value in seed_stats.items():
            self.stdout.write(f'{key}: {value}')

    def seed_demo_data(self):
        created = {
            'users': 0,
            'departments': 0,
            'positions': 0,
            'employees': 0,
            'work_logs': 0,
            'leave_requests': 0,
            'documents': 0,
            'notifications': 0,
            'audit_logs': 0,
        }

        user_specs = [
            {
                'username': 'demo_admin',
                'email': 'demo.admin@webx.local',
                'first_name': 'Olena',
                'last_name': 'Kravets',
                'role': UserRole.ADMIN,
                'is_staff': True,
            },
            {
                'username': 'ops_manager',
                'email': 'ops.manager@webx.local',
                'first_name': 'Andrii',
                'last_name': 'Melnyk',
                'role': UserRole.MANAGER,
            },
            {
                'username': 'finance_manager',
                'email': 'finance.manager@webx.local',
                'first_name': 'Iryna',
                'last_name': 'Bondar',
                'role': UserRole.MANAGER,
            },
            {
                'username': 'it_manager',
                'email': 'it.manager@webx.local',
                'first_name': 'Maksym',
                'last_name': 'Tkachenko',
                'role': UserRole.MANAGER,
            },
            {
                'username': 'worker_anna',
                'email': 'anna.hrytsenko@webx.local',
                'first_name': 'Anna',
                'last_name': 'Hrytsenko',
                'role': UserRole.EMPLOYEE,
            },
            {
                'username': 'worker_oleh',
                'email': 'oleh.kovalenko@webx.local',
                'first_name': 'Oleh',
                'last_name': 'Kovalenko',
                'role': UserRole.EMPLOYEE,
            },
            {
                'username': 'worker_sofia',
                'email': 'sofia.romaniuk@webx.local',
                'first_name': 'Sofia',
                'last_name': 'Romaniuk',
                'role': UserRole.EMPLOYEE,
            },
            {
                'username': 'worker_dmytro',
                'email': 'dmytro.shevchenko@webx.local',
                'first_name': 'Dmytro',
                'last_name': 'Shevchenko',
                'role': UserRole.EMPLOYEE,
            },
            {
                'username': 'worker_nazar',
                'email': 'nazar.babenko@webx.local',
                'first_name': 'Nazar',
                'last_name': 'Babenko',
                'role': UserRole.EMPLOYEE,
            },
            {
                'username': 'worker_maria',
                'email': 'maria.levchenko@webx.local',
                'first_name': 'Maria',
                'last_name': 'Levchenko',
                'role': UserRole.EMPLOYEE,
            },
            {
                'username': 'worker_yevhen',
                'email': 'yevhen.marchenko@webx.local',
                'first_name': 'Yevhen',
                'last_name': 'Marchenko',
                'role': UserRole.EMPLOYEE,
            },
            {
                'username': 'worker_viktoria',
                'email': 'viktoria.soloviova@webx.local',
                'first_name': 'Viktoria',
                'last_name': 'Soloviova',
                'role': UserRole.EMPLOYEE,
            },
            {
                'username': 'worker_ihor',
                'email': 'ihor.poliakov@webx.local',
                'first_name': 'Ihor',
                'last_name': 'Poliakov',
                'role': UserRole.EMPLOYEE,
            },
        ]

        users = {}
        for spec in user_specs:
            user, was_created = self.upsert_user(**spec)
            users[spec['username']] = user
            created['users'] += int(was_created)

        department_specs = [
            {
                'name': 'Operations',
                'description': 'Daily operations, logistics, and execution control.',
                'manager_username': 'ops_manager',
                'positions': ['Operations Manager', 'Senior Operator', 'Operator', 'Dispatcher'],
            },
            {
                'name': 'Finance',
                'description': 'Budgeting, payroll, invoices, and reporting.',
                'manager_username': 'finance_manager',
                'positions': ['Finance Manager', 'Accountant', 'Payroll Specialist'],
            },
            {
                'name': 'IT',
                'description': 'Infrastructure, internal tools, and technical support.',
                'manager_username': 'it_manager',
                'positions': ['IT Manager', 'Backend Developer', 'Support Engineer'],
            },
        ]

        departments = {}
        positions = {}
        for spec in department_specs:
            department, was_created = Department.objects.update_or_create(
                name=spec['name'],
                defaults={'description': spec['description']},
            )
            created['departments'] += int(was_created)
            departments[spec['name']] = department

            for title in spec['positions']:
                position, pos_created = Position.objects.update_or_create(
                    title=title,
                    department=department,
                    defaults={'description': f'{title} role in {department.name} department.'},
                )
                created['positions'] += int(pos_created)
                positions[(spec['name'], title)] = position

        employee_specs = [
            ('ops_manager', 'Andrii Melnyk', 'Operations', 'Operations Manager', date(1987, 6, 12), date(2021, 3, 15), EmployeeStatus.ACTIVE, '+380970000101', 'Kyiv, Solomianska St. 14', 'Heads the operations department and reviews attendance.'),
            ('finance_manager', 'Iryna Bondar', 'Finance', 'Finance Manager', date(1989, 11, 4), date(2020, 5, 18), EmployeeStatus.ACTIVE, '+380970000102', 'Kyiv, Predslavynska St. 8', 'Approves finance-related requests and contracts.'),
            ('it_manager', 'Maksym Tkachenko', 'IT', 'IT Manager', date(1990, 1, 23), date(2022, 2, 7), EmployeeStatus.ACTIVE, '+380970000103', 'Kyiv, Naberezhno-Luhova St. 27', 'Coordinates releases, tooling, and support rotation.'),
            ('worker_anna', 'Anna Hrytsenko', 'Operations', 'Senior Operator', date(1994, 8, 19), date(2023, 4, 10), EmployeeStatus.ACTIVE, '+380970000201', 'Kyiv, Velyka Vasylkivska St. 22', 'Consistent performer with high accuracy metrics.'),
            ('worker_oleh', 'Oleh Kovalenko', 'Operations', 'Operator', date(1996, 2, 14), date(2024, 1, 8), EmployeeStatus.VACATION, '+380970000202', 'Bucha, Yablunska St. 3', 'Currently on annual leave.'),
            ('worker_sofia', 'Sofia Romaniuk', 'Operations', 'Dispatcher', date(1998, 9, 30), date(2024, 6, 3), EmployeeStatus.SICK_LEAVE, '+380970000203', 'Irpin, Universytetska St. 11', 'On short-term sick leave.'),
            ('worker_dmytro', 'Dmytro Shevchenko', 'Finance', 'Accountant', date(1993, 4, 9), date(2022, 9, 5), EmployeeStatus.ACTIVE, '+380970000204', 'Kyiv, Saksahanskoho St. 75', 'Handles monthly close and reconciliation.'),
            ('worker_nazar', 'Nazar Babenko', 'Finance', 'Payroll Specialist', date(1997, 7, 21), date(2023, 1, 16), EmployeeStatus.ACTIVE, '+380970000205', 'Vyshneve, Svobody St. 40', 'Owns payroll processing and benefit exports.'),
            ('worker_maria', 'Maria Levchenko', 'IT', 'Backend Developer', date(1995, 12, 2), date(2022, 7, 11), EmployeeStatus.ACTIVE, '+380970000206', 'Kyiv, Obolonska Naberezhna 15', 'Works on internal APIs and integrations.'),
            ('worker_yevhen', 'Yevhen Marchenko', 'IT', 'Support Engineer', date(1992, 3, 17), date(2021, 11, 1), EmployeeStatus.ACTIVE, '+380970000207', 'Kyiv, Verkhnii Val 9', 'Primary on-call support engineer.'),
            ('worker_viktoria', 'Viktoria Soloviova', 'IT', 'Support Engineer', date(1999, 10, 13), date(2025, 2, 3), EmployeeStatus.ACTIVE, '+380970000208', 'Kyiv, Hlybochytska St. 31', 'Newest support engineer, still within probation period.'),
            ('worker_ihor', 'Ihor Poliakov', 'Operations', 'Operator', date(1991, 5, 27), date(2020, 8, 24), EmployeeStatus.DISMISSED, '+380970000209', 'Brovary, Kyivska St. 52', 'Dismissed employee kept for history and audit trails.'),
        ]

        employees = {}
        for (
            username,
            full_name,
            department_name,
            position_title,
            birth_date,
            hired_at,
            status,
            phone,
            address,
            notes,
        ) in employee_specs:
            user = users[username]
            employee, was_created = Employee.objects.update_or_create(
                user=user,
                defaults={
                    'full_name': full_name,
                    'birth_date': birth_date,
                    'email': user.email,
                    'phone': phone,
                    'address': address,
                    'position': positions[(department_name, position_title)],
                    'department': departments[department_name],
                    'hired_at': hired_at,
                    'probation_end_date': hired_at + timedelta(days=90),
                    'contract_end_date': hired_at + timedelta(days=365 * 3),
                    'status': status,
                    'notes': notes,
                },
            )
            created['employees'] += int(was_created)
            employees[username] = employee

        for spec in department_specs:
            department = departments[spec['name']]
            department.manager = employees[spec['manager_username']]
            department.save(update_fields=['manager'])

        created['work_logs'] += self.seed_work_logs(employees)
        created['leave_requests'] += self.seed_leave_requests(employees, users['demo_admin'])
        created['documents'] += self.seed_documents(employees, users['demo_admin'])
        created['notifications'] += self.seed_notifications(users, employees)
        created['audit_logs'] += self.seed_audit_logs(users, employees)

        return created

    def upsert_user(self, *, username, email, first_name, last_name, role, is_staff=False):
        user, created = User.objects.get_or_create(username=username, defaults={'email': email})
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.role = role
        user.is_staff = is_staff or role == UserRole.ADMIN
        user.is_superuser = False
        user.is_blocked = False
        user.set_password(self.demo_password)
        user.save()
        return user, created

    def seed_work_logs(self, employees):
        created_count = 0
        absence_cycle = [
            AbsenceType.NONE,
            AbsenceType.NONE,
            AbsenceType.DAY_OFF,
            AbsenceType.NONE,
            AbsenceType.SICK_LEAVE,
            AbsenceType.NONE,
            AbsenceType.UNPAID,
        ]
        today = timezone.localdate()

        for employee_index, username in enumerate(sorted(name for name in employees if name.startswith('worker_')), start=1):
            employee = employees[username]
            for day_offset in range(1, 8):
                work_date = today - timedelta(days=day_offset)
                if employee.status == EmployeeStatus.DISMISSED and day_offset < 4:
                    continue

                absence_type = absence_cycle[(employee_index + day_offset) % len(absence_cycle)]
                if absence_type == AbsenceType.NONE:
                    started_at = time(9, 0)
                    ended_at = time(18, 0)
                    lateness_minutes = (employee_index * day_offset) % 18
                    overtime_minutes = (employee_index * (day_offset + 1)) % 45
                else:
                    started_at = time(9, 0)
                    ended_at = time(17, 0)
                    lateness_minutes = 0
                    overtime_minutes = 0

                _, was_created = WorkLog.objects.update_or_create(
                    employee=employee,
                    work_date=work_date,
                    defaults={
                        'started_at': started_at,
                        'ended_at': ended_at,
                        'lateness_minutes': lateness_minutes,
                        'overtime_minutes': overtime_minutes,
                        'absence_type': absence_type,
                        'note': f'{employee.full_name} demo work log for {work_date.isoformat()}.',
                    },
                )
                created_count += int(was_created)

        return created_count

    def seed_leave_requests(self, employees, review_actor):
        created_count = 0
        requests = [
            ('worker_anna', AbsenceType.ANNUAL_LEAVE, date(2026, 5, 12), date(2026, 5, 16), RequestStatus.APPROVED, 'Approved in advance.'),
            ('worker_oleh', AbsenceType.ANNUAL_LEAVE, date(2026, 6, 2), date(2026, 6, 6), RequestStatus.PENDING, ''),
            ('worker_sofia', AbsenceType.SICK_LEAVE, date(2026, 4, 21), date(2026, 4, 25), RequestStatus.APPROVED, 'Medical certificate attached.'),
            ('worker_dmytro', AbsenceType.DAY_OFF, date(2026, 5, 5), date(2026, 5, 5), RequestStatus.REJECTED, 'Month-end close period.'),
            ('worker_nazar', AbsenceType.UNPAID, date(2026, 7, 7), date(2026, 7, 9), RequestStatus.PENDING, ''),
            ('worker_maria', AbsenceType.DAY_OFF, date(2026, 5, 19), date(2026, 5, 19), RequestStatus.APPROVED, 'Release compensatory day.'),
            ('worker_yevhen', AbsenceType.ANNUAL_LEAVE, date(2026, 8, 10), date(2026, 8, 21), RequestStatus.PENDING, ''),
        ]

        for username, absence_type, start_date, end_date, status, review_comment in requests:
            _, was_created = LeaveRequest.objects.update_or_create(
                employee=employees[username],
                start_date=start_date,
                end_date=end_date,
                defaults={
                    'absence_type': absence_type,
                    'reason': f'Demo {absence_type} request for {employees[username].full_name}.',
                    'status': status,
                    'reviewed_by': review_actor if status != RequestStatus.PENDING else None,
                    'reviewed_at': timezone.now() if status != RequestStatus.PENDING else None,
                    'review_comment': review_comment,
                },
            )
            created_count += int(was_created)

        return created_count

    def seed_documents(self, employees, fallback_user):
        created_count = 0
        documents = [
            ('worker_anna', DocumentCategory.CONTRACT, 'Employment Contract', 'Signed employment contract.'),
            ('worker_anna', DocumentCategory.APPLICATION, 'Annual Leave Application', 'Application for annual leave.'),
            ('worker_oleh', DocumentCategory.ORDER, 'Vacation Order', 'Vacation approval order.'),
            ('worker_sofia', DocumentCategory.OTHER, 'Medical Certificate', 'Certificate for sick leave period.'),
            ('worker_dmytro', DocumentCategory.PASSPORT, 'Passport Copy', 'Scanned passport copy for payroll records.'),
            ('worker_nazar', DocumentCategory.CONTRACT, 'NDA Addendum', 'Supplementary confidentiality addendum.'),
            ('worker_maria', DocumentCategory.ORDER, 'Remote Work Order', 'Order enabling hybrid work schedule.'),
            ('worker_yevhen', DocumentCategory.APPLICATION, 'Equipment Request', 'Request for support equipment refresh.'),
            ('worker_viktoria', DocumentCategory.CONTRACT, 'Probation Agreement', 'Initial probation agreement.'),
            ('worker_ihor', DocumentCategory.ORDER, 'Dismissal Order', 'Dismissal paperwork archived for audit.'),
        ]

        for index, (username, category, title, content) in enumerate(documents, start=1):
            employee = employees[username]
            document, was_created = EmployeeDocument.objects.get_or_create(
                employee=employee,
                title=title,
                defaults={
                    'category': category,
                    'uploaded_by': employee.user or fallback_user,
                },
            )
            document.category = category
            document.uploaded_by = employee.user or fallback_user

            desired_name = f'employee_documents/demo_{index:02d}_{username}_{title.lower().replace(" ", "_")}.txt'
            current_name = document.file.name if document.file else ''
            if current_name != desired_name:
                if current_name:
                    document.file.delete(save=False)
                document.file.save(desired_name, ContentFile(content), save=False)

            document.save()
            created_count += int(was_created)

        return created_count

    def seed_notifications(self, users, employees):
        created_count = 0
        notifications = [
            ('demo_admin', 'System Summary', 'Demo data has been refreshed and dashboards are up to date.', 'system', False),
            ('ops_manager', 'Pending Leave Review', 'There are pending leave requests in Operations.', 'leave_request', False),
            ('finance_manager', 'Payroll Reminder', 'Payroll export should be completed before Friday 15:00.', 'payroll', True),
            ('it_manager', 'Incident Review', 'Review yesterday support incidents and close remaining tickets.', 'system', False),
            ('worker_anna', 'Document Uploaded', 'A new contract document was attached to your profile.', 'document', True),
            ('worker_oleh', 'Leave Request Pending', 'Your annual leave request is awaiting review.', 'leave_request', False),
            ('worker_sofia', 'Sick Leave Approved', 'Your sick leave request was approved.', 'leave_request', True),
            ('worker_maria', 'Deployment Note', 'Backend release has been scheduled for tonight.', 'system', False),
            ('worker_viktoria', 'Probation Check-In', 'Your probation review is planned for next week.', 'hr', False),
        ]

        for recipient_username, title, message, category, is_read in notifications:
            _, was_created = Notification.objects.update_or_create(
                recipient=users[recipient_username],
                title=title,
                defaults={
                    'message': message,
                    'category': category,
                    'is_read': is_read,
                    'related_model': 'Employee' if recipient_username in employees else '',
                    'related_object_id': employees[recipient_username].id if recipient_username in employees else None,
                },
            )
            created_count += int(was_created)

        return created_count

    def seed_audit_logs(self, users, employees):
        created_count = 0
        dmytro_request = LeaveRequest.objects.filter(employee=employees['worker_dmytro']).first()
        maria_log = WorkLog.objects.filter(employee=employees['worker_maria']).first()

        log_specs = [
            {
                'actor': users['demo_admin'],
                'action': AuditAction.CREATE,
                'model_name': 'Department',
                'object_id': str(employees['worker_anna'].department_id),
                'object_repr': employees['worker_anna'].department.name,
                'details': {'source': 'demo_seed'},
            },
            {
                'actor': users['ops_manager'],
                'action': AuditAction.UPDATE,
                'model_name': 'Employee',
                'object_id': str(employees['worker_anna'].id),
                'object_repr': employees['worker_anna'].full_name,
                'details': {'field': 'status', 'new': employees['worker_anna'].status},
            },
            {
                'actor': users['finance_manager'],
                'action': AuditAction.UPDATE,
                'model_name': 'LeaveRequest',
                'object_id': str(dmytro_request.pk),
                'object_repr': str(dmytro_request),
                'details': {'decision': RequestStatus.REJECTED},
            },
            {
                'actor': users['it_manager'],
                'action': AuditAction.CREATE,
                'model_name': 'WorkLog',
                'object_id': str(maria_log.pk),
                'object_repr': str(maria_log),
                'details': {'seed': True},
            },
        ]

        for spec in log_specs:
            _, was_created = AuditLog.objects.update_or_create(
                actor=spec['actor'],
                action=spec['action'],
                model_name=spec['model_name'],
                object_id=spec['object_id'],
                defaults={
                    'object_repr': spec['object_repr'],
                    'details': spec['details'],
                    'ip_address': '127.0.0.1',
                },
            )
            created_count += int(was_created)

        create_audit_log(
            actor=users['demo_admin'],
            action=AuditAction.CREATE,
            model_name='DemoSeed',
            object_id='run',
            object_repr='Demo seed execution',
            details={'executed_at': timezone.now().isoformat()},
        )
        created_count += 1

        return created_count
