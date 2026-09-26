"""
Invoked either:
  - by habits/scheduler.py's in-process APScheduler (if DAYBOOK_ENABLE_SCHEDULER=1), or
  - directly by an external cron / Windows Task Scheduler entry every few
    minutes.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from habits.models import UserSettings
from habits.reports import send_daily_report_email


class Command(BaseCommand):
    help = "Send the daily report email to every opted-in user whose configured send time has arrived."

    def add_arguments(self, parser):
        parser.add_argument(
            '--window-minutes', type=int, default=5,
            help='How close (in minutes) the current time must be to a user\'s configured send time to count as "now". '
                 'Should be >= how often this command actually runs, or some users could be skipped entirely.',
        )
        parser.add_argument(
            '--force-user', type=str, default=None,
            help='Send immediately to this username, ignoring both the opt-in flag and the time window — for testing.',
        )

    def handle(self, *args, **options):
        window = options['window_minutes']
        force_username = options['force_user']

        if force_username:
            queryset = UserSettings.objects.filter(owner__username=force_username)
            if not queryset.exists():
                self.stderr.write(self.style.ERROR(f'No user named "{force_username}".'))
                return
        else:
            queryset = UserSettings.objects.filter(daily_report_enabled=True)

        now = timezone.localtime()
        now_minutes = now.hour * 60 + now.minute

        sent, skipped, failed = 0, 0, 0
        for user_settings in queryset:
            if not force_username:
                target_minutes = user_settings.daily_report_time.hour * 60 + user_settings.daily_report_time.minute
                if abs(now_minutes - target_minutes) > window:
                    continue
            try:
                if send_daily_report_email(user_settings.owner):
                    sent += 1
                else:
                    skipped += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f'Failed to email {user_settings.owner}: {exc}'))

        self.stdout.write(self.style.SUCCESS(
            f'Daily reports: {sent} sent, {skipped} skipped (no email on file), {failed} failed.'
        ))
