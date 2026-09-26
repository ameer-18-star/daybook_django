import calendar
import json
from collections import OrderedDict
from datetime import date, time, timedelta

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Max
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_http_methods

from tasks.forms import CustomReportForm
from tasks.models import Task

from .analytics import build_year_heatmap, daily_rows_for_range, habit_stats, overview_stats
from .badges import all_badges_status, check_and_unlock_badges
from .forms import HabitForm, JournalEntryForm, ProfileForm, UserSettingsForm
from .models import (
    ACCENT_COLOR_CHOICES, Habit, HabitChecklistItem, HabitEntry, HabitReviewRating,
    JournalEntry, SECTION_CHOICES, UserSettings, WeeklyReview,
)
from .services import build_today_sections, compute_current_streak, grace_days_remaining
from .timeline import DEFAULT_DURATION_MINUTES, compute_timeline_layout

def _format_hour(hour: int) -> str:
    hour = hour % 24
    period = 'AM' if hour < 12 else 'PM'
    display_hour = hour % 12 or 12
    return f'{display_hour} {period}'


def _habit_color(habit) -> str:
    """habit.color if manually set, otherwise a stable pick derived from the
    habit's own id — same habit always gets the same color across
    requests/sessions without needing a value stored in the database."""
    if habit.color:
        return habit.color
    keys = [key for key, _ in ACCENT_COLOR_CHOICES]
    return keys[int(habit.id.hex[:8], 16) % len(keys)]

# ─── helpers ────────────────────────────────────────────────────────────────

def _entry_for_today(habit):
    today = timezone.localdate()
    entry, _ = HabitEntry.objects.get_or_create(habit=habit, date=today)
    return entry, today


def _sync_checklist_items(habit, form):
    """Regenerate a checklist habit's items from the textarea on save.
    NOTE: this replaces item rows wholesale (new ids each edit), so past
    entries' checked_item_ids can go stale if you rename/reorder items —
    a known Phase 1 simplification; a proper inline editor that preserves
    item ids is a reasonable later upgrade if this bites you in practice."""
    habit.checklist_items.all().delete()
    if habit.habit_type == 'checklist':
        for i, text in enumerate(form.parsed_checklist_items()):
            HabitChecklistItem.objects.create(habit=habit, text=text, order=i)


def _serialize_new_badges(user):
    """Run the badge engine and return newly unlocked badges in JSON-ready
    form, for the AJAX endpoints to surface as a toast."""
    return [
        {'key': b.key, 'name': b.name, 'description': b.description, 'icon': b.icon}
        for b in check_and_unlock_badges(user)
    ]

# ─── pages ──────────────────────────────────────────────────────────────────

@login_required
def habit_list(request):
    today = timezone.localdate()
    user_settings = UserSettings.get_for(request.user)

    habits_qs = (
        Habit.objects.filter(owner=request.user, archived=False)
        .prefetch_related('checklist_items')
        .order_by('section', 'order', 'created_at')
    )
    entries_today = {
        e.habit_id: e for e in HabitEntry.objects.filter(habit__owner=request.user, date=today)
    }

    sections = OrderedDict()
    for key, label in SECTION_CHOICES:
        sections[key] = {'label': label, 'habits': []}

    for habit in habits_qs:
        entry = entries_today.get(habit.id)
        checklist_items = list(habit.checklist_items.all()) if habit.habit_type == 'checklist' else []
        checked_ids = set(entry.checked_item_ids) if entry else set()

        sections[habit.section]['habits'].append({
            'habit': habit,
            'entry': entry,
            'streak': compute_current_streak(habit, today),
            'grace_remaining': grace_days_remaining(habit),
            'checklist_items': checklist_items,
            'checklist_progress': f'{len(checked_ids)}/{len(checklist_items)}' if checklist_items else '',
            'checked_ids': [str(i) for i in checked_ids],
        })

    archived_habits = Habit.objects.filter(owner=request.user, archived=True).order_by('-updated_at')[:20]

    return render(request, 'habits/list.html', {
        'sections': sections,
        'today': today,
        'user_settings': user_settings,
        'archived_habits': archived_habits,
    })


