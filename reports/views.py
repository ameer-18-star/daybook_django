import calendar
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from tasks.forms import CustomReportForm
from .analytics import aggregate, iso_week_range, month_range
from .pdf import render_to_pdf


WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def _weekly_context(request):
    today = timezone.localdate()
    ref_date = parse_date(request.GET.get('date', '')) or today
    week_start, week_end = iso_week_range(ref_date)
    iso_year, iso_week, _ = ref_date.isocalendar()
    agg = aggregate(week_start, week_end, today, request.user)

    prev_ref = week_start - timedelta(days=1)
    next_ref = week_end + timedelta(days=1)

    return {
        'title': 'Weekly Report',
        'period_label': f'ISO Week {iso_week:02d}, {iso_year} '
                        f'({week_start.strftime("%b %d")} \u2013 {week_end.strftime("%b %d, %Y")})',
        'report_type': 'weekly',
        'today': today,
        'weekday_labels': WEEKDAY_LABELS,
        'prev_url': f"?date={prev_ref.isoformat()}",
        'next_url': f"?date={next_ref.isoformat()}",
        'show_next': week_end < today,
        **agg,
    }


def _monthly_context(request):
    today = timezone.localdate()
    ref_date = parse_date(request.GET.get('date', '')) or today
    month_start, month_end = month_range(ref_date)
    agg = aggregate(month_start, month_end, today, request.user)

    prev_ref = month_start - timedelta(days=1)
    next_ref = month_end + timedelta(days=1)

    return {
        'title': 'Monthly Report',
        'period_label': f'{calendar.month_name[ref_date.month]} {ref_date.year}',
        'report_type': 'monthly',
        'today': today,
        'weekday_labels': WEEKDAY_LABELS,
        'prev_url': f"?date={prev_ref.isoformat()}",
        'next_url': f"?date={next_ref.isoformat()}",
        'show_next': month_end < today,
        **agg,
    }


def _custom_context(request):
    today = timezone.localdate()
    default_start = today - timedelta(days=29)
    start = parse_date(request.GET.get('start', '')) or default_start
    end = parse_date(request.GET.get('end', '')) or today
    if start > end:
        start, end = end, start
    if (end - start).days > 366:
        start = end - timedelta(days=366)

    agg = aggregate(start, end, today, request.user)
    form = CustomReportForm(initial={'start': start, 'end': end})

    return {
        'title': 'Custom Report',
        'period_label': f'{start.strftime("%b %d, %Y")} \u2013 {end.strftime("%b %d, %Y")}',
        'report_type': 'custom',
        'today': today,
        'weekday_labels': WEEKDAY_LABELS,
        'custom_form': form,
        **agg,
    }


@login_required
def weekly_report(request):
    return render(request, 'reports/report.html', _weekly_context(request))


@login_required
def monthly_report(request):
    return render(request, 'reports/report.html', _monthly_context(request))


@login_required
def custom_report(request):
    return render(request, 'reports/report.html', _custom_context(request))


@login_required
def weekly_report_pdf(request):
    ctx = _weekly_context(request)
    return render_to_pdf('reports/report_pdf.html', ctx, f"daybook-weekly-{ctx['start']}.pdf")


@login_required
def monthly_report_pdf(request):
    ctx = _monthly_context(request)
    return render_to_pdf('reports/report_pdf.html', ctx, f"daybook-monthly-{ctx['start']}.pdf")


@login_required
def custom_report_pdf(request):
    ctx = _custom_context(request)
    return render_to_pdf('reports/report_pdf.html', ctx, f"daybook-custom-{ctx['start']}.pdf")
