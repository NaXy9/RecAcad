from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from apps.recordings.models import Recording
from apps.groups.models import Group
from apps.processing.models import VideoJob, Transcript, Summary, Notes
from apps.processing.tasks import process_video_job
from unittest.mock import patch

User = get_user_model()

class VideoJobTests(APITestCase):
    def setUp(self):
        # пользователи
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'pass')
        self.member = User.objects.create_user('member', 'member@example.com', 'pass')
        self.other = User.objects.create_user('other', 'other@example.com', 'pass')

        # группа + запись
        self.group = Group.objects.create(title='G1', owner=self.owner)
        self.group.members.add(self.owner, self.member)
        self.recording = Recording.objects.create(
            owner=self.owner,
            group=self.group,
            video_file='test.mp4'
        )

        # endpoints
        self.list_url = reverse('videojob-list')
        # токены
        def token_for(user):
            refresh = RefreshToken.for_user(user)
            return str(refresh.access_token)
        self.token_owner = token_for(self.owner)
        self.token_member = token_for(self.member)
        self.token_other = token_for(self.other)

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_create_job_as_member(self):
        self.auth(self.token_member)
        resp = self.client.post(self.list_url, {'recording': self.recording.id})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        job = VideoJob.objects.get(id=resp.data['id'])
        self.assertEqual(job.recording, self.recording)
        self.assertEqual(job.status, 'PENDING')

    def test_create_job_unauthorized(self):
        self.auth(self.token_other)
        resp = self.client.post(self.list_url, {'recording': self.recording.id})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_jobs_filters_by_group(self):
        # создаём пару задач в этой группе и одну в чужой
        VideoJob.objects.create(recording=self.recording)
        other_group = Group.objects.create(title='G2', owner=self.other)
        other_group.members.add(self.other)
        other_rec = Recording.objects.create(owner=self.other, group=other_group, video_file='a.mp4')
        VideoJob.objects.create(recording=other_rec)

        self.auth(self.token_member)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # только 1 задача
        self.assertEqual(len(resp.data), 1)

    def test_retrieve_job_permission(self):
        job = VideoJob.objects.create(recording=self.recording)
        detail = reverse('videojob-detail', args=[job.id])

        self.auth(self.token_other)
        resp = self.client.get(detail)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        self.auth(self.token_member)
        resp = self.client.get(detail)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_transcript_summary_notes_endpoints_empty(self):
        job = VideoJob.objects.create(recording=self.recording)
        for action in ['transcript', 'summary', 'notes']:
            url = reverse(f'videojob-{action}', args=[job.id])
            self.auth(self.token_member)
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_transcript_summary_notes_after_create(self):
        job = VideoJob.objects.create(recording=self.recording)
        Transcript.objects.create(job=job, text='txt', timestamps=[0,1,2])
        Summary.objects.create(job=job, text='sum')
        Notes.objects.create(job=job, text='notes')

        for model, action, expected in [
            (Transcript, 'transcript', {'text':'txt','timestamps':[0,1,2]}),
            (Summary, 'summary', {'text':'sum'}),
            (Notes, 'notes', {'text':'notes'}),
        ]:
            url = reverse(f'videojob-{action}', args=[job.id])
            self.auth(self.token_member)
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            for k,v in expected.items():
                self.assertEqual(resp.data[k], v)

    @patch('apps.processing.tasks.subprocess.run', lambda *args, **kwargs: None)
    @patch('apps.processing.tasks.EncDecCTCModelBPE')
    def test_process_video_job_task_success(self, MockModel):
        # подменим модель и subprocess чтобы не запускать внешние зависимости
        job = VideoJob.objects.create(recording=self.recording)
        class DummyModel:
            @staticmethod
            def restore_from(p): return DummyModel()
            def transcribe(self, lst): return ["hello world"]
        MockModel.restore_from = DummyModel.restore_from

        job = VideoJob.objects.create(recording=self.recording)
        process_video_job(job.id)
        job.refresh_from_db()

        self.assertEqual(job.status, 'SUCCESS')
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.finished_at)
        # и дочерние объекты созданы
        self.assertTrue(hasattr(job, 'transcript'))
        self.assertEqual(job.transcript.text, "hello world")
        self.assertTrue(hasattr(job, 'summary'))
        self.assertTrue(hasattr(job, 'notes'))

    @patch('apps.processing.tasks.subprocess.run', side_effect=RuntimeError("ffmpeg err"))
    def test_process_video_job_task_failure(self, mock_run):
        """
        Если ffmpeg упадёт, задача должна пометиться FAILED,
        в логе появится текст ошибки, и finished_at заполнится.
        """
        job = VideoJob.objects.create(recording=self.recording)
        process_video_job(job.id)
        job.refresh_from_db()

        self.assertEqual(job.status, 'FAILED')
        self.assertIn("ffmpeg err", job.log)
        self.assertIsNotNone(job.finished_at)
