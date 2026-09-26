from django.urls import path
from . import views

urlpatterns = [
    path('', views.habit_list, name='habit_list'),
    path('new/', views.habit_create, name='habit_create'),
    path('<uuid:habit_id>/edit/', views.habit_edit, name='habit_edit'),
    path('<uuid:habit_id>/delete/', views.habit_delete, name='habit_delete'),
    path('<uuid:habit_id>/archive-toggle/', views.habit_archive_toggle, name='habit_archive_toggle'),
    path('<uuid:habit_id>/pause-toggle/', views.habit_pause_toggle, name='habit_pause_toggle'),

    # Daily interaction (JSON API)
    path('api/<uuid:habit_id>/toggle-yesno/', views.habit_toggle_yes_no, name='habit_toggle_yes_no'),
    path('api/<uuid:habit_id>/log-numeric/', views.habit_log_numeric, name='habit_log_numeric'),
    path('api/<uuid:habit_id>/checklist-toggle/', views.habit_checklist_toggle, name='habit_checklist_toggle'),
    path('api/<uuid:habit_id>/grace-day/', views.habit_use_grace_day, name='habit_use_grace_day'),
    path('api/reorder/', views.habit_reorder, name='habit_reorder'),
    path('api/bulk-action/', views.habit_bulk_action, name='habit_bulk_action'),

    path('settings/compact-toggle/', views.toggle_compact_mode, name='toggle_compact_mode'),

    # Phase 3: Swimlane Timeline
    path('timeline/', views.habit_timeline, name='habit_timeline'),
    path('timeline/hours/', views.update_timeline_hours, name='update_timeline_hours'),

    # Phase 4: Statistics & Analytics
    path('stats/', views.stats_overview, name='stats_overview'),
    path('stats/<uuid:habit_id>/', views.habit_stats_detail, name='habit_stats_detail'),
    path('export/json/', views.habit_export_json, name='habit_export_json'),

    # Phase 5: Productivity Suite
    path('calendar/', views.yearly_calendar, name='yearly_calendar'),
    path('calendar/<int:year>/<int:month>/<int:day>/', views.day_detail, name='day_detail'),
    path('journal/', views.journal_list, name='journal_list'),
    path('journal/<int:year>/<int:month>/<int:day>/', views.journal_entry, name='journal_entry'),
    path('review/', views.weekly_review, name='weekly_review'),
    path('review/summary/', views.weekly_review_summary, name='weekly_review_summary'),
    path('review/restart/', views.weekly_review_restart, name='weekly_review_restart'),

    # Phase 6: Gamification
    path('badges/', views.badges_page, name='badges_page'),

    # Phase 7: Profile, Backup & Restore
    path('profile/', views.profile_view, name='profile'),
    path('backup/', views.backup_restore_view, name='backup_restore'),
    path('import/json/', views.habit_import_json, name='habit_import_json'),
]
