from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


app_name = "accounts"

urlpatterns = [
    path("accounts/register/", views.register, name="register"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("people/", views.user_directory, name="user_directory"),
    path("u/<str:username>/", views.profile, name="profile"),
    path("u/<str:username>/edit/", views.profile_edit, name="profile_edit"),
    path("u/<str:username>/follow/", views.follow_user, name="follow"),
    path("u/<str:username>/unfollow/", views.unfollow_user, name="unfollow"),
]