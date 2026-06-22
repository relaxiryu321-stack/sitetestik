from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status

from hr.models import UserRole

from .base import HrApiBaseTestCase


class AuthApiTests(HrApiBaseTestCase):
    def test_register_returns_worker_role_and_token(self):
        response = self.client.post(
            '/api/auth/register/',
            {
                'username': 'new-worker',
                'first_name': 'New',
                'last_name': 'Worker',
                'email': 'new-worker@example.com',
                'password': 'StrongPass123!',
                'password_confirm': 'StrongPass123!',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['role'], UserRole.EMPLOYEE)

    def test_login_me_change_password_and_logout_work_for_all_roles(self):
        for index, user in enumerate((self.admin, self.manager, self.worker), start=1):
            with self.subTest(role=user.role):
                self.clear_auth()

                login_response = self.client.post(
                    '/api/auth/login/',
                    {'username': user.username, 'password': 'StrongPass123!'},
                    format='json',
                )
                self.assertEqual(login_response.status_code, status.HTTP_200_OK)
                self.assertEqual(login_response.data['user']['role'], user.role)

                self.client.credentials(HTTP_AUTHORIZATION=f"Token {login_response.data['token']}")

                me_response = self.client.get('/api/auth/me/')
                self.assertEqual(me_response.status_code, status.HTTP_200_OK)
                self.assertEqual(me_response.data['username'], user.username)

                patch_response = self.client.patch(
                    '/api/auth/me/',
                    {'first_name': f'{user.username}-updated', 'role': UserRole.ADMIN},
                    format='json',
                )
                self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
                self.assertEqual(patch_response.data['first_name'], f'{user.username}-updated')
                self.assertEqual(patch_response.data['role'], user.role)

                new_password = f'UpdatedSecurePass{index}!9'
                change_password_response = self.client.post(
                    '/api/auth/change-password/',
                    {'old_password': 'StrongPass123!', 'new_password': new_password},
                    format='json',
                )
                self.assertEqual(change_password_response.status_code, status.HTTP_200_OK)
                self.assertIn('token', change_password_response.data)

                self.client.credentials(HTTP_AUTHORIZATION=f"Token {change_password_response.data['token']}")
                logout_response = self.client.post('/api/auth/logout/')
                self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)

                self.clear_auth()
                relogin_response = self.client.post(
                    '/api/auth/login/',
                    {'username': user.username, 'password': new_password},
                    format='json',
                )
                self.assertEqual(relogin_response.status_code, status.HTTP_200_OK)

    def test_password_reset_request_and_confirm_updates_password(self):
        request_response = self.client.post(
            '/api/auth/password-reset/',
            {'email': self.worker.email},
            format='json',
        )
        self.assertEqual(request_response.status_code, status.HTTP_200_OK)

        uid = urlsafe_base64_encode(force_bytes(self.worker.pk))
        token = default_token_generator.make_token(self.worker)
        confirm_response = self.client.post(
            '/api/auth/password-reset/confirm/',
            {
                'uid': uid,
                'token': token,
                'new_password': 'ResetPass123!',
            },
            format='json',
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

        login_response = self.client.post(
            '/api/auth/login/',
            {'username': self.worker.username, 'password': 'ResetPass123!'},
            format='json',
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
