
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True) # AD users might not have email in local DB
    password_hash = db.Column(db.String(256), nullable=True) # Nullable for AD users
    is_ldap = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(20), default='user') # 'admin', 'user'

    # Optional: Cache AD group memberships locally if needed
    # groups = db.Column(db.String(500)) 

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.is_ldap:
            return False # Should verify against AD via Auth Provider
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return '<User {}>'.format(self.username)

    @property
    def is_admin(self):
        return self.role == 'admin'

class SecureLink(db.Model):
    token = db.Column(db.String(36), primary_key=True) # UUID
    file_id = db.Column(db.String(150), nullable=False)
    granted_to_email = db.Column(db.String(150), nullable=False)
    granted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    
    def is_valid(self):
        from datetime import datetime
        return datetime.utcnow() < self.expires_at

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False) # LOGIN, LINK_ACCESS, HIJACK_ATTEMPT, PURGE, UPLOAD
    user_id = db.Column(db.Integer, nullable=True) # If logged in
    user_email = db.Column(db.String(150), nullable=True) # If known via link
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(200), nullable=True)
    details = db.Column(db.Text, nullable=True) # JSON or text
    timestamp = db.Column(db.DateTime, nullable=False)

class LedgerBlock(db.Model):
    index = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.Float, nullable=False)
    data = db.Column(db.JSON, nullable=False)
    previous_hash = db.Column(db.String(64), nullable=False)
    hash = db.Column(db.String(64), nullable=False)

class PDFMetadata(db.Model):
    id = db.Column(db.String(36), primary_key=True) # UUID
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(150), nullable=False) # Internal Name
    original_filename = db.Column(db.String(150), nullable=False)
    file_hash = db.Column(db.String(64), nullable=False)
    upload_timestamp = db.Column(db.DateTime, nullable=False)
    is_purged = db.Column(db.Boolean, default=False)
    ledger_ref = db.Column(db.String(64), nullable=True) # Hash of the block

class AccessPermission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pdf_id = db.Column(db.String(36), db.ForeignKey('pdf_metadata.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    can_view = db.Column(db.Boolean, default=True)
    granted_at = db.Column(db.DateTime, nullable=False)

