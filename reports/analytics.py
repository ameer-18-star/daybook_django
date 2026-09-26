"""
Analytics engine — Django port of reporter.py.
Works directly with the Task ORM instead of flat JSON files.
"""
import calendar
from collections import Counter
from datetime import date, timedelta

from tasks.models import Task

# Heat-level thresholds for the calendar grid.
#   < 75%  -> red
#   75-99% -> yellow
#   100%   -> green
#   no log -> none (empty/gray)
GREEN_THRESHOLD = 100
YELLOW_THRESHOLD = 75


def heat_level(pct, logged: bool) -> str:
    if not logged:
        return 'none'
    if pct >= GREEN_THRESHOLD:
        return 'green'
    if pct >= YELLOW_THRESHOLD:
        return 'yellow'
    return 'red'


def iso_week_range(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.isoweekday() - 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def month_range(today: date) -> tuple[date, date]:
    first = today.replace(day=1)
    last_day_num = calendar.monthrange(today.year, today.month)[1]
    last = today.replace(day=last_day_num)
    return first, last


def date_span(start: date, end: date) -> list[date]:
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def build_calendar_weeks(daily_rows: list[dict], start: date):
    """Pad daily_rows into full Mon-Sun weeks for a GitHub-style grid.
    Leading/trailing cells outside the range are None (rendered blank)."""
    rows_by_date = {row['date']: row for row in daily_rows}
    if not daily_rows:
        return []

    grid_start = start - timedelta(days=start.isoweekday() - 1)  # back to Monday
    end = daily_rows[-1]['date']
    grid_end = end + timedelta(days=7 - end.isoweekday())  # forward to Sunday

    all_days = date_span(grid_start, grid_end)
    weeks = []
    week = []
    for d in all_days:
        week.append(rows_by_date.get(d))  # None if outside actual range
        if len(week) == 7:
            weeks.append(week)
            week = []
    return weeks


def aggregate(start: date, end: date, today: date, user) -> dict:
    """Compute all report metrics for [start, end] window, scoped to one user."""
    full_span = date_span(start, end)
    elapsed_span = [d for d in full_span if d <= today]

    tasks_qs = Task.objects.filter(owner=user, date__gte=start, date__lte=end, parent__isnull=True)
    tasks_by_date = {}
    for task in tasks_qs:
        tasks_by_date.setdefault(task.date, []).append(task)

    total_tasks = 0
    total_completed = 0
    category_counter = Counter()
    priority_counter = Counter()
    most_productive_day = None
    best_day = None    # highest completion % among logged days
    worst_day = None   # lowest completion % among logged days
    daily_rows = []
    active_days = []
    green_days = yellow_days = red_days = 0
    logged_pct_sum = 0
    current_green_streak = 0
    longest_green_streak = 0

    for d in full_span:
        day_tasks = tasks_by_date.get(d, None)
        if day_tasks is None:
            daily_rows.append({
                'date': d, 'logged': False, 'total': 0,
                'completed': 0, 'pct': None, 'level': 'none',
            })
            current_green_streak = 0
            continue

        active_days.append(d)
        completed_tasks = [t for t in day_tasks if t.completed]
        day_total = len(day_tasks)
        day_completed = len(completed_tasks)

        total_tasks += day_total
        total_completed += day_completed

        for t in completed_tasks:
            category_counter[t.category] += 1
            priority_counter[t.priority] += 1

        if most_productive_day is None or day_completed > most_productive_day[1]:
            most_productive_day = (d, day_completed)

        pct = round((day_completed / day_total) * 100) if day_total else 0
        level = heat_level(pct, True)

        if level == 'green':
            green_days += 1
            current_green_streak += 1
            longest_green_streak = max(longest_green_streak, current_green_streak)
        else:
            current_green_streak = 0
            if level == 'yellow':
                yellow_days += 1
            elif level == 'red':
                red_days += 1

        logged_pct_sum += pct
        if best_day is None or pct > best_day[1]:
            best_day = (d, pct)
        if worst_day is None or pct < worst_day[1]:
            worst_day = (d, pct)

        daily_rows.append({
            'date': d, 'logged': True, 'total': day_total,
            'completed': day_completed, 'pct': pct, 'level': level,
        })

    missed_days = [d for d in elapsed_span if d not in active_days]
    completion_pct = round((total_completed / total_tasks) * 100) if total_tasks else 0
    avg_daily_pct = round(logged_pct_sum / len(active_days)) if active_days else 0

    return {
        'start': start,
        'end': end,
        'total_tasks': total_tasks,
        'total_completed': total_completed,
        'completion_pct': completion_pct,
        'avg_daily_pct': avg_daily_pct,
        'most_productive_day': most_productive_day,
        'best_day': best_day,
        'worst_day': worst_day,
        'category_breakdown': category_counter.most_common(),
        'category_max': max(category_counter.values()) if category_counter else 1,
        'priority_breakdown': priority_counter.most_common(),
        'active_days': active_days,
        'missed_days': missed_days,
        'elapsed_days_count': len(elapsed_span),
        'daily_rows': daily_rows,
        'calendar_weeks': build_calendar_weeks(daily_rows, start),
        'green_days': green_days,
        'yellow_days': yellow_days,
        'red_days': red_days,
        'none_days': len(full_span) - len(active_days),
        'longest_green_streak': longest_green_streak,
    }
