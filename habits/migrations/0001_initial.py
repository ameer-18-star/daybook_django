import uuid
from datetime import time as dt_time

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Habit',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('text', models.CharField(max_length=140)),
                ('habit_type', models.CharField(choices=[
                    ('yes_no', 'Yes / No'), ('numeric', 'Numeric'), ('checklist', 'Checklist'),
                ], default='yes_no', max_length=10)),
                ('section', models.CharField(choices=[
                    ('have_to_do', 'Have To Do'), ('need_to_do', 'Need To Do'), ('would_do', 'Would Do'),
                ], default='need_to_do', max_length=20)),
                ('scheduled_time', models.TimeField(blank=True, null=True)),
                ('duration_minutes', models.PositiveIntegerField(
                    blank=True, null=True,
                    help_text='Expected duration in minutes, used for the Swimlane Timeline and total-load stats.',
                )),
                ('target_value', models.FloatField(blank=True, null=True)),
                ('target_unit', models.CharField(blank=True, default='', max_length=30)),
                ('order', models.PositiveIntegerField(default=0)),
                ('paused', models.BooleanField(default=False)),
                ('paused_until', models.DateField(
                    blank=True, help_text='Optional auto-resume date. Leave blank for an indefinite pause.', null=True,
                )),
                ('archived', models.BooleanField(default=False)),
                ('grace_days_allowed', models.PositiveIntegerField(default=0)),
                ('color', models.CharField(blank=True, choices=[
                    ('teal', 'Teal'), ('blue', 'Blue'), ('purple', 'Purple'), ('rose', 'Rose'),
                    ('amber', 'Amber'), ('green', 'Green'), ('slate', 'Slate'), ('clay', 'Clay'),
                ], max_length=10, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='habits', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['section', 'order', 'created_at']},
        ),
        migrations.CreateModel(
            name='HabitChecklistItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('text', models.CharField(max_length=140)),
                ('order', models.PositiveIntegerField(default=0)),
                ('habit', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='checklist_items', to='habits.habit',
                )),
            ],
            options={'ordering': ['order']},
        ),
        migrations.CreateModel(
            name='HabitEntry',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('date', models.DateField()),
                ('completed', models.BooleanField(default=False)),
                ('numeric_value', models.FloatField(blank=True, null=True)),
                ('checked_item_ids', models.JSONField(blank=True, default=list)),
                ('used_grace_day', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('note', models.TextField(blank=True, default='', max_length=1000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('habit', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='habits.habit',
                )),
            ],
            options={'ordering': ['-date']},
        ),
        migrations.AlterUniqueTogether(
            name='habitentry',
            unique_together={('habit', 'date')},
        ),
        migrations.CreateModel(
            name='UserSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accent_color', models.CharField(choices=[
                    ('teal', 'Teal'), ('blue', 'Blue'), ('purple', 'Purple'), ('rose', 'Rose'),
                    ('amber', 'Amber'), ('green', 'Green'), ('slate', 'Slate'), ('clay', 'Clay'),
                ], default='teal', max_length=10)),
                ('card_theme', models.CharField(choices=[
                    ('classic', 'Classic'), ('minimal', 'Minimal'), ('bold', 'Bold'),
                ], default='classic', max_length=10)),
                ('compact_mode', models.BooleanField(default=False)),
                ('dark_mode', models.BooleanField(
                    default=False,
                    help_text='Server-side mirror of the theme, for contexts without JS (e.g. the daily report '
                              'email). The in-app toggle is still the client-side localStorage switch already in use.',
                )),
                ('timeline_start_hour', models.PositiveSmallIntegerField(
                    default=6, validators=[django.core.validators.MinValueValidator(0),
                                            django.core.validators.MaxValueValidator(23)],
                )),
                ('timeline_end_hour', models.PositiveSmallIntegerField(
                    default=22, validators=[django.core.validators.MinValueValidator(1),
                                             django.core.validators.MaxValueValidator(24)],
                )),
                ('daily_report_enabled', models.BooleanField(default=False)),
                ('daily_report_time', models.TimeField(default=dt_time(7, 0))),
                ('daily_report_email', models.EmailField(
                    blank=True, default='', help_text="Leave blank to use the account's login email.", max_length=254,
                )),
                ('avatar', models.ImageField(blank=True, null=True, upload_to='avatars/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, related_name='habit_settings',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'verbose_name': 'User settings', 'verbose_name_plural': 'User settings'},
        ),
    ]
