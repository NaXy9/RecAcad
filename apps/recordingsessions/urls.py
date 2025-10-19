from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import SessionViewSet, StartRecordingSessionAPIView, StopRecordingSessionAPIView

router = DefaultRouter()
router.register(r'', SessionViewSet, basename='session')

urlpatterns = [
    # сначала «стартер» сессии
    path('start/', StartRecordingSessionAPIView.as_view(), name='start-recording-session'),
    path('<int:session_id>/stop/', StopRecordingSessionAPIView.as_view(), name='stop-session'),
    # а затем уже REST-роуты
    *router.urls,
]
