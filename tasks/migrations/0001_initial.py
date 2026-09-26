import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('text', models.CharField(max_length=140)),
                ('category', models.CharField(
                    choices=[('Work','Work'),('Personal','Personal'),('Fitness','Fitness'),('Other','Other')],
                    default='Work', max_length=20)),
                ('priority', models.CharField(
                    choices=[('High','High'),('Medium','Medium'),('Low','Low')],
                    default='Medium', max_length=10)),
                ('completed', models.BooleanField(default=False)),
                ('date', models.DateField(default=django.utils.timezone.localdate)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.CreateModel(
            name='Streak',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_completion_date', models.DateField(blank=True, null=True)),
                ('current', models.PositiveIntegerField(default=0)),
            ],
        ),
    ]
