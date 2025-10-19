from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

from .models import RecordingSession
from .serializers import SessionSerializer
from apps.groups.models import Group
from bot.tasks import start_conference_bot, stop_conference_bot


class SessionViewSet(viewsets.ModelViewSet):
    serializer_class = SessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return RecordingSession.objects.filter(
            Q(owner=user) | Q(group__members=user)
        ).distinct().order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class StartRecordingSessionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        link = request.data.get('link')
        group_id = request.data.get('group')

        if not link or not group_id:
            return Response(
                {'detail': 'Требуется ссылка и идентификатор группы.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            group = Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            return Response({'detail': 'Группа не найдена.'}, status=status.HTTP_404_NOT_FOUND)

        if request.user not in group.members.all():
            return Response({'detail': 'Вы не состоите в данной группе.'}, status=status.HTTP_403_FORBIDDEN)

        session = RecordingSession.objects.create(
            owner=request.user,
            group=group,
            link=link,
        )

        start_conference_bot.delay(session.id, link, "Кебабот", request.user.id, group.id)

        return Response({
            'detail': 'Сессия записи создана и бот запущен.',
            'session_id': session.id
        }, status=status.HTTP_201_CREATED)


class StopRecordingSessionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        user = request.user
        session = get_object_or_404(RecordingSession, id=session_id)

        if not (session.owner == user or user in session.group.members.all()):
            return Response({'detail': 'У вас нет доступа к этой сессии.'}, status=status.HTTP_403_FORBIDDEN)

        if session.status != 'active':
            return Response({'detail': 'Сессия уже остановлена или завершена.'}, status=status.HTTP_400_BAD_REQUEST)

        stop_conference_bot.delay(session.id)

        session.status = 'stopped'
        session.end_time = timezone.now()
        session.save()

        return Response({'detail': 'Сессия остановлена.'}, status=status.HTTP_200_OK)
