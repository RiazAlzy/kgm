from django.urls import path
from . import views

urlpatterns =[
    path('', views.core_index, name='core_index'),
    path('upload/', views.upload_document, name='upload_document'),
    path('progress/<str:file_hash>/', views.document_progress, name='document_progress'),
]