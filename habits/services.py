"""
Streak calculation — deliberately its own module since both the Phase 1
habit list (to show a current-streak badge) and the Phase 4 stats pages
(streak calendar, report card, badges) need the same definition of
"what counts as an unbroken streak."

Definition used here: walking backwards from a reference date, a day
counts toward the streak if it has an entry that is either `completed`
or `used_grace_day`. A day with no entry yet (including "today", before
you've logged anything) does not break the streak — it simply isn't
counted yet. The first day that was logged but NOT completed (and did
not use a grace day) ends the streak.
"""
from datetime import timedelta


def compute_current_streak(habit, upto_date, lookback_days: int = 400) -> int:
    entries = {
        e.date: e
        for e in habit.entries.filter(date__lte=upto_date, date__gte=upto_date - timedelta(days=lookback_days))
    }

    day = upto_date
    if day not in entries:
        # Today (or the reference date) hasn't been logged yet — don't let
        # an unlogged "today" break an otherwise-live streak.
        day -= timedelta(days=1)

    streak = 0
    while True:
        entry = entries.get(day)
        if entry and (entry.completed or entry.used_grace_day):
            streak += 1
            day -= timedelta(days=1)
        else:
            break
    return streak


def grace_days_used(habit) -> int:
    return habit.entries.filter(used_grace_day=True).count()


def grace_days_remaining(habit) -> int:
    return max(0, habit.grace_days_allowed - grace_days_used(habit))


def build_today_sections(user, target_date):
    """Build the same {section_key: {'label':..., 'habits': [...]}} shape
    used by both the full Habits page and the compact "Today's Habits"
    section embedded in the Daybook Tasks page — one source of truth so
    the two views can never quietly drift apart from each other."""
    from collections import OrderedDict

    from .models import Habit, HabitEntry, SECTION_CHOICES

    habits_qs = (
        Habit.objects.filter(owner=user, archived=False)
        .prefetch_related('checklist_items')
        .order_by('section', 'order', 'created_at')
    )
    entries_for_date = {
        e.habit_id: e for e in HabitEntry.objects.filter(habit__owner=user, date=target_date)
    }

    sections = OrderedDict()
    for key, label in SECTION_CHOICES:
        sections[key] = {'label': label, 'habits': []}

    for habit in habits_qs:
        entry = entries_for_date.get(habit.id)
        checklist_items = list(habit.checklist_items.all()) if habit.habit_type == 'checklist' else []
        checked_ids = set(entry.checked_item_ids) if entry else set()

        sections[habit.section]['habits'].append({
            'habit': habit,
            'entry': entry,
            'streak': compute_current_streak(habit, target_date),
            'grace_remaining': grace_days_remaining(habit),
            'checklist_items': checklist_items,
            'checklist_progress': f'{len(checked_ids)}/{len(checklist_items)}' if checklist_items else '',
            'checked_ids': [str(i) for i in checked_ids],
        })
    return sections
