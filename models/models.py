from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta 

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Subscription fields - ADD THESE
    subscription_status = db.Column(db.Enum('trial', 'active', 'expired'), default='trial')
    trial_start_date = db.Column(db.DateTime, default=datetime.utcnow)
    subscription_end_date = db.Column(db.DateTime, nullable=True)
    plan_type = db.Column(db.Enum('trial', '1month', '3month', '6month'), default='trial')
    razorpay_customer_id = db.Column(db.String(100), nullable=True)

    categories = db.relationship('Category', backref='user', lazy=True, cascade="all, delete-orphan")
    investments = db.relationship('Investment', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    # ADD THIS METHOD
    def is_subscription_valid(self):
        if self.is_admin:
            return True
        if self.subscription_status == 'trial':
            return datetime.utcnow() <= self.trial_start_date + timedelta(days=30)
        if self.subscription_status == 'active':
            return self.subscription_end_date and datetime.utcnow() <= self.subscription_end_date
        return False

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50), default='fas fa-wallet')
    color = db.Column(db.String(20), default='#6366F1')
    description = db.Column(db.Text)

    investments = db.relationship('Investment', backref='category', lazy=True, cascade="all, delete-orphan")

class Wallet(db.Model):
    __tablename__ = 'wallets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # e.g. "HDFC Savings", "Cash"
    wallet_type = db.Column(db.String(50), default='bank')  # bank, cash, upi, crypto
    icon = db.Column(db.String(50), default='fas fa-wallet')
    color = db.Column(db.String(20), default='#4F8EF7')
    balance = db.Column(db.Float, default=0.0)  # manual balance or calculated
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='wallets')

class ExpenseCategory(db.Model):
    __tablename__ = 'expense_categories'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50), default='fas fa-receipt')
    color = db.Column(db.String(20), default='#FF6B7A')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='expense_categories')

class Investment(db.Model):
    __tablename__ = 'investments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallets.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    investment_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    wallet = db.relationship('Wallet', backref='investments')

class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=False)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallets.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255))
    expense_date = db.Column(db.Date, nullable=False, default=date.today)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='expenses')
    category = db.relationship('ExpenseCategory', backref='expenses')
    wallet = db.relationship('Wallet', backref='expenses')

class Income(db.Model):
    __tablename__ = 'incomes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallets.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255))
    income_date = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='incomes')
    wallet = db.relationship('Wallet', backref='incomes')

class UsageLog(db.Model):
    __tablename__ = 'usage_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    endpoint = db.Column(db.String(255))
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    date_only = db.Column(db.Date, default=date.today, index=True)

    user = db.relationship('User', backref='usage_logs')