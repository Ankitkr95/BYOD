from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    # Access Control Rules
    path('access-rules/', views.AccessRulesView.as_view(), name='access_rules'),
    path('access-rules/create/', views.AccessRuleCreateView.as_view(), name='access_rule_create'),
    path('access-rules/<int:pk>/edit/', views.AccessRuleUpdateView.as_view(), name='access_rule_edit'),
    path('access-rules/<int:pk>/delete/', views.AccessRuleDeleteView.as_view(), name='access_rule_delete'),
    
    # Session Monitoring
    path('sessions/', views.SessionMonitorView.as_view(), name='session_monitor'),
    path('sessions/<int:session_id>/', views.session_detail_view, name='session_detail'),
    path('sessions/<int:session_id>/end/', views.end_session_view, name='end_session'),
    path('sessions/cleanup/', views.cleanup_expired_sessions, name='cleanup_sessions'),
    path('sessions/user/<int:user_id>/', views.manage_user_sessions, name='manage_user_sessions'),
    
    # Security Alerts
    path('alerts/', views.SecurityAlertsView.as_view(), name='security_alerts'),
    
    # API Endpoints
    path('api/session-stats/', views.session_stats_api, name='session_stats_api'),
    path('api/session-statistics/', views.session_statistics_api, name='session_statistics_api'),
]