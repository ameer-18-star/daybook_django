"""
Phase 0 — data model foundation for the habit tracker.

Deliberately separate from `tasks` (one-off daily to-dos): a Habit is a
recurring thing you track over time, with its own type, schedule, and
streak/grace-day rules. `HabitEntry` is the daily log against a habit —
the habit-tracker equivalent of a Task, but shaped around "did you do
the thing today" rather than "here's a one-off item."

No views/templates yet — this phase is models + admin + migrations only.
"""
import uuid
from datetime import time as dt_time

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


# ─── shared choice lists ────────────────────────────────────────────────────

HABIT_TYPE_CHOICES = [
    ('yes_no', 'Yes / No'),
    ('numeric', 'Numeric'),
    ('checklist', 'Checklist'),
]

# NOTE: confirm these three section names/behavior before Phase 1 UI work —
# built here on the assumption the original "3 Sections" design still holds.
SECTION_CHOICES = [
    ('have_to_do', 'Have To Do'),
    ('need_to_do', 'Need To Do'),
    ('would_do', 'Would Do'),
]

# 8 accent presets, referenced by Customization (Phase 8) and used as a
# fallback lane color in the Swimlane Timeline (Phase 3) when a habit
# doesn't have its own color set.
ACCENT_COLOR_CHOICES = [
    ('teal', 'Teal'), ('blue', 'Blue'), ('purple', 'Purple'), ('rose', 'Rose'),
    ('amber', 'Amber'), ('green', 'Green'), ('slate', 'Slate'), ('clay', 'Clay'),
]

CARD_THEME_CHOICES = [
    ('classic', 'Classic'),
    ('minimal', 'Minimal'),
    ('bold', 'Bold'),
]


class Habit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='habits')

    text = models.CharField(max_length=140)
    habit_type = models.CharField(max_length=10, choices=HABIT_TYPE_CHOICES, default='yes_no')
    section = models.CharField(max_length=20, choices=SECTION_CHOICES, default='need_to_do')

    # Scheduling — null scheduled_time means "anytime" (explicitly supported,
    # per the requirement to keep unscheduled habits as a first-class option).
    scheduled_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Expected duration in minutes, used for the Swimlane Timeline and total-load stats.',
    )

    # Numeric-type target (e.g. "drink 8 glasses of water"). Ignored for
    # other habit types.
    target_value = models.FloatField(null=True, blank=True)
    target_unit = models.CharField(max_length=30, blank=True, default='')

    # Drag-and-drop ordering, scoped within (owner, section) — Phase 2 will
    # renumber this on reorder.
    order = models.PositiveIntegerField(default=0)

    # Lifecycle
    paused = models.BooleanField(default=False)
    paused_until = models.DateField(
        null=True, blank=True,
        help_text='Optional auto-resume date. Leave blank for an indefinite pause.',
    )
    archived = models.BooleanField(default=False)

    # Streak protection — exact rolling-window semantics ("N per week" vs
    # "N total, ever") to be finalized with streak-calculation logic in a
    # later phase; the field just stores the allowance for now.
    grace_days_allowed = models.PositiveIntegerField(default=0)

    # Swimlane Timeline lane color. Null = derive one deterministically from
    # the habit's id at render time, so every habit still gets a distinct,
    # stable color without forcing a manual choice.
    color = models.CharField(max_length=10, choices=ACCENT_COLOR_CHOICES, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['section', 'order', 'created_at']

    def __str__(self):
        return f'{self.text} ({self.get_habit_type_display()}, {self.get_section_display()})'

    @property
    def is_scheduled(self) -> bool:
        return self.scheduled_time is not None

    @property
    def is_paused_now(self) -> bool:
        if not self.paused:
            return False
        if self.paused_until is None:
            return True
        from django.utils import timezone
        return timezone.localdate() <= self.paused_until


class HabitChecklistItem(models.Model):
    """A sub-item template for a 'checklist' type habit, e.g. a Habit called
    'Morning routine' might have items: Stretch, Meditate, Journal.
    Which items were checked on a given day lives on HabitEntry, not here —
    this table only defines the template, so editing it doesn't rewrite
    history."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name='checklist_items')
    text = models.CharField(max_length=140)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.text} (in {self.habit.text})'


class HabitEntry(models.Model):
    """One day's log against one habit. Meaning of the value fields depends
    on the parent habit's type:
      - yes_no:     `completed` is the only field that matters.
      - numeric:    `numeric_value` holds the logged amount; `completed` is
                    derived (value >= habit.target_value) but stored too,
                    so streak queries don't need a join back to Habit.
      - checklist:  `checked_item_ids` holds which HabitChecklistItem ids
                    were ticked that day; `completed` means all were ticked.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name='entries')
    date = models.DateField()

    completed = models.BooleanField(default=False)
    numeric_value = models.FloatField(null=True, blank=True)
    checked_item_ids = models.JSONField(default=list, blank=True)

    used_grace_day = models.BooleanField(default=False)

    # Timestamp of completion (distinct from `date`, which is the habit's
    # logical day) — feeds Time of Day Analysis in Phase 4.
    completed_at = models.DateTimeField(null=True, blank=True)

    note = models.TextField(max_length=1000, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        unique_together = [('habit', 'date')]

    def __str__(self):
        status = '\u2713' if self.completed else '\u25cb'
        return f'[{status}] {self.habit.text} \u2014 {self.date}'


class UserSettings(models.Model):
    """One row per user. Backs Customization (Phase 8) and the Daily Report
    email (Phase 9). Created lazily via get_for(); no signal-based
    auto-creation, to keep this phase migration-only with no side effects."""
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='habit_settings')

    accent_color = models.CharField(max_length=10, choices=ACCENT_COLOR_CHOICES, default='teal')
    card_theme = models.CharField(max_length=10, choices=CARD_THEME_CHOICES, default='classic')
    compact_mode = models.BooleanField(default=False)
    dark_mode = models.BooleanField(
        default=False,
        help_text='Server-side mirror of the theme, for contexts without JS (e.g. the daily report email). '
                   'The in-app toggle is still the client-side localStorage switch already in use.',
    )

    timeline_start_hour = models.PositiveSmallIntegerField(
        default=6, validators=[MinValueValidator(0), MaxValueValidator(23)],
    )
    timeline_end_hour = models.PositiveSmallIntegerField(
        default=22, validators=[MinValueValidator(1), MaxValueValidator(24)],
    )

    daily_report_enabled = models.BooleanField(default=False)
    daily_report_time = models.TimeField(default=dt_time(7, 0))
    daily_report_email = models.EmailField(
        blank=True, default='',
        help_text="Leave blank to use the account's login email.",
    )

    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User settings'
        verbose_name_plural = 'User settings'

    def __str__(self):
        return f'Settings for {self.owner}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.avatar:
            self._resize_avatar_if_needed()

    def _resize_avatar_if_needed(self, max_size=(256, 256)):
        """Downscale a freshly uploaded avatar in place. Wrapped in a broad
        except: a corrupt or unreadable file here should never take down
        the whole save() — worst case, the original upload is kept at
        whatever size it came in."""
        try:
            from PIL import Image
            img = Image.open(self.avatar.path)
            if img.height > max_size[1] or img.width > max_size[0]:
                img.thumbnail(max_size, Image.LANCZOS)
                img.save(self.avatar.path)
        except Exception:
            pass

    @classmethod
    def get_for(cls, user):
        obj, _ = cls.objects.get_or_create(owner=user)
        return obj

    def report_email(self) -> str:
        return self.daily_report_email or self.owner.email