@login_required
def habit_create(request):
    if request.method == 'POST':
        form = HabitForm(request.POST)
        if form.is_valid():
            habit = form.save(commit=False)
            habit.owner = request.user
            top_order = Habit.objects.filter(
                owner=request.user, section=habit.section
            ).aggregate(Max('order'))['order__max'] or 0
            habit.order = top_order + 1
            habit.save()
            _sync_checklist_items(habit, form)
            check_and_unlock_badges(request.user)
            return redirect('habit_list')
    else:
        form = HabitForm()
    return render(request, 'habits/habit_form.html', {'form': form, 'is_edit': False})


@login_required
def habit_edit(request, habit_id):
    habit = get_object_or_404(Habit, pk=habit_id, owner=request.user)
    if request.method == 'POST':
        form = HabitForm(request.POST, instance=habit)
        if form.is_valid():
            habit = form.save()
            _sync_checklist_items(habit, form)
            return redirect('habit_list')
    else:
        form = HabitForm(instance=habit)
    return render(request, 'habits/habit_form.html', {'form': form, 'is_edit': True, 'habit': habit})


@login_required
@require_http_methods(["POST"])
def habit_delete(request, habit_id):
    habit = get_object_or_404(Habit, pk=habit_id, owner=request.user)
    habit.delete()
    return redirect('habit_list')


@login_required
@require_http_methods(["POST"])
def habit_archive_toggle(request, habit_id):
    habit = get_object_or_404(Habit, pk=habit_id, owner=request.user)
    habit.archived = not habit.archived
    habit.save()
    return redirect('habit_list')


@login_required
@require_http_methods(["POST"])
def habit_pause_toggle(request, habit_id):
    habit = get_object_or_404(Habit, pk=habit_id, owner=request.user)
    habit.paused = not habit.paused
    if not habit.paused:
        habit.paused_until = None
    habit.save()
    return redirect('habit_list')


@login_required
@require_http_methods(["POST"])
def toggle_compact_mode(request):
    s = UserSettings.get_for(request.user)
    s.compact_mode = not s.compact_mode
    s.save()
    return redirect('habit_list')


# ─── daily interaction (JSON API) ───────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def habit_toggle_yes_no(request, habit_id):
    habit = get_object_or_404(Habit, pk=habit_id, owner=request.user, habit_type='yes_no')
    entry, today = _entry_for_today(habit)
    entry.completed = not entry.completed
    entry.completed_at = timezone.now() if entry.completed else None
    if entry.completed:
        entry.used_grace_day = False
    entry.save()
    return JsonResponse({
        'completed': entry.completed,
        'streak': compute_current_streak(habit, today),
        'new_badges': _serialize_new_badges(request.user),
    })


@login_required
@require_http_methods(["POST"])
def habit_log_numeric(request, habit_id):
    habit = get_object_or_404(Habit, pk=habit_id, owner=request.user, habit_type='numeric')
    try:
        data = json.loads(request.body)
        value = float(data.get('value'))
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'error': 'Invalid value'}, status=400)

    entry, today = _entry_for_today(habit)
    entry.numeric_value = value
    entry.completed = (value >= habit.target_value) if habit.target_value is not None else (value > 0)
    entry.completed_at = timezone.now() if entry.completed else None
    if entry.completed:
        entry.used_grace_day = False
    entry.save()
    return JsonResponse({
        'completed': entry.completed,
        'numeric_value': entry.numeric_value,
        'streak': compute_current_streak(habit, today),
        'new_badges': _serialize_new_badges(request.user),
    })


@login_required
@require_http_methods(["POST"])
def habit_checklist_toggle(request, habit_id):
    habit = get_object_or_404(Habit, pk=habit_id, owner=request.user, habit_type='checklist')
    try:
        data = json.loads(request.body)
        item_id = str(data['item_id'])
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Invalid request'}, status=400)

    entry, today = _entry_for_today(habit)
    checked = set(entry.checked_item_ids)
    if item_id in checked:
        checked.discard(item_id)
    else:
        checked.add(item_id)
    entry.checked_item_ids = list(checked)

    all_ids = {str(i.id) for i in habit.checklist_items.all()}
    entry.completed = bool(all_ids) and all_ids.issubset(checked)
    entry.completed_at = timezone.now() if entry.completed else None
    if entry.completed:
        entry.used_grace_day = False
    entry.save()

    return JsonResponse({
        'checked_item_ids': entry.checked_item_ids,
        'completed': entry.completed,
        'streak': compute_current_streak(habit, today),
        'new_badges': _serialize_new_badges(request.user),
    })


