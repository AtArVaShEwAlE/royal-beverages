import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class"""
    
    # Flask Secret Key (for sessions and security)
    SECRET_KEY = os.getenv('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Detect database type based on environment
    USE_POSTGRES = os.getenv('USE_POSTGRES', 'false').lower() == 'true'
    
    if USE_POSTGRES:
        # PostgreSQL Configuration (for PythonAnywhere)
        DB_TYPE = 'postgresql'
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
            f"{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
        )
        SQLALCHEMY_TRACK_MODIFICATIONS = False
    else:
        # MySQL Configuration (for local development)
        DB_TYPE = 'mysql'
        MYSQL_HOST = os.getenv('DB_HOST', 'localhost')
        MYSQL_USER = os.getenv('DB_USER', 'root')
        MYSQL_PASSWORD = os.getenv('DB_PASSWORD', '')
        MYSQL_DB = os.getenv('DB_NAME', 'royal_beverages_db')
        MYSQL_CURSORCLASS = 'DictCursor'
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour in seconds
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Email Configuration (for notifications later)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    
    # Upload Configuration (for future use)
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Pagination
    ITEMS_PER_PAGE = 10
    
    # App Configuration
    DEBUG = True  # Set to False in production
    TESTING = False


class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True  # Requires HTTPS


# Dictionary to easily switch between configurations
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}