from datetime import datetime

from django.forms.models import model_to_dict

from .models import AuditLog, EmployeeHistory, Notification


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def serialize_value(value):
    if value is None:
        return None
    if hasattr(value, 'pk'):
        return {'id': value.pk, 'label': str(value)}
    if hasattr(value, 'storage') and hasattr(value, 'name'):
        return value.name
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def snapshot_instance(instance):
    data = model_to_dict(instance)
    return {key: serialize_value(value) for key, value in data.items()}


def diff_snapshots(before, after):
    changes = {}
    keys = set(before.keys()) | set(after.keys())
    for key in keys:
        if before.get(key) != after.get(key):
            changes[key] = {'old': before.get(key), 'new': after.get(key)}
    return changes


def create_employee_history(employee, actor, before, after):
    changes = diff_snapshots(before, after)
    if changes:
        EmployeeHistory.objects.create(employee=employee, changed_by=actor, changes=changes)


def create_audit_log(*, actor, action, model_name, object_id='', object_repr='', details=None, request=None):
    AuditLog.objects.create(
        actor=actor if actor and actor.is_authenticated else None,
        action=action,
        model_name=model_name,
        object_id=str(object_id) if object_id else '',
        object_repr=object_repr,
        details=details or {},
        ip_address=get_client_ip(request) if request else None,
    )


def create_notification(*, recipient, title, message, category='system', related_model='', related_object_id=None):
    if not recipient:
        return None
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        category=category,
        related_model=related_model,
        related_object_id=related_object_id,
    )
