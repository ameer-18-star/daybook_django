import json
import uuid
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .forms import RegisterForm, TaskTemplateForm
from .models import Streak, Tag, Task, TaskTemplate


# ─── helpers ────────────────────────────────────────────────────────────────

def _today():
    return timezone.localdate()


def _yesterday():
    return _today() - timedelta(days=1)


def _task_stats(tasks_qs):
    tasks = list(tasks_qs)
    total = len(tasks)
    completed = sum(1 for t in tasks if t.completed)
    pending = total - completed
    high_pending = sum(1 for t in tasks if not t.completed and t.priority == 'High')
    pct = round((completed / total) * 100) if total else 0
    return {
        'total': total,
        'completed': completed,
        'pending': pending,
        'high_priority_remaining': high_pending,
        'completion_rate': pct,
    }


def _update_streak(user, completed_a_task: bool):
    streak = Streak.get_for(user)
    today = _today()

    if not completed_a_task:
        still_any_completed = Task.objects.filter(owner=user, date=today, completed=True).exists()
        if not still_any_completed and streak.last_completion_date == today:
            if streak.current > 0:
                streak.current -= 1
            streak.last_completion_date = _yesterday() if streak.current > 0 else None
            streak.save()
        return streak

    if streak.last_completion_date == today:
        return streak

    if streak.last_completion_date == _yesterday():
        streak.current += 1
    else:
        streak.current = 1

    streak.last_completion_date = today
    streak.save()
    return streak


def _reconcile_streak(user):
    streak = Streak.get_for(user)
    today = _today()
    if (streak.last_completion_date
            and streak.last_completion_date != today
            and streak.last_completion_date != _yesterday()):
        streak.current = 0
        streak.save()
    return streak


def _generate_recurring_tasks(user, target_date):
    """Materialize today's habit-template tasks, idempotently."""
    templates = TaskTemplate.objects.filter(owner=user, active=True)
    for tpl in templates:
        if not tpl.occurs_on(target_date):
            continue
        already = Task.objects.filter(owner=user, template=tpl, date=target_date).exists()
        if not already:
            Task.objects.create(
                owner=user, text=tpl.text, category=tpl.category,
                priority=tpl.priority, date=target_date, template=tpl,
            )


# ─── pages ──────────────────────────────────────────────────────────────────

def register(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect('index')
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})


def logout_view(request):
    """Custom view (instead of the built-in LogoutView) purely to flash a
    confirmation message on the way back to the login page — the sign-out
    itself is the same auth_logout() the built-in view uses."""
    auth_logout(request)
    messages.info(request, "You've been signed out.")
    return redirect('login')


@login_required
def index(request):
    today = _today()
    streak = _reconcile_streak(request.user)

    view_date_str = request.GET.get('date', today.isoformat())
    view_date = parse_date(view_date_str) or today
    is_today = (view_date == today)

    if is_today:
        _generate_recurring_tasks(request.user, today)

    tasks_qs = Task.objects.filter(owner=request.user, date=view_date, parent__isnull=True)

    query = request.GET.get('q', '').strip()
    if query:
        tasks_qs = tasks_qs.filter(text__icontains=query)

    tag_filter = request.GET.get('tag', '').strip()
    if tag_filter:
        tasks_qs = tasks_qs.filter(tags__name=tag_filter)

    tasks_qs = tasks_qs.prefetch_related('tags', 'subtasks').distinct()

    all_day_tasks = Task.objects.filter(owner=request.user, date=view_date, parent__isnull=True)
    stats = _task_stats(all_day_tasks)
    user_tags = Tag.objects.filter(owner=request.user)

    habit_sections = None
    if is_today:
        from habits.services import build_today_sections
        habit_sections = build_today_sections(request.user, today)

    return render(request, 'tasks/index.html', {
        'today': today,
        'view_date': view_date,
        'view_date_str': view_date.isoformat(),
        'tomorrow_date_str': (today + timedelta(days=1)).isoformat(),
        'is_today': is_today,
        'tasks': tasks_qs,
        'stats': stats,
        'streak': streak.current,
        'habit_sections': habit_sections,
        'categories': Task.CATEGORY_CHOICES,
        'priorities': Task.PRIORITY_CHOICES,
        'user_tags': user_tags,
        'search_query': query,
        'active_tag': tag_filter,
    })


@login_required
def habits(request):
    if request.method == 'POST':
        form = TaskTemplateForm(request.POST)
        if form.is_valid():
            tpl = form.save(commit=False)
            tpl.owner = request.user
            tpl.save()
            return redirect('recurring_tasks')
    else:
        form = TaskTemplateForm()

    templates = TaskTemplate.objects.filter(owner=request.user)
    return render(request, 'tasks/habits.html', {
        'form': form,
        'templates': templates,
    })


@login_required
@require_http_methods(["POST"])
def habit_toggle_active(request, template_id):
    tpl = get_object_or_404(TaskTemplate, pk=template_id, owner=request.user)
    tpl.active = not tpl.active
    tpl.save()
    return redirect('recurring_tasks')


