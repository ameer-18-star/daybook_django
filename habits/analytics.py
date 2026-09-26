"""
Phase 4 — statistics & analytics.

Mirrors the shape of reports/analytics.py (the Daybook task reports),
adapted to habits: entries are per-habit-per-day rather than per-task,
and there's a per-habit dimension (report card, streak calendar) that
the task reports never needed.

Kept self-contained from the `reports` app on purpose — habits
shouldn't have to depend on tasks/reports internals, even though the
underlying problem (build a day-by-day heatmap, aggregate a date
range) is the same shape.
"""
import calendar
from collections import OrderedDict
from datetime import date, timedelta

from django.utils import timezone

from .models import SECTION_CHOICES
from .services import compute_current_streak


# ─── pure logic (no DB access) — unit-testable in isolation ────────────────

GREEN_THRESHOLD = 100
YELLOW_THRESHOLD = 75

# Report Card rubric — rolling 30-day completion rate. Deliberately just a
# lookup table so the cutoffs are trivial to change later without touching
# any calling code.
GRADE_CUTOFFS = [
    (90, 'A'),
    (75, 'B'),
    (60, 'C'),
    (40, 'D'),
]


def heat_level(pct, logged: bool) -> str:
    if not logged:
        return 'none'
    if pct >= GREEN_THRESHOLD:
        return 'green'
    if pct >= YELLOW_THRESHOLD:
        return 'yellow'
    return 'red'


def letter_grade(pct) -> str:
    for cutoff, grade in GRADE_CUTOFFS:
        if pct >= cutoff:
            return grade
    return 'F'


def date_span(start: date, end: date) -> list[date]:
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def build_calendar_weeks(daily_rows: list[dict], start: date):
    """Pad daily_rows into full Mon-Sun weeks for a GitHub-style grid.
    Leading/trailing cells outside the range are None (rendered blank)."""
    if not daily_rows:
        return []
    rows_by_date = {row['date']: row for row in daily_rows}
    grid_start = start - timedelta(days=start.isoweekday() - 1)
    end = daily_rows[-1]['date']
    grid_end = end + timedelta(days=7 - end.isoweekday())

    weeks, week = [], []
    for d in date_span(grid_start, grid_end):
        week.append(rows_by_date.get(d))
        if len(week) == 7:
            weeks.append(week)
            week = []
    return weeks


def bucket_for_hour(hour: int) -> str:
    if 5 <= hour < 12:
        return 'morning'
    if 12 <= hour < 17:
        return 'afternoon'
    if 17 <= hour < 21:
        return 'evening'
    return 'night'


# ─── DB-backed aggregation ──────────────────────────────────────────────────

def daily_rows_for_range(user, start: date, end: date, habit=None) -> list[dict]:
    """One row per day in [start, end]. With habit=None, aggregates across
    every habit the user owns (used by the Overview heatmap); with a
    specific habit, describes just that habit's history (used by the
    per-habit streak calendar) — in that case each row also carries a
    'grace' level distinct from 'red', since a grace day isn't a miss."""
    from .models import HabitEntry  # local import avoids a circular import at module load

    qs = HabitEntry.objects.filter(habit__owner=user, date__gte=start, date__lte=end)
    if habit is not None:
        qs = qs.filter(habit=habit)

    entries_by_date = {}
    for e in qs:
        entries_by_date.setdefault(e.date, []).append(e)

    rows = []
    for d in date_span(start, end):
        day_entries = entries_by_date.get(d)
        if not day_entries:
            rows.append({
                'date': d, 'logged': False, 'total': 0, 'completed': 0,
                'pct': None, 'level': 'none', 'used_grace': False,
            })
            continue

        total = len(day_entries)
        completed = sum(1 for e in day_entries if e.completed)
        used_grace = any(e.used_grace_day for e in day_entries)
        pct = round(completed / total * 100) if total else 0
        level = heat_level(pct, True)

        if habit is not None and not day_entries[0].completed and day_entries[0].used_grace_day:
            level = 'grace'

        rows.append({
            'date': d, 'logged': True, 'total': total, 'completed': completed,
            'pct': pct, 'level': level, 'used_grace': used_grace,
        })
    return rows


def build_year_heatmap(user, year: int) -> dict:
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    daily_rows = daily_rows_for_range(user, start, end)
    return {
        'weeks': build_calendar_weeks(daily_rows, start),
        'year': year,
        'total_logged_days': sum(1 for r in daily_rows if r['logged']),
        'total_perfect_days': sum(1 for r in daily_rows if r['level'] == 'green'),
    }


def time_of_day_buckets(user, start: date, end: date) -> "OrderedDict[str, int]":
    from .models import HabitEntry

    buckets = OrderedDict([('morning', 0), ('afternoon', 0), ('evening', 0), ('night', 0)])
    qs = HabitEntry.objects.filter(
        habit__owner=user, date__gte=start, date__lte=end,
        completed=True, completed_at__isnull=False,
    )
    for e in qs:
        hour = timezone.localtime(e.completed_at).hour
        buckets[bucket_for_hour(hour)] += 1
    return buckets


