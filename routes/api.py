from flask import Blueprint, jsonify, request, session
from extensions import db
from models.models import Investment, Category, Wallet, Expense, ExpenseCategory, Income
from routes.auth import login_required
from datetime import datetime, timedelta, date
from calendar import monthrange
from dateutil.relativedelta import relativedelta

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/dashboard-stats')
@login_required
def dashboard_stats():
    user_id = session['user_id']
    investments = Investment.query.filter_by(user_id=user_id).all()
    categories = Category.query.filter_by(user_id=user_id).all()
    expenses = Expense.query.filter_by(user_id=user_id).all()
    exp_categories = ExpenseCategory.query.filter_by(user_id=user_id).all()
    incomes = Income.query.filter_by(user_id=user_id).all()

    # Get wallets
    wallets = Wallet.query.filter_by(user_id=user_id).all()
    total_wallet_balance = sum(w.balance for w in wallets)

    total = sum(i.amount for i in investments)
    total_expenses = sum(e.amount for e in expenses)

    today = datetime.today()
    monthly = sum(
        i.amount for i in investments
        if i.investment_date.month == today.month and i.investment_date.year == today.year
    )
    monthly_expenses = sum(
        e.amount for e in expenses
        if e.expense_date.month == today.month and e.expense_date.year == today.year
    )

    # Monthly income from Income table
    monthly_income = sum(
        inc.amount for inc in incomes
        if inc.income_date.month == today.month and inc.income_date.year == today.year
    )

    # Monthly counts
    monthly_expense_count = sum(1 for e in expenses if e.expense_date.month == today.month and e.expense_date.year == today.year)
    monthly_investment_count = sum(1 for i in investments if i.investment_date.month == today.month and i.investment_date.year == today.year)
    monthly_income_count = sum(1 for inc in incomes if inc.income_date.month == today.month and inc.income_date.year == today.year)

    # FIXED: Calculate last 6 calendar months correctly
    monthly_trend = []
    for i in range(5, -1, -1):
        # Go back i months from current month
        target_month = today - relativedelta(months=i)
        month_start = target_month.replace(day=1).date()
        last_day = monthrange(target_month.year, target_month.month)[1]
        month_end = target_month.replace(day=last_day).date()

        # Investment total for month
        month_investment = sum(
            inv.amount for inv in investments
            if month_start <= inv.investment_date <= month_end
        )
        # Expense total for month
        month_expense = sum(
            exp.amount for exp in expenses
            if month_start <= exp.expense_date <= month_end
        )
        # Income total for month
        month_income = sum(
            inc.amount for inc in incomes
            if month_start <= inc.income_date <= month_end
        )

        monthly_trend.append({
            "month": month_start.strftime('%Y-%m'),
            "total": float(month_investment), # investment
            "expense": float(month_expense), # FIXED
            "income": float(month_income) # FIXED
        })

    # Investment category stats
    category_stats = []
    for c in categories:
        cat_investments = [i for i in investments if i.category_id == c.id]
        category_stats.append({
            "id": c.id,
            "name": c.name,
            "icon": c.icon,
            "color": c.color,
            "total": float(sum(i.amount for i in cat_investments)),
            "count": len(cat_investments)
        })

    # Expense category stats for THIS MONTH only - for spend analysis chart
    expense_category_stats = []
    for c in exp_categories:
        cat_expenses = [e for e in expenses if e.category_id == c.id and e.expense_date.month == today.month and e.expense_date.year == today.year]
        if cat_expenses: # Only include categories with expenses this month
            expense_category_stats.append({
                "id": c.id,
                "name": c.name,
                "icon": c.icon,
                "color": c.color,
                "total_spent": float(round(sum(e.amount for e in cat_expenses), 2)),
                "expense_count": len(cat_expenses)
            })

    # Recent investments
    recent = sorted(investments, key=lambda x: x.investment_date, reverse=True)[:5]
    recent_data = [{
        "id": i.id,
        "amount": float(i.amount),
        "description": i.description,
        "investment_date": i.investment_date.strftime('%Y-%m-%d'),
        "category_id": i.category_id,
        "category_name": i.category.name if i.category else 'Unknown',
        "category_icon": i.category.icon if i.category else 'fas fa-wallet',
        "category_color": i.category.color if i.category else '#6366F1',
        "wallet_name": i.wallet.name if i.wallet else None
    } for i in recent]

    # Recent incomes
    recent_inc = sorted(incomes, key=lambda x: x.income_date, reverse=True)[:8]
    recent_incomes_data = [{
        "id": inc.id,
        "amount": float(inc.amount),
        "description": inc.description,
        "income_date": inc.income_date.strftime('%Y-%m-%d'),
        "wallet_id": inc.wallet_id,
        "wallet_name": inc.wallet.name if inc.wallet else 'Unknown',
        "wallet_color": inc.wallet.color if inc.wallet else '#4F8EF7'
    } for inc in recent_inc]

    return jsonify({
        "total": float(total),
        "monthly": float(monthly),
        "total_expenses": float(total_expenses),
        "monthly_expenses": float(monthly_expenses),
        "monthly_income": float(monthly_income),
        "monthly_expense_count": monthly_expense_count,
        "monthly_investment_count": monthly_investment_count,
        "monthly_income_count": monthly_income_count,
        "categories": category_stats,
        "expense_categories": expense_category_stats,
        "recent": recent_data,
        "recent_incomes": recent_incomes_data,
        "monthly_trend": monthly_trend,
        "wallets": {
            "total_balance": float(total_wallet_balance),
            "list": [{
                "id": w.id,
                "name": w.name,
                "balance": float(w.balance),
                "color": w.color,
                "icon": w.icon,
                "wallet_type": w.wallet_type,
                "is_default": w.is_default
            } for w in wallets]
        }
    })

