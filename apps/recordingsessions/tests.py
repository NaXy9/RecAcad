from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch
from rest_framework.test import APIClient

from django.contrib.auth import get_user_model
from apps.groups.models import Group
from apps.recordingsessions.models import RecordingSession

User = get_user_model()

class RecordingSessionTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        # создаём пользователей
        self.owner = User.objects.create_user('owner', 'o@example.com', 'pass')
        self.member = User.objects.create_user('member', 'm@example.com', 'pass')
        self.other = User.objects.create_user('other', 'x@example.com', 'pass')

        # создаём группу, добавляем туда owner и member
        self.group = Group.objects.create(title='TestGroup', owner=self.owner)
        self.group.members.set([self.owner, self.member])

        # получаем access-токены
        def token_for(user):
            refresh = RefreshToken.for_user(user)
            return str(refresh.access_token)

        self.token_owner = token_for(self.owner)
        self.token_member = token_for(self.member)
        self.token_other = token_for(self.other)

        # сброс авторизационных заголовков
        self.client.credentials()

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    #
    # Тесты ModelViewSet: list, create, retrieve
    #

    def test_list_sessions_filters_by_membership(self):
        s1 = RecordingSession.objects.create(owner=self.owner, group=self.group)
        other_group = Group.objects.create(title='G2', owner=self.other)
        other_group.members.add(self.other)
        RecordingSession.objects.create(owner=self.other, group=other_group)

        self.auth(self.token_member)
        resp = self.client.get(reverse('session-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['id'], s1.id)

    def test_create_session_via_viewset(self):
        self.auth(self.token_member)
        data = {'group': self.group.id, 'link': 'https://jazz.ru/xyz'}
        resp = self.client.post(reverse('session-list'), data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        sess = RecordingSession.objects.get(id=resp.data['id'])
        self.assertEqual(sess.owner, self.member)
        self.assertEqual(sess.group.id, self.group.id)
        self.assertEqual(sess.link, data['link'])
        self.assertEqual(sess.status, 'active')

    def test_retrieve_session_permissions(self):
        sess = RecordingSession.objects.create(owner=self.owner, group=self.group)
        url = reverse('session-detail', args=[sess.id])

        self.auth(self.token_other)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        self.auth(self.token_member)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['id'], sess.id)

    #
    # Тесты StartRecordingSessionAPIView
    #

    def test_start_missing_params(self):
        self.auth(self.token_member)
        resp = self.client.post(reverse('start-recording-session'), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Требуется ссылка', resp.data['detail'])

    def test_start_group_not_found(self):
        self.auth(self.token_member)
        resp = self.client.post(
            reverse('start-recording-session'),
            {'link': 'l', 'group': 999},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_start_not_member(self):
        self.auth(self.token_other)
        resp = self.client.post(
            reverse('start-recording-session'),
            {'link': 'l', 'group': self.group.id},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch('apps.recordingsessions.views.start_conference_bot.delay')
    def test_start_success(self, mock_delay):
        self.auth(self.token_member)
        data = {'link': 'https://jazz.ru/123', 'group': self.group.id}
        resp = self.client.post(reverse('start-recording-session'), data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('session_id', resp.data)

        sid = resp.data['session_id']
        sess = RecordingSession.objects.get(id=sid)
        self.assertEqual(sess.link, data['link'])
        self.assertEqual(sess.status, 'active')
        mock_delay.assert_called_once_with(sess.id, data['link'], "Кебабот")

    #
    # Тесты StopRecordingSessionAPIView
    #

    def test_stop_not_found(self):
        self.auth(self.token_owner)
        resp = self.client.post(reverse('stop-session', kwargs={'session_id': 999}), format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_stop_unauthorized(self):
        sess = RecordingSession.objects.create(owner=self.owner, group=self.group)
        self.auth(self.token_other)
        resp = self.client.post(reverse('stop-session', kwargs={'session_id': sess.id}), format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_stop_already_stopped(self):
        sess = RecordingSession.objects.create(owner=self.owner, group=self.group, status='stopped')
        self.auth(self.token_member)
        resp = self.client.post(reverse('stop-session', kwargs={'session_id': sess.id}), format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Сессия уже остановлена', resp.data['detail'])

    @patch('apps.recordingsessions.views.stop_conference_bot.delay')
    def test_stop_success(self, mock_delay):
        sess = RecordingSession.objects.create(owner=self.owner, group=self.group)
        self.auth(self.token_member)
        resp = self.client.post(reverse('stop-session', kwargs={'session_id': sess.id}), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        sess.refresh_from_db()
        self.assertEqual(sess.status, 'stopped')
        self.assertIsNotNone(sess.end_time)
        mock_delay.assert_called_once_with(sess.id)
