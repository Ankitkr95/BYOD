"""
Management command to create demo users for testing the BYOD Security System.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import UserProfile
from devices.models import Device
from security.models import AccessControl


class Command(BaseCommand):
    help = 'Create demo users with different roles for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing demo users before creating new ones',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Deleting existing demo users...')
            User.objects.filter(username__in=['admin', 'teacher', 'student']).delete()

        # Create superuser admin
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@byod.local',
                'first_name': 'System',
                'last_name': 'Administrator',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Created superuser: admin / admin123')
            )
        else:
            self.stdout.write('Admin user already exists')

        # Create admin profile
        admin_profile, created = UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={
                'role': 'admin',
                'phone_number': '+1234567890',
                'date_of_birth': '1990-01-01',
            }
        )

        # Create teacher user
        teacher_user, created = User.objects.get_or_create(
            username='teacher',
            defaults={
                'email': 'teacher@byod.local',
                'first_name': 'John',
                'last_name': 'Teacher',
                'is_staff': False,
                'is_superuser': False,
            }
        )
        if created:
            teacher_user.set_password('teacher123')
            teacher_user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Created teacher: teacher / teacher123')
            )
        else:
            self.stdout.write('Teacher user already exists')

        # Create teacher profile
        teacher_profile, created = UserProfile.objects.get_or_create(
            user=teacher_user,
            defaults={
                'role': 'teacher',
                'phone_number': '+1234567891',
                'date_of_birth': '1985-05-15',
            }
        )

        # Create student user
        student_user, created = User.objects.get_or_create(
            username='student',
            defaults={
                'email': 'student@byod.local',
                'first_name': 'Jane',
                'last_name': 'Student',
                'is_staff': False,
                'is_superuser': False,
            }
        )
        if created:
            student_user.set_password('student123')
            student_user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Created student: student / student123')
            )
        else:
            self.stdout.write('Student user already exists')

        # Create student profile
        student_profile, created = UserProfile.objects.get_or_create(
            user=student_user,
            defaults={
                'role': 'student',
                'phone_number': '+1234567892',
                'date_of_birth': '2000-09-20',
            }
        )

        # Create sample devices for users
        self.create_sample_devices()

        # Create access control rules
        self.create_access_control_rules()

        self.stdout.write(
            self.style.SUCCESS('\nDemo users created successfully!')
        )
        self.stdout.write('\nLogin credentials:')
        self.stdout.write('Administrator: admin / admin123')
        self.stdout.write('Teacher: teacher / teacher123')
        self.stdout.write('Student: student / student123')

    def create_sample_devices(self):
        """Create sample devices for demo users."""
        users = {
            'admin': User.objects.get(username='admin'),
            'teacher': User.objects.get(username='teacher'),
            'student': User.objects.get(username='student'),
        }

        devices_data = [
            {
                'user': users['admin'],
                'name': 'Admin Laptop',
                'device_type': 'laptop',
                'mac_address': '00:11:22:33:44:55',
                'operating_system': 'windows',
                'compliance_status': True,
            },
            {
                'user': users['teacher'],
                'name': 'Teacher MacBook',
                'device_type': 'laptop',
                'mac_address': '00:11:22:33:44:56',
                'operating_system': 'macos',
                'compliance_status': True,
            },
            {
                'user': users['student'],
                'name': 'Student Laptop',
                'device_type': 'laptop',
                'mac_address': '00:11:22:33:44:57',
                'operating_system': 'windows',
                'compliance_status': True,
            },
            {
                'user': users['student'],
                'name': 'Student Phone',
                'device_type': 'smartphone',
                'mac_address': '00:11:22:33:44:58',
                'operating_system': 'android',
                'compliance_status': False,
            },
        ]

        for device_data in devices_data:
            device, created = Device.objects.get_or_create(
                user=device_data['user'],
                mac_address=device_data['mac_address'],
                defaults=device_data
            )
            if created:
                self.stdout.write(f'Created device: {device.name} for {device.user.username}')

    def create_access_control_rules(self):
        """Create access control rules for different roles."""
        
        # Get admin user for created_by field
        admin_user = User.objects.get(username='admin')
        
        # Student access control - most restrictive
        student_rules, created = AccessControl.objects.get_or_create(
            role='student',
            defaults={
                'allowed_domains': '["education.com", "khan-academy.org", "coursera.org", "edx.org"]',
                'blocked_domains': '["facebook.com", "twitter.com", "instagram.com", "tiktok.com", "youtube.com"]',
                'time_restrictions': '{"start_time": "08:00", "end_time": "17:00", "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]}',
                'created_by': admin_user,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write('Created access control rules for students')

        # Teacher access control - moderate restrictions
        teacher_rules, created = AccessControl.objects.get_or_create(
            role='teacher',
            defaults={
                'allowed_domains': '["*"]',  # Allow all domains
                'blocked_domains': '["gambling.com", "adult-content.com"]',
                'time_restrictions': '{"start_time": "06:00", "end_time": "22:00"}',
                'created_by': admin_user,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write('Created access control rules for teachers')

        # Administrator access control - minimal restrictions
        admin_rules, created = AccessControl.objects.get_or_create(
            role='admin',
            defaults={
                'allowed_domains': '["*"]',  # Allow all domains
                'blocked_domains': '[]',  # No blocked domains
                'time_restrictions': '{}',  # No time restrictions
                'created_by': admin_user,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write('Created access control rules for administrators')