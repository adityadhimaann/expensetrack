import random
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from transactions.models import Budget, Category, Keyword, Transaction


class Command(BaseCommand):
    help = 'Populates the database with realistic sample categories, keywords, budgets, and transactions spanning 90 days.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Username of the account to attach records to (default: admin)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing transactions, budgets, keywords, and categories for this user before seeding'
        )

    def handle(self, *args, **options):
        username = options['username']
        clear = options['clear']

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': f'{username}@example.com'}
        )
        if created:
            user.set_password('admin123')
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created user '{username}' with default password 'admin123'"))
        else:
            self.stdout.write(f"Using existing user '{username}'")

        if clear:
            Transaction.objects.filter(user=user).delete()
            Budget.objects.filter(user=user).delete()
            Keyword.objects.filter(user=user).delete()
            Category.objects.filter(user=user).delete()
            self.stdout.write(self.style.WARNING(f"Cleared existing records for user '{username}'"))

        # 1. Categories Definition
        categories_data = [
            ('Food & Dining', 'expense'),
            ('Groceries', 'expense'),
            ('Transportation', 'expense'),
            ('Utilities & Bills', 'expense'),
            ('Entertainment', 'expense'),
            ('Shopping', 'expense'),
            ('Healthcare', 'expense'),
            ('Housing & Rent', 'expense'),
            ('Salary', 'income'),
            ('Freelance', 'income'),
            ('Investments', 'income'),
        ]

        category_objs = {}
        for cat_name, _ in categories_data:
            cat, _ = Category.objects.get_or_create(user=user, name=cat_name)
            category_objs[cat_name] = cat
        self.stdout.write(self.style.SUCCESS(f"Created/verified {len(category_objs)} categories."))

        # 2. Smart Keyword Rules
        keywords_map = {
            'Food & Dining': ['zomato', 'swiggy', 'starbucks', 'mcdonalds', 'burger', 'cafe', 'restaurant', 'kfc', 'pizza', 'subway', 'dine'],
            'Groceries': ['blinkit', 'zepto', 'instamart', 'bigbasket', 'supermarket', 'dmart', 'milk', 'vegetables', 'fruits'],
            'Transportation': ['uber', 'ola', 'rapido', 'metro', 'petrol', 'diesel', 'fuel', 'toll', 'parking', 'irctc'],
            'Utilities & Bills': ['electricity', 'airtel', 'jio', 'broadband', 'wifi', 'water bill', 'gas cylinder', 'tatasky'],
            'Entertainment': ['netflix', 'spotify', 'bookmyshow', 'cinema', 'prime video', 'youtube', 'hotstar', 'gaming'],
            'Shopping': ['amazon', 'flipkart', 'myntra', 'zara', 'clothing', 'electronics', 'sneakers'],
            'Healthcare': ['apollo', 'pharmacy', 'doctor', 'clinic', '1mg', 'hospital', 'medicine', 'dental'],
            'Housing & Rent': ['rent', 'landlord', 'society maintenance', 'lease'],
            'Salary': ['salary', 'payroll', 'monthly salary', 'bonus', 'stipend'],
            'Freelance': ['freelance', 'client payment', 'upwork', 'consulting'],
        }

        total_keywords = 0
        for cat_name, words in keywords_map.items():
            cat = category_objs.get(cat_name)
            if not cat:
                continue
            for word in words:
                _, created = Keyword.objects.get_or_create(user=user, text=word, defaults={'category': cat})
                if created:
                    total_keywords += 1
        self.stdout.write(self.style.SUCCESS(f"Created {total_keywords} smart keywords."))

        # 3. Monthly Budgets
        budgets_data = {
            'Food & Dining': 12000.00,
            'Groceries': 15000.00,
            'Transportation': 6000.00,
            'Utilities & Bills': 5000.00,
            'Entertainment': 4000.00,
            'Shopping': 10000.00,
            'Healthcare': 3000.00,
            'Housing & Rent': 25000.00,
        }

        for cat_name, amount in budgets_data.items():
            cat = category_objs.get(cat_name)
            if cat:
                Budget.objects.update_or_create(
                    user=user,
                    category=cat,
                    defaults={'amount': Decimal(str(amount))}
                )
        self.stdout.write(self.style.SUCCESS(f"Configured {len(budgets_data)} monthly budgets."))

        # 4. Realistic Transactions across past 90 days
        now = timezone.now()
        transactions_to_create = []

        # Fixed recurring monthly transactions
        for month_offset in [0, 1, 2]:
            month_date = now - timedelta(days=month_offset * 30 + 5)
            # Salary
            transactions_to_create.append(Transaction(
                user=user,
                category=category_objs['Salary'],
                transaction_type='income',
                amount=Decimal('78000.00'),
                description='Monthly Corporate Salary - Tech Corp',
                date=month_date.replace(day=1, hour=10, minute=0)
            ))
            # Rent
            transactions_to_create.append(Transaction(
                user=user,
                category=category_objs['Housing & Rent'],
                transaction_type='expense',
                amount=Decimal('25000.00'),
                description='Apartment Monthly Rent & Maintenance',
                date=month_date.replace(day=3, hour=11, minute=30)
            ))
            # Electricity Bill
            transactions_to_create.append(Transaction(
                user=user,
                category=category_objs['Utilities & Bills'],
                transaction_type='expense',
                amount=Decimal(str(round(random.uniform(2200, 3100), 2))),
                description='State Electricity Board Bill',
                date=month_date.replace(day=8, hour=14, minute=15)
            ))
            # Wifi Broadband
            transactions_to_create.append(Transaction(
                user=user,
                category=category_objs['Utilities & Bills'],
                transaction_type='expense',
                amount=Decimal('1199.00'),
                description='Airtel Fiber Broadband Bill',
                date=month_date.replace(day=10, hour=9, minute=45)
            ))
            # Mobile Recharge
            transactions_to_create.append(Transaction(
                user=user,
                category=category_objs['Utilities & Bills'],
                transaction_type='expense',
                amount=Decimal('749.00'),
                description='Jio 5G Prepaid Recharge Plan',
                date=month_date.replace(day=12, hour=16, minute=20)
            ))
            # Subscriptions
            transactions_to_create.append(Transaction(
                user=user,
                category=category_objs['Entertainment'],
                transaction_type='expense',
                amount=Decimal('649.00'),
                description='Netflix Premium 4K Plan',
                date=month_date.replace(day=15, hour=8, minute=0)
            ))
            transactions_to_create.append(Transaction(
                user=user,
                category=category_objs['Entertainment'],
                transaction_type='expense',
                amount=Decimal('119.00'),
                description='Spotify Individual Subscription',
                date=month_date.replace(day=16, hour=8, minute=15)
            ))
            # Freelance bonus
            if month_offset != 1:
                transactions_to_create.append(Transaction(
                    user=user,
                    category=category_objs['Freelance'],
                    transaction_type='income',
                    amount=Decimal(str(random.choice([14500.00, 18000.00, 22500.00]))),
                    description='UI/UX Design Consultation - Upwork Client',
                    date=month_date.replace(day=20, hour=18, minute=30)
                ))

        # Dynamic variable daily/weekly spending templates
        daily_expense_templates = [
            ('Food & Dining', ['Zomato Dinner Order - Biryani By Kilo', 'Swiggy Gourmet Lunch delivery', 'Starbucks Cold Brew & Bagel', 'McDonalds Burger & Fries Meal', 'Local Cafe Coffee & Pastry', 'Subway Roasted Chicken Sub'], (180, 850)),
            ('Groceries', ['Blinkit quick delivery - Milk & bread', 'Zepto 10-min fruits & vegetables', 'Instamart weekly groceries & spices', 'BigBasket monthly staple supplies', 'DMart household cleaning goods'], (250, 2800)),
            ('Transportation', ['Uber Cab to Cyber City Office', 'Ola Auto ride to metro station', 'Shell Petrol pump - Car fuel refill', 'Metro SmartCard Auto Recharge', 'Rapido Bike taxi ride'], (90, 2200)),
            ('Entertainment', ['BookMyShow movie tickets - IMAX', 'Weekend Dinner & Bowling arcade', 'Steam Weekend Indie Game Purchase'], (350, 1500)),
            ('Shopping', ['Amazon order - Wireless noise cancelling headphones', 'Myntra Casual Shirts & Denim sale', 'Flipkart Smart Home bulb & socket', 'Zara casual blazer'], (650, 4800)),
            ('Healthcare', ['Apollo Pharmacy multivitamins & pain relief', '1mg health wellness checkup kit', 'Dental checkup and cleaning clinic'], (200, 2400)),
        ]

        # Generate realistic scattered spending across each of the 90 days
        for day_ago in range(1, 90):
            tx_date = now - timedelta(days=day_ago, hours=random.randint(1, 14), minutes=random.randint(0, 59))
            
            # 1-3 transactions per day
            num_txs = random.choices([0, 1, 2, 3], weights=[0.1, 0.45, 0.35, 0.1])[0]
            for _ in range(num_txs):
                cat_name, desc_choices, amount_range = random.choice(daily_expense_templates)
                amount = Decimal(str(round(random.uniform(*amount_range), 2)))
                description = random.choice(desc_choices)

                transactions_to_create.append(Transaction(
                    user=user,
                    category=category_objs[cat_name],
                    transaction_type='expense',
                    amount=amount,
                    description=description,
                    date=tx_date
                ))

        Transaction.objects.bulk_create(transactions_to_create)
        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded {len(transactions_to_create)} transactions across 90 days for '{username}'!"
        ))
        self.stdout.write(self.style.SUCCESS("FinSight AI backend database is fully populated and ready for demonstration!"))