@api_bp.route('/api/income', methods=['POST'])
@login_required
def add_income():
    user_id = session['user_id']
    data = request.get_json()

    wallet = Wallet.query.filter_by(id=data['wallet_id'], user_id=user_id).first()
    if not wallet:
        return jsonify({"success": False, "message": "Invalid wallet"}), 400

    try:
        amount = float(data['amount'])
        if amount <= 0:
            return jsonify({"success": False, "message": "Amount must be positive"}), 400

        # Create income record
        new_income = Income(
            user_id=user_id,
            wallet_id=int(data['wallet_id']),
            amount=amount,
            description=data.get('description', ''),
            income_date=datetime.strptime(data.get('income_date', date.today().strftime('%Y-%m-%d')), '%Y-%m-%d').date()
        )
        wallet.balance += amount # increase wallet balance
        db.session.add(new_income)
        db.session.commit()
        return jsonify({"success": True, "message": "Income added", "new_balance": wallet.balance})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "Failed to add income"}), 500

@api_bp.route('/api/incomes', methods=['GET'])
@login_required
def get_incomes():
    user_id = session['user_id']
    incomes = Income.query.filter_by(user_id=user_id).order_by(Income.income_date.desc()).all()
    return jsonify([{
        "id": i.id,
        "amount": i.amount,
        "description": i.description,
        "income_date": i.income_date.strftime('%Y-%m-%d'),
        "wallet_id": i.wallet_id,
        "wallet_name": i.wallet.name if i.wallet else 'Unknown'
    } for i in incomes])

