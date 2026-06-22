from datetime import datetime

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AuditAction,
    AuditLog,
    Department,
    Employee,
    EmployeeDocument,
    EmployeeHistory,
    LeaveRequest,
    Notification,
    Position,
    RequestStatus,
    User,
    UserRole,
    WorkLog,
)
from .permissions import (
    IsAdmin,
    IsAdminOrManager,
    can_access_employee,
    filter_employee_queryset_for_user,
    get_managed_department_ids,
    get_user_employee,
    is_admin,
    is_employee,
    is_manager,
    manages_department,
    manages_employee,
)
from .serializers import (
    AuditLogSerializer,
    ChangePasswordSerializer,
    DepartmentSerializer,
    DepartmentStructureSerializer,
    EmployeeDocumentSerializer,
    EmployeeHistorySerializer,
    EmployeeSerializer,
    LeaveRequestSerializer,
    LeaveReviewSerializer,
    LoginSerializer,
    NotificationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PositionSerializer,
    RegistrationSerializer,
    UserSerializer,
    WorkLogSerializer,
)
from .services import create_audit_log, create_employee_history, create_notification, snapshot_instance


class AuditedModelViewSet(viewsets.ModelViewSet):
    audit_model_name = None

    def perform_create(self, serializer):
        instance = serializer.save()
        create_audit_log(
            actor=self.request.user,
            action=AuditAction.CREATE,
            model_name=self.audit_model_name or instance.__class__.__name__,
            object_id=instance.pk,
            object_repr=str(instance),
            details=snapshot_instance(instance),
            request=self.request,
        )

    def perform_update(self, serializer):
        before = snapshot_instance(self.get_object())
        instance = serializer.save()
        create_audit_log(
            actor=self.request.user,
            action=AuditAction.UPDATE,
            model_name=self.audit_model_name or instance.__class__.__name__,
            object_id=instance.pk,
            object_repr=str(instance),
            details={'before': before, 'after': snapshot_instance(instance)},
            request=self.request,
        )

    def perform_destroy(self, instance):
        details = snapshot_instance(instance)
        model_name = self.audit_model_name or instance.__class__.__name__
        object_id = instance.pk
        object_repr = str(instance)
        instance.delete()
        create_audit_log(
            actor=self.request.user,
            action=AuditAction.DELETE,
            model_name=model_name,
            object_id=object_id,
            object_repr=object_repr,
            details=details,
            request=self.request,
        )


class RoleScopedAccessMixin:
    manager_employee_editable_fields = {
        'position',
        'status',
        'notes',
        'probation_end_date',
        'contract_end_date',
    }

    def get_managed_department_ids(self):
        return get_managed_department_ids(self.request.user)

    def get_user_employee(self):
        return get_user_employee(self.request.user)

    def filter_for_current_user(self, queryset, *, employee_field=None):
        return filter_employee_queryset_for_user(queryset, self.request.user, employee_field=employee_field)

    def ensure_can_access_employee(self, employee, message='You do not have access to this employee.'):
        if not can_access_employee(self.request.user, employee):
            raise PermissionDenied(message)

    def ensure_manager_controls_employee(self, employee, message='You can only manage employees in your departments.'):
        if is_admin(self.request.user):
            return
        if is_manager(self.request.user) and manages_employee(self.request.user, employee):
            return
        raise PermissionDenied(message)


class RegistrationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        create_audit_log(
            actor=user,
            action=AuditAction.CREATE,
            model_name='User',
            object_id=user.pk,
            object_repr=str(user),
            details={'source': 'registration'},
            request=request,
        )
        return Response({'token': token.key, 'user': UserSerializer(user).data}, status=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        login(request, user)
        create_audit_log(
            actor=user,
            action=AuditAction.LOGIN,
            model_name='User',
            object_id=user.pk,
            object_repr=str(user),
            request=request,
        )
        return Response({'token': token.key, 'user': UserSerializer(user).data})


class LogoutAPIView(APIView):
    def post(self, request):
        token = Token.objects.filter(user=request.user).first()
        if token:
            token.delete()
        create_audit_log(
            actor=request.user,
            action=AuditAction.LOGOUT,
            model_name='User',
            object_id=request.user.pk,
            object_repr=str(request.user),
            request=request,
        )
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeAPIView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        allowed_fields = {'first_name', 'last_name', 'email'}
        data = {key: value for key, value in request.data.items() if key in allowed_fields}
        serializer = UserSerializer(request.user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        create_audit_log(
            actor=request.user,
            action=AuditAction.UPDATE,
            model_name='User',
            object_id=request.user.pk,
            object_repr=str(request.user),
            details={'updated_fields': list(data.keys())},
            request=request,
        )
        return Response(serializer.data)


class ChangePasswordAPIView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
        create_audit_log(
            actor=request.user,
            action=AuditAction.PASSWORD_CHANGE,
            model_name='User',
            object_id=request.user.pk,
            object_repr=str(request.user),
            request=request,
        )
        return Response({'token': token.key})


class PasswordResetRequestAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = User.objects.filter(email=email).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f'{settings.FRONTEND_RESET_URL}?uid={uid}&token={token}'
            send_mail(
                subject='Password reset',
                message=f'Use this link to reset your password: {reset_url}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
            create_audit_log(
                actor=user,
                action=AuditAction.PASSWORD_RESET_REQUEST,
                model_name='User',
                object_id=user.pk,
                object_repr=str(user),
                request=request,
            )
        return Response({'detail': 'If the email exists, reset instructions were sent.'})


class PasswordResetConfirmAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        Token.objects.filter(user=user).delete()
        create_audit_log(
            actor=user,
            action=AuditAction.PASSWORD_RESET_CONFIRM,
            model_name='User',
            object_id=user.pk,
            object_repr=str(user),
            request=request,
        )
        return Response({'detail': 'Password has been reset.'})


class UserViewSet(AuditedModelViewSet):
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['username', 'email', 'role']
    filter_backends = [SearchFilter, OrderingFilter]
    audit_model_name = 'User'

    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        user = self.get_object()
        user.is_blocked = True
        user.save()
        create_audit_log(
            actor=request.user,
            action=AuditAction.UPDATE,
            model_name='User',
            object_id=user.pk,
            object_repr=str(user),
            details={'is_blocked': True},
            request=request,
        )
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        user = self.get_object()
        user.is_blocked = False
        user.save()
        create_audit_log(
            actor=request.user,
            action=AuditAction.UPDATE,
            model_name='User',
            object_id=user.pk,
            object_repr=str(user),
            details={'is_blocked': False},
            request=request,
        )
        return Response(UserSerializer(user).data)


class DepartmentViewSet(AuditedModelViewSet):
    queryset = Department.objects.select_related('manager').all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    filter_backends = [SearchFilter, OrderingFilter]
    audit_model_name = 'Department'

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [IsAdmin()]

    @action(detail=False, methods=['get'])
    def structure(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = DepartmentStructureSerializer(queryset, many=True)
        return Response(serializer.data)


class PositionViewSet(AuditedModelViewSet):
    queryset = Position.objects.select_related('department').all()
    serializer_class = PositionSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['title', 'description', 'department__name']
    ordering_fields = ['title', 'created_at']
    filter_backends = [SearchFilter, OrderingFilter]
    audit_model_name = 'Position'

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [IsAdmin()]


class EmployeeViewSet(RoleScopedAccessMixin, AuditedModelViewSet):
    queryset = Employee.objects.select_related('user', 'department', 'position').all()
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['full_name', 'email', 'phone', 'position__title', 'department__name', 'status']
    ordering_fields = ['full_name', 'hired_at', 'status', 'created_at']
    filter_backends = [SearchFilter, OrderingFilter]
    audit_model_name = 'Employee'

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get('department'):
            queryset = queryset.filter(department_id=params['department'])
        if params.get('position'):
            queryset = queryset.filter(position_id=params['position'])
        if params.get('status'):
            queryset = queryset.filter(status=params['status'])
        return self.filter_for_current_user(queryset)

    def get_permissions(self):
        if self.action in {'create', 'destroy'}:
            return [IsAdmin()]
        if self.action in {'update', 'partial_update'}:
            return [IsAdminOrManager()]
        return [permissions.IsAuthenticated()]

    def get_object(self):
        employee = super().get_object()
        self.ensure_can_access_employee(employee)
        return employee

    def perform_create(self, serializer):
        instance = serializer.save()
        create_audit_log(
            actor=self.request.user,
            action=AuditAction.CREATE,
            model_name='Employee',
            object_id=instance.pk,
            object_repr=str(instance),
            details=snapshot_instance(instance),
            request=self.request,
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        if is_manager(self.request.user):
            forbidden_fields = set(serializer.validated_data) - self.manager_employee_editable_fields
            if forbidden_fields:
                raise PermissionDenied(
                    f"Managers can update only: {', '.join(sorted(self.manager_employee_editable_fields))}."
                )
            position = serializer.validated_data.get('position')
            if position and position.department_id and not manages_department(self.request.user, position.department_id):
                raise PermissionDenied('You can only assign positions from your departments.')
        before = snapshot_instance(instance)
        updated = serializer.save()
        after = snapshot_instance(updated)
        create_employee_history(updated, self.request.user, before, after)
        create_audit_log(
            actor=self.request.user,
            action=AuditAction.UPDATE,
            model_name='Employee',
            object_id=updated.pk,
            object_repr=str(updated),
            details={'before': before, 'after': after},
            request=self.request,
        )

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        employee = self.get_object()
        serializer = EmployeeHistorySerializer(employee.history_entries.all(), many=True)
        return Response(serializer.data)


class EmployeeHistoryViewSet(RoleScopedAccessMixin, viewsets.ReadOnlyModelViewSet):
    queryset = EmployeeHistory.objects.select_related('employee', 'changed_by').all()
    serializer_class = EmployeeHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.filter_for_current_user(super().get_queryset(), employee_field='employee')


class WorkLogViewSet(RoleScopedAccessMixin, AuditedModelViewSet):
    queryset = WorkLog.objects.select_related('employee', 'employee__user').all()
    serializer_class = WorkLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['employee__full_name', 'note', 'absence_type']
    ordering_fields = ['work_date', 'created_at', 'overtime_minutes', 'lateness_minutes']
    filter_backends = [SearchFilter, OrderingFilter]
    audit_model_name = 'WorkLog'

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get('employee'):
            queryset = queryset.filter(employee_id=params['employee'])
        if params.get('start_date'):
            queryset = queryset.filter(work_date__gte=params['start_date'])
        if params.get('end_date'):
            queryset = queryset.filter(work_date__lte=params['end_date'])
        return self.filter_for_current_user(queryset, employee_field='employee')

    def perform_create(self, serializer):
        if is_employee(self.request.user):
            employee = self.get_user_employee()
            if not employee:
                raise ValidationError('No employee profile is linked to this user.')
            instance = serializer.save(employee=employee)
        else:
            employee = serializer.validated_data.get('employee')
            if not employee:
                raise ValidationError({'employee': 'This field is required.'})
            if is_manager(self.request.user):
                self.ensure_manager_controls_employee(employee)
            instance = serializer.save()
        create_audit_log(
            actor=self.request.user,
            action=AuditAction.CREATE,
            model_name='WorkLog',
            object_id=instance.pk,
            object_repr=str(instance),
            details=snapshot_instance(instance),
            request=self.request,
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        employee = serializer.validated_data.get('employee', instance.employee)
        if is_employee(self.request.user) and employee.user_id != self.request.user.id:
            raise PermissionDenied('You can only edit your own work logs.')
        if is_manager(self.request.user):
            self.ensure_manager_controls_employee(employee)
        super().perform_update(serializer)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        queryset = self.get_queryset()
        totals = {}
        for log in queryset:
            key = str(log.employee)
            start_dt = datetime.combine(log.work_date, log.started_at)
            end_dt = datetime.combine(log.work_date, log.ended_at)
            worked_minutes = int((end_dt - start_dt).total_seconds() // 60)
            employee_stats = totals.setdefault(
                key,
                {'employee_id': log.employee_id, 'worked_minutes': 0, 'lateness_minutes': 0, 'overtime_minutes': 0},
            )
            employee_stats['worked_minutes'] += worked_minutes
            employee_stats['lateness_minutes'] += log.lateness_minutes
            employee_stats['overtime_minutes'] += log.overtime_minutes
        return Response(totals)


class LeaveRequestViewSet(RoleScopedAccessMixin, AuditedModelViewSet):
    queryset = LeaveRequest.objects.select_related('employee', 'employee__user', 'reviewed_by').all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['employee__full_name', 'absence_type', 'status', 'reason']
    ordering_fields = ['created_at', 'start_date', 'end_date', 'status']
    filter_backends = [SearchFilter, OrderingFilter]
    audit_model_name = 'LeaveRequest'

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get('employee'):
            queryset = queryset.filter(employee_id=params['employee'])
        if params.get('status'):
            queryset = queryset.filter(status=params['status'])
        if params.get('absence_type'):
            queryset = queryset.filter(absence_type=params['absence_type'])
        if params.get('start_date'):
            queryset = queryset.filter(end_date__gte=params['start_date'])
        if params.get('end_date'):
            queryset = queryset.filter(start_date__lte=params['end_date'])
        return self.filter_for_current_user(queryset, employee_field='employee')

    def perform_create(self, serializer):
        if is_employee(self.request.user):
            employee = self.get_user_employee()
            if not employee:
                raise ValidationError('No employee profile is linked to this user.')
            instance = serializer.save(employee=employee)
        else:
            employee = serializer.validated_data.get('employee')
            if not employee:
                raise ValidationError({'employee': 'This field is required.'})
            if is_manager(self.request.user):
                self.ensure_manager_controls_employee(employee)
            instance = serializer.save()
        create_audit_log(
            actor=self.request.user,
            action=AuditAction.CREATE,
            model_name='LeaveRequest',
            object_id=instance.pk,
            object_repr=str(instance),
            details=snapshot_instance(instance),
            request=self.request,
        )
        for manager in User.objects.filter(Q(role=UserRole.MANAGER) | Q(role=UserRole.ADMIN)):
            create_notification(
                recipient=manager,
                title='New leave request',
                message=f'New leave request from {instance.employee.full_name}.',
                category='leave_request',
                related_model='LeaveRequest',
                related_object_id=instance.pk,
            )

    def perform_update(self, serializer):
        instance = self.get_object()
        if is_employee(self.request.user):
            if instance.employee.user_id != self.request.user.id or instance.status != RequestStatus.PENDING:
                raise PermissionDenied('You can only edit your own pending requests.')
        elif is_manager(self.request.user):
            self.ensure_manager_controls_employee(instance.employee)
            if instance.status != RequestStatus.PENDING:
                raise PermissionDenied('Managers can only edit pending leave requests.')
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        if is_employee(self.request.user):
            if instance.employee.user_id != self.request.user.id or instance.status != RequestStatus.PENDING:
                raise PermissionDenied('You can only delete your own pending requests.')
        elif is_manager(self.request.user):
            self.ensure_manager_controls_employee(instance.employee)
            if instance.status != RequestStatus.PENDING:
                raise PermissionDenied('Managers can only delete pending leave requests.')
        super().perform_destroy(instance)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def review(self, request, pk=None):
        leave_request = self.get_object()
        if is_manager(request.user):
            self.ensure_manager_controls_employee(leave_request.employee)
            if leave_request.employee.user_id == request.user.id:
                raise PermissionDenied('Managers cannot review their own leave requests.')
        if leave_request.status != RequestStatus.PENDING:
            raise ValidationError('Only pending leave requests can be reviewed.')
        serializer = LeaveReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leave_request.status = serializer.validated_data['status']
        leave_request.review_comment = serializer.validated_data.get('review_comment', '')
        leave_request.reviewed_by = request.user
        leave_request.reviewed_at = timezone.now()
        leave_request.save()
        create_audit_log(
            actor=request.user,
            action=AuditAction.UPDATE,
            model_name='LeaveRequest',
            object_id=leave_request.pk,
            object_repr=str(leave_request),
            details={'review_status': leave_request.status, 'review_comment': leave_request.review_comment},
            request=request,
        )
        if leave_request.employee.user:
            create_notification(
                recipient=leave_request.employee.user,
                title='Leave request reviewed',
                message=f'Your leave request was {leave_request.status}.',
                category='leave_request',
                related_model='LeaveRequest',
                related_object_id=leave_request.pk,
            )
        return Response(LeaveRequestSerializer(leave_request).data)

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        queryset = self.get_queryset().filter(status=RequestStatus.APPROVED)
        serializer = LeaveRequestSerializer(queryset, many=True)
        return Response(serializer.data)


class EmployeeDocumentViewSet(RoleScopedAccessMixin, AuditedModelViewSet):
    queryset = EmployeeDocument.objects.select_related('employee', 'employee__user', 'uploaded_by').all()
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['title', 'category', 'employee__full_name']
    ordering_fields = ['created_at', 'title']
    filter_backends = [SearchFilter, OrderingFilter]
    audit_model_name = 'EmployeeDocument'

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('employee'):
            queryset = queryset.filter(employee_id=self.request.query_params['employee'])
        if self.request.query_params.get('category'):
            queryset = queryset.filter(category=self.request.query_params['category'])
        return self.filter_for_current_user(queryset, employee_field='employee')

    def perform_create(self, serializer):
        if is_employee(self.request.user):
            employee = self.get_user_employee()
            if not employee:
                raise ValidationError('No employee profile is linked to this user.')
            instance = serializer.save(uploaded_by=self.request.user, employee=employee)
        else:
            employee = serializer.validated_data.get('employee')
            if not employee:
                raise ValidationError({'employee': 'This field is required.'})
            if is_manager(self.request.user):
                self.ensure_manager_controls_employee(employee)
            instance = serializer.save(uploaded_by=self.request.user)
        create_audit_log(
            actor=self.request.user,
            action=AuditAction.CREATE,
            model_name='EmployeeDocument',
            object_id=instance.pk,
            object_repr=str(instance),
            details=snapshot_instance(instance),
            request=self.request,
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        employee = serializer.validated_data.get('employee', instance.employee)
        if is_employee(self.request.user) and employee.user_id != self.request.user.id:
            raise PermissionDenied('You can only edit your own documents.')
        if is_manager(self.request.user):
            self.ensure_manager_controls_employee(employee)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        if is_employee(self.request.user) and instance.employee.user_id != self.request.user.id:
            raise PermissionDenied('You can only delete your own documents.')
        if is_manager(self.request.user):
            self.ensure_manager_controls_employee(instance.employee)
        file_field = instance.file
        super().perform_destroy(instance)
        if file_field:
            file_field.delete(save=False)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering_fields = ['created_at']

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('actor').all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdmin]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['model_name', 'object_repr', 'actor__username', 'action']
    ordering_fields = ['created_at', 'action', 'model_name']
