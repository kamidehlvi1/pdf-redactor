
import ldap3
from models import User, db
from config import Config

class AuthProvider:
    def authenticate(self, username, password):
        raise NotImplementedError

    def search_users(self, query):
        raise NotImplementedError

class LocalProvider(AuthProvider):
    def authenticate(self, username, password):
        user = User.query.filter_by(username=username, is_ldap=False).first()
        if user and user.check_password(password):
            return user
        return None

    def search_users(self, query):
        users = User.query.filter(User.username.ilike('%{}%'.format(query)), User.is_ldap==False).limit(10).all()
        return [{'id': u.id, 'username': u.username, 'source': 'Local', 'email': u.email} for u in users]

    def create_user(self, username, password, email=None):
        if User.query.filter_by(username=username).first():
            return False # Already exists
        new_user = User(username=username, email=email, is_ldap=False)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return new_user

class LDAPProvider(AuthProvider):
    def __init__(self):
        self.enabled = Config.ENABLE_AD_AUTH
        self.server_uri = Config.LDAP_SERVER
        self.bind_dn = Config.LDAP_BIND_DN
        self.bind_password = Config.LDAP_BIND_PASSWORD
        self.search_base = Config.LDAP_SEARCH_BASE

    def authenticate(self, username, password):
        if not self.enabled:
            return None
        
        # 1. Bind with Service Account (or Anonymous if supported, but typically Service Account)
        # For simplicity, we might try direct bind with user credentials if user DN can be constructed.
        # But best practice: Bind Service -> Search User DN -> Bind User
        
        try:
            server = ldap3.Server(self.server_uri, get_info=ldap3.ALL)
            # Bind with service account to find the user
            conn = ldap3.Connection(server, user=self.bind_dn, password=self.bind_password, auto_bind=True)
            
            # Search for the user to get their DN
            search_filter = '(sAMAccountName={})'.format(username)
            conn.search(self.search_base, search_filter, attributes=['mail', 'displayName'])
            
            if not conn.entries:
                return None
            
            user_entry = conn.entries[0]
            user_dn = user_entry.entry_dn
            user_email = str(user_entry.mail) if 'mail' in user_entry else None
            
            # 2. Verify Creds: Bind with User DN and Password
            user_conn = ldap3.Connection(server, user=user_dn, password=password)
            if not user_conn.bind():
                return None # Bad password
                
            # 3. Valid. Return User object. 
            # We treat AD users as transient or we sync them to local DB. 
            # Syncing is better for "Allowed Users" references by ID.
            
            user = User.query.filter_by(username=username, is_ldap=True).first()
            if not user:
                user = User(username=username, email=user_email, is_ldap=True)
                db.session.add(user)
                db.session.commit()
            
            return user
            
        except Exception as e:
            print("LDAP Error: {}".format(e))
            return None

    def search_users(self, query):
        if not self.enabled:
            return []
            
        try:
            server = ldap3.Server(self.server_uri, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, user=self.bind_dn, password=self.bind_password, auto_bind=True)
            
            search_filter = '(&(objectClass=user)(sAMAccountName=*{}*))'.format(query)
            conn.search(self.search_base, search_filter, attributes=['sAMAccountName', 'mail'], size_limit=10)
            
            results = []
            for entry in conn.entries:
                results.append({
                    'id': str(entry.sAMAccountName), # Use string for AD (or we sync and use int ID?)
                    # For consistency with Local, let's return a dict structure. 
                    # If the user selects this, we might auto-create the shadow user record.
                    'username': str(entry.sAMAccountName),
                    'source': 'Active Directory',
                    'email': str(entry.mail) if 'mail' in entry else ""
                })
            return results
        except Exception as e:
            print("LDAP Search Error: {}".format(e))
            return []

class CompositeAuthProvider:
    def __init__(self):
        self.local = LocalProvider()
        self.ldap = LDAPProvider()

    def authenticate(self, username, password):
        # Try Local first
        user = self.local.authenticate(username, password)
        if user:
            return user
        
        # Try LDAP
        return self.ldap.authenticate(username, password)

    def search(self, query):
        local_results = self.local.search_users(query)
        ldap_results = self.ldap.search_users(query)
        return local_results + ldap_results
