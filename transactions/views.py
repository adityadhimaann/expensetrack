import csv
import json
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView
from django.views.generic.edit import DeleteView, UpdateView

from .categorizer import TransactionCategorizer
from .forms import CategoryForm, TransactionForm
from .models import Budget, Category, Keyword, Transaction


class AddCategoryView(LoginRequiredMixin, View):
    """
    API endpoint for adding a category via modal AJAX request.
    """
    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8') if request.body else '{}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)

        form = CategoryForm(data)
        if form.is_valid():
            category_name = form.cleaned_data['name'].strip()
            if Category.objects.filter(user=request.user, name__iexact=category_name).exists():
                return JsonResponse({'status': 'error', 'message': 'This category already exists.'}, status=400)
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            return JsonResponse({'status': 'success', 'category_id': category.id, 'category_name': category.name})
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid data submitted.'}, status=400)


class AddTransactionView(LoginRequiredMixin, View):
    """
    Handles recording a new transaction.
    """
    def get(self, request):
        form = TransactionForm(user=request.user)
        return render(request, 'transactions/add_transaction.html', {'form': form})

    def post(self, request):
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            messages.success(request, 'Transaction saved successfully!')
            return redirect('dashboard')
        messages.error(request, 'Please correct the errors in the form.')
        return render(request, 'transactions/add_transaction.html', {'form': form})


class SuggestCategoryView(LoginRequiredMixin, View):
    """
    Suggests category based on transaction description using custom and default rules.
    """
    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8') if request.body else '{}')
            description = data.get('description', '').strip()
            if not description:
                return JsonResponse({'status': 'error', 'message': 'Description is empty.'}, status=400)

            user_categories = Category.objects.filter(user=request.user)
            user_keywords = Keyword.objects.filter(user=request.user)
            
            categorizer = TransactionCategorizer(user_categories, user_keywords)
            suggested_category_id = categorizer.suggest_category(description)

            if suggested_category_id:
                return JsonResponse({'status': 'success', 'category_id': suggested_category_id})
            return JsonResponse({'status': 'no_suggestion'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class ManageRulesView(LoginRequiredMixin, ListView):
    """
    Lists categories with their associated smart keyword rules and allows add/delete.
    """
    model = Category
    template_name = 'transactions/manage_rules.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user).prefetch_related('keywords')

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        if action == 'add_keyword':
            category_id = request.POST.get('category_id')
            keyword_text = request.POST.get('keyword_text', '').strip().lower()
            if not keyword_text:
                messages.warning(request, 'Keyword text cannot be empty.')
                return redirect(reverse('manage_rules'))
            category = get_object_or_404(Category, id=category_id, user=request.user)
            if not Keyword.objects.filter(user=request.user, text=keyword_text).exists():
                Keyword.objects.create(user=request.user, category=category, text=keyword_text)
                messages.success(request, f"Rule added: '{keyword_text}' -> {category.name}")
            else:
                messages.warning(request, f"Keyword '{keyword_text}' already exists.")
        elif action == 'delete_keyword':
            keyword_id = request.POST.get('keyword_id')
            keyword = get_object_or_404(Keyword, id=keyword_id, user=request.user)
            keyword.delete()
            messages.success(request, 'Rule deleted.')
        return redirect(reverse('manage_rules'))


class UpdateTransactionView(LoginRequiredMixin, UpdateView):
    """
    Allows user to edit their own existing transaction.
    """
    model = Transaction
    form_class = TransactionForm
    template_name = 'transactions/edit_transaction.html'
    success_url = reverse_lazy('dashboard')

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Transaction updated successfully!')
        return super().form_valid(form)


class DeleteTransactionView(LoginRequiredMixin, DeleteView):
    """
    Allows user to delete their own existing transaction.
    """
    model = Transaction
    template_name = 'transactions/transaction_confirm_delete.html'
    success_url = reverse_lazy('dashboard')

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Transaction deleted successfully!')
        return super().form_valid(form)


class ExportTransactionsCSVView(LoginRequiredMixin, View):
    """
    Exports the user's transactions as a downloadable CSV file.
    """
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="transactions.csv"'

        writer = csv.writer(response)
        writer.writerow(['Date', 'Description', 'Category', 'Type', 'Amount'])

        transactions = Transaction.objects.filter(user=request.user).order_by('date')
        for transaction in transactions:
            writer.writerow([
                transaction.date.strftime('%Y-%m-%d %H:%M'),
                transaction.description,
                transaction.category.name if transaction.category else 'N/A',
                transaction.transaction_type,
                transaction.amount
            ])

        return response


class ManageBudgetsView(LoginRequiredMixin, View):
    """
    Allows user to configure monthly budget limits per category.
    """
    template_name = 'transactions/manage_budgets.html'

    def get(self, request, *args, **kwargs):
        categories = Category.objects.filter(user=request.user)
        budgets = Budget.objects.filter(user=request.user)
        budget_map = {budget.category.id: budget.amount for budget in budgets}
        
        context = {
            'categories': categories,
            'budget_map': budget_map,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        for key, value in request.POST.items():
            if key.startswith('budget_'):
                category_id = key.split('_')[1]
                try:
                    category = Category.objects.get(id=category_id, user=request.user)
                    amount = float(value) if value else 0.0
                    Budget.objects.update_or_create(
                        user=request.user,
                        category=category,
                        defaults={'amount': amount}
                    )
                except (Category.DoesNotExist, ValueError):
                    continue
        messages.success(request, 'Budgets updated successfully!')
        return redirect('manage_budgets')
