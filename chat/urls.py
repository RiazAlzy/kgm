from django.urls import path
from . import views

app_name = 'chat'

urlpatterns =[
    path('', views.chat_interface, name='chat_interface'),
]