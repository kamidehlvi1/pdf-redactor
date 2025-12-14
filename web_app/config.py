
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask Settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev_super_secret_key_change_in_prod'
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    
    # Database Settings (Local Users)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'local_users.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # MinIO Settings (Object Storage)
    # If MINIO_ENDPOINT is not set, we default to local file storage for backward compatibility during dev
    MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT') # e.g., 'play.min.io:9000'
    MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY')
    MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY')
    MINIO_BUCKET = os.environ.get('MINIO_BUCKET') or 'secure-pdfs'
    MINIO_SECURE = os.environ.get('MINIO_SECURE', 'True').lower() == 'true'

    # Active Directory Settings (LDAP)
    LDAP_SERVER = os.environ.get('LDAP_SERVER') # e.g., 'ldap://domain.com'
    LDAP_BIND_DN = os.environ.get('LDAP_BIND_DN') # Service account to search users
    LDAP_BIND_PASSWORD = os.environ.get('LDAP_BIND_PASSWORD')
    LDAP_SEARCH_BASE = os.environ.get('LDAP_SEARCH_BASE') # e.g., 'dc=example,dc=com'
    
    # Email Settings (Zimbra/SMTP)
    SMTP_SERVER = os.environ.get('SMTP_SERVER')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'True').lower() == 'true'
    SMTP_DEFAULT_SENDER = os.environ.get('SMTP_DEFAULT_SENDER') or 'noreply@example.com'

    # Feature Flags
    ENABLE_AD_AUTH = os.environ.get('ENABLE_AD_AUTH', 'False').lower() == 'true'
    ENABLE_MINIO = os.environ.get('ENABLE_MINIO', 'False').lower() == 'true'
    ENABLE_EMAIL = os.environ.get('ENABLE_EMAIL', 'False').lower() == 'true'