def overview_stats(user, start: date, end: date) -> dict:
    from .models import HabitEntry

    qs = HabitEntry.objects.filter(habit__owner=user, date__gte=start, date__lte=end).select_related('habit')
    total_entries = qs.count()
    total_completed = qs.filter(completed=True).count()
    completion_pct = round(total_completed / total_entries * 100) if total_entries else 0

    section_counts = {}   # section_key -> [total, completed]
    habit_counts = {}     # habit_id -> [habit, total, completed]
    for e in qs:
        s_total, s_completed = section_counts.setdefault(e.habit.section, [0, 0])
        section_counts[e.habit.section][0] = s_total + 1
        if e.completed:
            section_counts[e.habit.section][1] = s_completed + 1

        if e.habit_id not in habit_counts:
            habit_counts[e.habit_id] = [e.habit, 0, 0]
        habit_counts[e.habit_id][1] += 1
        if e.completed:
            habit_counts[e.habit_id][2] += 1

    section_breakdown = []
    for key, label in SECTION_CHOICES:
        total, completed = section_counts.get(key, [0, 0])
        pct = round(completed / total * 100) if total else 0
        section_breakdown.append({'key': key, 'label': label, 'total': total, 'completed': completed, 'pct': pct})

    today = timezone.localdate()
    top_habits = []
    for habit, total, completed in habit_counts.values():
        pct = round(completed / total * 100) if total else 0
        top_habits.append({
            'habit': habit, 'total': total, 'completed': completed, 'pct': pct,
            'streak': compute_current_streak(habit, today),
            'grade': letter_grade(pct),
        })
    top_habits.sort(key=lambda h: h['completed'], reverse=True)

    return {
        'total_entries': total_entries,
        'total_completed': total_completed,
        'completion_pct': completion_pct,
        'daily_rows': daily_rows_for_range(user, start, end),
        'section_breakdown': section_breakdown,
        'top_habits': top_habits[:8],
        'time_of_day': time_of_day_buckets(user, start, end),
    }


def report_card(habit, window_days: int = 30) -> dict:
    """Rolling window ending today — deliberately independent of whatever
    custom date range the page is showing, since a report card answers
    'how am I doing right now', not 'how did I do in this arbitrary past
    window'."""
    today = timezone.localdate()
    start = today - timedelta(days=window_days - 1)
    rows = daily_rows_for_range(habit.owner, start, today, habit=habit)
    logged = sum(1 for r in rows if r['logged'])
    completed = sum(r['completed'] for r in rows if r['logged'])
    pct = round(completed / logged * 100) if logged else 0
    return {'pct': pct, 'grade': letter_grade(pct), 'window_days': window_days, 'logged_days': logged}


def habit_period_summary(habit) -> dict:
    """Weekly / monthly / yearly completion numbers, each period's own
    calendar boundary (ISO week, calendar month, calendar year) rather
    than a rolling window — matches how the Daybook task reports already
    define 'this week' / 'this month'."""
    today = timezone.localdate()
    week_start = today - timedelta(days=today.isoweekday() - 1)
    week_end = week_start + timedelta(days=6)
    month_start = today.replace(day=1)
    month_end = month_start.replace(day=calendar.monthrange(today.year, today.month)[1])
    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)

    def summarize(start, end):
        clamped_end = min(end, today)
        if clamped_end < start:
            return {'total': 0, 'completed': 0, 'pct': 0}
        rows = daily_rows_for_range(habit.owner, start, clamped_end, habit=habit)
        logged = sum(1 for r in rows if r['logged'])
        completed = sum(r['completed'] for r in rows if r['logged'])
        pct = round(completed / logged * 100) if logged else 0
        return {'total': logged, 'completed': completed, 'pct': pct}

    return {
        'week': summarize(week_start, week_end),
        'month': summarize(month_start, month_end),
        'year': summarize(year_start, year_end),
    }


def longest_streak_ever(habit) -> int:
    """Full-history scan (not just the current streak) — a gap day with no
    entry at all breaks the streak here, unlike compute_current_streak's
    'today not logged yet doesn't count against you' leniency, since this
    is describing the past rather than an in-progress streak."""
    entries_by_date = {e.date: e for e in habit.entries.all()}
    if not entries_by_date:
        return 0

    start = min(entries_by_date.keys())
    end = max(timezone.localdate(), max(entries_by_date.keys()))

    longest = current = 0
    d = start
    while d <= end:
        entry = entries_by_date.get(d)
        if entry and (entry.completed or entry.used_grace_day):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
        d += timedelta(days=1)
    return longest


def habit_stats(habit, start: date, end: date) -> dict:
    daily_rows = daily_rows_for_range(habit.owner, start, end, habit=habit)
    logged = sum(1 for r in daily_rows if r['logged'])
    completed = sum(r['completed'] for r in daily_rows if r['logged'])
    pct = round(completed / logged * 100) if logged else 0

    return {
        'daily_rows': daily_rows,
        'calendar_weeks': build_calendar_weeks(daily_rows, start),
        'logged_days': logged,
        'completed_days': completed,
        'pct': pct,
        'report_card': report_card(habit),
        'period_summary': habit_period_summary(habit),
        'longest_streak': longest_streak_ever(habit),
        'current_streak': compute_current_streak(habit, timezone.localdate()),
    }
