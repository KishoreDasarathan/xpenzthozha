from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for, flash
from extensions import db
from models.models import User, Investment, Category, Wallet, Expense, Income, ExpenseCategory, UsageLog
from routes.auth import admin_required
from sqlalchemy import inspect, text, func
from datetime import datetime, timedelta, date
from flask import request, flash

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
@admin_required
def admin_panel():
    users = User.query.order_by(User.id.desc()).all()
    return render_template('admin.html', users=users, timedelta=timedelta)

# ========== STATS ==========
@admin_bp.route('/api/admin/stats')
@admin_required
def get_stats():
    # Real DB size in MB
    db_size = db.session.execute(text(
        "SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) "
        "FROM information_schema.tables WHERE table_schema = DATABASE()"
    )).scalar() or 0

    # Max DB size - change if your hosting limit differs
    db_limit_mb = 5120

    # Online users: active in last 5 minutes
    five_min_ago = datetime.utcnow() - timedelta(minutes=5)
    online_users = User.query.filter(User.last_active >= five_min_ago).count()

    return jsonify({
        'db_size_mb': float(db_size),
        'db_limit_mb': db_limit_mb,
        'db_percent': round((float(db_size) / db_limit_mb) * 100, 1),
        'users': User.query.count(),
        'online_users': online_users,
        'investments': Investment.query.count()
    })

@admin_bp.route('/api/admin/usage-report')
@admin_required
def usage_report():
    # Last 7 days usage
    seven_days_ago = date.today() - timedelta(days=6)
    
    daily_stats = db.session.query(
        UsageLog.date_only,
        func.count(UsageLog.id).label('requests'),
        func.count(func.distinct(UsageLog.user_id)).label('active_users')
    ).filter(
        UsageLog.date_only >= seven_days_ago
    ).group_by(UsageLog.date_only).order_by(UsageLog.date_only).all()

    return jsonify([{
        'date': stat.date_only.strftime('%Y-%m-%d'),
        'date_label': stat.date_only.strftime('%a %d'),
        'requests': stat.requests,
        'active_users': stat.active_users or 0
    } for stat in daily_stats])

# ========== USERS CRUD ==========
@admin_bp.route('/api/admin/users')
@admin_required
def get_users():
    five_min_ago = datetime.utcnow() - timedelta(minutes=5)
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'is_admin': u.is_admin,
        'created_at': u.created_at.isoformat() if u.created_at else None,
        'last_active': u.last_active.isoformat() if u.last_active else None,
        'is_online': u.last_active and u.last_active >= five_min_ago,
        'investment_count': Investment.query.filter_by(user_id=u.id).count()
    } for u in users])

@admin_bp.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    if user_id == session['user_id']:
        return jsonify({'success': False, 'message': "Can't edit yourself here"}), 400

    user = User.query.get_or_404(user_id)
    data = request.json

    if 'username' in data:
        new_username = data['username'].strip()
        if User.query.filter(User.username == new_username, User.id!= user_id).first():
            return jsonify({'success': False, 'message': 'Username taken'}), 400
        user.username = new_username

    if 'password' in data and data['password']:
        if len(data['password']) < 6:
            return jsonify({'success': False, 'message': 'Password must be 6+ chars'}), 400
        user.set_password(data['password'])

    db.session.commit()
    return jsonify({'success': True})

@admin_bp.route('/api/admin/toggle_admin/<int:user_id>', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    if user_id == session['user_id']:
        return jsonify({'success': False, 'message': "Can't change your own admin status"})

    user = User.query.get_or_404(user_id)
    user.is_admin = not user.is_admin
    db.session.commit()
    return jsonify({'success': True, 'is_admin': user.is_admin})

@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    if user_id == session['user_id']:
        return jsonify({'success': False, 'message': "Can't delete yourself"})

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True})

# ========== INVESTMENTS ==========
@admin_bp.route('/api/admin/investments')
@admin_required
def get_all_investments():
    investments = db.session.query(Investment, User.username).join(User).all()
    return jsonify([{
        'id': inv.id,
        'username': username,
        'name': inv.category.name if inv.category else 'Deleted',
        'type': inv.category.name if inv.category else 'N/A',
        'amount': float(inv.amount),
        'date': inv.investment_date.isoformat()
    } for inv, username in investments])

