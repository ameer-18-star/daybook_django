from django.contrib import admin
from .models import (
    Habit, HabitChecklistItem, HabitEntry, HabitReviewRating,
    JournalEntry, UserBadge, UserSettings, WeeklyReview,
)

class HabitChecklistItemInline(admin.TabularInline):
    model = HabitChecklistItem
    extra = 1


@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = [
        'text', 'owner', 'habit_type', 'section', 'scheduled_time',
        'paused', 'archived', 'order',
    ]
    list_filter = ['owner', 'habit_type', 'section', 'paused', 'archived']
    search_fields = ['text', 'owner__username']
    ordering = ['owner', 'section', 'order']
    inlines = [HabitChecklistItemInline]


@admin.register(HabitEntry)
class HabitEntryAdmin(admin.ModelAdmin):
    list_display = ['habit', 'date', 'completed', 'numeric_value', 'used_grace_day', 'completed_at']
    list_filter = ['date', 'completed', 'used_grace_day', 'habit__owner']
    search_fields = ['habit__text']
    date_hierarchy = 'date'


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'owner', 'accent_color', 'card_theme', 'compact_mode', 'dark_mode',
        'daily_report_enabled', 'daily_report_time',
    ]
    list_filter = ['accent_color', 'card_theme', 'compact_mode', 'daily_report_enabled']

@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['owner', 'date', 'mood']
    list_filter = ['mood', 'owner']
    search_fields = ['text', 'owner__username']
    date_hierarchy = 'date'


class HabitReviewRatingInline(admin.TabularInline):
    model = HabitReviewRating
    extra = 0


@admin.register(WeeklyReview)
class WeeklyReviewAdmin(admin.ModelAdmin):
    list_display = ['owner', 'week_start', 'completed_at']
    list_filter = ['owner']
    inlines = [HabitReviewRatingInline]


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ['owner', 'key', 'unlocked_at']
    list_filter = ['key', 'owner']
