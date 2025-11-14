"""
Main project views for BYOD Security System.
"""

from django.shortcuts import render
from django.views.generic import TemplateView


class HomePageView(TemplateView):
    """
    Home page view for unauthenticated users.
    Shows project information and login/signup options.
    """
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'BYOD Security System',
            'features': [
                {
                    'title': 'Device Management',
                    'description': 'Secure registration and monitoring of personal devices in educational environments.',
                    'icon': 'laptop'
                },
                {
                    'title': 'User Authentication',
                    'description': 'Role-based access control for students, teachers, and administrators.',
                    'icon': 'users'
                },
                {
                    'title': 'Activity Monitoring',
                    'description': 'Real-time tracking of device usage and productivity metrics.',
                    'icon': 'activity'
                },
                {
                    'title': 'Security Controls',
                    'description': 'Advanced session management and access control policies.',
                    'icon': 'shield'
                },
                {
                    'title': 'Reporting & Analytics',
                    'description': 'Comprehensive reports on device compliance and user activity.',
                    'icon': 'chart'
                },
                {
                    'title': 'Responsive Design',
                    'description': 'Modern, mobile-friendly interface with dark/light theme support.',
                    'icon': 'smartphone'
                }
            ],
            'stats': {
                'security_features': '10+',
                'supported_devices': 'All',
                'user_roles': '3',
                'compliance_tracking': '24/7'
            }
        })
        return context