# ─── Phase 5: Productivity Suite ────────────────────────────────────────────

class JournalEntry(models.Model):
    MOOD_CHOICES = [
        ('great', 'Great'),
        ('good', 'Good'),
        ('neutral', 'Neutral'),
        ('low', 'Low'),
        ('rough', 'Rough'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='journal_entries')
    date = models.DateField()
    mood = models.CharField(max_length=10, choices=MOOD_CHOICES, blank=True, default='')
    text = models.TextField(max_length=8000, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        unique_together = [('owner', 'date')]  # one entry per day, matches the "daily" framing

    def __str__(self):
        return f'{self.owner} \u2014 {self.date}'


class WeeklyReview(models.Model):
    """One per (owner, ISO week). The wizard walks through each habit in
    order; `completed_at` is set once every habit in the week has a rating."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='weekly_reviews')
    week_start = models.DateField()  # Monday of the ISO week
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-week_start']
        unique_together = [('owner', 'week_start')]

    def __str__(self):
        return f'{self.owner} \u2014 week of {self.week_start}'


class HabitReviewRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(WeeklyReview, on_delete=models.CASCADE, related_name='ratings')
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name='review_ratings')
    effort_rating = models.PositiveSmallIntegerField()  # 1-5, validated in the view
    note = models.TextField(max_length=1000, blank=True, default='')

    class Meta:
        unique_together = [('review', 'habit')]

    def __str__(self):
        return f'{self.habit.text}: {self.effort_rating}/5'


# ─── Phase 6: Gamification ──────────────────────────────────────────────────

class UserBadge(models.Model):
    """Which badges a user has unlocked. The badge *definitions* (name,
    description, unlock criteria) live in code (habits/badges.py) rather
    than the database, since they're fixed by the app rather than
    user-editable — this table just records the unlock events."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='badges')
    key = models.CharField(max_length=40)
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('owner', 'key')]
        ordering = ['-unlocked_at']

    def __str__(self):
        return f'{self.owner}: {self.key}'