@api_bp.route('/api/incomes/<int:id>', methods=['PUT', 'DELETE'])
@login_required
def api_income_detail(id):
    user_id = session['user_id']
    income = Income.query.filter_by(id=id, user_id=user_id).first()
    
    if not income:
        return jsonify({'success': False, 'message': 'Income not found'}), 404
    
    if request.method == 'PUT':
        data = request.get_json()
        
        wallet = Wallet.query.filter_by(id=data['wallet_id'], user_id=user_id).first()
        if not wallet:
            return jsonify({"success": False, "message": "Invalid wallet"}), 400

        try:
            new_amount = float(data['amount'])
            if new_amount <= 0:
                return jsonify({"success": False, "message": "Amount must be positive"}), 400

            # Refund old wallet, charge new wallet
            old_wallet = income.wallet
            old_amount = income.amount
            
            if old_wallet:
                old_wallet.balance -= old_amount
            
            if wallet.balance + old_amount < new_amount:
                return jsonify({"success": False, "message": "Insufficient wallet balance"}), 400
                
            wallet.balance += new_amount

            # Update income
            income.wallet_id = int(data['wallet_id'])
            income.amount = new_amount
            income.description = data.get('description', '')
            income.income_date = datetime.strptime(data['income_date'], '%Y-%m-%d').date()
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Income updated'})
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "message": "Failed to update income"}), 500
    
    elif request.method == 'DELETE':
        # Refund wallet balance when deleting income
        if income.wallet:
            income.wallet.balance -= income.amount

        db.session.delete(income)
        db.session.commit()
        return jsonify({'success': True})

@api_bp.route('/api/investments', methods=['GET', 'POST'])
@login_required
def investments():
    user_id = session['user_id']

    if request.method == 'GET':
        investments = Investment.query.filter_by(user_id=user_id).all()
        return jsonify([{
            "id": i.id,
            "category_id": i.category_id,
            "wallet_id": i.wallet_id,
            "amount": i.amount,
            "description": i.description,
            "investment_date": i.investment_date.strftime('%Y-%m-%d'),
            "notes": i.notes,
            "created_at": i.created_at.isoformat(),
            "category_name": i.category.name if i.category else 'Unknown',
            "wallet_name": i.wallet.name if i.wallet else 'Unknown'
        } for i in investments])

    elif request.method == 'POST':
        data = request.get_json()

        category = Category.query.filter_by(id=data['category_id'], user_id=user_id).first()
        wallet = Wallet.query.filter_by(id=data['wallet_id'], user_id=user_id).first()
        if not category or not wallet:
            return jsonify({"success": False, "message": "Invalid category or wallet"}), 400

        try:
            amount = float(data['amount'])
            if amount <= 0:
                return jsonify({"success": False, "message": "Amount must be positive"}), 400
            if wallet.balance < amount:
                return jsonify({"success": False, "message": "Insufficient wallet balance"}), 400

            new_investment = Investment(
                user_id=user_id,
                category_id=int(data['category_id']),
                wallet_id=int(data['wallet_id']),
                amount=amount,
                description=data.get('description', ''),
                investment_date=datetime.strptime(data['investment_date'], '%Y-%m-%d').date(),
                notes=data.get('notes', '')
            )
            wallet.balance -= amount  # deduct from wallet
            db.session.add(new_investment)
            db.session.commit()
            return jsonify({"success": True, "id": new_investment.id, "message": "Investment added"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "message": "Failed to add investment"}), 500

@api_bp.route('/api/investments/<int:id>', methods=['DELETE'])
@login_required
def delete_investment(id):
    user_id = session['user_id']
    investment = Investment.query.filter_by(id=id, user_id=user_id).first()

    if not investment:
        return jsonify({'success': False, 'message': 'Not found'}), 404

    # Refund wallet balance when deleting investment
    if investment.wallet:
        investment.wallet.balance += investment.amount

    db.session.delete(investment)
    db.session.commit()
    return jsonify({'success': True})

@api_bp.route('/api/categories', methods=['GET', 'POST'])
@login_required
def api_categories():
    user_id = session['user_id']

    if request.method == 'GET':
        categories = Category.query.filter_by(user_id=user_id).all()
        investments = Investment.query.filter_by(user_id=user_id).all()

        data = []
        for c in categories:
            cat_investments = [i for i in investments if i.category_id == c.id]
            data.append({
                "id": c.id,
                "name": c.name,
                "icon": c.icon,
                "color": c.color,
                "description": c.description,
                "total_invested": round(sum(i.amount for i in cat_investments), 2),
                "investment_count": len(cat_investments)
            })
        return jsonify(data)

    elif request.method == 'POST':
        data = request.get_json()
        new_category = Category(
            user_id=user_id,
            name=data['name'],
            icon=data.get('icon', 'fas fa-wallet'),
            color=data.get('color', '#6366F1'),
            description=data.get('description', '')
        )
        db.session.add(new_category)
        db.session.commit()
        return jsonify({"success": True, "id": new_category.id, "message": "Category created"})

