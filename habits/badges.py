"""
Phase 6 — badge rule engine.
"""
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone


@dataclass(frozen=True)
class BadgeRule:
    key: str
    name: str
    description: str
    icon: str  # must match a key in templates/icons.html


BADGE_RULES = [
    BadgeRule('first_habit', 'Getting Started', 'Create your first habit.', 'plus'),
    BadgeRule('streak_7', '7-Day Streak', 'Complete any habit 7 days in a row.', 'flame'),
    BadgeRule('streak_30', '30-Day Streak', 'Complete any habit 30 days in a row.', 'flame'),
    BadgeRule('streak_100', '100-Day Streak', 'Complete any habit 100 days in a row.', 'flame'),
    BadgeRule('total_50', '50 Completions', 'Log 50 total completed habit check-ins.', 'check-square'),
    BadgeRule('total_250', '250 Completions', 'Log 250 total completed habit check-ins.', 'check-square'),
    BadgeRule('total_1000', '1000 Completions', 'Log 1000 total completed habit check-ins.', 'check-square'),
    BadgeRule('perfect_week', 'Perfect Week', 'Complete every logged habit for 7 days straight.', 'award'),
]

BADGE_RULES_BY_KEY = {r.key: r for r in BADGE_RULES}


def check_and_unlock_badges(user) -> list[BadgeRule]:
    from .analytics import daily_rows_for_range
    from .models import Habit, HabitEntry, UserBadge
    from .services import compute_current_streak

    already = set(UserBadge.objects.filter(owner=user).values_list('key', flat=True))
    newly_unlocked = []

    def unlock(key):
        if key in already:
            return
        UserBadge.objects.get_or_create(owner=user, key=key)
        already.add(key)
        newly_unlocked.append(BADGE_RULES_BY_KEY[key])

    if Habit.objects.filter(owner=user).exists():
        unlock('first_habit')

    best_streak = 0
    for habit in Habit.objects.filter(owner=user, archived=False):
        best_streak = max(best_streak, compute_current_streak(habit, timezone.localdate()))
    if best_streak >= 7:
        unlock('streak_7')
    if best_streak >= 30:
        unlock('streak_30')
    if best_streak >= 100:
        unlock('streak_100')

    total_completed = HabitEntry.objects.filter(habit__owner=user, completed=True).count()
    if total_completed >= 50:
        unlock('total_50')
    if total_completed >= 250:
        unlock('total_250')
    if total_completed >= 1000:
        unlock('total_1000')

    today = timezone.localdate()
    rows = daily_rows_for_range(user, today - timedelta(days=6), today)
    if len(rows) == 7 and all(r['logged'] and r['level'] == 'green' for r in rows):
        unlock('perfect_week')

    return newly_unlocked


def all_badges_status(user) -> list[dict]:
    unlocked_map = {b.key: b.unlocked_at for b in user.badges.all()}
    result = []
    for rule in BADGE_RULES:
        result.append({
            'rule': rule,
            'unlocked': rule.key in unlocked_map,
            'unlocked_at': unlocked_map.get(rule.key),
        })
    return result