@login_required
@require_http_methods(["POST"])
def habit_use_grace_day(request, habit_id):
    habit = get_object_or_404(Habit, pk=habit_id, owner=request.user)
    if grace_days_remaining(habit) <= 0:
        return JsonResponse({'error': 'No grace days remaining'}, status=400)

    entry, today = _entry_for_today(habit)
    if entry.completed:
        return JsonResponse({'error': 'Already completed today'}, status=400)

    entry.used_grace_day = True
    entry.save()
    return JsonResponse({
        'used_grace_day': True,
        'grace_remaining': grace_days_remaining(habit),
        'streak': compute_current_streak(habit, today),
        'new_badges': _serialize_new_badges(request.user),
    })


# ─── Phase 2: drag-and-drop reordering + bulk edit ─────────────────────────

@login_required
@require_http_methods(["POST"])
def habit_reorder(request):
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    valid_sections = {key for key, _ in SECTION_CHOICES}
    habit_ids = [item.get('id') for item in items]
    habits_by_id = {str(h.id): h for h in Habit.objects.filter(owner=request.user, id__in=habit_ids)}

    to_update = []
    for item in items:
        habit = habits_by_id.get(str(item.get('id')))
        section = item.get('section')
        order = item.get('order')
        if not habit or section not in valid_sections or not isinstance(order, int):
            continue
        habit.section = section
        habit.order = order
        to_update.append(habit)

    if to_update:
        Habit.objects.bulk_update(to_update, ['section', 'order'])
    return JsonResponse({'ok': True, 'updated': len(to_update)})


@login_required
@require_http_methods(["POST"])
def habit_bulk_action(request):
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
        action = data.get('action')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not ids or action not in ('move', 'archive', 'delete'):
        return JsonResponse({'error': 'Invalid request'}, status=400)

    qs = Habit.objects.filter(owner=request.user, id__in=ids)
    affected = qs.count()
    if affected == 0:
        return JsonResponse({'error': 'No matching habits'}, status=404)

    if action == 'move':
        section = data.get('section')
        valid_sections = {key for key, _ in SECTION_CHOICES}
        if section not in valid_sections:
            return JsonResponse({'error': 'Invalid section'}, status=400)
        qs.update(section=section)
    elif action == 'archive':
        qs.update(archived=True)
    elif action == 'delete':
        qs.delete()

    return JsonResponse({'ok': True, 'affected': affected})

# ─── Phase 3: Swimlane Timeline ─────────────────────────────────────────────

@login_required
def habit_timeline(request):
    today = timezone.localdate()
    view_date = parse_date(request.GET.get('date', '')) or today
    user_settings = UserSettings.get_for(request.user)

    window_start = user_settings.timeline_start_hour * 60
    window_end = user_settings.timeline_end_hour * 60
    window_valid = window_end > window_start

    habits_qs = Habit.objects.filter(owner=request.user, archived=False)
    entries = {
        e.habit_id: e for e in HabitEntry.objects.filter(habit__owner=request.user, date=view_date)
    }

    scheduled_events = []
    anytime_habits = []
    for habit in habits_qs:
        entry = entries.get(habit.id)
        if habit.scheduled_time is None:
            anytime_habits.append({'habit': habit, 'entry': entry, 'color': _habit_color(habit)})
        else:
            start_minutes = habit.scheduled_time.hour * 60 + habit.scheduled_time.minute
            duration = habit.duration_minutes or DEFAULT_DURATION_MINUTES
            scheduled_events.append({
                'habit': habit,
                'entry': entry,
                'start': start_minutes,
                'duration': duration,
                'color': _habit_color(habit),
            })

    layout = compute_timeline_layout(scheduled_events, window_start, window_end) if window_valid else []

    hour_labels = []
    if window_valid:
        for hour in range(user_settings.timeline_start_hour, user_settings.timeline_end_hour + 1):
            hour_labels.append({
                'label': _format_hour(hour),
                'top_pct': round((hour * 60 - window_start) / (window_end - window_start) * 100, 3),
            })

    now = timezone.localtime()
    now_minutes = now.hour * 60 + now.minute
    now_in_window = window_valid and window_start <= now_minutes <= window_end
    now_top_pct = round((now_minutes - window_start) / (window_end - window_start) * 100, 3) if now_in_window else None

    HOUR_HEIGHT_PX = 64
    total_minutes = window_end - window_start if window_valid else 0

    return render(request, 'habits/timeline.html', {
        'view_date': view_date,
        'today': today,
        'is_today': view_date == today,
        'prev_date': view_date - timedelta(days=1),
        'next_date': view_date + timedelta(days=1),
        'user_settings': user_settings,
        'layout': layout,
        'anytime_habits': anytime_habits,
        'hour_labels': hour_labels,
        'now_top_pct': now_top_pct,
        'window_valid': window_valid,
        'total_minutes': total_minutes,
        'timeline_height_px': round(total_minutes / 60 * HOUR_HEIGHT_PX) if window_valid else 0,
    })


