import shutil
import tempfile
from datetime import date, time

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

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


class HrApiBaseTestCase(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_dir = tempfile.mkdtemp(prefix='hr-api-tests-')
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.admin = self.create_user('admin', UserRole.ADMIN, 'admin@example.com')
        self.manager = self.create_user('manager', UserRole.MANAGER, 'manager@example.com')
        self.worker = self.create_user('worker', UserRole.EMPLOYEE, 'worker@example.com')
        self.outsider = self.create_user('outsider', UserRole.EMPLOYEE, 'outsider@example.com')

        self.managed_department = Department.objects.create(name='Operations', description='Managed department')
        self.other_department = Department.objects.create(name='Finance', description='Unmanaged department')

        self.manager_position = Position.objects.create(title='Operations Manager', department=self.managed_department)
        self.worker_position = Position.objects.create(title='Operator', department=self.managed_department)
        self.outsider_position = Position.objects.create(title='Accountant', department=self.other_department)

        self.manager_employee = self.create_employee(
            user=self.manager,
            full_name='Manager Person',
            email='manager.employee@example.com',
            department=self.managed_department,
            position=self.manager_position,
        )
        self.managed_department.manager = self.manager_employee
        self.managed_department.save(update_fields=['manager'])

        self.worker_employee = self.create_employee(
            user=self.worker,
            full_name='Worker Person',
            email='worker.employee@example.com',
            department=self.managed_department,
            position=self.worker_position,
        )
        self.outsider_employee = self.create_employee(
            user=self.outsider,
            full_name='Outsider Person',
            email='outsider.employee@example.com',
            department=self.other_department,
            position=self.outsider_position,
        )

        self.worker_log = WorkLog.objects.create(
            employee=self.worker_employee,
            work_date=date(2026, 4, 20),
            started_at=time(9, 0),
            ended_at=time(18, 0),
            lateness_minutes=5,
            overtime_minutes=15,
            absence_type=AbsenceType.NONE,
            note='Worker log',
        )
        self.outsider_log = WorkLog.objects.create(
            employee=self.outsider_employee,
            work_date=date(2026, 4, 21),
            started_at=time(10, 0),
            ended_at=time(19, 0),
            lateness_minutes=0,
            overtime_minutes=20,
            absence_type=AbsenceType.NONE,
            note='Outsider log',
        )

        self.worker_leave_request = LeaveRequest.objects.create(
            employee=self.worker_employee,
            absence_type=AbsenceType.ANNUAL_LEAVE,
            start_date=date(2026, 5, 10),
            end_date=date(2026, 5, 12),
            reason='Worker vacation',
            status=RequestStatus.PENDING,
        )
        self.approved_worker_leave_request = LeaveRequest.objects.create(
            employee=self.worker_employee,
            absence_type=AbsenceType.DAY_OFF,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 1),
            reason='Approved worker day off',
            status=RequestStatus.APPROVED,
        )
        self.outsider_leave_request = LeaveRequest.objects.create(
            employee=self.outsider_employee,
            absence_type=AbsenceType.SICK_LEAVE,
            start_date=date(2026, 5, 15),
            end_date=date(2026, 5, 18),
            reason='Outsider sick leave',
            status=RequestStatus.PENDING,
        )

        self.worker_document = EmployeeDocument.objects.create(
            employee=self.worker_employee,
            category=DocumentCategory.CONTRACT,
            title='Worker Contract',
            file=self.make_file('worker-contract.txt', b'worker-contract'),
            uploaded_by=self.worker,
        )
        self.outsider_document = EmployeeDocument.objects.create(
            employee=self.outsider_employee,
            category=DocumentCategory.PASSPORT,
            title='Outsider Passport',
            file=self.make_file('outsider-passport.txt', b'outsider-passport'),
            uploaded_by=self.outsider,
        )

        self.worker_notification = Notification.objects.create(
            recipient=self.worker,
            title='Worker notice',
            message='Worker-specific notification',
            category='system',
        )
        self.manager_notification = Notification.objects.create(
            recipient=self.manager,
            title='Manager notice',
            message='Manager-specific notification',
            category='system',
        )

        self.audit_log = AuditLog.objects.create(
            actor=self.admin,
            action=AuditAction.CREATE,
            model_name='Seed',
            object_id='1',
            object_repr='Seed object',
            details={'seed': True},
        )

    def create_user(self, username, role, email):
        return User.objects.create_user(
            username=username,
            email=email,
            password='StrongPass123!',
            first_name=username.capitalize(),
            last_name='User',
            role=role,
        )

    def create_employee(self, *, user, full_name, email, department, position):
        return Employee.objects.create(
            user=user,
            full_name=full_name,
            birth_date=date(1995, 1, 1),
            email=email,
            phone='+380000000000',
            address='Kyiv',
            position=position,
            department=department,
            hired_at=date(2024, 1, 10),
            probation_end_date=date(2024, 4, 10),
            contract_end_date=date(2027, 1, 10),
            status=EmployeeStatus.ACTIVE,
            notes='Seed employee',
        )

    def authenticate(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return token

    def clear_auth(self):
        self.client.credentials()

    def make_file(self, name='test.txt', content=b'test-content'):
        return SimpleUploadedFile(name, content, content_type='text/plain')
