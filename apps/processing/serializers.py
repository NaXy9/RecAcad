from rest_framework import serializers
from .models import VideoJob, Transcript, Summary, Notes

class VideoJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoJob
        fields = '__all__'
        read_only_fields = ['status', 'log', 'created_at', 'started_at', 'finished_at']

class TranscriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transcript
        fields = ['text', 'timestamps']

class SummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Summary
        fields = ['text']

class NotesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notes
        fields = ['text']