@login_required
@require_http_methods(["POST"])
def habit_delete(request, template_id):
    tpl = get_object_or_404(TaskTemplate, pk=template_id, owner=request.user)
    tpl.delete()
    return redirect('recurring_tasks')


# ─── task CRUD (JSON API) ────────────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def task_create(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    task_date = parse_date(data.get('date', '')) or _today()
    due_time = parse_time(data['due_time']) if data.get('due_time') else None

    task = Task.objects.create(
        owner=request.user,
        text=data.get('text', '').strip()[:140],
        category=data.get('category', 'Work'),
        priority=data.get('priority', 'Medium'),
        date=task_date,
        due_time=due_time,
        notes=data.get('notes', '').strip()[:2000],
    )

    tag_names = [t.strip() for t in data.get('tags', []) if t.strip()]
    for name in tag_names:
        tag, _ = Tag.objects.get_or_create(owner=request.user, name=name[:30])
        task.tags.add(tag)

    tasks = Task.objects.filter(owner=request.user, date=task_date, parent__isnull=True)
    return JsonResponse({'task': task.to_dict(), 'stats': _task_stats(tasks)})


@login_required
@require_http_methods(["POST"])
def task_toggle(request, task_id):
    task = get_object_or_404(Task, pk=task_id, owner=request.user)
    task.completed = not task.completed
    task.save()

    if task.date == _today() and task.parent_id is None:
        streak = _update_streak(request.user, task.completed)
        streak_count = streak.current
    else:
        streak_count = Streak.get_for(request.user).current

    tasks = Task.objects.filter(owner=request.user, date=task.date, parent__isnull=True)
    return JsonResponse({
        'task': task.to_dict(),
        'stats': _task_stats(tasks),
        'streak': streak_count,
    })


@login_required
@require_http_methods(["POST"])
def task_edit(request, task_id):
    task = get_object_or_404(Task, pk=task_id, owner=request.user)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    task.text = data.get('text', task.text).strip()[:140]
    task.category = data.get('category', task.category)
    task.priority = data.get('priority', task.priority)
    task.notes = data.get('notes', task.notes).strip()[:2000]
    if 'due_time' in data:
        task.due_time = parse_time(data['due_time']) if data['due_time'] else None
    task.save()

    if 'tags' in data:
        task.tags.clear()
        for name in [t.strip() for t in data['tags'] if t.strip()]:
            tag, _ = Tag.objects.get_or_create(owner=request.user, name=name[:30])
            task.tags.add(tag)

    tasks = Task.objects.filter(owner=request.user, date=task.date, parent__isnull=True)
    return JsonResponse({'task': task.to_dict(), 'stats': _task_stats(tasks)})


@login_required
@require_http_methods(["POST"])
def task_delete(request, task_id):
    task = get_object_or_404(Task, pk=task_id, owner=request.user)
    task_date = task.date
    task.delete()
    tasks = Task.objects.filter(owner=request.user, date=task_date, parent__isnull=True)
    return JsonResponse({'stats': _task_stats(tasks), 'streak': Streak.get_for(request.user).current})


