from rest_framework import status

from hr.models import (
    AbsenceType,
    EmployeeHistory,
    RequestStatus,
    UserRole,
)

from .base import HrApiBaseTestCase


class UserEndpointTests(HrApiBaseTestCase):
    def test_users_endpoints_are_admin_only(self):
        self.authenticate(self.admin)

        list_response = self.client.get('/api/users/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        create_response = self.client.post(
            '/api/users/',
            {
                'username': 'new-manager',
                'email': 'new-manager@example.com',
                'first_name': 'New',
                'last_name': 'Manager',
                'role': UserRole.MANAGER,
                'password': 'AnotherStrongPass123!',
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        new_user_id = create_response.data['id']

        update_response = self.client.patch(
            f'/api/users/{new_user_id}/',
            {'last_name': 'Updated'},
            format='json',
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        block_response = self.client.post(f'/api/users/{new_user_id}/block/')
        self.assertEqual(block_response.status_code, status.HTTP_200_OK)
        self.assertTrue(block_response.data['is_blocked'])

        unblock_response = self.client.post(f'/api/users/{new_user_id}/unblock/')
        self.assertEqual(unblock_response.status_code, status.HTTP_200_OK)
        self.assertFalse(unblock_response.data['is_blocked'])

        delete_response = self.client.delete(f'/api/users/{new_user_id}/')
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        for user in (self.manager, self.worker):
            with self.subTest(role=user.role):
                self.authenticate(user)
                self.assertEqual(self.client.get('/api/users/').status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(
                    self.client.post(
                        '/api/users/',
                        {
                            'username': f'{user.username}-created',
                            'email': f'{user.username}-created@example.com',
                            'role': UserRole.EMPLOYEE,
                        },
                        format='json',
                    ).status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertEqual(
                    self.client.post(f'/api/users/{self.admin.id}/block/').status_code,
                    status.HTTP_403_FORBIDDEN,
                )


class StructureEndpointTests(HrApiBaseTestCase):
    def test_departments_are_read_only_for_manager_and_worker(self):
        self.authenticate(self.admin)
        self.assertEqual(self.client.get('/api/departments/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/departments/{self.managed_department.id}/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/api/departments/structure/').status_code, status.HTTP_200_OK)

        create_response = self.client.post(
            '/api/departments/',
            {'name': 'Admin Department', 'description': 'Created by admin', 'manager': self.manager_employee.id},
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        department_id = create_response.data['id']

        update_response = self.client.patch(
            f'/api/departments/{department_id}/',
            {'description': 'Updated by admin'},
            format='json',
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.delete(f'/api/departments/{department_id}/').status_code,
            status.HTTP_204_NO_CONTENT,
        )

        for user in (self.manager, self.worker):
            with self.subTest(role=user.role):
                self.authenticate(user)
                self.assertEqual(self.client.get('/api/departments/').status_code, status.HTTP_200_OK)
                self.assertEqual(self.client.get('/api/departments/structure/').status_code, status.HTTP_200_OK)
                self.assertEqual(
                    self.client.post('/api/departments/', {'name': f'{user.username}-department'}, format='json').status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertEqual(
                    self.client.patch(
                        f'/api/departments/{self.managed_department.id}/',
                        {'description': 'forbidden'},
                        format='json',
                    ).status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertEqual(
                    self.client.delete(f'/api/departments/{self.managed_department.id}/').status_code,
                    status.HTTP_403_FORBIDDEN,
                )

    def test_positions_are_read_only_for_manager_and_worker(self):
        self.authenticate(self.admin)
        self.assertEqual(self.client.get('/api/positions/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/positions/{self.worker_position.id}/').status_code, status.HTTP_200_OK)

        create_response = self.client.post(
            '/api/positions/',
            {
                'title': 'Admin Position',
                'department': self.managed_department.id,
                'description': 'Created by admin',
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        position_id = create_response.data['id']

        update_response = self.client.patch(
            f'/api/positions/{position_id}/',
            {'description': 'Updated by admin'},
            format='json',
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.delete(f'/api/positions/{position_id}/').status_code, status.HTTP_204_NO_CONTENT)

        for user in (self.manager, self.worker):
            with self.subTest(role=user.role):
                self.authenticate(user)
                self.assertEqual(self.client.get('/api/positions/').status_code, status.HTTP_200_OK)
                self.assertEqual(
                    self.client.post(
                        '/api/positions/',
                        {'title': f'{user.username}-position', 'department': self.managed_department.id},
                        format='json',
                    ).status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertEqual(
                    self.client.patch(
                        f'/api/positions/{self.worker_position.id}/',
                        {'description': 'forbidden'},
                        format='json',
                    ).status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertEqual(
                    self.client.delete(f'/api/positions/{self.worker_position.id}/').status_code,
                    status.HTTP_403_FORBIDDEN,
                )


class EmployeeEndpointTests(HrApiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.worker_history = EmployeeHistory.objects.create(
            employee=self.worker_employee,
            changed_by=self.admin,
            changes={'status': {'old': 'active', 'new': 'vacation'}},
        )
        self.outsider_history = EmployeeHistory.objects.create(
            employee=self.outsider_employee,
            changed_by=self.admin,
            changes={'status': {'old': 'active', 'new': 'dismissed'}},
        )

    def test_employee_endpoints_follow_role_scope(self):
        self.authenticate(self.admin)
        admin_list = self.client.get('/api/employees/')
        self.assertEqual(admin_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(admin_list.data), 3)

        admin_create = self.client.post(
            '/api/employees/',
            {
                'full_name': 'Admin Created Employee',
                'birth_date': '1997-07-07',
                'email': 'created@example.com',
                'phone': '+380111111111',
                'address': 'Lviv',
                'position': self.worker_position.id,
                'department': self.managed_department.id,
                'hired_at': '2026-01-01',
                'status': 'active',
            },
            format='json',
        )
        self.assertEqual(admin_create.status_code, status.HTTP_201_CREATED)
        created_employee_id = admin_create.data['id']
        self.assertEqual(
            self.client.patch(
                f'/api/employees/{created_employee_id}/',
                {'notes': 'Updated by admin'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(self.client.delete(f'/api/employees/{created_employee_id}/').status_code, status.HTTP_204_NO_CONTENT)

        self.authenticate(self.manager)
        manager_list = self.client.get('/api/employees/')
        self.assertEqual(manager_list.status_code, status.HTTP_200_OK)
        manager_ids = {item['id'] for item in manager_list.data}
        self.assertEqual(manager_ids, {self.manager_employee.id, self.worker_employee.id})
        self.assertEqual(self.client.get(f'/api/employees/{self.worker_employee.id}/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/employees/{self.outsider_employee.id}/').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.patch(
                f'/api/employees/{self.worker_employee.id}/',
                {'notes': 'Manager updated notes', 'status': 'vacation'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/employees/{self.worker_employee.id}/',
                {'email': 'forbidden@example.com'},
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                '/api/employees/',
                {
                    'full_name': 'Forbidden Employee',
                    'birth_date': '1998-08-08',
                    'email': 'forbidden@example.com',
                    'phone': '+380222222222',
                    'address': 'Kyiv',
                    'position': self.worker_position.id,
                    'department': self.managed_department.id,
                    'hired_at': '2026-02-02',
                    'status': 'active',
                },
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(self.client.delete(f'/api/employees/{self.worker_employee.id}/').status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(self.worker)
        worker_list = self.client.get('/api/employees/')
        self.assertEqual(worker_list.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in worker_list.data], [self.worker_employee.id])
        self.assertEqual(self.client.get(f'/api/employees/{self.worker_employee.id}/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/employees/{self.outsider_employee.id}/').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.patch(
                f'/api/employees/{self.worker_employee.id}/',
                {'notes': 'Worker edit'},
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(self.client.post('/api/employees/', {}, format='json').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(f'/api/employees/{self.worker_employee.id}/').status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_history_endpoints_follow_scope(self):
        self.authenticate(self.admin)
        admin_history_list = self.client.get('/api/employee-history/')
        self.assertEqual(admin_history_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(admin_history_list.data), 2)
        self.assertEqual(self.client.get(f'/api/employees/{self.worker_employee.id}/history/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/employee-history/{self.outsider_history.id}/').status_code, status.HTTP_200_OK)

        self.authenticate(self.manager)
        manager_history_list = self.client.get('/api/employee-history/')
        self.assertEqual(manager_history_list.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in manager_history_list.data], [self.worker_history.id])
        self.assertEqual(self.client.get(f'/api/employees/{self.worker_employee.id}/history/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/employees/{self.outsider_employee.id}/history/').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(f'/api/employee-history/{self.worker_history.id}/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/employee-history/{self.outsider_history.id}/').status_code, status.HTTP_404_NOT_FOUND)

        self.authenticate(self.worker)
        worker_history_list = self.client.get('/api/employee-history/')
        self.assertEqual(worker_history_list.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in worker_history_list.data], [self.worker_history.id])
        self.assertEqual(self.client.get(f'/api/employees/{self.worker_employee.id}/history/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/employees/{self.outsider_employee.id}/history/').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(f'/api/employee-history/{self.worker_history.id}/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/employee-history/{self.outsider_history.id}/').status_code, status.HTTP_404_NOT_FOUND)


class WorkLogEndpointTests(HrApiBaseTestCase):
    def test_work_log_endpoints_follow_role_scope(self):
        self.authenticate(self.admin)
        self.assertEqual(self.client.get('/api/work-logs/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/work-logs/{self.outsider_log.id}/').status_code, status.HTTP_200_OK)
        admin_stats = self.client.get('/api/work-logs/stats/')
        self.assertEqual(admin_stats.status_code, status.HTTP_200_OK)
        self.assertEqual(len(admin_stats.data), 2)

        admin_create = self.client.post(
            '/api/work-logs/',
            {
                'employee': self.outsider_employee.id,
                'work_date': '2026-04-22',
                'started_at': '09:00:00',
                'ended_at': '17:30:00',
                'lateness_minutes': 0,
                'overtime_minutes': 0,
                'absence_type': AbsenceType.NONE,
                'note': 'Admin created log',
            },
            format='json',
        )
        self.assertEqual(admin_create.status_code, status.HTTP_201_CREATED)
        admin_log_id = admin_create.data['id']
        self.assertEqual(
            self.client.patch(
                f'/api/work-logs/{admin_log_id}/',
                {'note': 'Updated by admin'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(self.client.delete(f'/api/work-logs/{admin_log_id}/').status_code, status.HTTP_204_NO_CONTENT)

        self.authenticate(self.manager)
        manager_list = self.client.get('/api/work-logs/')
        self.assertEqual(manager_list.status_code, status.HTTP_200_OK)
        manager_ids = {item['id'] for item in manager_list.data}
        self.assertIn(self.worker_log.id, manager_ids)
        self.assertNotIn(self.outsider_log.id, manager_ids)
        self.assertEqual(self.client.get(f'/api/work-logs/{self.worker_log.id}/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/work-logs/{self.outsider_log.id}/').status_code, status.HTTP_404_NOT_FOUND)

        manager_create = self.client.post(
            '/api/work-logs/',
            {
                'employee': self.worker_employee.id,
                'work_date': '2026-04-23',
                'started_at': '08:30:00',
                'ended_at': '17:00:00',
                'lateness_minutes': 0,
                'overtime_minutes': 0,
                'absence_type': AbsenceType.NONE,
                'note': 'Manager created log',
            },
            format='json',
        )
        self.assertEqual(manager_create.status_code, status.HTTP_201_CREATED)
        manager_log_id = manager_create.data['id']
        self.assertEqual(
            self.client.post(
                '/api/work-logs/',
                {
                    'employee': self.outsider_employee.id,
                    'work_date': '2026-04-24',
                    'started_at': '09:00:00',
                    'ended_at': '17:00:00',
                    'lateness_minutes': 0,
                    'overtime_minutes': 0,
                    'absence_type': AbsenceType.NONE,
                    'note': 'Forbidden manager log',
                },
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/work-logs/{manager_log_id}/',
                {'ended_at': '17:15:00'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(self.client.patch(f'/api/work-logs/{self.outsider_log.id}/', {'note': 'forbidden'}, format='json').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(f'/api/work-logs/{manager_log_id}/').status_code, status.HTTP_204_NO_CONTENT)

        self.authenticate(self.worker)
        worker_list = self.client.get('/api/work-logs/')
        self.assertEqual(worker_list.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in worker_list.data], [self.worker_log.id])
        worker_stats = self.client.get('/api/work-logs/stats/')
        self.assertEqual(worker_stats.status_code, status.HTTP_200_OK)
        self.assertEqual(set(worker_stats.data.keys()), {self.worker_employee.full_name})

        worker_create = self.client.post(
            '/api/work-logs/',
            {
                'employee': self.outsider_employee.id,
                'work_date': '2026-04-25',
                'started_at': '09:05:00',
                'ended_at': '18:10:00',
                'lateness_minutes': 5,
                'overtime_minutes': 10,
                'absence_type': AbsenceType.NONE,
                'note': 'Worker self log',
            },
            format='json',
        )
        self.assertEqual(worker_create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(worker_create.data['employee'], self.worker_employee.id)
        worker_created_log_id = worker_create.data['id']
        self.assertEqual(
            self.client.patch(
                f'/api/work-logs/{worker_created_log_id}/',
                {'ended_at': '18:20:00'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(self.client.patch(f'/api/work-logs/{self.outsider_log.id}/', {'note': 'forbidden'}, format='json').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(f'/api/work-logs/{worker_created_log_id}/').status_code, status.HTTP_204_NO_CONTENT)


class LeaveRequestEndpointTests(HrApiBaseTestCase):
    def test_leave_request_endpoints_follow_scope_and_review_rules(self):
        self.authenticate(self.admin)
        self.assertEqual(self.client.get('/api/leave-requests/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/leave-requests/{self.outsider_leave_request.id}/').status_code, status.HTTP_200_OK)
        admin_calendar = self.client.get('/api/leave-requests/calendar/')
        self.assertEqual(admin_calendar.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in admin_calendar.data], [self.approved_worker_leave_request.id])

        admin_create = self.client.post(
            '/api/leave-requests/',
            {
                'employee': self.outsider_employee.id,
                'absence_type': AbsenceType.UNPAID,
                'start_date': '2026-07-01',
                'end_date': '2026-07-02',
                'reason': 'Admin created request',
            },
            format='json',
        )
        self.assertEqual(admin_create.status_code, status.HTTP_201_CREATED)
        admin_request_id = admin_create.data['id']
        self.assertEqual(
            self.client.patch(
                f'/api/leave-requests/{admin_request_id}/',
                {'reason': 'Updated by admin'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(
                f'/api/leave-requests/{admin_request_id}/review/',
                {'status': RequestStatus.APPROVED, 'review_comment': 'Admin approved'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(self.client.delete(f'/api/leave-requests/{admin_request_id}/').status_code, status.HTTP_204_NO_CONTENT)

        self.authenticate(self.manager)
        manager_list = self.client.get('/api/leave-requests/')
        self.assertEqual(manager_list.status_code, status.HTTP_200_OK)
        manager_ids = {item['id'] for item in manager_list.data}
        self.assertIn(self.worker_leave_request.id, manager_ids)
        self.assertIn(self.approved_worker_leave_request.id, manager_ids)
        self.assertNotIn(self.outsider_leave_request.id, manager_ids)
        self.assertEqual(self.client.get(f'/api/leave-requests/{self.worker_leave_request.id}/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/leave-requests/{self.outsider_leave_request.id}/').status_code, status.HTTP_404_NOT_FOUND)

        manager_create = self.client.post(
            '/api/leave-requests/',
            {
                'employee': self.worker_employee.id,
                'absence_type': AbsenceType.DAY_OFF,
                'start_date': '2026-07-10',
                'end_date': '2026-07-10',
                'reason': 'Manager created request',
            },
            format='json',
        )
        self.assertEqual(manager_create.status_code, status.HTTP_201_CREATED)
        manager_request_id = manager_create.data['id']
        self.assertEqual(
            self.client.post(
                '/api/leave-requests/',
                {
                    'employee': self.outsider_employee.id,
                    'absence_type': AbsenceType.DAY_OFF,
                    'start_date': '2026-07-11',
                    'end_date': '2026-07-11',
                    'reason': 'Forbidden manager request',
                },
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/leave-requests/{manager_request_id}/',
                {'reason': 'Manager updated request'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/leave-requests/{self.approved_worker_leave_request.id}/',
                {'reason': 'Forbidden approved edit'},
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                f'/api/leave-requests/{self.worker_leave_request.id}/review/',
                {'status': RequestStatus.APPROVED, 'review_comment': 'Manager approved'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(
                f'/api/leave-requests/{self.outsider_leave_request.id}/review/',
                {'status': RequestStatus.REJECTED, 'review_comment': 'Forbidden'},
                format='json',
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.delete(f'/api/leave-requests/{manager_request_id}/').status_code, status.HTTP_204_NO_CONTENT)

        manager_own_request = self.client.post(
            '/api/leave-requests/',
            {
                'employee': self.manager_employee.id,
                'absence_type': AbsenceType.DAY_OFF,
                'start_date': '2026-07-20',
                'end_date': '2026-07-20',
                'reason': 'Manager personal request',
            },
            format='json',
        )
        self.assertEqual(manager_own_request.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            self.client.post(
                f"/api/leave-requests/{manager_own_request.data['id']}/review/",
                {'status': RequestStatus.APPROVED, 'review_comment': 'Should fail'},
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.authenticate(self.worker)
        worker_list = self.client.get('/api/leave-requests/')
        self.assertEqual(worker_list.status_code, status.HTTP_200_OK)
        worker_ids = {item['id'] for item in worker_list.data}
        self.assertIn(self.worker_leave_request.id, worker_ids)
        self.assertIn(self.approved_worker_leave_request.id, worker_ids)
        self.assertNotIn(self.outsider_leave_request.id, worker_ids)

        worker_calendar = self.client.get('/api/leave-requests/calendar/')
        self.assertEqual(worker_calendar.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item['id'] for item in worker_calendar.data},
            {self.approved_worker_leave_request.id, self.worker_leave_request.id},
        )

        worker_create = self.client.post(
            '/api/leave-requests/',
            {
                'employee': self.outsider_employee.id,
                'absence_type': AbsenceType.UNPAID,
                'start_date': '2026-07-30',
                'end_date': '2026-07-31',
                'reason': 'Worker self request',
            },
            format='json',
        )
        self.assertEqual(worker_create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(worker_create.data['employee'], self.worker_employee.id)
        worker_request_id = worker_create.data['id']
        self.assertEqual(
            self.client.patch(
                f'/api/leave-requests/{worker_request_id}/',
                {'reason': 'Worker updated request'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/leave-requests/{self.approved_worker_leave_request.id}/',
                {'reason': 'Forbidden worker edit'},
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                f'/api/leave-requests/{worker_request_id}/review/',
                {'status': RequestStatus.APPROVED, 'review_comment': 'Forbidden'},
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(self.client.delete(f'/api/leave-requests/{worker_request_id}/').status_code, status.HTTP_204_NO_CONTENT)


class DocumentNotificationAuditEndpointTests(HrApiBaseTestCase):
    def test_document_endpoints_follow_role_scope(self):
        self.authenticate(self.admin)
        self.assertEqual(self.client.get('/api/documents/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/documents/{self.outsider_document.id}/').status_code, status.HTTP_200_OK)

        admin_create = self.client.post(
            '/api/documents/',
            {
                'employee': self.outsider_employee.id,
                'category': 'other',
                'title': 'Admin document',
                'file': self.make_file('admin-document.txt', b'admin-document'),
            },
            format='multipart',
        )
        self.assertEqual(admin_create.status_code, status.HTTP_201_CREATED)
        admin_document_id = admin_create.data['id']
        self.assertEqual(
            self.client.patch(
                f'/api/documents/{admin_document_id}/',
                {'title': 'Admin updated document'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(self.client.delete(f'/api/documents/{admin_document_id}/').status_code, status.HTTP_204_NO_CONTENT)

        self.authenticate(self.manager)
        manager_list = self.client.get('/api/documents/')
        self.assertEqual(manager_list.status_code, status.HTTP_200_OK)
        manager_ids = {item['id'] for item in manager_list.data}
        self.assertIn(self.worker_document.id, manager_ids)
        self.assertNotIn(self.outsider_document.id, manager_ids)
        self.assertEqual(self.client.get(f'/api/documents/{self.worker_document.id}/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/documents/{self.outsider_document.id}/').status_code, status.HTTP_404_NOT_FOUND)

        manager_create = self.client.post(
            '/api/documents/',
            {
                'employee': self.worker_employee.id,
                'category': 'order',
                'title': 'Manager document',
                'file': self.make_file('manager-document.txt', b'manager-document'),
            },
            format='multipart',
        )
        self.assertEqual(manager_create.status_code, status.HTTP_201_CREATED)
        manager_document_id = manager_create.data['id']
        self.assertEqual(
            self.client.post(
                '/api/documents/',
                {
                    'employee': self.outsider_employee.id,
                    'category': 'order',
                    'title': 'Forbidden manager document',
                    'file': self.make_file('forbidden-manager-document.txt', b'forbidden'),
                },
                format='multipart',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/documents/{manager_document_id}/',
                {'title': 'Manager updated document'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(self.client.patch(f'/api/documents/{self.outsider_document.id}/', {'title': 'forbidden'}, format='json').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(f'/api/documents/{manager_document_id}/').status_code, status.HTTP_204_NO_CONTENT)

        self.authenticate(self.worker)
        worker_list = self.client.get('/api/documents/')
        self.assertEqual(worker_list.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in worker_list.data], [self.worker_document.id])
        self.assertEqual(self.client.get(f'/api/documents/{self.worker_document.id}/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/documents/{self.outsider_document.id}/').status_code, status.HTTP_404_NOT_FOUND)

        worker_create = self.client.post(
            '/api/documents/',
            {
                'employee': self.outsider_employee.id,
                'category': 'application',
                'title': 'Worker document',
                'file': self.make_file('worker-document.txt', b'worker-document'),
            },
            format='multipart',
        )
        self.assertEqual(worker_create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(worker_create.data['employee'], self.worker_employee.id)
        worker_document_id = worker_create.data['id']
        self.assertEqual(
            self.client.patch(
                f'/api/documents/{worker_document_id}/',
                {'title': 'Worker updated document'},
                format='json',
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(self.client.patch(f'/api/documents/{self.outsider_document.id}/', {'title': 'forbidden'}, format='json').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(f'/api/documents/{worker_document_id}/').status_code, status.HTTP_204_NO_CONTENT)

    def test_notifications_and_audit_logs_follow_role_scope(self):
        expected_notifications = {
            self.admin: [],
            self.manager: [self.manager_notification.id],
            self.worker: [self.worker_notification.id],
        }
        for user, expected_ids in expected_notifications.items():
            with self.subTest(role=user.role):
                self.authenticate(user)
                notification_list = self.client.get('/api/notifications/')
                self.assertEqual(notification_list.status_code, status.HTTP_200_OK)
                self.assertEqual([item['id'] for item in notification_list.data], expected_ids)
                if expected_ids:
                    self.assertEqual(
                        self.client.get(f"/api/notifications/{expected_ids[0]}/").status_code,
                        status.HTTP_200_OK,
                    )
                    mark_read_response = self.client.post(f"/api/notifications/{expected_ids[0]}/mark_read/")
                    self.assertEqual(mark_read_response.status_code, status.HTTP_200_OK)
                    self.assertTrue(mark_read_response.data['is_read'])

        self.authenticate(self.worker)
        self.assertEqual(self.client.get(f'/api/notifications/{self.manager_notification.id}/').status_code, status.HTTP_404_NOT_FOUND)

        self.authenticate(self.admin)
        self.assertEqual(self.client.get('/api/audit-logs/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/audit-logs/{self.audit_log.id}/').status_code, status.HTTP_200_OK)

        for user in (self.manager, self.worker):
            with self.subTest(role=user.role):
                self.authenticate(user)
                self.assertEqual(self.client.get('/api/audit-logs/').status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(self.client.get(f'/api/audit-logs/{self.audit_log.id}/').status_code, status.HTTP_403_FORBIDDEN)
