from django.urls import path
from . import views

app_name = 'graph'

urlpatterns =[
    path('', views.graph_view, name='index'),
    path('api/expand/', views.api_expand_node, name='api_expand'),
    path('api/asset/<str:sqlite_asset_ids>/', views.asset_modal, name='asset_modal'),
]