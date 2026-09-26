from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),

    # Auth
    path('accounts/register/', views.register, name='register'),
    path('accounts/login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        redirect_authenticated_user=True,
    ), name='login'),

    # Recurring task templates
    path('recurring-tasks/', views.habits, name='recurring_tasks'),
    path('recurring-tasks/<uuid:template_id>/toggle/', views.habit_toggle_active, name='recurring_task_toggle_active'),
    path('recurring-tasks/<uuid:template_id>/delete/', views.habit_delete, name='recurring_task_delete'),

    # Task CRUD (JSON API)
    path('api/tasks/create/', views.task_create, name='task_create'),
    path('api/tasks/<uuid:task_id>/toggle/', views.task_toggle, name='task_toggle'),
    path('api/tasks/<uuid:task_id>/edit/', views.task_edit, name='task_edit'),
    path('api/tasks/<uuid:task_id>/delete/', views.task_delete, name='task_delete'),
    path('api/tasks/clear-completed/', views.tasks_clear_completed, name='tasks_clear_completed'),

    # Subtasks (JSON API)
    path('api/tasks/<uuid:task_id>/subtasks/create/', views.subtask_create, name='subtask_create'),
    path('api/subtasks/<uuid:task_id>/toggle/', views.subtask_toggle, name='subtask_toggle'),
    path('api/subtasks/<uuid:task_id>/delete/', views.subtask_delete, name='subtask_delete'),

    # Export / Import
    path('export/json/', views.export_json, name='export_json'),
    path('export/txt/', views.export_txt, name='export_txt'),
    path('import/json/', views.import_json, name='import_json'),

    # Weekly Planner — forward planning for the week ahead
    path('planner/', views.weekly_planner, name='weekly_planner'),
    path('planner/add/', views.weekly_planner_add_task, name='weekly_planner_add_task'),
    path('planner/<uuid:task_id>/toggle/', views.weekly_planner_toggle_task, name='weekly_planner_toggle_task'),
    path('planner/<uuid:task_id>/delete/', views.weekly_planner_delete_task, name='weekly_planner_delete_task'),

    path('accounts/logout/', views.logout_view, name='logout'),
]