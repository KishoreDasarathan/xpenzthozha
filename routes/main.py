from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify, current_app
from routes.auth import login_required, get_current_user, subscription_required
from datetime import datetime, timedelta
import razorpay

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    user = get_current_user()
    
    # Calculate trial days left
    trial_days_left = 0
    trial_end_date = None
    if user.subscription_status == 'trial':
        trial_end_date = user.trial_start_date + timedelta(days=30)
        trial_days_left = max(0, (trial_end_date - datetime.utcnow()).days)
    
    return render_template('dashboard.html', 
                         username=session.get('username'),
                         user=user,
                         trial_days_left=trial_days_left,
                         trial_end_date=trial_end_date)

@main_bp.route('/add-investment')
@login_required
@subscription_required  # Locked
def add_investment():
    return render_template('add_investment.html')

@main_bp.route('/categories')
@login_required
@subscription_required  # Locked
def categories():
    return render_template('categories.html')

@main_bp.route('/wallet')
@login_required
@subscription_required  # Locked
def wallet():
    return render_template('wallet.html')

@main_bp.route('/wallet', methods=['POST'])
@login_required
@subscription_required  # Locked
def wallet_action():
    return render_template('wallet.html')

@main_bp.route('/manage-expenses')
@login_required
@subscription_required  # Locked
def manage_expenses():
    return render_template('manage_expenses.html')

@main_bp.route('/add-transaction')
@login_required
@subscription_required  # Locked
def add_transaction():
    return render_template('add_transaction.html')

@main_bp.route('/invest-dashboard')
@login_required
@subscription_required  # Locked
def invest_dashboard():
    return render_template('invest_dashboard.html')

@main_bp.route('/monthly-breakdown')
@login_required
@subscription_required  # Locked
def monthly_breakdown_page():
    return render_template('monthly_breakdown.html')

@main_bp.route('/preferences')
@login_required
def preferences():
    return render_template('preferences.html')

@main_bp.route('/pricing')
@login_required
def pricing():
    user = get_current_user()
    
    # Always set these, even for non-trial users
    trial_days_left = 0
    trial_end_date = None
    
    if user.subscription_status == 'trial':
        trial_end_date = user.trial_start_date + timedelta(days=30)
        trial_days_left = max(0, (trial_end_date - datetime.utcnow()).days)
    
    plans = [
        {'id': '1month', 'name': '1 Month', 'price': 19, 'duration': 30},
        {'id': '3month', 'name': '3 Months', 'price': 50, 'duration': 90},
        {'id': '6month', 'name': '6 Months', 'price': 100, 'duration': 180}
    ]
    
    return render_template('pricing.html', 
                         user=user,
                         trial_days_left=trial_days_left,
                         trial_end_date=trial_end_date,
                         plans=plans)

# --- RAZORPAY PAYMENT ROUTES ---
@main_bp.route('/create-order', methods=['POST'])
@login_required
def create_order():
    plan_id = request.json.get('plan_id')
    plans = {
        '1month': {'amount': 1900, 'days': 30, 'name': '1 Month Plan'},
        '3month': {'amount': 5000, 'days': 90, 'name': '3 Months Plan'},
        '6month': {'amount': 10000, 'days': 180, 'name': '6 Months Plan'}
    }
    
    if plan_id not in plans:
        return jsonify({'success': False, 'message': 'Invalid plan'}), 400
    
    plan = plans[plan_id]
    user = get_current_user()
    
    client = razorpay.Client(auth=(current_app.config['RAZORPAY_KEY_ID'], 
                                   current_app.config['RAZORPAY_KEY_SECRET']))
    
    try:
        order = client.order.create({
            'amount': plan['amount'],
            'currency': 'INR',
            'receipt': f"order_rcpt_{user.id}_{plan_id}",
            'notes': {
                'user_id': str(user.id),
                'plan_id': plan_id,
                'plan_days': str(plan['days'])
            }
        })
        
        return jsonify({
            'success': True,
            'order_id': order['id'],
            'amount': order['amount'],
            'key_id': current_app.config['RAZORPAY_KEY_ID'],
            'user_name': getattr(user, 'username', 'User'),
            'user_email': getattr(user, 'email', 'test@example.com'),
            'plan_name': plan['name']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# Add this new route to handle callback from Payment Link
@main_bp.route('/payment-callback')
@login_required
def payment_callback():
    payment_id = request.args.get('razorpay_payment_id')
    payment_link_id = request.args.get('razorpay_payment_link_id')
    status = request.args.get('razorpay_payment_link_status')
    
    if status == 'paid':
        client = razorpay.Client(auth=(current_app.config['RAZORPAY_KEY_ID'], 
                                       current_app.config['RAZORPAY_KEY_SECRET']))
        
        try:
            # Fetch payment link details to get notes
            link = client.payment_link.fetch(payment_link_id)
            user_id = int(link['notes']['user_id'])
            plan_days = int(link['notes']['plan_days'])
            plan_id = link['notes']['plan_id']
            
            user = get_current_user()
            
            # Activate plan
            if user.is_subscription_valid() and user.subscription_end_date and user.subscription_end_date > datetime.utcnow():
                user.subscription_end_date += timedelta(days=plan_days)
            else:
                user.subscription_end_date = datetime.utcnow() + timedelta(days=plan_days)
                
            user.subscription_status = 'active'
            user.plan_type = plan_id
            
            from extensions import db
            db.session.commit()
            
            flash('Payment successful! Plan activated.', 'success')
            return redirect(url_for('main.dashboard'))
            
        except Exception as e:
            print("CALLBACK ERROR:", str(e))
            flash('Payment received but activation failed. Contact support.', 'danger')
            return redirect(url_for('main.pricing'))
    else:
        flash('Payment failed or cancelled.', 'danger')
        return redirect(url_for('main.pricing'))

@main_bp.route('/payment-success', methods=['POST'])
@login_required
def payment_success():
    data = request.json
    client = razorpay.Client(auth=(current_app.config['RAZORPAY_KEY_ID'], 
                                   current_app.config['RAZORPAY_KEY_SECRET']))
    
    try:
        # Verify signature
        params_dict = {
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        }
        client.utility.verify_payment_signature(params_dict)
        
        # Signature valid, activate plan
        order = client.order.fetch(data['razorpay_order_id'])
        user_id = int(order['notes']['user_id'])
        plan_id = order['notes']['plan_id']
        plan_days = int(order['notes']['plan_days'])
        
        user = get_current_user()
        
        # If already active, extend. Else start new
        if user.is_subscription_valid() and user.subscription_end_date and user.subscription_end_date > datetime.utcnow():
            user.subscription_end_date += timedelta(days=plan_days)
        else:
            user.subscription_end_date = datetime.utcnow() + timedelta(days=plan_days)
            
        user.subscription_status = 'active'
        user.plan_type = plan_id
        
        from extensions import db
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Payment successful! Plan activated.'})
        
    except razorpay.errors.SignatureVerificationError:
        return jsonify({'success': False, 'message': 'Payment verification failed'}), 400
    except Exception as e:
        print("PAYMENT SUCCESS ERROR:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500

@main_bp.route('/help')
def help_support():
    return render_template('help_support.html')
