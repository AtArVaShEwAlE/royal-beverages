import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class"""
    
    # Flask Secret Key (for sessions and security)
    SECRET_KEY = os.getenv('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # MySQL Configuration (works on local, Railway, and Render)
    DB_TYPE = 'mysql'
    MYSQL_HOST     = os.getenv('DB_HOST', 'localhost')
    MYSQL_USER     = os.getenv('DB_USER', 'root')
    MYSQL_PASSWORD = os.getenv('DB_PASSWORD', '')
    MYSQL_DB       = os.getenv('DB_NAME', 'royal_beverages_db')
    MYSQL_PORT     = int(os.getenv('DB_PORT', 3306))   # Railway uses a custom port
    MYSQL_CURSORCLASS = 'DictCursor'
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = 3600
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Email Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@royalbeverages.com')
    
    # Upload Configuration
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # Pagination
    ITEMS_PER_PAGE = 10

    # App Configuration
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}