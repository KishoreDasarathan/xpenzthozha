from flask import Flask, request, session
from dotenv import load_dotenv
import config
load_dotenv()  # Load .env before importing config

from extensions import db
from routes.auth import auth_bp
from routes.main import main_bp
from routes.admin import admin_bp
from routes.api import api_bp
from datetime import datetime, timezone
import random

app = Flask(__name__)
app.config.from_object(config.Config)

db.init_app(app)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# Import models after db.init_app to avoid circular imports
from models.models import UsageLog, User

@app.before_request
def track_usage():
    # Skip static files and admin polling endpoints
    if request.endpoint in ['static'] or request.path.startswith('/api/admin/stats') or request.path.startswith('/api/admin/usage-report'):
        return
    
    user_id = session.get('user_id')
    if user_id:
        # Update last_active for online tracking
        try:
            User.query.filter_by(id=user_id).update({'last_active': datetime.now(timezone.utc)})
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error updating last_active: {e}")
    
    # Log request for daily stats - sample only 1/10 to avoid DB spam
    if random.randint(1, 10) == 1:
        try:
            log = UsageLog(
                user_id=user_id,
                endpoint=request.endpoint or request.path,
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error logging usage: {e}")

# Create tables
with app.app_context():
    try:
        db.create_all()
        print("Database tables checked/created successfully")
    except Exception as e:
        print(f"DB init error: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)