@login_required
@require_http_methods(["POST"])
def update_timeline_hours(request):
    user_settings = UserSettings.get_for(request.user)
    try:
        start_hour = int(request.POST.get('timeline_start_hour'))
        end_hour = int(request.POST.get('timeline_end_hour'))
    except (TypeError, ValueError):
        return redirect('habit_timeline')

    start_hour = max(0, min(23, start_hour))
    end_hour = max(1, min(24, end_hour))
    if start_hour < end_hour:
        user_settings.timeline_start_hour = start_hour
        user_settings.timeline_end_hour = end_hour
        user_settings.save()
    return redirect('habit_timeline')

# ─── Phase 4: Statistics & Analytics ────────────────────────────────────────

def _clamp_range(start, end, today, max_days=366):
    if start > end:
        start, end = end, start
    if (end - start).days > max_days:
        start = end - timedelta(days=max_days)
    return start, end


@login_required
def stats_overview(request):
    today = timezone.localdate()
    start = parse_date(request.GET.get('start', '')) or (today - timedelta(days=29))
    end = parse_date(request.GET.get('end', '')) or today
    start, end = _clamp_range(start, end, today)

    overview = overview_stats(request.user, start, end)
    year_heatmap = build_year_heatmap(request.user, today.year)
    range_form = CustomReportForm(initial={'start': start, 'end': end})

    return render(request, 'habits/stats_overview.html', {
        'start': start,
        'end': end,
        'today': today,
        'range_form': range_form,
        'year_heatmap': year_heatmap,
        **overview,
    })


@login_required
def habit_stats_detail(request, habit_id):
    habit = get_object_or_404(Habit, pk=habit_id, owner=request.user)
    today = timezone.localdate()
    start = parse_date(request.GET.get('start', '')) or (today - timedelta(days=89))
    end = parse_date(request.GET.get('end', '')) or today
    start, end = _clamp_range(start, end, today)

    stats = habit_stats(habit, start, end)
    range_form = CustomReportForm(initial={'start': start, 'end': end})

    return render(request, 'habits/habit_stats_detail.html', {
        'habit': habit,
        'start': start,
        'end': end,
        'today': today,
        'range_form': range_form,
        **stats,
    })


