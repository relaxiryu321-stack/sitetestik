from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = 'admin', 'Admin'
    MANAGER = 'manager', 'Manager'
    EMPLOYEE = 'employee', 'Employee'


class User(AbstractUser):
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.EMPLOYEE)
    is_blocked = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        self.is_active = not self.is_blocked
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username


class EmployeeStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    VACATION = 'vacation', 'On vacation'
    DISMISSED = 'dismissed', 'Dismissed'
    SICK_LEAVE = 'sick_leave', 'Sick leave'


class AbsenceType(models.TextChoices):
    NONE = 'none', 'None'
    ANNUAL_LEAVE = 'annual_leave', 'Annual leave'
    SICK_LEAVE = 'sick_leave', 'Sick leave'
    DAY_OFF = 'day_off', 'Day off'
    UNPAID = 'unpaid', 'Unpaid leave'
    ABSENT = 'absent', 'Absent'


class RequestStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class DocumentCategory(models.TextChoices):
    PASSPORT = 'passport', 'Passport data'
    ORDER = 'order', 'Order'
    CONTRACT = 'contract', 'Labor contract'
    APPLICATION = 'application', 'Application'
    OTHER = 'other', 'Other'


class Department(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    manager = models.ForeignKey(
        'Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_departments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Position(models.Model):
    title = models.CharField(max_length=255)
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='positions',
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']
        constraints = [
            models.UniqueConstraint(fields=['title', 'department'], name='unique_position_per_department')
        ]

    def __str__(self):
        return self.title


class Employee(models.Model):
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='employee_profile')
    full_name = models.CharField(max_length=255)
    birth_date = models.DateField()
    email = models.EmailField()
    phone = models.CharField(max_length=32)
    address = models.TextField()
    position = models.ForeignKey(Position, null=True, blank=True, on_delete=models.SET_NULL, related_name='employees')
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employees',
    )
    hired_at = models.DateField()
    probation_end_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=EmployeeStatus.choices, default=EmployeeStatus.ACTIVE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return self.full_name


class EmployeeHistory(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='history_entries')
    changed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='employee_changes')
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'History for {self.employee.full_name}'


class WorkLog(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='work_logs')
    work_date = models.DateField()
    started_at = models.TimeField()
    ended_at = models.TimeField()
    lateness_minutes = models.PositiveIntegerField(default=0)
    overtime_minutes = models.PositiveIntegerField(default=0)
    absence_type = models.CharField(max_length=20, choices=AbsenceType.choices, default=AbsenceType.NONE)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-work_date', 'employee__full_name']
        constraints = [
            models.UniqueConstraint(fields=['employee', 'work_date'], name='unique_employee_workday')
        ]

    def __str__(self):
        return f'{self.employee.full_name} - {self.work_date}'


class LeaveRequest(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    absence_type = models.CharField(max_length=20, choices=AbsenceType.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=RequestStatus.choices, default=RequestStatus.PENDING)
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_leave_requests',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.employee.full_name} - {self.absence_type}'


class EmployeeDocument(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents')
    category = models.CharField(max_length=20, choices=DocumentCategory.choices, default=DocumentCategory.OTHER)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='employee_documents/%Y/%m/')
    uploaded_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='uploaded_documents',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(max_length=50, default='system')
    is_read = models.BooleanField(default=False)
    related_model = models.CharField(max_length=100, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class AuditAction(models.TextChoices):
    CREATE = 'create', 'Create'
    UPDATE = 'update', 'Update'
    DELETE = 'delete', 'Delete'
    LOGIN = 'login', 'Login'
    LOGOUT = 'logout', 'Logout'
    PASSWORD_CHANGE = 'password_change', 'Password change'
    PASSWORD_RESET_REQUEST = 'password_reset_request', 'Password reset request'
    PASSWORD_RESET_CONFIRM = 'password_reset_confirm', 'Password reset confirm'


class AuditLog(models.Model):
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_logs')
    action = models.CharField(max_length=40, choices=AuditAction.choices)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} {self.model_name}'
