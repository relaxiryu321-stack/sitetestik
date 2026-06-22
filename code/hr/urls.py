from rest_framework.routers import DefaultRouter
from django.urls import include, path

from .views import (
    AuditLogViewSet,
    ChangePasswordAPIView,
    DepartmentViewSet,
    EmployeeDocumentViewSet,
    EmployeeHistoryViewSet,
    EmployeeViewSet,
    LeaveRequestViewSet,
    LoginAPIView,
    LogoutAPIView,
    MeAPIView,
    NotificationViewSet,
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
    PositionViewSet,
    RegistrationAPIView,
    UserViewSet,
    WorkLogViewSet,
)

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')
router.register('departments', DepartmentViewSet, basename='department')
router.register('positions', PositionViewSet, basename='position')
router.register('employees', EmployeeViewSet, basename='employee')
router.register('employee-history', EmployeeHistoryViewSet, basename='employee-history')
router.register('work-logs', WorkLogViewSet, basename='work-log')
router.register('leave-requests', LeaveRequestViewSet, basename='leave-request')
router.register('documents', EmployeeDocumentViewSet, basename='document')
router.register('notifications', NotificationViewSet, basename='notification')
router.register('audit-logs', AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('auth/register/', RegistrationAPIView.as_view(), name='auth-register'),
    path('auth/login/', LoginAPIView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutAPIView.as_view(), name='auth-logout'),
    path('auth/me/', MeAPIView.as_view(), name='auth-me'),
    path('auth/change-password/', ChangePasswordAPIView.as_view(), name='auth-change-password'),
    path('auth/password-reset/', PasswordResetRequestAPIView.as_view(), name='auth-password-reset'),
    path('auth/password-reset/confirm/', PasswordResetConfirmAPIView.as_view(), name='auth-password-reset-confirm'),
    path('', include(router.urls)),
]
