from django.urls import path
from .views import UserMeAPIView, UserListAPIView, UserRegisterAPIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('register/', UserRegisterAPIView.as_view(), name='user-register'),
    path('me/', UserMeAPIView.as_view(), name='user-me'),
    path('', UserListAPIView.as_view(), name='user-list'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
