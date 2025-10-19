# apps/recordings/tests.py
import io
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status
from django.conf import settings
from django.contrib.auth import get_user_model
from apps.groups.models import Group
from apps.recordings.models import Recording
from apps.processing.models import VideoJob

User = get_user_model()

class RecordingTests(APITestCase):
    def setUp(self):
        # Пользователи
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'pass')
        self.member = User.objects.create_user('member', 'member@example.com', 'pass')
        self.other = User.objects.create_user('other', 'other@example.com', 'pass')

        # Группа и добавление участников
        self.group = Group.objects.create(title='TestGroup', owner=self.owner)
        self.group.members.add(self.owner, self.member)

        # Подготовка тестового файла
        self.video_content = b'\x00' * 64
        self.uploaded_file = SimpleUploadedFile(
            'test.mp4', self.video_content, content_type='video/mp4'
        )

        # Эндпоинты
        self.list_url    = reverse('recording-list')
        self.upload_url  = reverse('recording-upload')
        # detail URL будет строиться при тесте
        self.bot_url     = reverse('bot-upload')

        # заголовок авторизации
        self.client.force_authenticate(user=self.owner)

    def test_create_recording_success(self):
        """Успешная загрузка своим и участником группы"""
        # по очереди владелец и member
        for user in (self.owner, self.member):
            self.client.force_authenticate(user=user)
            resp = self.client.post(self.upload_url, {
                'group': self.group.id,
                'video_file': self.uploaded_file
            }, format='multipart')
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
            rec = Recording.objects.latest('id')
            self.assertEqual(rec.owner, user)
            self.assertEqual(rec.group, self.group)

    def test_create_recording_for_non_member(self):
        """Запрет загрузки пользователем вне группы"""
        self.client.force_authenticate(user=self.other)
        resp = self.client.post(self.upload_url, {
            'group': self.group.id,
            'video_file': self.uploaded_file
        }, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_recording_invalid_group(self):
        """Запрет при несуществующей группе"""
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post(self.upload_url, {
            'group': 9999,
            'video_file': self.uploaded_file
        }, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_recordings(self):
        """Список записей включает свои и групповые"""
        # создаём несколько записей
        rec1 = Recording.objects.create(owner=self.owner, group=self.group, video_file='v1.mp4')
        other_group = Group.objects.create(title='Other', owner=self.other)
        other_group.members.add(self.other)
        rec2 = Recording.objects.create(owner=self.other, group=other_group, video_file='v2.mp4')

        # owner видит только rec1
        self.client.force_authenticate(user=self.owner)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['id'], rec1.id)

        # other видит только rec2
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(self.list_url)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['id'], rec2.id)

    def test_retrieve_recording_permission(self):
        """Доступ к деталям только своим и групповым"""
        rec = Recording.objects.create(owner=self.owner, group=self.group, video_file='f.mp4')
        url = reverse('recording-detail', args=[rec.id])

        self.client.force_authenticate(user=self.other)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(user=self.member)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # проверяем поля сериализатора
        self.assertIn('group_title', resp.data)
        self.assertEqual(resp.data['group_title'], 'TestGroup')
        self.assertIn('status', resp.data)
        self.assertEqual(resp.data['status'], 'NOT_PROCESSED')

    def test_bot_upload_missing_api_key(self):
        """Запрет загрузки от бота без ключа"""
        resp = self.client.post(self.bot_url, {
            'username': self.owner.username,
            'group_id': self.group.id,
            'video_file': self.uploaded_file
        }, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_bot_upload_invalid_key(self):
        """Запрет при неверном API-ключе"""
        resp = self.client.post(
            self.bot_url,
            {
                'username': self.owner.username,
                'group_id': self.group.id,
                'video_file': self.uploaded_file
            },
            format='multipart',
            **{'HTTP_X_API_KEY': 'wrongkey'}
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_bot_upload_user_or_group_not_found(self):
        """404 если не найден пользователь или группа"""
        # корректный ключ
        api_key = settings.BOT_API_KEY
        headers = {'HTTP_X_API_KEY': api_key}
        # несуществующий пользователь
        resp1 = self.client.post(
            self.bot_url,
            {'username': 'nope', 'group_id': self.group.id, 'video_file': self.uploaded_file},
            format='multipart',
            **headers
        )
        self.assertEqual(resp1.status_code, status.HTTP_404_NOT_FOUND)

        # несуществующая группа
        resp2 = self.client.post(
            self.bot_url,
            {'username': self.owner.username, 'group_id': 9999, 'video_file': self.uploaded_file},
            format='multipart',
            **headers
        )
        self.assertEqual(resp2.status_code, status.HTTP_404_NOT_FOUND)

    def test_bot_upload_success(self):
        """Успешная загрузка ботом и создание VideoJob"""
        api_key = settings.BOT_API_KEY
        headers = {'HTTP_X_API_KEY': api_key}
        resp = self.client.post(
            self.bot_url,
            {'username': self.owner.username, 'group_id': self.group.id, 'video_file': self.uploaded_file},
            format='multipart',
            **headers
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # запись и джоб созданы
        rec = Recording.objects.latest('id')
        self.assertEqual(rec.owner, self.owner)
        self.assertTrue(VideoJob.objects.filter(recording=rec).exists())
