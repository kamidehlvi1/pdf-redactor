
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
