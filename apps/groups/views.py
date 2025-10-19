from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Group
from .serializers import GroupCreateSerializer, GroupDetailSerializer
from apps.users.models import CustomUser


class GroupCreateView(generics.CreateAPIView):
    queryset = Group.objects.all()
    serializer_class = GroupCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()



class GroupListView(generics.ListAPIView):
    serializer_class = GroupDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.request.user.member_groups.all()


class GroupAddMemberView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        group_id = self.kwargs.get('pk')
        username = request.data.get('username')

        try:
            group = Group.objects.get(id=group_id, owner=request.user)
        except Group.DoesNotExist:
            return Response({'detail': 'Группа не найдена или вы не являетесь владельцем.'},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            user_to_add = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            return Response({'detail': 'Пользователь с таким логином не найден.'},
                            status=status.HTTP_404_NOT_FOUND)

        group.members.add(user_to_add)
        return Response({'detail': f'Пользователь {username} добавлен в группу.'})

class GroupDetailView(generics.RetrieveAPIView):
    queryset = Group.objects.all()
    serializer_class = GroupDetailSerializer
    permission_classes = [IsAuthenticated]

class GroupRemoveMemberView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        username = request.data.get('username')

        try:
            group = Group.objects.get(id=pk)
        except Group.DoesNotExist:
            return Response({'detail': 'Группа не найдена.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            user_to_remove = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            return Response({'detail': 'Пользователь не найден.'}, status=status.HTTP_404_NOT_FOUND)

        # Проверяем, состоит ли пользователь в группе
        if user_to_remove not in group.members.all():
            return Response({'detail': 'Пользователь не состоит в группе.'}, status=status.HTTP_400_BAD_REQUEST)

        # Владелец не может удалить сам себя
        if user_to_remove == group.owner:
            return Response({'detail': 'Создатель группы не может удалить сам себя.'}, status=status.HTTP_400_BAD_REQUEST)

        # Разрешаем удаление только владельцу ИЛИ самому пользователю
        if request.user != group.owner and request.user != user_to_remove:
            return Response({'detail': 'Вы не имеете прав на это действие.'}, status=status.HTTP_403_FORBIDDEN)

        group.members.remove(user_to_remove)
        return Response({'detail': f'Пользователь {username} удалён из группы.'}, status=status.HTTP_200_OK)
    
class GroupDeleteView(generics.DestroyAPIView):
    queryset = Group.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Разрешить удаление только своих групп
        return Group.objects.filter(owner=self.request.user)
