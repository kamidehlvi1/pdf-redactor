
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
                    'id': str(entry.sAMAccountName), 
                    'username': str(entry.sAMAccountName),
                    'source': 'Active Directory',
                    'email': str(entry.mail) if 'mail' in entry else ""
                })
            return results
        except Exception as e:
            print("LDAP Search Error: {}".format(e))
            return []

    def create_ad_user(self, username, password, email=None, firstname="User", lastname="Name"):
        if not self.enabled:
            return False, "AD Not Enabled"
            
        try:
            server = ldap3.Server(self.server_uri, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, user=self.bind_dn, password=self.bind_password, auto_bind=True)
            
            # Construct DN
            # Default to CN=Users,DC=example,DC=com (Same as Search Base or specifically Users container)
            # We assume Search Base is the domain root or appropriate OU. Let's try to infer or use config.
            # Simplified: Use Search Base directly if it's an OU, or append string.
            # For robustness, we will assume self.search_base is where we want to put them for now.
            dn = "CN={},{}".format(username, self.search_base)
            
            attributes = {
                'objectClass': ['top', 'person', 'organizationalPerson', 'user'],
                'cn': username,
                'sAMAccountName': username,
                'userPrincipalName': '{}@{}'.format(username, self.search_base.replace('DC=','').replace(',','.')), # Rough domain guess
                'userPassword': password,
                'givenName': firstname,
                'sn': lastname,
                'displayName': "{} {}".format(firstname, lastname),
                'mail': email or "",
                'userAccountControl': 512 # Enable Account (Normal Account)
            }
            
            if conn.add(dn, attributes=attributes):
                return True, "User Created in AD"
            else:
                return False, "LDAP Error: {}".format(conn.result['description'])
                
        except Exception as e:
            return False, str(e)

    def create_ad_group(self, groupname):
        if not self.enabled:
            return False, "AD Not Enabled"
            
        try:
            server = ldap3.Server(self.server_uri, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, user=self.bind_dn, password=self.bind_password, auto_bind=True)
            
            dn = "CN={},{}".format(groupname, self.search_base)
            
            attributes = {
                'objectClass': ['top', 'group'],
                'cn': groupname,
                'sAMAccountName': groupname,
                'groupType': -2147483646 # Global Security Group
            }
            
            if conn.add(dn, attributes=attributes):
                return True, "Group Created"
            else:
                return False, "LDAP Error: {}".format(conn.result['description'])
                
        except Exception as e:
            return False, str(e)

    def add_user_to_group(self, username, groupname):
        if not self.enabled:
            return False, "AD Not Enabled"
        
        try:
            server = ldap3.Server(self.server_uri, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, user=self.bind_dn, password=self.bind_password, auto_bind=True)
            
            # 1. Find User DN
            conn.search(self.search_base, '(sAMAccountName={})'.format(username), attributes=['distinguishedName'])
            if not conn.entries:
                return False, "User not found"
            user_dn = conn.entries[0].entry_dn
            
            # 2. Find Group DN
            conn.search(self.search_base, '(&(objectClass=group)(cn={}))'.format(groupname), attributes=['distinguishedName'])
            if not conn.entries:
                return False, "Group not found"
            group_dn = conn.entries[0].entry_dn
            
            # 3. Modify Group
            if conn.modify(group_dn, {'member': [(ldap3.MODIFY_ADD, [user_dn])]}):
                return True, "User added to group"
            else:
                return False, "LDAP Error: {}".format(conn.result['description'])
                
        except Exception as e:
            return False, str(e)

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
