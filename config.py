import os

class Config:
    # Secret key for session security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-123456789')
    
    # Database configuration
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "database.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
