from django.urls import path

from . import views

app_name = "comments"
urlpatterns = [
    path("post/<int:post_id>/comment/", views.add_post_comment, name="add"),
    path("comment/<int:comment_id>/delete/", views.delete, name="delete"),
]
