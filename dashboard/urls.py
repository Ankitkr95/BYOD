from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='home'),
    path('stats/', views.StatsAPIView.as_view(), name='stats_api'),
]