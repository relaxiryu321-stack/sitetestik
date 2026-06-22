from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .models import (
    AbsenceType,
    AuditLog,
    Department,
    Employee,
    EmployeeDocument,
    EmployeeHistory,
    LeaveRequest,
    Notification,
    Position,
    User,
    UserRole,
    WorkLog,
)


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'role',
            'is_blocked',
            'is_active',
            'password',
        ]
        read_only_fields = ['is_active']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'password', 'password_confirm']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        password_validation.validate_password(attrs['password'])
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        return User.objects.create_user(
            role=UserRole.EMPLOYEE,
            password=validated_data.pop('password'),
            **validated_data,
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get('request'),
            username=attrs.get('username'),
            password=attrs.get('password'),
        )
        if not user:
            raise serializers.ValidationError('Invalid credentials.')
        if user.is_blocked:
            raise serializers.ValidationError('User is blocked.')
        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context['request'].user
        if not user.check_password(attrs['old_password']):
            raise serializers.ValidationError({'old_password': 'Incorrect password.'})
        password_validation.validate_password(attrs['new_password'], user=user)
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs['uid']))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError) as exc:
            raise serializers.ValidationError({'uid': 'Invalid reset identifier.'}) from exc
        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({'token': 'Invalid or expired token.'})
        password_validation.validate_password(attrs['new_password'], user=user)
        attrs['user'] = user
        return attrs


class DepartmentSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source='manager.full_name', read_only=True)

    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'manager', 'manager_name', 'created_at', 'updated_at']


class PositionSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Position
        fields = ['id', 'title', 'department', 'department_name', 'description', 'created_at', 'updated_at']


class EmployeeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    position_title = serializers.CharField(source='position.title', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id',
            'user',
            'user_username',
            'full_name',
            'birth_date',
            'email',
            'phone',
            'address',
            'position',
            'position_title',
            'department',
            'department_name',
            'hired_at',
            'probation_end_date',
            'contract_end_date',
            'status',
            'notes',
            'created_at',
            'updated_at',
        ]


class EmployeeHistorySerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source='changed_by.username', read_only=True)

    class Meta:
        model = EmployeeHistory
        fields = ['id', 'employee', 'changed_by', 'changed_by_username', 'changes', 'created_at']


class WorkLogSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = WorkLog
        fields = [
            'id',
            'employee',
            'employee_name',
            'work_date',
            'started_at',
            'ended_at',
            'lateness_minutes',
            'overtime_minutes',
            'absence_type',
            'note',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'employee': {'required': False},
        }

    def validate(self, attrs):
        started_at = attrs.get('started_at', getattr(self.instance, 'started_at', None))
        ended_at = attrs.get('ended_at', getattr(self.instance, 'ended_at', None))
        if started_at and ended_at and ended_at <= started_at:
            raise serializers.ValidationError({'ended_at': 'End time must be after start time.'})
        return attrs


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            'id',
            'employee',
            'employee_name',
            'absence_type',
            'start_date',
            'end_date',
            'reason',
            'status',
            'reviewed_by',
            'reviewed_by_username',
            'reviewed_at',
            'review_comment',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['status', 'reviewed_by', 'reviewed_at', 'review_comment']
        extra_kwargs = {
            'employee': {'required': False},
        }

    def validate(self, attrs):
        absence_type = attrs.get('absence_type', getattr(self.instance, 'absence_type', None))
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if absence_type == AbsenceType.NONE:
            raise serializers.ValidationError({'absence_type': 'Choose a real absence type.'})
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({'end_date': 'End date must be on or after start date.'})
        return attrs


class LeaveReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['approved', 'rejected'])
    review_comment = serializers.CharField(required=False, allow_blank=True)


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)

    class Meta:
        model = EmployeeDocument
        fields = [
            'id',
            'employee',
            'employee_name',
            'category',
            'title',
            'file',
            'uploaded_by',
            'uploaded_by_username',
            'created_at',
        ]
        read_only_fields = ['uploaded_by']
        extra_kwargs = {
            'employee': {'required': False},
        }


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id',
            'recipient',
            'title',
            'message',
            'category',
            'is_read',
            'related_model',
            'related_object_id',
            'created_at',
        ]
        read_only_fields = ['recipient', 'created_at']


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'actor',
            'actor_username',
            'action',
            'model_name',
            'object_id',
            'object_repr',
            'ip_address',
            'details',
            'created_at',
        ]


class DepartmentStructurePositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ['id', 'title']


class DepartmentStructureEmployeeSerializer(serializers.ModelSerializer):
    position_title = serializers.CharField(source='position.title', read_only=True)

    class Meta:
        model = Employee
        fields = ['id', 'full_name', 'status', 'position_title']


class DepartmentStructureSerializer(serializers.ModelSerializer):
    positions = DepartmentStructurePositionSerializer(many=True, read_only=True)
    employees = DepartmentStructureEmployeeSerializer(many=True, read_only=True)
    manager_name = serializers.CharField(source='manager.full_name', read_only=True)

    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'manager_name', 'positions', 'employees']
