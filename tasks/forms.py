from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Task, TaskTemplate

User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'task-text-input')


class TaskTemplateForm(forms.ModelForm):
    # TaskTemplate.category/priority are plain CharFields with no `choices`
    # on the model, so a ModelForm-derived Select widget would render with
    # zero <option> tags. Declaring these explicitly (mirroring Task's own
    # choice lists, since a template materializes into a Task) gives the
    # dropdowns real options and makes the fields submit correctly.
    category = forms.ChoiceField(
        choices=Task.CATEGORY_CHOICES,
        initial='Work',
        widget=forms.Select(attrs={'class': 'select'}),
    )
    priority = forms.ChoiceField(
        choices=Task.PRIORITY_CHOICES,
        initial='Medium',
        widget=forms.Select(attrs={'class': 'select'}),
    )

    class Meta:
        model = TaskTemplate
        # 'active' intentionally excluded: it's never rendered by the
        # create form, and a BooleanField the form doesn't render still
        # gets included in cleaned_data as False (unchecked-checkbox
        # semantics), which silently overrode the model's default=True on
        # every new habit. Pausing/resuming already has its own dedicated
        # toggle endpoint — new habits should just start active.
        fields = ['text', 'category', 'priority', 'recurrence_type', 'days_of_week']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'task-text-input', 'maxlength': 140}),
            'recurrence_type': forms.Select(attrs={'class': 'select'}),
            'days_of_week': forms.TextInput(attrs={'class': 'task-text-input', 'placeholder': 'e.g. 0,2,4'}),
        }


class CustomReportForm(forms.Form):
    start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'select'}))
    end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'select'}))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start'), cleaned.get('end')
        if start and end and start > end:
            raise forms.ValidationError('Start date must be before end date.')
        if start and end and (end - start).days > 366:
            raise forms.ValidationError('Range too large — please pick up to one year.')
        return cleaned