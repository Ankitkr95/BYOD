from django.urls import path
from . import views

app_name = 'productivity'

urlpatterns = [
    # Activity logs
    path('activity-logs/', views.ActivityLogListView.as_view(), name='activity_logs'),
    
    # Reports
    path('reports/', views.ReportsView.as_view(), name='reports'),
    
    # Export functionality
    path('export/', views.ExportCSVView.as_view(), name='export_csv'),
    
    # API endpoints
    path('api/activity-stats/', views.activity_stats_api, name='activity_stats_api'),
]