from django.urls import path
from .views import RecordingCreateView, RecordingListView, RecordingDetailView, BotUploadAPIView

urlpatterns = [
    path('', RecordingListView.as_view(), name='recording-list'),
    path('upload/', RecordingCreateView.as_view(), name='recording-upload'),
    path('<int:pk>/', RecordingDetailView.as_view(), name='recording-detail'),
    path('upload-from-bot/', BotUploadAPIView.as_view(), name='bot-upload'),
]
