from django.urls import path

from . import schema  # noqa: F401 - registers the drf-spectacular auth extension
from .views import LoginView, MeView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
]