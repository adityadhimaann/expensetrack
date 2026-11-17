import json
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .categorizer import TransactionCategorizer
from .forecaster import SpendingForecaster
from .forms import CategoryForm, TransactionForm
from .models import Budget, Category, Keyword, Transaction


class ModelAndFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='modeluser', password='password123')
        self.other_user = User.objects.create_user(username='othermodeluser', password='password123')

    def test_category_creation_and_uniqueness(self):
        cat1 = Category.objects.create(user=self.user, name='Food')
        self.assertEqual(str(cat1), 'Food')

        # Same user duplicate name raises IntegrityError
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(user=self.user, name='Food')

        # Different user can have the same category name
        cat_other = Category.objects.create(user=self.other_user, name='Food')
        self.assertEqual(cat_other.name, 'Food')

    def test_transaction_form_filters_user_categories(self):
        Category.objects.create(user=self.user, name='User Category')
        Category.objects.create(user=self.other_user, name='Other Category')

        form = TransactionForm(user=self.user)
        categories = list(form.fields['category'].queryset.values_list('name', flat=True))
        self.assertIn('User Category', categories)
        self.assertNotIn('Other Category', categories)


class AddTransactionViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='txuser', password='password123')
        self.category = Category.objects.create(user=self.user, name='Groceries')
        self.add_url = reverse('add_transaction')

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.add_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_get_add_transaction_page(self):
        self.client.login(username='txuser', password='password123')
        response = self.client.get(self.add_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'transactions/add_transaction.html')

    def test_post_add_transaction_success(self):
        self.client.login(username='txuser', password='password123')
        post_data = {
            'transaction_type': 'expense',
            'amount': '350.50',
            'description': 'Supermarket apples & bananas',
            'category': str(self.category.id),
            'date': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        }
        response = self.client.post(self.add_url, data=post_data)
        self.assertRedirects(response, reverse('dashboard'))

        tx = Transaction.objects.get(description='Supermarket apples & bananas')
        self.assertEqual(tx.user, self.user)
        self.assertEqual(tx.amount, Decimal('350.50'))
        self.assertEqual(tx.category, self.category)

    def test_post_add_transaction_invalid(self):
        self.client.login(username='txuser', password='password123')
        post_data = {
            'transaction_type': 'expense',
            'amount': '',  # missing amount
            'description': '',
        }
        response = self.client.post(self.add_url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.filter(user=self.user).exists())


class UpdateAndDeleteTransactionViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='owner', password='password123')
        self.other_user = User.objects.create_user(username='intruder', password='password123')

        self.category = Category.objects.create(user=self.user, name='Bills')
        self.tx = Transaction.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal('500.00'),
            transaction_type='expense',
            description='Original Electricity Bill'
        )

    def test_owner_can_update_transaction(self):
        self.client.login(username='owner', password='password123')
        edit_url = reverse('edit_transaction', kwargs={'pk': self.tx.id})
        post_data = {
            'transaction_type': 'expense',
            'amount': '620.00',
            'description': 'Updated Electricity Bill',
            'category': str(self.category.id),
            'date': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        }
        response = self.client.post(edit_url, data=post_data)
        self.assertRedirects(response, reverse('dashboard'))
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.amount, Decimal('620.00'))
        self.assertEqual(self.tx.description, 'Updated Electricity Bill')

    def test_non_owner_cannot_update_transaction(self):
        self.client.login(username='intruder', password='password123')
        edit_url = reverse('edit_transaction', kwargs={'pk': self.tx.id})
        response = self.client.get(edit_url)
        self.assertEqual(response.status_code, 404)

    def test_owner_can_delete_transaction(self):
        self.client.login(username='owner', password='password123')
        delete_url = reverse('delete_transaction', kwargs={'pk': self.tx.id})
        response = self.client.post(delete_url)
        self.assertRedirects(response, reverse('dashboard'))
        self.assertFalse(Transaction.objects.filter(id=self.tx.id).exists())

    def test_non_owner_cannot_delete_transaction(self):
        self.client.login(username='intruder', password='password123')
        delete_url = reverse('delete_transaction', kwargs={'pk': self.tx.id})
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Transaction.objects.filter(id=self.tx.id).exists())


class AddCategoryViewAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='catuser', password='password123')
        self.add_cat_url = reverse('add_category')

    def test_add_category_success(self):
        self.client.login(username='catuser', password='password123')
        payload = json.dumps({'name': 'Fitness'})
        response = self.client.post(self.add_cat_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['category_name'], 'Fitness')
        self.assertTrue(Category.objects.filter(user=self.user, name='Fitness').exists())

    def test_add_duplicate_category_fails(self):
        self.client.login(username='catuser', password='password123')
        Category.objects.create(user=self.user, name='Fitness')
        payload = json.dumps({'name': 'fitness'})  # case-insensitive check
        response = self.client.post(self.add_cat_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('already exists', response.json()['message'])

    def test_add_category_invalid_json(self):
        self.client.login(username='catuser', password='password123')
        response = self.client.post(self.add_cat_url, data='not-json', content_type='application/json')
        self.assertEqual(response.status_code, 400)


class SuggestCategoryViewAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='suggestuser', password='password123')
        self.suggest_url = reverse('suggest_category')

        self.cat_food = Category.objects.create(user=self.user, name='Food')
        self.cat_transport = Category.objects.create(user=self.user, name='Transport')

        # Custom keyword
        Keyword.objects.create(user=self.user, category=self.cat_transport, text='rickshaw')

    def test_suggest_category_custom_keyword(self):
        self.client.login(username='suggestuser', password='password123')
        payload = json.dumps({'description': 'Paid rickshaw ride home'})
        response = self.client.post(self.suggest_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['category_id'], self.cat_transport.id)

    def test_suggest_category_default_fallback(self):
        self.client.login(username='suggestuser', password='password123')
        payload = json.dumps({'description': 'Zomato order delivery'})
        response = self.client.post(self.suggest_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['category_id'], self.cat_food.id)

    def test_suggest_category_no_suggestion(self):
        self.client.login(username='suggestuser', password='password123')
        payload = json.dumps({'description': 'Random unmapped transaction'})
        response = self.client.post(self.suggest_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'no_suggestion')

    def test_suggest_category_empty_description(self):
        self.client.login(username='suggestuser', password='password123')
        payload = json.dumps({'description': ''})
        response = self.client.post(self.suggest_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 400)


class ManageRulesAndBudgetsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='ruleuser', password='password123')
        self.client.login(username='ruleuser', password='password123')
        self.cat = Category.objects.create(user=self.user, name='Food')
        self.rules_url = reverse('manage_rules')
        self.budgets_url = reverse('manage_budgets')

    def test_add_and_delete_keyword_rule(self):
        # Add keyword
        response = self.client.post(self.rules_url, data={
            'action': 'add_keyword',
            'category_id': str(self.cat.id),
            'keyword_text': 'haldiram'
        })
        self.assertRedirects(response, self.rules_url)
        kw = Keyword.objects.get(user=self.user, text='haldiram')
        self.assertEqual(kw.category, self.cat)

        # Delete keyword
        del_response = self.client.post(self.rules_url, data={
            'action': 'delete_keyword',
            'keyword_id': str(kw.id)
        })
        self.assertRedirects(del_response, self.rules_url)
        self.assertFalse(Keyword.objects.filter(id=kw.id).exists())

    def test_manage_budgets_get_and_post(self):
        get_resp = self.client.get(self.budgets_url)
        self.assertEqual(get_resp.status_code, 200)

        post_resp = self.client.post(self.budgets_url, data={
            f'budget_{self.cat.id}': '7500.00'
        })
        self.assertRedirects(post_resp, self.budgets_url)
        budget = Budget.objects.get(user=self.user, category=self.cat)
        self.assertEqual(budget.amount, Decimal('7500.00'))


class ExportCSVTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='csvuser', password='password123')
        self.client.login(username='csvuser', password='password123')
        cat = Category.objects.create(user=self.user, name='Utilities')
        Transaction.objects.create(
            user=self.user,
            category=cat,
            amount=Decimal('1200.00'),
            transaction_type='expense',
            description='Water bill'
        )

    def test_export_csv_view(self):
        response = self.client.get(reverse('export_transactions_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="transactions.csv"', response['Content-Disposition'])
        content = response.content.decode('utf-8')
        self.assertIn('Water bill', content)
        self.assertIn('Utilities', content)
        self.assertIn('1200.00', content)


class SpendingForecasterUnitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='forecastuser', password='password123')

    def test_empty_transactions_returns_none(self):
        forecaster = SpendingForecaster(Transaction.objects.filter(user=self.user))
        self.assertIsNone(forecaster.forecast_next_30_days())

    def test_short_history_uses_daily_average(self):
        now = timezone.now()
        Transaction.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            transaction_type='expense',
            description='Day 1',
            date=now - timedelta(days=2)
        )
        Transaction.objects.create(
            user=self.user,
            amount=Decimal('200.00'),
            transaction_type='expense',
            description='Day 2',
            date=now - timedelta(days=1)
        )
        forecaster = SpendingForecaster(Transaction.objects.filter(user=self.user))
        forecast = forecaster.forecast_next_30_days()
        self.assertIsNotNone(forecast)
        self.assertGreater(forecast, 0)

    def test_long_history_uses_sarima_model(self):
        now = timezone.now()
        txs = []
        for i in range(40):
            txs.append(Transaction(
                user=self.user,
                amount=Decimal(str(50 + (i % 7) * 20)),
                transaction_type='expense',
                description=f'Expense day {i}',
                date=now - timedelta(days=40 - i)
            ))
        Transaction.objects.bulk_create(txs)
        forecaster = SpendingForecaster(Transaction.objects.filter(user=self.user))
        forecast = forecaster.forecast_next_30_days()
        self.assertIsNotNone(forecast)
        self.assertGreater(forecast, 0)
