# Daybook

A self-hosted, full-stack Django app that combines a daily task manager
with a complete habit tracker — one-off and recurring tasks, three
types of habits, a swimlane day timeline, statistics, a journal,
gamification, and email reports, all under one login.

Built on a "paper ledger" design language: warm ivory paper, deep ink
text, a single teal accent for completion, Fraunces/Inter/IBM Plex Mono
typography, and a persistent left sidebar for navigation.

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Setup](#setup)
  - [Linux / macOS](#linux--macos)
  - [Windows](#windows)
- [Environment variables](#environment-variables)
- [Sending daily reports](#sending-daily-reports)
- [Upgrading an existing single-user deployment](#upgrading-an-existing-single-user-deployment)
- [Viewing the database](#viewing-the-database)
- [Testing this project](#testing-this-project)
- [Known limitations](#known-limitations)
- [Architecture notes](#architecture-notes)
- [License](#license)

---

## Features

### Tasks
- One-off daily tasks with category, priority, due time, notes, tags, and subtasks
- Search and tag filtering
- Recurring task templates (daily / weekdays / custom days) that materialize onto today's list automatically
- Daily completion streak
- Export today's tasks to JSON/TXT, import a JSON backup — all reachable from the sidebar's **Data** section

### Habits
- Three habit types: **Yes/No**, **Numeric** (with a target + unit), **Checklist** (with sub-items)
- Three organizational sections: Have To Do / Need To Do / Would Do
- Optional scheduled time + duration, or "anytime"
- Pause/resume, archive, grace days (streak protection for occasional misses)
- Drag-and-drop reordering within and across sections; bulk move/archive/delete
- **Swimlane Timeline** — a day view with colored lanes per habit, automatic overlap/lane-packing, a live current-time needle, and an "anytime" row
- **Today's Habits** also appear directly on the main Tasks screen, fully interactive

### Statistics & Analytics
- Overview dashboard: completion rate, section breakdown, top habits, time-of-day analysis
- Year-long GitHub-style contribution heatmap
- Per-habit page: report card (letter grade), current/longest streak, weekly/monthly/yearly numbers, a completion-trend chart, and a streak calendar
- Custom date ranges on every stat view
- Full JSON data export (also used by Backup & Restore)

### Productivity suite
- Yearly calendar — click any day to see every task, habit entry, and journal entry logged that day
- Daily journal with mood tagging and full-text search
- Weekly Habit Review — a step-by-step wizard rating effort per habit with optional reflection notes

### Gamification
- Badges for streak milestones, total completions, and perfect weeks — unlocked automatically, with an in-app toast notification

### Profile & account
- Change username, email, and password from one Profile page
- Account avatar (auto-resized on upload)
- Preferences: accent color, card theme, compact mode, timeline hours, daily report settings

### Backup & data portability
- Download your entire habit history as one JSON file
- Restore from a backup file (additive only — never overwrites existing data; duplicates are skipped by id)

### Customization
- Dark / light mode
- 8 accent color presets, applied instantly across the whole app via CSS custom properties
- 3 card themes (Classic / Minimal / Bold)

### Daily report email
- Optional daily email summarizing the day's tasks and habits
- SMTP settings via environment variables — nothing hardcoded
- Delivered either by an in-process scheduler (opt-in, single-process deployments) or an external cron job (recommended for anything with multiple worker processes)

### Navigation
- A persistent left sidebar, grouped hierarchically (Tasks/Recurring Tasks, Habits, Reports, Data, Account), replacing what used to be flat rows of buttons on every page
- Active-page highlighting, off-canvas collapse on mobile

---

## Tech stack

- **Backend:** Django 4.2+ (tested on 5.2), SQLite
- **Frontend:** vanilla HTML/CSS/JS — no build step, no framework
- **Charts:** Chart.js (CDN)
- **Drag & drop:** SortableJS (CDN)
- **Images:** Pillow (avatar resizing)
- **PDF export:** xhtml2pdf
- **Scheduling:** APScheduler (optional, in-process)

---

## Project structure

```
daybook_django/
├── manage.py
├── requirements.txt
├── db.sqlite3                (created on first migrate)
├── daybook/                   project package
│   ├── settings.py
│   ├── urls.py
│   ├── middleware.py           no-cache middleware (prevents stale pages after logout)
│   └── wsgi.py
├── tasks/                      one-off tasks, recurring task templates, auth
│   ├── models.py               Task, Tag, TaskTemplate, Streak
│   ├── views.py                 pages + JSON API + auth (register/login/logout)
│   └── templates/
├── reports/                     weekly/monthly/custom Task reports (heatmap, PDF, trend chart)
│   ├── analytics.py
│   └── templates/
├── habits/                      the habit tracker — the bulk of the app
│   ├── models.py                Habit, HabitChecklistItem, HabitEntry, UserSettings,
│   │                            JournalEntry, WeeklyReview, HabitReviewRating, UserBadge
│   ├── services.py              streak calculation, shared section-builder
│   ├── analytics.py             stats/heatmap/report-card aggregation
│   ├── timeline.py              swimlane layout algorithm (pure Python, unit-tested)
│   ├── badges.py                badge rule engine
│   ├── reports.py               daily report email content + sending
│   ├── scheduler.py             optional in-process APScheduler
│   ├── context_processors.py    injects accent color/card theme/avatar globally
│   ├── management/commands/
│   │   └── send_daily_reports.py
│   └── templates/
├── templates/                   shared base template (sidebar nav, footer, theme toggle) + icon library
│   ├── base.html
│   └── icons.html               inline SVG icon set (no emoji anywhere in the UI)
└── static/
    ├── css/style.css            single global stylesheet — theming, layout, components
    └── js/
        ├── app.js                Task page interactions
        └── habits.js              Habit interactions (shared by the Habits page and
                                    the "Today's Habits" section on the Tasks page)
```

---

## Setup

### Linux / macOS

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser      # optional, for /admin/
python manage.py runserver
```

### Windows

**PowerShell:**

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

**Command Prompt:**

```cmd
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

If PowerShell blocks the activation script ("running scripts is disabled"), run once:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Open `http://127.0.0.1:8000` — you'll be redirected to sign in. Click
"Create one" to register your first account. Everything (tasks, habits,
journal, stats) is scoped per-account.

---

## Environment variables

None are required to run locally — sensible defaults are used everywhere
(console email backend, scheduler off). Set these for real email delivery:

| Variable | Purpose | Default |
|---|---|---|
| `DAYBOOK_EMAIL_BACKEND` | Django email backend | console (prints to terminal) |
| `DAYBOOK_EMAIL_HOST` | SMTP host | `localhost` |
| `DAYBOOK_EMAIL_PORT` | SMTP port | `587` |
| `DAYBOOK_EMAIL_HOST_USER` | SMTP username | *(empty)* |
| `DAYBOOK_EMAIL_HOST_PASSWORD` | SMTP password | *(empty)* |
| `DAYBOOK_EMAIL_USE_TLS` | `true`/`false` | `true` |
| `DAYBOOK_DEFAULT_FROM_EMAIL` | From address | `noreply@daybook.local` |
| `DAYBOOK_ENABLE_SCHEDULER` | `1` to auto-start the in-process daily-report scheduler | unset (off) |

**Never commit real SMTP credentials.** Set these in your shell, a
`.env` file loaded before Django starts, or your hosting platform's
secrets manager — not in `settings.py`.

---

## Sending daily reports

Two ways to trigger `send_daily_reports`, pick one based on your deployment:

- **Single-process deployment** (e.g. `manage.py runserver`, or one gunicorn worker): set `DAYBOOK_ENABLE_SCHEDULER=1` and the app checks every 5 minutes internally.
- **Multiple worker processes** (gunicorn `-w 2+`, uwsgi with multiple processes, etc.): **do not** use the in-process scheduler — each worker would start its own copy and every user would get duplicate emails. Use external cron instead:
  ```
  */5 * * * * cd /path/to/project && python manage.py send_daily_reports
  ```

Test the whole pipeline without real SMTP first:
```bash
python manage.py send_daily_reports --force-user yourusername
```

---

## Upgrading an existing single-user deployment

If you're running an older version of this app from before multi-user
accounts existed, existing tasks have no owner yet:

```bash
python manage.py migrate
python manage.py createsuperuser --username yourname   # if you don't have one
python manage.py assign_orphan_tasks yourname           # claims pre-existing tasks
```

---

## Viewing the database

The app uses SQLite (`db.sqlite3` in the project root). A few ways to inspect it directly:

- **Django Admin** — `python manage.py createsuperuser`, then visit `/admin/`
- **[DB Browser for SQLite](https://sqlitebrowser.org/dl/)** — free GUI, open `db.sqlite3` directly
- **Django shell** — `python manage.py shell`, then e.g. `from habits.models import Habit; Habit.objects.all()`
- **sqlite3 CLI** — `sqlite3 db.sqlite3`, then `.tables`, `.schema <table>`, `SELECT * FROM <table>;`

---

## Testing this project

Logic that doesn't require a live database is unit-tested directly (the
swimlane timeline layout algorithm, the heatmap color thresholds, the
report-card letter grades, the calendar-week padding). Everything else
is verified through a four-step protocol:

1. **Environment** — `pip install -r requirements.txt`, confirm no dependency conflicts
2. **Migrations** — `python manage.py migrate` + `makemigrations --check --dry-run`
3. **Static pass** — `py_compile` every `.py` file, `node --check` every `.js` file, verify every template's `{% if %}/{% for %}/{% block %}` tags balance, cross-reference every `{% url %}` against a defined `path(..., name=...)`
4. **Dynamic pass** — run the dev server, exercise every page and every write action (create/edit/delete/toggle) against a real database, not just confirm the code compiles

---

## Known limitations

Worth knowing before you rely on them — these are deliberate trade-offs, not bugs:

- **Daily report send time is server-local, not per-user.** `UserSettings.daily_report_time` has no timezone attached; "send at 7am" means 7am in the server's configured `TIME_ZONE`, not wherever you actually are.
- **`UserSettings.dark_mode` field is currently unused.** Dark mode is a client-side (localStorage) toggle; this DB field exists for a future server-rendered version but isn't wired to anything yet.
- **No true push notifications.** "Reminders" are in-app due-time badges (Due soon / Overdue) shown while the page is open.
- **Backup import never merges conflicting data** — only adds what's missing (matched by id). There's no UI for resolving a true conflict between two divergent datasets.
- **Card theming still uses `!important`** in a few page-local `<style>` blocks (Stats, Reports, Journal entry) that haven't been migrated onto the shared CSS custom-property tokens the main stylesheet uses everywhere else.
- **Editing a checklist habit's items regenerates them from scratch**, so historical checked-state can go stale if you rename/reorder items after the fact.
- **Bulk "move to section" doesn't renumber `order`** — moved habits may land in a slightly arbitrary position within their new section until you drag one to fix it.
- **No PNG snapshot export.** An earlier version could screenshot the Tasks dashboard as an image; this was removed (not replaced) since it depended on DOM specific to that one page and couldn't be generalized when export/import moved to the sidebar.

---

## Architecture notes

Three Django apps, with a deliberate one-directional dependency:

```
reports  ──depends on──▶  tasks
habits   ──depends on──▶  tasks
tasks    ──never depends on either──
```

`tasks` owns authentication and the original one-off task list, and
knows nothing about habits. `habits` is the larger app — it imports
from `tasks` where it genuinely needs to (e.g. the Yearly Calendar's
day-detail view shows both habit entries and tasks). This direction
was chosen once, early, and held for the rest of the build.

**Theming** is entirely CSS custom properties — every color is
`var(--accent)`, `var(--accent-soft)`, etc., set at `:root`. Dark mode,
the 8 accent presets, and the 3 card themes are just attribute-selector
overrides of those same variables (`[data-theme="dark"]`,
`[data-accent="rose"]`, `[data-card-theme="bold"]`).

**Navigation** lives in one place: `templates/base.html`'s sidebar,
shared by every page via `{% extends "base.html" %}`. Active-page
highlighting uses `request.resolver_match.url_name` — no JavaScript
required.

---

## License

Personal project — add a license here if you plan to share or open-source it (MIT is a common permissive choice for a project like this).
