from django.urls import re_path

from .consumers import UserSocketConsumer

websocket_urlpatterns = [re_path(r"^ws/?$", UserSocketConsumer.as_asgi())]
