"""
Phase 9 — Daily Report email.
"""
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone


def build_daily_report_context(user, target_date):
    from tasks.models import Task
    from .models import HabitEntry

    tasks_qs = Task.objects.filter(owner=user, date=target_date, parent__isnull=True).order_by('created_at')
    total_tasks = tasks_qs.count()
    completed_tasks = tasks_qs.filter(completed=True).count()
    task_pct = round(completed_tasks / total_tasks * 100) if total_tasks else 0

    habit_entries = list(
        HabitEntry.objects.filter(habit__owner=user, date=target_date)
        .select_related('habit')
        .order_by('habit__section', 'habit__order')
    )
    total_habits = len(habit_entries)
    completed_habits = sum(1 for e in habit_entries if e.completed)
    habit_pct = round(completed_habits / total_habits * 100) if total_habits else 0

    return {
        'user': user,
        'date': target_date,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'task_pct': task_pct,
        'tasks': list(tasks_qs),
        'total_habits': total_habits,
        'completed_habits': completed_habits,
        'habit_pct': habit_pct,
        'habit_entries': habit_entries,
    }


def send_daily_report_email(user, target_date=None) -> bool:
    """Returns False (without raising) if there's nowhere to send it —
    e.g. no email on file at all — so callers can count skips separately
    from real send failures."""
    from .models import UserSettings

    target_date = target_date or timezone.localdate()
    user_settings = UserSettings.get_for(user)
    to_email = user_settings.report_email()
    if not to_email:
        return False

    context = build_daily_report_context(user, target_date)
    html_body = render_to_string('habits/email/daily_report.html', context)
    text_body = (
        f"Daybook — Daily Summary for {target_date.strftime('%A, %B %d, %Y')}\n\n"
        f"Tasks: {context['completed_tasks']}/{context['total_tasks']} ({context['task_pct']}%)\n"
        f"Habits: {context['completed_habits']}/{context['total_habits']} ({context['habit_pct']}%)\n"
    )

    message = EmailMultiAlternatives(
        subject=f"Your Daybook summary — {target_date.strftime('%b %d, %Y')}",
        body=text_body,
        to=[to_email],
    )
    message.attach_alternative(html_body, 'text/html')
    message.send(fail_silently=False)
    return True
