from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

class UserTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.register_url = reverse('user-register')
        self.token_url = reverse('token_obtain_pair')
        self.me_url = reverse('user-me')
        self.user_list_url = reverse('user-list')

    def authenticate(self):
        """Helper: авторизовать тестовый клиент."""
        resp = self.client.post(self.token_url, {
            'username': 'testuser',
            'password': 'testpass123'
        })
        token = resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_user_registration_success(self):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpassword123'
        }
        resp = self.client.post(self.register_url, data)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_user_registration_duplicate_username(self):
        # дубликат username должен давать 400
        data = {
            'username': 'testuser',
            'email': 'dup@example.com',
            'password': 'whatever123'
        }
        resp = self.client.post(self.register_url, data)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', resp.data)

    def test_user_registration_duplicate_email(self):
        User.objects.create_user(
            username='otheruser',
            email='testt@example.com',
            password='whatever123'
        )
        data = {
            'username': 'newuser',
            'email': 'testt@example.com',  # тот же email
            'password': 'newpassword123'
        }
        resp = self.client.post(self.register_url, data)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', resp.data)


    def test_token_obtain_success(self):
        resp = self.client.post(self.token_url, {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

    def test_token_obtain_invalid(self):
        resp = self.client.post(self.token_url, {
            'username': 'testuser',
            'password': 'wrongpass'
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_current_user_unauthenticated(self):
        # Теперь возвращает 403 Forbidden
        resp = self.client.get(self.me_url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_current_user_info(self):
        self.authenticate()
        resp = self.client.get(self.me_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['username'], 'testuser')
        self.assertEqual(resp.data['first_name'], 'Test')
        self.assertEqual(resp.data['last_name'], 'User')

    def test_patch_current_user_success(self):
        self.authenticate()
        resp = self.client.patch(self.me_url, {'first_name': 'Updated'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(resp.data['first_name'], 'Updated')

    def test_patch_current_user_readonly_fields_ignored(self):
        self.authenticate()
        original_username = self.user.username
        original_email = self.user.email

        # Попытка изменить read-only поля
        resp = self.client.patch(self.me_url, {
            'username': 'hacker',
            'email': 'h@x.com',
            'first_name': 'NameOnly'
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Убедиться, что username/email не изменились, но first_name изменился
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, original_username)
        self.assertEqual(self.user.email, original_email)
        self.assertEqual(self.user.first_name, 'NameOnly')

    def test_user_list_without_filter(self):
        User.objects.create_user(username='another', password='pass', email='a@b.com')
        resp = self.client.get(self.user_list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 2)

    def test_user_list_filter_by_username(self):
        User.objects.create_user(username='unique', password='pass', email='u@e.com')
        resp = self.client.get(self.user_list_url, {'username': 'unique'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['username'], 'unique')
