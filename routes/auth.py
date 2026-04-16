from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import db
from models.models import User, Category
from functools import wraps
from flask import session, redirect, url_for, flash

auth_bp = Blueprint('auth', __name__)

def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            session.clear()  # kill stale session
            flash('Please log in to continue.', 'error')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def subscription_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        if not user.is_subscription_valid():
            flash('Your subscription has expired. Please renew to continue.', 'error')
            return redirect(url_for('main.pricing'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            session.clear()
            flash('Please log in to continue.', 'error')
            return redirect(url_for('auth.login', next=request.url))
        if not user.is_admin:
            return render_template('error.html', message='Admin access required'), 403
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    user = get_current_user()
    if user:
        return redirect(url_for('admin.admin_panel' if user.is_admin else 'main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin.admin_panel' if user.is_admin else 'main.dashboard'))
        else:
            return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    user = get_current_user()
    if user:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')

            if len(username) < 3:
                return render_template('signup.html', error='Username must be at least 3 characters')
            if len(password) < 6:
                return render_template('signup.html', error='Password must be at least 6 characters')

            if User.query.filter_by(username=username).first():
                return render_template('signup.html', error='Username already exists')

            is_first_user = User.query.count() == 0
            
            user = User(username=username, is_admin=is_first_user)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            default_categories = [
                {"name": "Gold", "icon": "fas fa-coins", "color": "#FFD700", "description": "Gold investments"},
                {"name": "SIP", "icon": "fas fa-chart-line", "color": "#00D4AA", "description": "Mutual funds SIP"},
                {"name": "Silver", "icon": "fas fa-medal", "color": "#C0C0C0", "description": "Silver investments"},
                {"name": "PPF", "icon": "fas fa-piggy-bank", "color": "#4F46E5", "description": "Public Provident Fund"}
            ]
            for cat in default_categories:
                db.session.add(Category(user_id=user.id, **cat))
            db.session.commit()

            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('admin.admin_panel' if user.is_admin else 'main.dashboard'))

        except Exception as e:
            db.session.rollback()
            print(f"Signup error: {e}")
            return render_template('signup.html', error='Signup failed. Please try again.')

    return render_template('signup.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))