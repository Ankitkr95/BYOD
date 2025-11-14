"""
Django management command to generate sample data for the BYOD Security System.
This command creates sample users, devices, activity logs, and other test data.
"""

import json
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction

from users.models import UserProfile
from devices.models import Device
from productivity.models import ActivityLog, PerformanceReport
from security.models import AccessControl, SessionTracker


class Command(BaseCommand):
    help = 'Generate sample data for testing the BYOD Security System'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=20,
            help='Number of users to create (default: 20)'
        )
        parser.add_argument(
            '--devices-per-user',
            type=int,
            default=2,
            help='Average number of devices per user (default: 2)'
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=30,
            help='Number of days back to generate activity data (default: 30)'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing sample data before generating new data'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting sample data generation...'))
        
        if options['clear_existing']:
            self.clear_existing_data()
        
        with transaction.atomic():
            # Create users and profiles
            users = self.create_users(options['users'])
            self.stdout.write(f'Created {len(users)} users')
            
            # Create devices
            devices = self.create_devices(users, options['devices_per_user'])
            self.stdout.write(f'Created {len(devices)} devices')
            
            # Create access control rules
            access_rules = self.create_access_rules(users)
            self.stdout.write(f'Created {len(access_rules)} access control rules')
            
            # Create activity logs and sessions
            activities, sessions = self.create_activity_data(users, devices, options['days_back'])
            self.stdout.write(f'Created {len(activities)} activity logs and {len(sessions)} sessions')
            
            # Create performance reports
            reports = self.create_performance_reports(users, options['days_back'])
            self.stdout.write(f'Created {len(reports)} performance reports')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Sample data generation completed successfully!\n'
                f'Summary:\n'
                f'  - Users: {len(users)}\n'
                f'  - Devices: {len(devices)}\n'
                f'  - Access Rules: {len(access_rules)}\n'
                f'  - Activity Logs: {len(activities)}\n'
                f'  - Sessions: {len(sessions)}\n'
                f'  - Performance Reports: {len(reports)}'
            )
        )

    def clear_existing_data(self):
        """Clear existing sample data (keeps admin users)."""
        self.stdout.write('Clearing existing sample data...')
        
        # Delete in reverse dependency order
        PerformanceReport.objects.all().delete()
        ActivityLog.objects.all().delete()
        SessionTracker.objects.all().delete()
        AccessControl.objects.all().delete()
        Device.objects.all().delete()
        
        # Delete non-superuser users
        User.objects.filter(is_superuser=False).delete()
        
        self.stdout.write('Existing sample data cleared.')

    def create_users(self, count):
        """Create sample users with different roles."""
        users = []
        
        # Sample names and data
        first_names = [
            'Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank', 'Grace', 'Henry',
            'Ivy', 'Jack', 'Kate', 'Liam', 'Maya', 'Noah', 'Olivia', 'Paul',
            'Quinn', 'Ruby', 'Sam', 'Tara', 'Uma', 'Victor', 'Wendy', 'Xander',
            'Yara', 'Zoe'
        ]
        
        last_names = [
            'Anderson', 'Brown', 'Clark', 'Davis', 'Evans', 'Foster', 'Garcia',
            'Harris', 'Johnson', 'King', 'Lee', 'Miller', 'Nelson', 'Parker',
            'Quinn', 'Roberts', 'Smith', 'Taylor', 'Wilson', 'Young'
        ]
        
        # Role distribution: 1 admin, 3-4 teachers, rest students
        roles = ['admin'] + ['teacher'] * 4 + ['student'] * (count - 5)
        random.shuffle(roles)
        
        for i in range(count):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            username = f"{first_name.lower()}.{last_name.lower()}{i+1}"
            email = f"{username}@school.edu"
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password='password123',  # Simple password for testing
                first_name=first_name,
                last_name=last_name
            )
            
            # Update profile role (profile is created automatically by signal)
            user.profile.role = roles[i] if i < len(roles) else 'student'
            user.profile.save()
            
            users.append(user)
        
        return users

    def create_devices(self, users, avg_devices_per_user):
        """Create sample devices for users."""
        devices = []
        
        device_names = [
            'MacBook Pro', 'iPad Air', 'iPhone 13', 'Dell Laptop', 'Surface Pro',
            'Samsung Galaxy', 'Chromebook', 'ThinkPad', 'iMac', 'Android Tablet',
            'Gaming Laptop', 'Work Phone', 'Personal Laptop', 'Study Tablet'
        ]
        
        device_types = ['laptop', 'tablet', 'smartphone']
        operating_systems = ['windows', 'macos', 'ios', 'android', 'linux', 'other']
        
        for user in users:
            # Random number of devices per user (1-4)
            num_devices = random.randint(1, min(4, avg_devices_per_user + 2))
            
            for i in range(num_devices):
                device_type = random.choice(device_types)
                
                # Choose appropriate OS based on device type
                if device_type == 'smartphone':
                    os_choices = ['ios', 'android']
                elif device_type == 'tablet':
                    os_choices = ['ios', 'android', 'windows']
                else:  # laptop
                    os_choices = ['windows', 'macos', 'linux', 'other']
                
                # Generate MAC address
                mac_address = ':'.join([
                    f'{random.randint(0, 255):02X}' for _ in range(6)
                ])
                
                device = Device.objects.create(
                    user=user,
                    name=f"{random.choice(device_names)} {i+1}",
                    device_type=device_type,
                    mac_address=mac_address,
                    operating_system=random.choice(os_choices),
                    compliance_status=random.choice([True, True, True, False]),  # 75% compliant
                    registered_at=timezone.now() - timedelta(days=random.randint(1, 90)),
                    last_seen=timezone.now() - timedelta(hours=random.randint(0, 48))
                )
                
                devices.append(device)
        
        return devices

    def create_access_rules(self, users):
        """Create sample access control rules."""
        access_rules = []
        
        # Get admin users
        admin_users = [u for u in users if hasattr(u, 'profile') and u.profile.role == 'admin']
        if not admin_users:
            return access_rules
        
        admin_user = admin_users[0]
        
        # Sample domain lists
        educational_domains = [
            'khan-academy.org', 'coursera.org', 'edx.org', 'wikipedia.org',
            'scholar.google.com', 'jstor.org', 'pubmed.ncbi.nlm.nih.gov'
        ]
        
        blocked_domains = [
            'facebook.com', 'instagram.com', 'tiktok.com', 'snapchat.com',
            'twitter.com', 'youtube.com', 'netflix.com', 'gaming.com'
        ]
        
        # Create rules for each role
        roles = ['student', 'teacher', 'admin']
        
        for role in roles:
            if role == 'student':
                allowed = educational_domains[:5]  # Limited access for students
                blocked = blocked_domains
            elif role == 'teacher':
                allowed = educational_domains + ['classroom.google.com', 'zoom.us']
                blocked = blocked_domains[:4]  # Less restrictive
            else:  # admin
                allowed = ['*']  # Full access
                blocked = []
            
            access_rule = AccessControl.objects.create(
                role=role,
                allowed_domains=json.dumps(allowed),
                blocked_domains=json.dumps(blocked),
                time_restrictions=json.dumps({
                    'weekdays': {'start': '08:00', 'end': '17:00'},
                    'weekends': {'start': '09:00', 'end': '15:00'}
                }),
                created_by=admin_user,
                is_active=True
            )
            
            access_rules.append(access_rule)
        
        return access_rules

    def create_activity_data(self, users, devices, days_back):
        """Create sample activity logs and session data."""
        activities = []
        sessions = []
        
        activity_types = [
            'web_browsing', 'application_usage', 'file_access', 'active',
            'login', 'logout', 'idle', 'other'
        ]
        
        session_statuses = ['active', 'inactive', 'expired', 'terminated', 'violation']
        
        # Generate data for each day
        for day_offset in range(days_back):
            date = timezone.now() - timedelta(days=day_offset)
            
            # Only generate data for weekdays (school days)
            if date.weekday() < 5:  # Monday = 0, Friday = 4
                
                # Random subset of users active each day
                active_users = random.sample(users, random.randint(len(users)//2, len(users)))
                
                for user in active_users:
                    user_devices = [d for d in devices if d.user == user]
                    if not user_devices:
                        continue
                    
                    # Create 1-3 sessions per active user per day
                    num_sessions = random.randint(1, 3)
                    
                    for session_num in range(num_sessions):
                        device = random.choice(user_devices)
                        
                        # Session timing
                        session_start = date.replace(
                            hour=random.randint(8, 16),
                            minute=random.randint(0, 59),
                            second=0,
                            microsecond=0
                        )
                        
                        session_duration = timedelta(minutes=random.randint(30, 180))
                        session_end = session_start + session_duration
                        
                        # Create session
                        status = random.choice(session_statuses)
                        if day_offset == 0 and session_num == 0:  # Some current sessions
                            status = 'active'
                            session_end = None
                        
                        session = SessionTracker.objects.create(
                            user=user,
                            device=device,
                            login_time=session_start,
                            logout_time=session_end,
                            ip_address=f"192.168.1.{random.randint(10, 254)}",
                            status=status,
                            session_key=f"session_{user.id}_{device.id}_{day_offset}_{session_num}",
                            violation_count=random.randint(0, 3) if status == 'violation' else 0
                        )
                        
                        sessions.append(session)
                        
                        # Create activities for this session
                        if session_end:  # Only for completed sessions
                            num_activities = random.randint(2, 6)
                            
                            for activity_num in range(num_activities):
                                activity_start = session_start + timedelta(
                                    minutes=random.randint(0, int(session_duration.total_seconds() // 60))
                                )
                                
                                activity_duration = timedelta(minutes=random.randint(5, 45))
                                
                                # Sample resources accessed
                                resources = [
                                    'https://classroom.google.com/assignment/123',
                                    'https://docs.google.com/document/456',
                                    'https://khan-academy.org/math/algebra',
                                    'https://wikipedia.org/article/science',
                                    'https://zoom.us/meeting/789'
                                ]
                                
                                activity = ActivityLog.objects.create(
                                    user=user,
                                    device=device,
                                    duration=activity_duration,
                                    resources_accessed=json.dumps(random.sample(resources, random.randint(1, 3))),
                                    timestamp=activity_start,
                                    activity_type=random.choice(activity_types)
                                )
                                
                                activities.append(activity)
        
        return activities, sessions

    def create_performance_reports(self, users, days_back):
        """Create sample performance reports."""
        reports = []
        
        # Generate weekly reports
        for week_offset in range(0, days_back, 7):
            report_date = timezone.now().date() - timedelta(days=week_offset)
            
            for user in users:
                # Skip admin users for performance reports
                if hasattr(user, 'profile') and user.profile.role == 'admin':
                    continue
                
                # Calculate realistic scores based on role and randomness
                base_productivity = 75 if hasattr(user, 'profile') and user.profile.role == 'teacher' else 65
                base_attendance = 85 if hasattr(user, 'profile') and user.profile.role == 'teacher' else 80
                
                productivity_score = max(0, min(100, base_productivity + random.randint(-20, 25)))
                attendance_percentage = max(0, min(100, base_attendance + random.randint(-15, 20)))
                
                report = PerformanceReport.objects.create(
                    user=user,
                    report_type='weekly',
                    productivity_score=productivity_score,
                    attendance_percentage=attendance_percentage,
                    report_date=report_date,
                    start_date=report_date - timedelta(days=6),  # Week start
                    end_date=report_date,  # Week end
                    generated_at=timezone.now() - timedelta(days=week_offset)
                )
                
                reports.append(report)
        
        return reports