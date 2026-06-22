from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    AuditLog,
    Department,
    Employee,
    EmployeeDocument,
    EmployeeHistory,
    LeaveRequest,
    Notification,
    Position,
    User,
    WorkLog,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('username', 'email', 'role', 'is_blocked', 'is_staff')
    list_filter = ('role', 'is_blocked', 'is_staff')
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('HR access', {'fields': ('role', 'is_blocked')}),
    )


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'manager', 'updated_at')
    search_fields = ('name',)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('title', 'department', 'updated_at')
    search_fields = ('title',)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'department', 'position', 'status', 'hired_at')
    list_filter = ('status', 'department')
    search_fields = ('full_name', 'email', 'phone')


@admin.register(EmployeeHistory)
class EmployeeHistoryAdmin(admin.ModelAdmin):
    list_display = ('employee', 'changed_by', 'created_at')
    list_filter = ('created_at',)


@admin.register(WorkLog)
class WorkLogAdmin(admin.ModelAdmin):
    list_display = ('employee', 'work_date', 'started_at', 'ended_at', 'overtime_minutes')
    list_filter = ('work_date', 'absence_type')


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'absence_type', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'absence_type')


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'employee', 'category', 'created_at')
    list_filter = ('category',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'category', 'is_read', 'created_at')
    list_filter = ('category', 'is_read')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'model_name', 'object_repr', 'actor', 'created_at')
    list_filter = ('action', 'model_name', 'created_at')
    search_fields = ('object_repr', 'actor__username')
