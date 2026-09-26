import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'daybook.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(username='testadmin')

client = Client()
logged_in = client.login(username='testadmin', password='testpass123')
print(f"Login via test Client: {'OK' if logged_in else 'FAILED'}")
print()

# Top-level pages to smoke test, per the requested list
pages = [
    ("Tasks (index)",            "/"),
    ("Habits (list)",            "/habits/"),
    ("Timeline",                 "/habits/timeline/"),
    ("Stats overview",           "/habits/stats/"),
    ("Yearly Calendar",          "/habits/calendar/"),
    ("Journal list",             "/habits/journal/"),
    ("Journal entry (today)",    None),  # filled in below with today's date
    ("Profile",                  "/habits/profile/"),
    ("Backup & Restore",         "/habits/backup/"),
    ("Badges",                   "/habits/badges/"),
    ("Weekly Review",            "/habits/review/"),
    ("Weekly report",            "/reports/weekly/"),
    ("Monthly report",           "/reports/monthly/"),
    ("Custom report",            "/reports/custom/"),
    ("Recurring Tasks",          "/recurring-tasks/"),
]

import datetime
today = datetime.date.today()
pages[6] = ("Journal entry (today)", f"/habits/journal/{today.year}/{today.month}/{today.day}/")

results = []
for label, url in pages:
    try:
        resp = client.get(url, follow=False)
        status = resp.status_code
        error_detail = ""
        if status >= 500:
            # Try to extract the exception message/type from the DEBUG=True error page or exc_info
            content = resp.content.decode('utf-8', errors='replace')
            # crude extraction of the traceback summary line Django puts in <title> or exception_type
            import re
            m = re.search(r'<title>(.*?)</title>', content, re.DOTALL)
            error_detail = m.group(1).strip() if m else content[:300]
        results.append((label, url, status, error_detail))
    except Exception as e:
        results.append((label, url, "EXCEPTION", f"{type(e).__name__}: {e}"))

print(f"{'PAGE':<28} {'URL':<45} {'STATUS':<8} DETAIL")
print("-" * 120)
for label, url, status, detail in results:
    print(f"{label:<28} {url:<45} {str(status):<8} {detail[:80]}")
