from django.urls import re_path
from . import consumers

websocket_urlpatterns =[
    re_path(r'^ws/chat/stream/$', consumers.ChatConsumer.as_asgi()),
]