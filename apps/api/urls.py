from django.urls import path, include

urlpatterns = [
    path('users/', include('apps.users.urls')),
    path('groups/', include('apps.groups.urls')),
    path('recordings/', include('apps.recordings.urls')),
    path('processing/', include('apps.processing.urls')),
    path('sessions/', include('apps.recordingsessions.urls')),
]
