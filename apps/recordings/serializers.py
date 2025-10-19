from rest_framework import serializers
from .models import Recording
from apps.processing.models import VideoJob
from apps.processing.models import Notes, Summary
import json

class RecordingDetailSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)
    group_title = serializers.SerializerMethodField()
    video_file_url = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    status = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = Recording
        fields = [
            'id',
            'owner',
            'group',
            'group_title',
            'video_file_url',
            'created_at',
            'status',
            'notes',
            'summary',
        ]
        read_only_fields = fields

    def get_group_title(self, obj):
        return obj.group.title if obj.group else None

    def get_video_file_url(self, obj):
        request = self.context.get('request')
        if obj.video_file and request:
            return request.build_absolute_uri(obj.video_file.url)
        return None

    def get_status(self, obj):
        job = VideoJob.objects.filter(recording=obj).order_by('-started_at').first()
        return job.status if job else 'NOT_PROCESSED'

    def get_notes(self, obj):
        job = VideoJob.objects.filter(recording=obj).order_by('-started_at').first()
        if not job:
            return ''
        note = Notes.objects.filter(job=job).order_by('-id').first()
        return note.text if note and note.text else ''

    def get_summary(self, obj):
        job = VideoJob.objects.filter(recording=obj).order_by('-started_at').first()
        if not job:
            return ""
        summ = Summary.objects.filter(job=job).order_by('-id').first()
        if not summ:
            return ""
        return summ.text if summ and summ.text else ''
    
class BotUploadSerializer(serializers.Serializer):
    username = serializers.CharField()
    group_id = serializers.IntegerField()
    video_file = serializers.FileField()