@admin_bp.route('/api/admin/investments/<int:inv_id>', methods=['DELETE'])
@admin_required
def delete_investment_admin(inv_id):
    inv = Investment.query.get_or_404(inv_id)
    db.session.delete(inv)
    db.session.commit()
    return jsonify({'success': True})

# ========== DB BROWSER ==========
PROTECTED_COLS = {'id', 'password_hash', 'created_at'}

@admin_bp.route('/api/admin/tables')
@admin_required
def get_tables():
    inspector = inspect(db.engine)
    return jsonify({'tables': inspector.get_table_names()})

@admin_bp.route('/api/admin/table/<table_name>')
@admin_required
def get_table_data(table_name):
    filter_col = request.args.get('filter_col')
    filter_val = request.args.get('filter_val')

    query = f"SELECT * FROM {table_name}"
    params = {}
    if filter_col and filter_val:
        query += f" WHERE {filter_col} LIKE :val"
        params['val'] = f'%{filter_val}%'

    result = db.session.execute(text(query), params)
    rows = [dict(row._mapping) for row in result]
    columns = list(rows[0].keys()) if rows else []
    
    for row in rows:
        for k, v in row.items():
            if hasattr(v, 'isoformat'):
                row[k] = v.isoformat()
    
    return jsonify({'columns': columns, 'rows': rows})

@admin_bp.route('/api/admin/table/<table_name>/<int:row_id>', methods=['PUT'])
@admin_required
def update_table_row(table_name, row_id):
    data = request.json
    
    for col in PROTECTED_COLS:
        data.pop(col, None)

    if not data:
        return jsonify({'success': False, 'error': 'No editable fields provided'})

    for k, v in data.items():
        if isinstance(v, str) and 'T' in v and ('date' in k.lower() or 'at' in k.lower()):
            try:
                from dateutil import parser
                dt = parser.parse(v)
                data[k] = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass

    set_clause = ', '.join([f"{k} = :{k}" for k in data.keys()])
    query = f"UPDATE {table_name} SET {set_clause} WHERE id = :id"
    data['id'] = row_id

    try:
        db.session.execute(text(query), data)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/api/admin/table/<table_name>/<int:row_id>', methods=['DELETE'])
@admin_required
def delete_table_row(table_name, row_id):
    try:
        db.session.execute(text(f"DELETE FROM {table_name} WHERE id = :id"), {'id': row_id})
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})



@admin_bp.route('/admin/update-subscription', methods=['POST'])
@admin_required
def update_subscription():
    user_id = request.form.get('user_id')
    plan_type = request.form.get('plan_type')  # '1month', '3month', '6month', 'trial'
    action = request.form.get('action')  # 'activate', 'extend', 'expire'
    
    user = User.query.get_or_404(user_id)
    
    if action == 'expire':
        user.subscription_status = 'expired'
        user.subscription_end_date = datetime.utcnow()
        flash(f'Expired subscription for {user.username}', 'success')
        
    elif action in ['activate', 'extend']:
        duration_map = {
            '1month': 30,
            '3month': 90, 
            '6month': 180,
            'trial': 30
        }
        days = duration_map.get(plan_type, 30)
        
        if action == 'activate' or user.subscription_end_date is None or user.subscription_end_date < datetime.utcnow():
            # Start new subscription from today
            user.subscription_end_date = datetime.utcnow() + timedelta(days=days)
        else:
            # Extend existing subscription
            user.subscription_end_date += timedelta(days=days)
            
        user.subscription_status = 'active' if plan_type != 'trial' else 'trial'
        user.plan_type = plan_type
        if plan_type == 'trial':
            user.trial_start_date = datetime.utcnow()
            
        flash(f'Activated {plan_type} for {user.username}. Expires: {user.subscription_end_date.strftime("%d %b %Y")}', 'success')
    
    db.session.commit()
    return redirect(url_for('admin.admin_panel'))