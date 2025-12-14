
import sys
import os
import smtplib
from ldap3 import Server, Connection, ALL
from dotenv import load_dotenv

# Add web_app to path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), 'web_app'))
from config import Config

def test_ad():
    print("--- Testing Active Directory (LDAP) ---")
    server_uri = Config.LDAP_SERVER
    user_dn = Config.LDAP_BIND_DN
    password = Config.LDAP_BIND_PASSWORD
    
    print("Server: {}".format(server_uri))
    print("Bind DN: {}".format(user_dn))
    
    if not server_uri or not user_dn:
        print("[SKIP] LDAP_SERVER or LDAP_BIND_DN not set.")
        return

    try:
        server = Server(server_uri, get_info=ALL)
        conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        print("[SUCCESS] Successfully bound to AD.")
        print("Server Info: {}".format(server.info))
        
        # Try a search if possible
        if Config.LDAP_SEARCH_BASE:
            print("Testing Search in: {}".format(Config.LDAP_SEARCH_BASE))
            conn.search(Config.LDAP_SEARCH_BASE, '(objectClass=*)', size_limit=1)
            if conn.entries:
                print("[SUCCESS] Search returned {} entries.".format(len(conn.entries)))
            else:
                print("[WARNING] Search returned 0 entries. Check Search Base.")
    except Exception as e:
        print("[FAILED] AD Connection failed: {}".format(e))

def test_smtp():
    print("\n--- Testing Email (Zimbra/SMTP) ---")
    server_addr = Config.SMTP_SERVER
    port = Config.SMTP_PORT
    username = Config.SMTP_USERNAME
    password = Config.SMTP_PASSWORD
    use_tls = Config.SMTP_USE_TLS
    
    print("Server: {}:{}".format(server_addr, port))
    print("Username: {}".format(username))
    print("TLS: {}".format(use_tls))

    if not server_addr:
        print("[SKIP] SMTP_SERVER not set.")
        return

    try:
        smtp = smtplib.SMTP(server_addr, port)
        smtp.set_debuglevel(1)
        
        if use_tls:
            print("Starting TLS...")
            smtp.starttls()
            
        if username and password:
            print("Logging in...")
            smtp.login(username, password)
            print("[SUCCESS] SMTP Login successful.")
        else:
            print("[SUCCESS] SMTP Connected (No Auth).")
            
        smtp.quit()
    except Exception as e:
        print("[FAILED] SMTP Connection failed: {}".format(e))

if __name__ == "__main__":
    test_ad()
    test_smtp()
