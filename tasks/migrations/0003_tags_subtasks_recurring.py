import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tasks', '0002_add_owner'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30)),
                ('color', models.CharField(choices=[
                    ('teal', 'Teal'), ('amber', 'Amber'), ('clay', 'Clay'),
                    ('blue', 'Blue'), ('purple', 'Purple'), ('slate', 'Slate'),
                ], default='teal', max_length=10)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                             related_name='tags', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.AlterUniqueTogether(
            name='tag',
            unique_together={('owner', 'name')},
        ),
        migrations.CreateModel(
            name='TaskTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('text', models.CharField(max_length=140)),
                ('category', models.CharField(default='Work', max_length=20)),
                ('priority', models.CharField(default='Medium', max_length=10)),
                ('recurrence_type', models.CharField(choices=[
                    ('daily', 'Every day'), ('weekdays', 'Weekdays (Mon–Fri)'), ('custom', 'Custom days'),
                ], default='daily', max_length=10)),
                ('days_of_week', models.CharField(
                    blank=True, default='', max_length=20,
                    help_text="Comma-separated day numbers for 'custom' recurrence, Mon=0..Sun=6, e.g. '0,2,4'",
                )),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                             related_name='task_templates', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddField(
            model_name='task',
            name='due_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='notes',
            field=models.TextField(blank=True, default='', max_length=2000),
        ),
        migrations.AddField(
            model_name='task',
            name='parent',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='subtasks', to='tasks.task',
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='template',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='generated_tasks', to='tasks.tasktemplate',
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='tasks', to='tasks.tag'),
        ),
    ]
