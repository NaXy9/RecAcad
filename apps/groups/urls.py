from django.urls import path
from .views import (
    GroupCreateView, GroupListView, GroupAddMemberView,
    GroupDetailView, GroupRemoveMemberView, GroupDeleteView
)

urlpatterns = [
    path('', GroupListView.as_view(), name='group-list'),
    path('create/', GroupCreateView.as_view(), name='group-create'),
    path('<int:pk>/', GroupDetailView.as_view(), name='group-detail'),
    path('<int:pk>/add-member/', GroupAddMemberView.as_view(), name='group-add-member'),
    path('<int:pk>/remove-member/', GroupRemoveMemberView.as_view(), name='group-remove-member'),
    path('<int:pk>/delete/', GroupDeleteView.as_view(), name='group-delete'),
]
