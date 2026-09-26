from django import forms
from django.contrib.auth import get_user_model

from .models import Habit, JournalEntry, UserSettings

User = get_user_model()

class HabitForm(forms.ModelForm):
    checklist_items_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'notes-textarea', 'rows': 4,
            'placeholder': 'One checklist item per line, e.g.\nStretch\nMeditate\nJournal',
        }),
        label='Checklist items',
    )

    has_scheduled_time = forms.BooleanField(required=False, label='Assign a specific time')

    class Meta:
        model = Habit
        fields = [
            'text', 'habit_type', 'section', 'scheduled_time', 'duration_minutes',
            'target_value', 'target_unit', 'grace_days_allowed', 'color',
        ]
        widgets = {
            'text': forms.TextInput(attrs={'class': 'task-text-input', 'maxlength': 140}),
            'habit_type': forms.Select(attrs={'class': 'select'}),
            'section': forms.Select(attrs={'class': 'select'}),
            'scheduled_time': forms.TimeInput(attrs={'class': 'select', 'type': 'time'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'select', 'min': 1, 'placeholder': 'minutes'}),
            'target_value': forms.NumberInput(attrs={'class': 'select', 'step': 'any', 'placeholder': 'target'}),
            'target_unit': forms.TextInput(attrs={'class': 'select', 'placeholder': 'unit e.g. glasses'}),
            'grace_days_allowed': forms.NumberInput(attrs={'class': 'select', 'min': 0}),
            'color': forms.Select(attrs={'class': 'select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['color'].required = False
        self.fields['duration_minutes'].required = False
        self.fields['target_value'].required = False
        self.fields['target_unit'].required = False

        instance = kwargs.get('instance')
        if instance and instance.pk:
            self.fields['has_scheduled_time'].initial = instance.is_scheduled
            if instance.habit_type == 'checklist':
                self.fields['checklist_items_text'].initial = '\n'.join(
                    item.text for item in instance.checklist_items.all()
                )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('has_scheduled_time'):
            cleaned['scheduled_time'] = None
        elif not cleaned.get('scheduled_time'):
            self.add_error('scheduled_time', 'Set a time, or uncheck "Assign a specific time".')

        habit_type = cleaned.get('habit_type')
        if habit_type == 'numeric' and cleaned.get('target_value') is None:
            self.add_error('target_value', 'Numeric habits need a target value (e.g. 8 glasses).')
        if habit_type == 'checklist' and not cleaned.get('checklist_items_text', '').strip():
            self.add_error('checklist_items_text', 'Add at least one checklist item.')
        return cleaned

    def parsed_checklist_items(self) -> list[str]:
        raw = self.cleaned_data.get('checklist_items_text', '')
        return [line.strip() for line in raw.splitlines() if line.strip()]


class JournalEntryForm(forms.ModelForm):
    class Meta:
        model = JournalEntry
        fields = ['mood', 'text']
        widgets = {
            'mood': forms.Select(attrs={'class': 'select'}),
            'text': forms.Textarea(attrs={'class': 'notes-textarea', 'rows': 10, 'placeholder': "What's on your mind today?"}),
        }

class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'task-text-input'}),
            'email': forms.EmailInput(attrs={'class': 'task-text-input'}),
        }

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('That username is already taken.')
        return username


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = [
            'accent_color', 'card_theme', 'compact_mode',
            'timeline_start_hour', 'timeline_end_hour',
            'daily_report_enabled', 'daily_report_time', 'daily_report_email',
            'avatar',
        ]
        widgets = {
            'accent_color': forms.Select(attrs={'class': 'select'}),
            'card_theme': forms.Select(attrs={'class': 'select'}),
            'timeline_start_hour': forms.NumberInput(attrs={'class': 'select', 'min': 0, 'max': 23}),
            'timeline_end_hour': forms.NumberInput(attrs={'class': 'select', 'min': 1, 'max': 24}),
            'daily_report_time': forms.TimeInput(attrs={'class': 'select', 'type': 'time'}),
            'daily_report_email': forms.EmailInput(attrs={
                'class': 'task-text-input', 'placeholder': "defaults to your account's login email",
            }),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and hasattr(avatar, 'content_type') and avatar.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Image must be under 5MB.')
        return avatar
