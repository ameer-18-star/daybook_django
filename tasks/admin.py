from django.contrib import admin
from .models import Streak, Tag, Task, TaskTemplate


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['text', 'owner', 'date', 'category', 'priority', 'completed', 'parent']
    list_filter = ['date', 'category', 'priority', 'completed', 'owner']
    search_fields = ['text', 'owner__username']
    date_hierarchy = 'date'
    ordering = ['-date', 'created_at']


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'color']
    list_filter = ['owner', 'color']


@admin.register(TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    list_display = ['text', 'owner', 'recurrence_type', 'active']
    list_filter = ['owner', 'recurrence_type', 'active']


@admin.register(Streak)
class StreakAdmin(admin.ModelAdmin):
    list_display = ['owner', 'current', 'last_completion_date']