@api_bp.route('/api/categories/<int:id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_category(id):
    user_id = session['user_id']
    category = Category.query.filter_by(id=id, user_id=user_id).first()

    if not category:
        return jsonify({'error': 'Category not found'}), 404

    if request.method == 'GET':
        investments = Investment.query.filter_by(category_id=id, user_id=user_id).all()
        total = sum(i.amount for i in investments)
        return jsonify({
            "id": category.id,
            "name": category.name,
            "icon": category.icon,
            "color": category.color,
            "description": category.description,
            "total_invested": total
        })

    elif request.method == 'PUT':
        data = request.get_json()
        category.name = data['name']
        category.icon = data.get('icon', category.icon)
        category.color = data.get('color', category.color)
        category.description = data.get('description', category.description)
        db.session.commit()
        return jsonify({'success': True})

    elif request.method == 'DELETE':
        inv_count = Investment.query.filter_by(category_id=id, user_id=user_id).count()
        if inv_count > 0:
            return jsonify({'success': False, 'message': f'Cannot delete. {inv_count} investments use this category.'}), 400
        db.session.delete(category)
        db.session.commit()
        return jsonify({'success': True})

@api_bp.route('/api/wallets', methods=['GET', 'POST'])
@login_required
def api_wallets():
    user_id = session['user_id']
    
    if request.method == 'GET':
        wallets = Wallet.query.filter_by(user_id=user_id).all()
        total_balance = sum(w.balance for w in wallets)
        return jsonify({
            "wallets": [{
                "id": w.id,
                "name": w.name,
                "wallet_type": w.wallet_type,
                "icon": w.icon,
                "color": w.color,
                "balance": w.balance,
                "is_default": w.is_default,
                "created_at": w.created_at.isoformat()
            } for w in wallets],
            "total_balance": total_balance
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        
        # If this is first wallet or marked default, unset others
        if data.get('is_default') or Wallet.query.filter_by(user_id=user_id).count() == 0:
            Wallet.query.filter_by(user_id=user_id).update({"is_default": False})
        
        new_wallet = Wallet(
            user_id=user_id,
            name=data['name'],
            wallet_type=data.get('wallet_type', 'bank'),
            icon=data.get('icon', 'fas fa-wallet'),
            color=data.get('color', '#4F8EF7'),
            balance=float(data.get('balance', 0)),
            is_default=data.get('is_default', False) or Wallet.query.filter_by(user_id=user_id).count() == 0
        )
        db.session.add(new_wallet)
        db.session.commit()
        return jsonify({"success": True, "id": new_wallet.id})

@api_bp.route('/api/wallets/<int:id>', methods=['PUT', 'DELETE'])
@login_required
def api_wallet_detail(id):
    user_id = session['user_id']
    wallet = Wallet.query.filter_by(id=id, user_id=user_id).first()
    
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404
    
    if request.method == 'PUT':
        data = request.get_json()
        
        # If setting as default, unset others
        if data.get('is_default'):
            Wallet.query.filter_by(user_id=user_id).update({"is_default": False})
        
        wallet.name = data.get('name', wallet.name)
        wallet.wallet_type = data.get('wallet_type', wallet.wallet_type)
        wallet.icon = data.get('icon', wallet.icon)
        wallet.color = data.get('color', wallet.color)
        wallet.balance = float(data.get('balance', wallet.balance))
        wallet.is_default = data.get('is_default', wallet.is_default)
        db.session.commit()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        if wallet.is_default and Wallet.query.filter_by(user_id=user_id).count() > 1:
            return jsonify({'success': False, 'message': 'Cannot delete default wallet. Set another as default first.'}), 400
        
        # Check if wallet has investments or expenses
        inv_count = Investment.query.filter_by(wallet_id=id).count()
        exp_count = Expense.query.filter_by(wallet_id=id).count()
        if inv_count + exp_count > 0:
            return jsonify({'success': False, 'message': f'Cannot delete. {inv_count + exp_count} transactions use this wallet.'}), 400
            
        db.session.delete(wallet)
        db.session.commit()
        return jsonify({'success': True})

@api_bp.route('/api/expense-categories', methods=['GET', 'POST'])
@login_required
def api_expense_categories():
    user_id = session['user_id']
    
    if request.method == 'GET':
        categories = ExpenseCategory.query.filter_by(user_id=user_id).all()
        expenses = Expense.query.filter_by(user_id=user_id).all()
        
        data = []
        for c in categories:
            cat_expenses = [e for e in expenses if e.category_id == c.id]
            data.append({
                "id": c.id,
                "name": c.name,
                "icon": c.icon,
                "color": c.color,
                "total_spent": round(sum(e.amount for e in cat_expenses), 2),
                "expense_count": len(cat_expenses)
            })
        return jsonify(data)
    
    elif request.method == 'POST':
        data = request.get_json()
        new_cat = ExpenseCategory(
            user_id=user_id,
            name=data['name'],
            icon=data.get('icon', 'fas fa-receipt'),
            color=data.get('color', '#FF6B7A')
        )
        db.session.add(new_cat)
        db.session.commit()
        return jsonify({"success": True, "id": new_cat.id})

@api_bp.route('/api/expense-categories/<int:id>', methods=['PUT', 'DELETE'])
@login_required
def api_expense_category_detail(id):
    user_id = session['user_id']
    category = ExpenseCategory.query.filter_by(id=id, user_id=user_id).first()
    
    if not category:
        return jsonify({'error': 'Category not found'}), 404
    
    if request.method == 'PUT':
        data = request.get_json()
        category.name = data['name']
        category.icon = data.get('icon', category.icon)
        category.color = data.get('color', category.color)
        db.session.commit()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        # Check if category has expenses
        expense_count = Expense.query.filter_by(category_id=id, user_id=user_id).count()
        if expense_count > 0:
            return jsonify({'success': False, 'message': f'Cannot delete. {expense_count} expenses use this category.'}), 400
        db.session.delete(category)
        db.session.commit()
        return jsonify({'success': True})

@api_bp.route('/api/expenses', methods=['GET', 'POST'])
@login_required
def api_expenses():
    user_id = session['user_id']
    
    if request.method == 'GET':
        expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.expense_date.desc()).all()
        return jsonify([{
            "id": e.id,
            "category_id": e.category_id,
            "wallet_id": e.wallet_id,
            "amount": e.amount,
            "description": e.description,
            "expense_date": e.expense_date.strftime('%Y-%m-%d'),
            "notes": e.notes,
            "category_name": e.category.name if e.category else 'Unknown',
            "category_icon": e.category.icon if e.category else 'fas fa-receipt',
            "category_color": e.category.color if e.category else '#FF6B7A',
            "wallet_name": e.wallet.name if e.wallet else 'Unknown'
        } for e in expenses])
    
    elif request.method == 'POST':
        data = request.get_json()

        category = ExpenseCategory.query.filter_by(id=data['category_id'], user_id=user_id).first()
        wallet = Wallet.query.filter_by(id=data['wallet_id'], user_id=user_id).first()
        if not category or not wallet:
            return jsonify({"success": False, "message": "Invalid category or wallet"}), 400

        try:
            amount = float(data['amount'])
            if amount <= 0:
                return jsonify({"success": False, "message": "Amount must be positive"}), 400
            if wallet.balance < amount:
                return jsonify({"success": False, "message": "Insufficient wallet balance"}), 400

            new_expense = Expense(
                user_id=user_id,
                category_id=int(data['category_id']),
                wallet_id=int(data['wallet_id']),
                amount=amount,
                description=data.get('description', ''),
                expense_date=datetime.strptime(data['expense_date'], '%Y-%m-%d').date(),
                notes=data.get('notes', '')
            )
            wallet.balance -= amount  # deduct from wallet
            db.session.add(new_expense)
            db.session.commit()
            return jsonify({"success": True, "id": new_expense.id, "message": "Expense added"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "message": "Failed to add expense"}), 500

@api_bp.route('/api/expenses/<int:id>', methods=['PUT', 'DELETE'])
@login_required
def api_expense_detail(id):
    user_id = session['user_id']
    expense = Expense.query.filter_by(id=id, user_id=user_id).first()
    
    if not expense:
        return jsonify({'success': False, 'message': 'Expense not found'}), 404
    
    if request.method == 'PUT':
        data = request.get_json()
        
        # Validate new wallet/category
        wallet = Wallet.query.filter_by(id=data['wallet_id'], user_id=user_id).first()
        category = ExpenseCategory.query.filter_by(id=data['category_id'], user_id=user_id).first()
        if not wallet or not category:
            return jsonify({"success": False, "message": "Invalid wallet or category"}), 400

        try:
            new_amount = float(data['amount'])
            if new_amount <= 0:
                return jsonify({"success": False, "message": "Amount must be positive"}), 400

            # Refund old wallet, charge new wallet
            old_wallet = expense.wallet
            old_amount = expense.amount
            
            if old_wallet:
                old_wallet.balance += old_amount
            
            if wallet.balance < new_amount:
                return jsonify({"success": False, "message": "Insufficient wallet balance"}), 400
                
            wallet.balance -= new_amount

            # Update expense
            expense.wallet_id = int(data['wallet_id'])
            expense.category_id = int(data['category_id'])
            expense.amount = new_amount
            expense.description = data.get('description', '')
            expense.expense_date = datetime.strptime(data['expense_date'], '%Y-%m-%d').date()
            expense.notes = data.get('notes', '')
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Expense updated'})
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "message": "Failed to update expense"}), 500
    
    elif request.method == 'DELETE':
        # Refund wallet balance when deleting expense
        if expense.wallet:
            expense.wallet.balance += expense.amount

        db.session.delete(expense)
        db.session.commit()
        return jsonify({'success': True})

