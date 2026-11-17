from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from transactions.models import Budget, Category, Transaction


class SignUpViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.signup_url = reverse('signup')
        self.login_url = reverse('login')

    def test_signup_page_renders_correctly(self):
        response = self.client.get(self.signup_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/signup.html')

    def test_signup_successful_creates_user_and_redirects(self):
        data = {
            'username': 'newuser',
            'password1': 'SecurePassword123!',
            'password2': 'SecurePassword123!',
        }
        response = self.client.post(self.signup_url, data=data)
        self.assertRedirects(response, self.login_url)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_signup_password_mismatch_shows_error(self):
        data = {
            'username': 'mismatchuser',
            'password1': 'Password123!',
            'password2': 'DifferentPassword456!',
        }
        response = self.client.post(self.signup_url, data=data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='mismatchuser').exists())


class DashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.dashboard_url = reverse('dashboard')
        self.user = User.objects.create_user(username='testdashboard', password='password123')
        self.other_user = User.objects.create_user(username='otheruser', password='password123')

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_authenticated_user_accesses_dashboard_empty_state(self):
        self.client.login(username='testdashboard', password='password123')
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/dashboard.html')
        self.assertEqual(len(response.context['transactions']), 0)
        self.assertEqual(response.context['chart_labels'], [])
        self.assertEqual(response.context['chart_data'], [])
        self.assertIsNone(response.context['forecasted_spending'])

    def test_dashboard_with_transactions_and_budgets(self):
        self.client.login(username='testdashboard', password='password123')
        cat_food = Category.objects.create(user=self.user, name='Food')
        cat_travel = Category.objects.create(user=self.user, name='Travel')

        # Create budget
        Budget.objects.create(user=self.user, category=cat_food, amount=Decimal('5000.00'))

        # Create transactions for this month
        Transaction.objects.create(
            user=self.user,
            category=cat_food,
            amount=Decimal('4000.00'),
            transaction_type='expense',
            description='Zomato order'
        )
        Transaction.objects.create(
            user=self.user,
            category=cat_travel,
            amount=Decimal('1500.00'),
            transaction_type='expense',
            description='Uber ride'
        )
        # Income transaction
        Transaction.objects.create(
            user=self.user,
            amount=Decimal('50000.00'),
            transaction_type='income',
            description='Salary'
        )

        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['transactions']), 3)

        # Budget progress should show warning (4000/5000 = 80%)
        budget_progress = response.context['budget_progress']
        self.assertEqual(len(budget_progress), 1)
        self.assertEqual(budget_progress[0]['category_name'], 'Food')
        self.assertEqual(budget_progress[0]['percentage'], 80.0)
        self.assertEqual(budget_progress[0]['bar_color_class'], 'warning')

    def test_budget_progress_color_classes(self):
        self.client.login(username='testdashboard', password='password123')
        cat_under = Category.objects.create(user=self.user, name='UnderBudget')
        cat_warn = Category.objects.create(user=self.user, name='WarnBudget')
        cat_danger = Category.objects.create(user=self.user, name='DangerBudget')

        Budget.objects.create(user=self.user, category=cat_under, amount=Decimal('1000.00'))
        Budget.objects.create(user=self.user, category=cat_warn, amount=Decimal('1000.00'))
        Budget.objects.create(user=self.user, category=cat_danger, amount=Decimal('1000.00'))

        # 50% spent -> success
        Transaction.objects.create(user=self.user, category=cat_under, amount=Decimal('500.00'), transaction_type='expense', description='T1')
        # 85% spent -> warning
        Transaction.objects.create(user=self.user, category=cat_warn, amount=Decimal('850.00'), transaction_type='expense', description='T2')
        # 120% spent -> danger
        Transaction.objects.create(user=self.user, category=cat_danger, amount=Decimal('1200.00'), transaction_type='expense', description='T3')

        response = self.client.get(self.dashboard_url)
        progress_map = {item['category_name']: item['bar_color_class'] for item in response.context['budget_progress']}
        self.assertEqual(progress_map['UnderBudget'], 'success')
        self.assertEqual(progress_map['WarnBudget'], 'warning')
        self.assertEqual(progress_map['DangerBudget'], 'danger')
