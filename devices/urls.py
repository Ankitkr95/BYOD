from django.urls import path
from . import views

app_name = 'devices'

urlpatterns = [
    # Device list and management
    path('', views.DeviceListView.as_view(), name='device_list'),
    path('register/', views.DeviceRegisterView.as_view(), name='device_register'),
    path('<int:pk>/', views.DeviceDetailView.as_view(), name='device_detail'),
    path('<int:pk>/edit/', views.DeviceUpdateView.as_view(), name='device_update'),
    path('<int:pk>/delete/', views.device_delete_view, name='device_delete'),
    
    # Device actions
    path('<int:pk>/toggle-compliance/', views.toggle_compliance_view, name='toggle_compliance'),
    
    # Access request management
    path('access-requests/', views.AccessRequestListView.as_view(), name='access_requests'),
    path('access-requests/<int:pk>/approve/', views.AccessRequestApproveView.as_view(), name='access_request_approve'),
    path('access-requests/<int:pk>/reject/', views.AccessRequestRejectView.as_view(), name='access_request_reject'),
    path('my-requests/', views.MyAccessRequestsView.as_view(), name='my_access_requests'),
]