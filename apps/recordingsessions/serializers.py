from rest_framework import serializers
from .models import RecordingSession

class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordingSession
        fields = '__all__'
        read_only_fields = ['owner', 'created_at', 'updated_at', 'status', 'end_time']