@api_bp.route('/api/monthly-breakdown')
@login_required
def monthly_breakdown():
    user_id = session['user_id']
    investments = Investment.query.filter_by(user_id=user_id).all()

    # Group by month
    monthly_data = {}
    for inv in investments:
        month_key = inv.investment_date.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = {'total': 0, 'count': 0, 'categories': {}}
        monthly_data[month_key]['total'] += inv.amount
        monthly_data[month_key]['count'] += 1
        cat_name = inv.category.name if inv.category else 'Unknown'
        monthly_data[month_key]['categories'][cat_name] = monthly_data[month_key]['categories'].get(cat_name, 0) + inv.amount

    # Format for table
    result = []
    for month, data in sorted(monthly_data.items(), reverse=True):
        top_cat = max(data['categories'].items(), key=lambda x: x[1])[0] if data['categories'] else '—'
        result.append({
            'month': datetime.strptime(month, '%Y-%m').strftime('%b %Y'),
            'total': round(data['total'], 2),
            'count': data['count'],
            'top_category': top_cat
        })

    return jsonify(result)


# CHANGE ONLY THIS NEW ONE - new URL
@api_bp.route('/api/monthly-breakdown-detail') # CHANGED URL
@login_required
def monthly_breakdown_api():
    user_id = session['user_id']
    month_str = request.args.get('month') # YYYY-MM

    if not month_str:
        return jsonify({"error": "month required"}), 400

    year, month = map(int, month_str.split('-'))
    month_start = date(year, month, 1)
    last_day = monthrange(year, month)[1]
    month_end = date(year, month, last_day)

    print(f"DEBUG: Filtering from {month_start} to {month_end}")

    incomes = Income.query.filter(
        Income.user_id == user_id,
        Income.income_date >= month_start,
        Income.income_date <= month_end
    ).order_by(Income.income_date.desc()).all()

    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= month_start,
        Expense.expense_date <= month_end
    ).order_by(Expense.expense_date.desc()).all()

    investments = Investment.query.filter(
        Investment.user_id == user_id,
        Investment.investment_date >= month_start,
        Investment.investment_date <= month_end
    ).order_by(Investment.investment_date.desc()).all()

    print(f"DEBUG: Found {len(incomes)} incomes, {len(expenses)} expenses, {len(investments)} investments")

    sum_income = sum(i.amount for i in incomes)
    sum_expense = sum(e.amount for e in expenses)
    sum_investment = sum(inv.amount for inv in investments)

    return jsonify({
        "month": month_str,
        "summary": {
            "income": float(sum_income),
            "expense": float(sum_expense),
            "investment": float(sum_investment)
        },
        "incomes": [{
            "id": i.id,
            "amount": float(i.amount),
            "description": i.description,
            "income_date": i.income_date.strftime('%Y-%m-%d'),
            "wallet_name": i.wallet.name if i.wallet else 'Unknown',
            "wallet_color": i.wallet.color if i.wallet else '#4F8EF7'
        } for i in incomes],
        "expenses": [{
            "id": e.id,
            "amount": float(e.amount),
            "description": e.description,
            "expense_date": e.expense_date.strftime('%Y-%m-%d'),
            "category_name": e.category.name if e.category else 'Unknown',
            "category_icon": e.category.icon if e.category else 'fas fa-receipt',
            "category_color": e.category.color if e.category else '#FF6B7A',
            "wallet_name": e.wallet.name if e.wallet else 'Unknown'
        } for e in expenses],
        "investments": [{
            "id": inv.id,
            "amount": float(inv.amount),
            "description": inv.description,
            "investment_date": inv.investment_date.strftime('%Y-%m-%d'),
            "category_name": inv.category.name if inv.category else 'Unknown',
            "category_icon": inv.category.icon if inv.category else 'fas fa-wallet',
            "category_color": inv.category.color if inv.category else '#6366F1',
            "wallet_name": inv.wallet.name if inv.wallet else 'Unknown'
        } for inv in investments]
    })