@login_required
@require_http_methods(["POST"])
def tasks_clear_completed(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    task_date = parse_date(data.get('date', '')) or _today()
    Task.objects.filter(owner=request.user, date=task_date, completed=True).delete()
    tasks = Task.objects.filter(owner=request.user, date=task_date, parent__isnull=True)
    return JsonResponse({'stats': _task_stats(tasks)})


# ─── subtasks ───────────────────────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def subtask_create(request, task_id):
    parent = get_object_or_404(Task, pk=task_id, owner=request.user)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    text = data.get('text', '').strip()[:140]
    if not text:
        return JsonResponse({'error': 'Text required'}, status=400)

    sub = Task.objects.create(
        owner=request.user, text=text, category=parent.category,
        priority=parent.priority, date=parent.date, parent=parent,
    )
    return JsonResponse({'subtask': sub.to_dict()})


@login_required
@require_http_methods(["POST"])
def subtask_toggle(request, task_id):
    sub = get_object_or_404(Task, pk=task_id, owner=request.user, parent__isnull=False)
    sub.completed = not sub.completed
    sub.save()
    return JsonResponse({'subtask': sub.to_dict()})


@login_required
@require_http_methods(["POST"])
def subtask_delete(request, task_id):
    sub = get_object_or_404(Task, pk=task_id, owner=request.user, parent__isnull=False)
    sub.delete()
    return JsonResponse({'ok': True})


# ─── export / import ────────────────────────────────────────────────────────

@login_required
def export_json(request):
    date_str = request.GET.get('date', _today().isoformat())
    target_date = parse_date(date_str) or _today()
    tasks = Task.objects.filter(owner=request.user, date=target_date, parent__isnull=True)
    stats = _task_stats(tasks)
    payload = {
        'date': target_date.isoformat(),
        'tasks': [t.to_dict() for t in tasks],
        'stats': stats,
    }
    response = HttpResponse(json.dumps(payload, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{target_date.isoformat()}.json"'
    return response


@login_required
def export_txt(request):
    date_str = request.GET.get('date', _today().isoformat())
    target_date = parse_date(date_str) or _today()
    tasks = list(Task.objects.filter(owner=request.user, date=target_date, parent__isnull=True))
    stats = _task_stats(tasks)

    lines = [
        'DAYBOOK — Daily Summary',
        f'Date: {target_date.isoformat()}',
        f'Completion: {stats["completed"]}/{stats["total"]} ({stats["completion_rate"]}%)',
        '-' * 40,
    ]
    for t in sorted(tasks, key=lambda x: x.created_at):
        box = '[X]' if t.completed else '[ ]'
        lines.append(f'{box} {t.text}  ({t.category} / {t.priority})')
    lines += ['-' * 40, 'Generated by Daybook Django']

    response = HttpResponse('\n'.join(lines), content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{target_date.isoformat()}-summary.txt"'
    return response


@login_required
@require_http_methods(["POST"])
def import_json(request):
    try:
        if request.FILES.get('file'):
            raw = request.FILES['file'].read()
            data = json.loads(raw)
        else:
            data = json.loads(request.body)
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Invalid JSON file'}, status=400)

    if not data.get('date') or not isinstance(data.get('tasks'), list):
        return JsonResponse({'error': "File must have 'date' and 'tasks' fields"}, status=400)

    import_date = parse_date(data['date'])
    if not import_date:
        return JsonResponse({'error': 'Invalid date in file'}, status=400)

    created_count = 0
    for t in data['tasks']:
        _, created = Task.objects.get_or_create(
            id=t.get('id', str(uuid.uuid4())),
            defaults={
                'owner': request.user,
                'text': t.get('text', '')[:140],
                'category': t.get('category', 'Work'),
                'priority': t.get('priority', 'Medium'),
                'completed': t.get('completed', False),
                'date': import_date,
            }
        )
        if created:
            created_count += 1

    return JsonResponse({
        'imported_date': import_date.isoformat(),
        'tasks_created': created_count,
        'redirect_url': f'/?date={import_date.isoformat()}',
    })


# ─── Weekly Planner ──────────────────────────────────────────────────────────
# Forward-looking planning for the week ahead — distinct from Habits'
# "Weekly Review" (a retrospective effort-rating wizard for the week just
# finished). This is for queuing up one-off tasks across the next 7 days
# before they arrive, so they don't all have to be added on the day.
#
# Habits are shown per day for reference only, not "added" here — a Habit
# is an ongoing recurring routine (tracked via the Habits app), not a
# date-specific item, so there's nothing new to create for it; it already
# shows up automatically on whichever days it's scheduled/anytime once it
# exists. This mirrors the existing precedent of tasks.views.index()
# reaching into habits.services for the "Today's Habits" section.

def _next_week_range(today):
    this_week_monday = today - timedelta(days=today.isoweekday() - 1)
    next_week_monday = this_week_monday + timedelta(days=7)
    return next_week_monday, next_week_monday + timedelta(days=6)


@login_required
def weekly_planner(request):
    today = _today()
    week_start, week_end = _next_week_range(today)

    from habits.models import Habit, SECTION_CHOICES
    from collections import OrderedDict

    active_habits = list(
        Habit.objects.filter(owner=request.user, archived=False)
        .order_by('section', 'order', 'created_at')
    )
    habit_sections = OrderedDict()
    for key, label in SECTION_CHOICES:
        habit_sections[key] = {'label': label, 'habits': []}
    for h in active_habits:
        habit_sections[h.section]['habits'].append(h)

    days = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        day_tasks = list(
            Task.objects.filter(owner=request.user, date=d, parent__isnull=True)
            .prefetch_related('tags').order_by('created_at')
        )
        days.append({
            'date': d,
            'tasks': day_tasks,
            'stats': _task_stats(day_tasks),
        })

    return render(request, 'tasks/weekly_planner.html', {
        'days': days,
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
        'categories': Task.CATEGORY_CHOICES,
        'priorities': Task.PRIORITY_CHOICES,
        'habit_sections': habit_sections,
    })


@login_required
@require_http_methods(["POST"])
def weekly_planner_add_task(request):
    task_date = parse_date(request.POST.get('date', ''))
    text = request.POST.get('text', '').strip()[:140]
    week_start, week_end = _next_week_range(_today())

    if task_date and text and week_start <= task_date <= week_end:
        Task.objects.create(
            owner=request.user,
            text=text,
            category=request.POST.get('category', 'Work'),
            priority=request.POST.get('priority', 'Medium'),
            date=task_date,
        )
    return redirect('weekly_planner')


@login_required
@require_http_methods(["POST"])
def weekly_planner_toggle_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id, owner=request.user)
    task.completed = not task.completed
    task.save()
    return redirect('weekly_planner')


@login_required
@require_http_methods(["POST"])
def weekly_planner_delete_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id, owner=request.user)
    task.delete()
    return redirect('weekly_planner')
