from django.urls import path

from . import views

app_name = "chat"
urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("create/", views.create, name="create"),
    path("with/<str:username>/", views.dialog_with_user, name="dialog_with_user"),
    path("message/<int:message_id>/delete/", views.delete, name="delete_message"),
    path("<int:conversation_id>/", views.dialog, name="dialog"),
]
