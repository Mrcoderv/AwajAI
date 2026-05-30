from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("call/", views.call_page, name="call_page"),
    path("chat/", views.chat_page, name="chat_page"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("code-map", views.code_map, name="code_map"),
]
