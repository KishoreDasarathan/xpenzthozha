import os

class Config:
    # Flask needs this for sessions/login to work
    SECRET_KEY = '8f3a9c2e1b4d7f0a9c3e5b2d8f1a4c7e9b0d3f6a2c5e8b1d4f7a0c3e6b9d2f5'
    
    # MySQL Database Config for Windows local
    MYSQL_USERNAME = 'root'
    MYSQL_PASSWORD = '1211'
    MYSQL_HOST = 'localhost'
    MYSQL_DB_NAME = 'xpense'
    
    # SQLAlchemy connection string with utf8mb4 for emojis
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_USERNAME}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB_NAME}?charset=utf8mb4"
    
    # SQLAlchemy settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_RECYCLE = 299
    SQLALCHEMY_POOL_TIMEOUT = 20
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}

    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')