"""
Management command for cleaning up expired sessions and session trackers.

This command can be run manually or scheduled as a cron job to maintain
session hygiene and prevent database bloat.
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from security.session_utils import SessionManager


class Command(BaseCommand):
    help = 'Clean up expired sessions and session trackers'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=getattr(settings, 'SESSION_TIMEOUT_MINUTES', 30),
            help='Session timeout in minutes (default: 30)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned up without actually doing it'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )
    
    def handle(self, *args, **options):
        timeout_minutes = options['timeout']
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting session cleanup (timeout: {timeout_minutes} minutes)')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No actual cleanup will be performed')
            )
        
        try:
            if dry_run:
                # For dry run, we'll just count what would be cleaned
                from django.utils import timezone
                from datetime import timedelta
                from security.models import SessionTracker
                from django.contrib.sessions.models import Session
                
                cutoff_time = timezone.now() - timedelta(minutes=timeout_minutes)
                
                expired_trackers = SessionTracker.objects.filter(
                    status='active',
                    last_activity__lt=cutoff_time
                ).count()
                
                orphaned_sessions = Session.objects.filter(
                    expire_date__lt=timezone.now()
                ).count()
                
                stats = {
                    'expired_session_trackers': expired_trackers,
                    'orphaned_sessions_cleaned': orphaned_sessions,
                    'total_cleaned': expired_trackers + orphaned_sessions
                }
                
                self.stdout.write('DRY RUN RESULTS:')
            else:
                # Perform actual cleanup
                stats = SessionManager.cleanup_expired_sessions(timeout_minutes)
            
            if 'error' in stats:
                raise CommandError(f'Cleanup failed: {stats["error"]}')
            
            # Display results
            self.stdout.write(
                self.style.SUCCESS(f'Cleanup completed successfully!')
            )
            
            if verbose or dry_run:
                self.stdout.write(f'  Expired session trackers: {stats["expired_session_trackers"]}')
                self.stdout.write(f'  Django sessions cleaned: {stats.get("django_sessions_cleaned", 0)}')
                self.stdout.write(f'  Orphaned sessions cleaned: {stats["orphaned_sessions_cleaned"]}')
                self.stdout.write(f'  Total items cleaned: {stats["total_cleaned"]}')
            else:
                self.stdout.write(f'  Total items cleaned: {stats["total_cleaned"]}')
            
            if stats['total_cleaned'] == 0:
                self.stdout.write(
                    self.style.WARNING('No expired sessions found to clean up.')
                )
        
        except Exception as e:
            raise CommandError(f'Session cleanup failed: {str(e)}')