import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

DAY_CHOICES = [
    (0, 'Mon'), (1, 'Tue'), (2, 'Wed'), (3, 'Thu'),
    (4, 'Fri'), (5, 'Sat'), (6, 'Sun'),
]

TAG_COLOR_CHOICES = [
    ('teal', 'Teal'), ('amber', 'Amber'), ('clay', 'Clay'),
    ('blue', 'Blue'), ('purple', 'Purple'), ('slate', 'Slate'),
]


class Tag(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tags')
    name = models.CharField(max_length=30)
    color = models.CharField(max_length=10, choices=TAG_COLOR_CHOICES, default='teal')

    class Meta:
        ordering = ['name']
        unique_together = [('owner', 'name')]

    def __str__(self):
        return self.name


class TaskTemplate(models.Model):
    """A recurring-task definition ('habit'). Materialized into real Task
    rows for 'today' each time a user loads the app (idempotent)."""
    RECURRENCE_CHOICES = [
        ('daily', 'Every day'),
        ('weekdays', 'Weekdays (Mon–Fri)'),
        ('custom', 'Custom days'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='task_templates')
    text = models.CharField(max_length=140)
    category = models.CharField(max_length=20, default='Work')
    priority = models.CharField(max_length=10, default='Medium')
    recurrence_type = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, default='daily')
    days_of_week = models.CharField(
        max_length=20, blank=True, default='',
        help_text="Comma-separated day numbers for 'custom' recurrence, Mon=0..Sun=6, e.g. '0,2,4'",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.text} ({self.get_recurrence_type_display()})'

    def occurs_on(self, d) -> bool:
        if not self.active:
            return False
        if self.recurrence_type == 'daily':
            return True
        if self.recurrence_type == 'weekdays':
            return d.isoweekday() <= 5
        if self.recurrence_type == 'custom':
            days = {int(x) for x in self.days_of_week.split(',') if x.strip().isdigit()}
            return (d.isoweekday() - 1) in days
        return False


class Task(models.Model):
    CATEGORY_CHOICES = [
        ('Work', 'Work'),
        ('Personal', 'Personal'),
        ('Fitness', 'Fitness'),
        ('Other', 'Other'),
    ]
    PRIORITY_CHOICES = [
        ('High', 'High'),
        ('Medium', 'Medium'),
        ('Low', 'Low'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='tasks', null=True, blank=True,
    )
    text = models.CharField(max_length=140)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='Work')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    completed = models.BooleanField(default=False)
    date = models.DateField(default=timezone.localdate)
    due_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(max_length=2000, blank=True, default='')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='subtasks',
    )
    template = models.ForeignKey(
        TaskTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_tasks',
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        status = '✓' if self.completed else '○'
        return f'[{status}] {self.text[:40]} ({self.date})'

    @property
    def is_overdue(self) -> bool:
        if self.completed or not self.due_time:
            return False
        now = timezone.localtime()
        return self.date == now.date() and self.due_time < now.time()

    @property
    def is_due_soon(self) -> bool:
        """Due within the next hour, today, not yet completed."""
        if self.completed or not self.due_time:
            return False
        now = timezone.localtime()
        if self.date != now.date():
            return False
        due_dt = timezone.make_aware(timezone.datetime.combine(self.date, self.due_time))
        delta = due_dt - now
        return timedelta(0) <= delta <= timedelta(hours=1)

    def to_dict(self):
        return {
            'id': str(self.id),
            'text': self.text,
            'category': self.category,
            'priority': self.priority,
            'completed': self.completed,
            'createdAt': self.created_at.isoformat(),
            'date': self.date.isoformat(),
            'dueTime': self.due_time.strftime('%H:%M') if self.due_time else None,
            'notes': self.notes,
            'tags': [t.name for t in self.tags.all()],
            'parentId': str(self.parent_id) if self.parent_id else None,
        }


class Streak(models.Model):
    """One row per user. owner is nullable so the pre-upgrade singleton
    row (from single-user installs) can coexist harmlessly — it's simply
    ignored by the app once every user gets their own row via get_for()."""
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='streak', null=True, blank=True,
    )
    last_completion_date = models.DateField(null=True, blank=True)
    current = models.PositiveIntegerField(default=0)

    @classmethod
    def get_for(cls, user):
        obj, _ = cls.objects.get_or_create(owner=user)
        return obj

    def __str__(self):
        return f'{self.owner}: {self.current} days (last: {self.last_completion_date})'
