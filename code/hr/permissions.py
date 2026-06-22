from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Department, UserRole


def is_admin(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role == UserRole.ADMIN))


def is_manager(user):
    return bool(user and user.is_authenticated and user.role == UserRole.MANAGER)


def is_employee(user):
    return bool(user and user.is_authenticated and user.role == UserRole.EMPLOYEE)


def get_user_employee(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, 'employee_profile', None)


def get_managed_department_ids(user):
    if not is_manager(user):
        return set()
    return set(Department.objects.filter(manager__user=user).values_list('id', flat=True))


def manages_department(user, department_or_id):
    department_id = getattr(department_or_id, 'pk', department_or_id)
    return bool(department_id and department_id in get_managed_department_ids(user))


def manages_employee(user, employee):
    return bool(employee and employee.department_id and manages_department(user, employee.department_id))


def is_self_employee(user, employee):
    return bool(employee and user and user.is_authenticated and employee.user_id == user.id)


def can_access_employee(user, employee):
    return is_admin(user) or manages_employee(user, employee) or is_self_employee(user, employee)


def filter_employee_queryset_for_user(queryset, user, employee_field=None):
    if is_admin(user):
        return queryset

    if employee_field:
        if is_manager(user):
            return queryset.filter(**{f'{employee_field}__department_id__in': get_managed_department_ids(user)})
        return queryset.filter(**{f'{employee_field}__user': user})

    if is_manager(user):
        return queryset.filter(department_id__in=get_managed_department_ids(user))
    return queryset.filter(user=user)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)


class IsAdminOrManager(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user) or is_manager(request.user)


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return is_admin(request.user)
