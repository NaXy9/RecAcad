from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.conf import settings

from .models import Recording
from .serializers import RecordingDetailSerializer, BotUploadSerializer
from apps.groups.models import Group
from apps.processing.models import VideoJob
from apps.processing.tasks import process_video_job

User = get_user_model()

class RecordingCreateView(generics.CreateAPIView):
    serializer_class = RecordingDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        group_id = self.request.data.get('group')
        try:
            group = Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            raise PermissionDenied("Группа не найдена.")

        if self.request.user not in group.members.all():
            raise PermissionDenied("Вы не состоите в этой группе.")

        serializer.save(owner=self.request.user, group=group)

class RecordingListView(generics.ListAPIView):
    serializer_class = RecordingDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Recording.objects.filter(
            Q(owner=user) | Q(group__members=user)
        ).distinct().order_by('-created_at')

class RecordingDetailView(generics.RetrieveAPIView):
    serializer_class = RecordingDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Recording.objects.filter(
            Q(owner=user) | Q(group__members=user)
        ).distinct()

class BotUploadAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        api_key = request.headers.get('X-API-KEY')
        if api_key != settings.BOT_API_KEY:
            return Response({'detail': 'Недопустимый API-ключ.'}, status=status.HTTP_403_FORBIDDEN)

        # 1) предварительно проверяем user и group
        username = request.data.get('username')
        group_id = request.data.get('group_id')
        try:
            user = User.objects.get(username=username)
            group = Group.objects.get(id=group_id)
        except (User.DoesNotExist, Group.DoesNotExist):
            return Response({'detail': 'Пользователь или группа не найдены.'},
                            status=status.HTTP_404_NOT_FOUND)

        # 2) теперь валидируем файл и остальные поля
        serializer = BotUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # 3) создаём запись и задачу
        video_file = serializer.validated_data['video_file']

        recording = Recording.objects.create(
            owner=user,
            group=group,
            video_file=video_file
        )
        job = VideoJob.objects.create(recording=recording)
        process_video_job.delay(job.id)

        return Response(
            {'detail': 'Файл успешно загружен и обработка запущена.'},
            status=status.HTTP_201_CREATED
        )
