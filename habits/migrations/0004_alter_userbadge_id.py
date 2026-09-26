from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('habits', '0003_journal_review_badges'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userbadge',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