@login_required
def habit_export_json(request):
    user = request.user
    habits_qs = Habit.objects.filter(owner=user).prefetch_related('checklist_items', 'entries')
    user_settings = UserSettings.get_for(user)

    habits_payload = []
    for habit in habits_qs:
        habits_payload.append({
            'id': str(habit.id),
            'text': habit.text,
            'habit_type': habit.habit_type,
            'section': habit.section,
            'scheduled_time': habit.scheduled_time.strftime('%H:%M') if habit.scheduled_time else None,
            'duration_minutes': habit.duration_minutes,
            'target_value': habit.target_value,
            'target_unit': habit.target_unit,
            'order': habit.order,
            'paused': habit.paused,
            'paused_until': habit.paused_until.isoformat() if habit.paused_until else None,
            'archived': habit.archived,
            'grace_days_allowed': habit.grace_days_allowed,
            'color': habit.color,
            'checklist_items': [
                {'id': str(ci.id), 'text': ci.text, 'order': ci.order}
                for ci in habit.checklist_items.all()
            ],
            'entries': [
                {
                    'date': e.date.isoformat(),
                    'completed': e.completed,
                    'numeric_value': e.numeric_value,
                    'checked_item_ids': e.checked_item_ids,
                    'used_grace_day': e.used_grace_day,
                    'completed_at': e.completed_at.isoformat() if e.completed_at else None,
                    'note': e.note,
                }
                for e in habit.entries.all()
            ],
        })

    payload = {
        'exported_at': timezone.now().isoformat(),
        'username': user.username,
        'settings': {
            'accent_color': user_settings.accent_color,
            'card_theme': user_settings.card_theme,
            'compact_mode': user_settings.compact_mode,
            'dark_mode': user_settings.dark_mode,
            'timeline_start_hour': user_settings.timeline_start_hour,
            'timeline_end_hour': user_settings.timeline_end_hour,
        },
        'habits': habits_payload,
    }

    response = HttpResponse(json.dumps(payload, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="daybook-habits-{timezone.localdate().isoformat()}.json"'
    return response

# ─── Phase 5: Productivity Suite ────────────────────────────────────────────

@login_required
def yearly_calendar(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
    except (TypeError, ValueError):
        year = today.year

    start = date(year, 1, 1)
    end = date(year, 12, 31)
    rows_by_date = {r['date']: r for r in daily_rows_for_range(request.user, start, end)}

    months = []
    for month in range(1, 13):
        month_weeks = []
        for week in calendar.monthcalendar(year, month):
            week_cells = []
            for day_num in week:
                if day_num == 0:
                    week_cells.append(None)
                    continue
                d = date(year, month, day_num)
                row = rows_by_date.get(d)
                week_cells.append({
                    'date': d,
                    'day': day_num,
                    'level': row['level'] if row else 'none',
                    'is_today': d == today,
                })
            month_weeks.append(week_cells)
        months.append({'month': month, 'name': calendar.month_name[month], 'weeks': month_weeks})

    return render(request, 'habits/yearly_calendar.html', {
        'year': year,
        'months': months,
        'prev_year': year - 1,
        'next_year': year + 1,
        'today': today,
    })


@login_required
def day_detail(request, year, month, day):
    try:
        the_date = date(year, month, day)
    except ValueError:
        raise Http404('Invalid date')

    habit_entries = (
        HabitEntry.objects.filter(habit__owner=request.user, date=the_date)
        .select_related('habit').order_by('habit__section', 'habit__order')
    )
    tasks_for_day = (
        Task.objects.filter(owner=request.user, date=the_date, parent__isnull=True)
        .prefetch_related('tags', 'subtasks').order_by('created_at')
    )
    journal_entry_for_day = JournalEntry.objects.filter(owner=request.user, date=the_date).first()

    return render(request, 'habits/day_detail.html', {
        'the_date': the_date,
        'habit_entries': habit_entries,
        'tasks_for_day': tasks_for_day,
        'journal_entry_for_day': journal_entry_for_day,
        'prev_date': the_date - timedelta(days=1),
        'next_date': the_date + timedelta(days=1),
        'today': timezone.localdate(),
    })


@login_required
def journal_list(request):
    query = request.GET.get('q', '').strip()
    mood_filter = request.GET.get('mood', '').strip()

    qs = JournalEntry.objects.filter(owner=request.user)
    if query:
        qs = qs.filter(text__icontains=query)
    if mood_filter:
        qs = qs.filter(mood=mood_filter)
    entries = qs.order_by('-date')[:200]

    today = timezone.localdate()
    return render(request, 'habits/journal_list.html', {
        'entries': entries,
        'query': query,
        'mood_filter': mood_filter,
        'mood_choices': JournalEntry.MOOD_CHOICES,
        'today': today,
        'has_today_entry': JournalEntry.objects.filter(owner=request.user, date=today).exists(),
    })


@login_required
def journal_entry(request, year, month, day):
    try:
        the_date = date(year, month, day)
    except ValueError:
        raise Http404('Invalid date')

    entry = JournalEntry.objects.filter(owner=request.user, date=the_date).first()

    if request.method == 'POST':
        form = JournalEntryForm(request.POST, instance=entry)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.owner = request.user
            obj.date = the_date
            obj.save()
            return redirect('journal_entry', year=year, month=month, day=day)
    else:
        form = JournalEntryForm(instance=entry)

    return render(request, 'habits/journal_entry.html', {
        'form': form,
        'the_date': the_date,
        'entry': entry,
        'today': timezone.localdate(),
        'prev_date': the_date - timedelta(days=1),
        'next_date': the_date + timedelta(days=1),
    })


@login_required
def weekly_review(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.isoweekday() - 1)
    review, _ = WeeklyReview.objects.get_or_create(owner=request.user, week_start=week_start)

    if request.method == 'GET' and review.completed_at and 'step' not in request.GET:
        return redirect('weekly_review_summary')

    habits = list(Habit.objects.filter(owner=request.user, archived=False).order_by('section', 'order'))
    week_end = week_start + timedelta(days=6)

    if not habits:
        return render(request, 'habits/weekly_review.html', {
            'no_habits': True, 'week_start': week_start, 'week_end': week_end,
        })

    if request.method == 'POST':
        habit = get_object_or_404(Habit, pk=request.POST.get('habit_id'), owner=request.user)
        try:
            step = int(request.POST.get('step', 0))
        except (TypeError, ValueError):
            step = 0

        try:
            effort = int(request.POST.get('effort_rating'))
            if not (1 <= effort <= 5):
                raise ValueError
        except (TypeError, ValueError):
            effort = None

        if effort is not None:
            HabitReviewRating.objects.update_or_create(
                review=review, habit=habit,
                defaults={'effort_rating': effort, 'note': request.POST.get('note', '').strip()[:1000]},
            )

        next_step = step + 1
        if next_step >= len(habits):
            review.completed_at = timezone.now()
            review.save()
            return redirect('weekly_review_summary')
        return redirect(f"{reverse('weekly_review')}?step={next_step}")

    try:
        step = int(request.GET.get('step', 0))
    except (TypeError, ValueError):
        step = 0
    step = max(0, min(step, len(habits) - 1))

    current_habit = habits[step]
    existing_rating = review.ratings.filter(habit=current_habit).first()

    return render(request, 'habits/weekly_review.html', {
        'review': review,
        'step': step,
        'total_steps': len(habits),
        'step_range': range(len(habits)),
        'current_habit': current_habit,
        'existing_rating': existing_rating,
        'week_start': week_start,
        'week_end': week_end,
        'is_last_step': step == len(habits) - 1,
    })


@login_required
def weekly_review_summary(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.isoweekday() - 1)
    review = get_object_or_404(WeeklyReview, owner=request.user, week_start=week_start)
    ratings = review.ratings.select_related('habit').order_by('habit__section', 'habit__order')

    return render(request, 'habits/weekly_review_summary.html', {
        'review': review,
        'ratings': ratings,
        'week_start': week_start,
        'week_end': week_start + timedelta(days=6),
    })


@login_required
@require_http_methods(["POST"])
def weekly_review_restart(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.isoweekday() - 1)
    review = get_object_or_404(WeeklyReview, owner=request.user, week_start=week_start)
    review.completed_at = None
    review.save()
    return redirect(f"{reverse('weekly_review')}?step=0")


# ─── Phase 6: Gamification ──────────────────────────────────────────────────

@login_required
def badges_page(request):
    return render(request, 'habits/badges.html', {
        'badges': all_badges_status(request.user),
    })

# ─── Phase 7: Profile, Backup & Restore ─────────────────────────────────────

@login_required
def profile_view(request):
    user = request.user
    user_settings = UserSettings.get_for(user)

    profile_form = ProfileForm(instance=user)
    settings_form = UserSettingsForm(instance=user_settings)
    password_form = PasswordChangeForm(user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'profile':
            profile_form = ProfileForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profile updated.')
                return redirect('profile')

        elif action == 'settings':
            settings_form = UserSettingsForm(request.POST, request.FILES, instance=user_settings)
            if settings_form.is_valid():
                settings_form.save()
                messages.success(request, 'Preferences updated.')
                return redirect('profile')

        elif action == 'password':
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, 'Password changed.')
                return redirect('profile')

    return render(request, 'habits/profile.html', {
        'profile_form': profile_form,
        'settings_form': settings_form,
        'password_form': password_form,
        'user_settings': user_settings,
    })


@login_required
def backup_restore_view(request):
    return render(request, 'habits/backup_restore.html', {})


@login_required
@require_http_methods(["POST"])
def habit_import_json(request):
    uploaded = request.FILES.get('file')
    if not uploaded:
        messages.error(request, 'Choose a JSON file to import.')
        return redirect('backup_restore')

    try:
        payload = json.loads(uploaded.read())
    except (json.JSONDecodeError, UnicodeDecodeError):
        messages.error(request, "That file isn't valid JSON.")
        return redirect('backup_restore')

    habits_payload = payload.get('habits')
    if not isinstance(habits_payload, list):
        messages.error(request, "That file doesn't look like a Daybook habits backup.")
        return redirect('backup_restore')

    created_habits = 0
    created_entries = 0
    skipped_habits = 0

    for h in habits_payload:
        habit_id = h.get('id')
        if not habit_id:
            continue
        if Habit.objects.filter(pk=habit_id).exists():
            skipped_habits += 1
            continue

        scheduled_time = None
        if h.get('scheduled_time'):
            try:
                hh, mm = (int(x) for x in h['scheduled_time'].split(':'))
                scheduled_time = time(hh, mm)
            except (ValueError, AttributeError, TypeError):
                scheduled_time = None

        habit = Habit.objects.create(
            id=habit_id,
            owner=request.user,
            text=(h.get('text') or 'Untitled habit')[:140],
            habit_type=h.get('habit_type', 'yes_no'),
            section=h.get('section', 'need_to_do'),
            scheduled_time=scheduled_time,
            duration_minutes=h.get('duration_minutes'),
            target_value=h.get('target_value'),
            target_unit=h.get('target_unit', '') or '',
            order=h.get('order', 0) or 0,
            paused=bool(h.get('paused', False)),
            paused_until=parse_date(h['paused_until']) if h.get('paused_until') else None,
            archived=bool(h.get('archived', False)),
            grace_days_allowed=h.get('grace_days_allowed', 0) or 0,
            color=h.get('color'),
        )
        created_habits += 1

        for ci in h.get('checklist_items', []):
            if not ci.get('id'):
                continue
            HabitChecklistItem.objects.get_or_create(
                id=ci['id'], habit=habit,
                defaults={'text': (ci.get('text') or '')[:140], 'order': ci.get('order', 0) or 0},
            )

        for e in h.get('entries', []):
            entry_date = parse_date(e.get('date') or '')
            if not entry_date:
                continue
            completed_at = parse_datetime(e['completed_at']) if e.get('completed_at') else None
            _, was_created = HabitEntry.objects.get_or_create(
                habit=habit, date=entry_date,
                defaults={
                    'completed': bool(e.get('completed', False)),
                    'numeric_value': e.get('numeric_value'),
                    'checked_item_ids': e.get('checked_item_ids') or [],
                    'used_grace_day': bool(e.get('used_grace_day', False)),
                    'completed_at': completed_at,
                    'note': e.get('note', '') or '',
                },
            )
            if was_created:
                created_entries += 1

    settings_payload = payload.get('settings') or {}
    if settings_payload:
        user_settings = UserSettings.get_for(request.user)
        for field in ('accent_color', 'card_theme', 'compact_mode', 'dark_mode',
                      'timeline_start_hour', 'timeline_end_hour'):
            if field in settings_payload:
                setattr(user_settings, field, settings_payload[field])
        user_settings.save()

    messages.success(
        request,
        f'Import complete: {created_habits} habit(s) and {created_entries} entry/entries added, '
        f'{skipped_habits} habit(s) skipped (already present).',
    )
    check_and_unlock_badges(request.user)
    return redirect('backup_restore')