@api_bp.route('/api/change-username', methods=['POST'])
@login_required
def change_username():
    from models.models import User
    data = request.get_json()
    new_username = data.get('username', '').strip()
    
    if len(new_username) < 3:
        return jsonify({'success': False, 'message': 'Username must be at least 3 characters'})
    
    # Check if username exists
    existing = User.query.filter(User.username == new_username, User.id != session['user_id']).first()
    if existing:
        return jsonify({'success': False, 'message': 'Username already taken'})
    
    user = User.query.get(session['user_id'])
    user.username = new_username
    db.session.commit()
    session['username'] = new_username
    return jsonify({'success': True})

@api_bp.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    from models.models import User
    
    data = request.get_json()
    current = data.get('current_password')
    new_pass = data.get('new_password')
    
    if len(new_pass) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'})
    
    user = User.query.get(session['user_id'])
    if not user.check_password(current):
        return jsonify({'success': False, 'message': 'Current password incorrect'})
    
    user.set_password(new_pass)
    db.session.commit()
    session.clear()  # Force logout
    return jsonify({'success': True, 'logout': True})

@api_bp.route('/api/reset-data', methods=['POST'])
@login_required
def reset_data():
    from models.models import User, Category, Investment, Wallet, ExpenseCategory, Expense, Income
    user_id = session['user_id']
    
    # Delete all user data but keep account
    Investment.query.filter_by(user_id=user_id).delete()
    Expense.query.filter_by(user_id=user_id).delete()
    Income.query.filter_by(user_id=user_id).delete()
    Wallet.query.filter_by(user_id=user_id).delete()
    Category.query.filter_by(user_id=user_id).delete()
    ExpenseCategory.query.filter_by(user_id=user_id).delete()
    
    db.session.commit()
    return jsonify({'success': True})

@api_bp.route('/api/delete-account', methods=['POST'])
@login_required
def delete_account():
    from models.models import User
    user_id = session['user_id']
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'})
    
    # Cascade handles all related data automatically due to cascade="all, delete-orphan"
    db.session.delete(user)
    db.session.commit()
    session.clear()
    return jsonify({'success': True})