from rest_framework import serializers
from .models import Group
from apps.users.models import CustomUser


class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'title']

    def create(self, validated_data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Нет доступа к request в контексте сериализатора.")

        user = request.user
        group = Group.objects.create(owner=user, **validated_data)
        group.members.add(user)
        return group



class GroupDetailSerializer(serializers.ModelSerializer):
    members = serializers.StringRelatedField(many=True)

    class Meta:
        model = Group
        fields = ['id', 'title', 'owner', 'members']
        read_only_fields = ['owner', 'members']
