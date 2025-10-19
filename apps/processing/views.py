from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import VideoJob
from .serializers import (
    VideoJobSerializer,
    TranscriptSerializer,
    SummarySerializer,
    NotesSerializer
)
from .tasks import process_video_job


class CanAccessJob(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        recording = obj.recording
        return (
            recording.owner == user or
            recording.group.members.filter(id=user.id).exists()
        )


class VideoJobViewSet(viewsets.ModelViewSet):
    serializer_class = VideoJobSerializer
    permission_classes = [permissions.IsAuthenticated, CanAccessJob]

    def get_queryset(self):
        user = self.request.user
        return VideoJob.objects.filter(
            recording__group__members=user
        ).distinct()

    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recording = serializer.validated_data['recording']
        user = request.user
        if recording.owner != user and not recording.group.members.filter(id=user.id).exists():
            return Response({'detail': 'Нет доступа к этой записи.'}, status=status.HTTP_403_FORBIDDEN)
        job = serializer.save()
        process_video_job.delay(job.id)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['get'])
    def transcript(self, request, pk=None):
        job = self.get_object()
        if hasattr(job, 'transcript'):
            serializer = TranscriptSerializer(job.transcript)
            return Response(serializer.data)
        return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        job = self.get_object()
        if hasattr(job, 'summary'):
            serializer = SummarySerializer(job.summary)
            return Response(serializer.data)
        return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def notes(self, request, pk=None):
        job = self.get_object()
        if hasattr(job, 'notes'):
            serializer = NotesSerializer(job.notes)
            return Response(serializer.data)
        return Response(status=status.HTTP_404_NOT_FOUND)
