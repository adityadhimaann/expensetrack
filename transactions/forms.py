from django import forms
from django.utils import timezone
from .models import Transaction, Category


class CategoryForm(forms.ModelForm):
    """
    A simple form for creating a new Category.
    """
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g., Groceries, Salary', 'class': 'form-control'}),
        }


class TransactionForm(forms.ModelForm):
    """
    A form for creating and updating Transaction instances.
    """
    class Meta:
        model = Transaction
        fields = ['transaction_type', 'amount', 'description', 'category', 'date']
        widgets = {
            'date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(TransactionForm, self).__init__(*args, **kwargs)

        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)

        self.fields['category'].empty_label = "Select a Category (Optional)"

        # Accept formats from HTML5 datetime-local input
        self.fields['date'].input_formats = [
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
        ]

        # Format date for HTML5 datetime-local widget when rendering unbound forms
        if not self.is_bound:
            if not self.instance.pk and 'date' not in self.initial:
                self.initial['date'] = timezone.now().strftime('%Y-%m-%dT%H:%M')
            elif self.instance.pk and self.instance.date:
                self.initial['date'] = self.instance.date.strftime('%Y-%m-%dT%H:%M')

        # Add Bootstrap styling classes
        for field_name, field in self.fields.items():
            existing_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing_class + ' form-control').strip()
