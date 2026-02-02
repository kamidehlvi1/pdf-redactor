
import os
import sys
import uuid
import json
import random
import string
import smtplib
import io
import zipfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify, send_file, session, abort
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import rect_redactor
from secure_redact import decrypt_data
from config import Config
from models import db, User, AuditLog, SecureLink, PDFMetadata, LedgerBlock, AccessPermission
from ledger import ledger
from auth import CompositeAuthProvider, LocalProvider
from storage import storage

app = Flask(__name__)
app.config.from_object(Config)

# Session Security
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Secure cookie requires HTTPS, but we can set it conditionally or disable for localhost dev
app.config['SESSION_COOKIE_SECURE'] = False # Set to True in prod with HTTPS

# Initialize Extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

auth_provider = CompositeAuthProvider()
local_provider = LocalProvider()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_first_request
def create_tables():
    db.create_all()
    # Create default admin if not exists
    if not User.query.filter_by(username='admin').first():
        local_provider.create_user('admin', 'admin', 'admin@example.com')
        # Assign admin role
        u = User.query.filter_by(username='admin').first()
        u.role = 'admin'
        db.session.commit()
    
    # Init Ledger
    ledger.create_genesis_block()

# --- Helper: Audit Logging ---
def log_audit(event_type, details=None, user=None):
    try:
        if not user:
            user = current_user if current_user.is_authenticated else None
            
        uid = user.id if user else None
        uemail = user.email if user else None
        
        # If details is dict, dump to json string
        if isinstance(details, dict):
            details = json.dumps(details)
            
        log = AuditLog(
            event_type=event_type,
            user_id=uid,
            user_email=uemail,
            ip_address=request.remote_addr,
            user_agent=str(request.user_agent),
            details=details,
            timestamp=datetime.utcnow()
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print("Audit Log Error: {}".format(e))

# --- Middleware: Session Security ---
@app.before_request
def check_session_hijack():
    if current_user.is_authenticated:
        # Expected IP/UA from session
        session_ip = session.get('ip')
        session_ua = session.get('ua')
        
        current_ip = request.remote_addr
        current_ua = str(request.user_agent)
        
        if session_ip and session_ip != current_ip:
            log_audit('HIJACK_ATTEMPT', 'IP Mismatch: {} vs {}'.format(session_ip, current_ip))
            logout_user()
            flash("Session invalidated due to IP change.")
            return redirect(url_for('login'))
            
        if session_ua and session_ua != current_ua:
            log_audit('HIJACK_ATTEMPT', 'UA Mismatch') # Don't log full UA to save space or log it if needed
            logout_user()
            flash("Session invalidated due to browser change.")
            return redirect(url_for('login'))

# --- Email Helper ---
def send_email(to_email, subject, body):
    if not Config.ENABLE_EMAIL or not to_email:
        print("Email disabled or no recipient. Would send: {} to {}".format(subject, to_email))
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = Config.SMTP_DEFAULT_SENDER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
        if Config.SMTP_USE_TLS:
            server.starttls()
        if Config.SMTP_USERNAME and Config.SMTP_PASSWORD:
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
        
        server.send_message(msg)
        server.quit()
        print("Email sent to {}".format(to_email))
    except Exception as e:
        print("Failed to send email: {}".format(e))

# --- Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = auth_provider.authenticate(username, password)
        if user:
            # Bind session to IP/UA for anti-hijacking
            session['ip'] = request.remote_addr
            session['ua'] = str(request.user_agent)
            session.permanent = True
            
            log_audit('LOGIN', user=user)
            login_user(user)
            return redirect(url_for('index'))
        else:
            log_audit('LOGIN_FAILED', {'username': username})
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
@login_required
def logout():
    log_audit('LOGOUT', user=current_user)
    logout_user()
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    # V3 Dashboard Data
    
    # 1. My PDFs
    my_pdfs = PDFMetadata.query.filter_by(owner_id=current_user.id).order_by(PDFMetadata.upload_timestamp.desc()).all()
    
    # 2. Shared With Me (via SecureLink)
    # Find links granted to current user's email
    shared_links = []
    if current_user.email:
        shared_links = SecureLink.query.filter_by(granted_to_email=current_user.email).all()
        
    # 3. Activity Logs
    # User sees their own logs. Admin sees all? Requirement: "Every user must have access to: Their own activity logs only"
    logs = AuditLog.query.filter((AuditLog.user_id == current_user.id) | (AuditLog.user_email == current_user.email)).order_by(AuditLog.timestamp.desc()).limit(50).all()
    
    return render_template('dashboard.html', user=current_user, my_pdfs=my_pdfs, shared_links=shared_links, logs=logs)

@app.route('/api/search_users')
@login_required
def search_users_api():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    results = auth_provider.search(query)
    return jsonify(results)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'pdf_file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    file = request.files['pdf_file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))
        
    if file:
        filename = file.filename
        
        # Handle Zip Bundle
        if filename.lower().endswith('.zip'):
             # Logic for zip upload (simplified for MinIO support: we must extract locally first)
             # MinIO doesn't support random access extraction easily without download.
             # So we use memory or temp file.
             temp_zip_path = os.path.join(app.config['UPLOAD_FOLDER'], "temp_" + str(uuid.uuid4()) + ".zip")
             file.save(temp_zip_path) # Temp save even if using MinIO, for extraction
             
             extracted_pdf_name = None
             try:
                 with zipfile.ZipFile(temp_zip_path, 'r') as zf:
                     for name in zf.namelist():
                         if name.lower().endswith('.pdf'):
                             # Extract to memory then save to storage
                             with zf.open(name) as pdf_f:
                                 # We need to save this using storage manager.
                                 # We wrap it in BytesIO to keep it consistent
                                 mem_pdf = io.BytesIO(pdf_f.read())
                                 extracted_pdf_name = name # Use original name or UUID?
                                 # Let's enforce UUID for internal storage to avoid conflicts
                                 internal_name = str(uuid.uuid4()) + ".pdf"
                                 storage.save_file(mem_pdf, internal_name)
                                 extracted_pdf_name = internal_name
                             break
             except Exception as e:
                 flash("Invalid Zip: " + str(e))
                 return redirect(url_for('index'))
             finally:
                 if os.path.exists(temp_zip_path):
                     os.remove(temp_zip_path)
            
             if extracted_pdf_name:
                 return redirect(url_for('editor', filename=extracted_pdf_name))
             else:
                 flash("No PDF found in Zip")
                 return redirect(url_for('index'))

        if not filename.lower().endswith('.pdf'):
             flash("Invalid file type. Please upload PDF.")
             return redirect(url_for('index'))
             
        # New PDF Upload
        internal_name = str(uuid.uuid4()) + ".pdf"
        
        # V3: Calculate Hash & Ledger
        import hashlib
        file.stream.seek(0)
        sha256_hash = hashlib.sha256(file.stream.read()).hexdigest()
        file.stream.seek(0)
        
        storage.save_file(file, internal_name)
        
        # Create Metadata
        meta = PDFMetadata(
            id=internal_name.replace('.pdf', ''), # UUID
            owner_id=current_user.id,
            filename=internal_name,
            original_filename=filename,
            file_hash=sha256_hash,
            upload_timestamp=datetime.utcnow(),
            is_purged=False
        )
        
        # Add to Ledger
        block_data = {
            'action': 'UPLOAD',
            'file_id': meta.id,
            'owner_id': current_user.id,
            'hash': sha256_hash,
            'filename': filename
        }
        block = ledger.add_block(block_data)
        meta.ledger_ref = block.hash
        
        db.session.add(meta)
        log_audit('UPLOAD', {'file_id': meta.id, 'hash': sha256_hash})
        db.session.commit()
        
        return redirect(url_for('editor', filename=internal_name))

@app.route('/editor/<filename>')
@login_required
def editor(filename):
    # V3 Logic
    meta = PDFMetadata.query.filter_by(filename=filename).first()
    
    if meta:
        if meta.is_purged:
            # Gone (We need a purged template or just error)
            flash("This document has been permanently purged.")
            return redirect(url_for('index'))
            
        # Permission Check
        # Owner or Admin -> Full Access (Editor Mode)
        if current_user.is_admin or current_user.id == meta.owner_id:
            # Serve the original Editor (index.html) which allows redaction
            return render_template('index.html', filename=filename, user=current_user)
            
        # Restricted User -> Viewer V3 (Restricted Mode)
        return render_template('viewer_v3.html', filename=filename, mode='restricted', user=current_user)

    # Legacy Fallback
    if not storage.exists(filename):
        flash("File not found.")
        return redirect(url_for('index'))
    return render_template('index.html', filename=filename, user=current_user)

    # Legacy Fallback
    if not storage.exists(filename):
        flash("File not found.")
        return redirect(url_for('index'))
    return render_template('index.html', filename=filename, user=current_user)

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    # This might be tricky with MinIO if we want to serve directly.
    # For now, we download to temp or use a stream.
    # storage.get_file_path returns a local path (downloading if needed).
    local_path = storage.get_file_path(filename)
    if local_path:
        return send_file(local_path)
    return "File not found", 404

@app.route('/redact', methods=['POST'])
@login_required
def redact():
    filename = request.form['filename']
    page = int(request.form['page'])
    zones_json = request.form.get('zones', '[]')
    
    try:
        zones = json.loads(zones_json)
    except:
        zones = []
        
    if not zones:
        flash("No redaction zones provided")
        return redirect(url_for('editor', filename=filename))
    
    # Process Zones for Passwords and Emails
    processed_zones = []
    
    for zone in zones:
        # Check if we need to auto-generate password
        # Frontend should send: { rect: [...], password: "...", allowedUsers: [{email: ...}] }
        
        pwd = zone.get('password', '')
        allowed_users = zone.get('allowedUsers', [])
        
        # If no password provided but we have allowed users, generate one
        if not pwd and allowed_users:
            alphabet = string.ascii_letters + string.digits + "!@#$%"
            # Use SystemRandom for cryptographic security
            pwd = ''.join(random.SystemRandom().choice(alphabet) for i in range(12))
            zone['password'] = pwd # Update for redactor to use
            
        # Send Emails
        if pwd and allowed_users:
            for u in allowed_users:
                email = u.get('email')
                if email:
                    # Create Secure Link
                    token = str(uuid.uuid4())
                    link = SecureLink(
                        token=token,
                        file_id=filename, # Link points to original or redacted? 
                        # Actually redacted view usually needs the redacted file. 
                        # We'll determine filename later in logic, but wait... 
                        # Secure Links should probably point to the output filename.
                        # But output filename isn't known yet! 
                        # Let's use the input filename and resolve 'redacted_' prefix dynamically or 
                        # Better: Process zones first, THEN send emails.
                    )
                    # Issue: filename here is INPUT filename. Output is likely 'redacted_' + filename.
                    # We should defer email sending until AFTER redaction or predict the name.
                    # The code predicts: output_filename = "redacted_" + filename (if not already)
                    
                    target_file = filename if filename.startswith("redacted_") else "redacted_" + filename
                    
                    link.file_id = target_file
                    link.granted_to_email = email
                    link.granted_by_id = current_user.id
                    link.created_at = datetime.utcnow()
                    link.expires_at = datetime.utcnow() + timedelta(days=7) # 1 week expiry
                    
                    db.session.add(link)
                    log_audit('LINK_CREATED', {'token': token, 'target': target_file, 'to': email})
                    
                    view_url = url_for('view_shared', token=token, _external=True)
                    
                    subject = "Secure Document Access Granted"
                    body = "Hello,\n\nYou have been granted access to a secure document.\n\n" \
                           "Access Link: {}\n" \
                           "Password: {}\n\n" \
                           "Please keep this credentials secure.".format(view_url, pwd)
                    send_email(email, subject, body)
            
            db.session.commit() # Commit links
        
        processed_zones.append(zone)

    # Prepare paths
    # Because rect_redactor works with filesystem paths, we need local files.
    input_path = storage.get_file_path(filename)
    if not input_path:
        flash("Original file lost.")
        return redirect(url_for('index'))

    if filename.startswith("redacted_"):
        output_filename = filename
    else:
        output_filename = "redacted_" + filename
        
    # We need a temp path for output before saving to storage
    temp_output_path = os.path.join(app.config['UPLOAD_FOLDER'], "temp_out_" + output_filename)
    
    try:
        # If modifying existing redacted, usage is input -> temp
        # rect_redactor expects input path.
        # If output_filename == filename, we are iterating.
        
        rect_redactor.redact_regions(input_path, temp_output_path, page - 1, processed_zones)
        
        # Now save temp_output_path back to storage
        with open(temp_output_path, 'rb') as f:
            storage.save_file(f, output_filename)
            
        # Handle Sidecar (.secure)
        # rect_redactor created temp_output_path + ".secure"
        temp_secure_path = temp_output_path + ".secure"
        real_secure_filename = output_filename + ".secure"
        
        new_data = []
        if os.path.exists(temp_secure_path):
            with open(temp_secure_path, "r") as f:
                new_data = json.load(f)
            os.remove(temp_secure_path)
            
        # Merge with existing secure data if exists in storage
        existing_data = []
        try:
            # Check if exists in storage
            if storage.exists(real_secure_filename):
                local_secure = storage.get_file_path(real_secure_filename)
                with open(local_secure, "r") as f:
                    existing_data = json.load(f)
        except:
            pass
            
        merged_data = existing_data + new_data
        
        # Write merged secure back to storage
        # Need string -> file obj
        secure_io = io.BytesIO(json.dumps(merged_data).encode('utf-8'))
        storage.save_file(secure_io, real_secure_filename)

        # Cleanup locals
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
            
        return redirect(url_for('editor', filename=output_filename))
        
    except Exception as e:
        flash("Redaction Error: {}".format(str(e)))
        import traceback
        traceback.print_exc()
        return redirect(url_for('editor', filename=filename))

@app.route('/api/secure_metadata/<filename>')
@login_required
def secure_metadata(filename):
    secure_name = filename + ".secure"
    if storage.exists(secure_name):
        local_path = storage.get_file_path(secure_name)
        if local_path:
            try:
                with open(local_path, "r") as f:
                    data = json.load(f)
                return {"zones": data}
            except:
                pass
    return {"zones": []}

@app.route('/api/decrypt_zone', methods=['POST'])
@login_required
def decrypt_zone():
    encrypted_content = request.json.get('content')
    password = request.json.get('password')
    
    try:
        decrypted = decrypt_data(encrypted_content, password)
        if decrypted.startswith("Decryption Failed") or decrypted.startswith("Error"):
             return {"error": "Incorrect Password"}, 401
        
        try:
            val = json.loads(decrypted)
            return {"text": val} 
        except:
            return {"text": decrypted}
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/download_bundle/<filename>')
@login_required
def download_bundle(filename):
    local_pdf = storage.get_file_path(filename)
    if not local_pdf:
        flash("File not found")
        return redirect(url_for('index'))
        
    secure_name = filename + ".secure"
    local_secure = storage.get_file_path(secure_name)
    
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        zf.write(local_pdf, filename)
        if local_secure:
            zf.write(local_secure, secure_name)
        
        zf.writestr("README.txt", "Use the Secure Web App to view the sensitive content.")
        
    memory_file.seek(0)
    return send_file(memory_file, attachment_filename="bundle_{}.zip".format(filename), as_attachment=True)

# Admin Routes for Local Users
@app.route('/admin')
@login_required
def admin_panel():
    if current_user.username != 'admin':
        flash("Unauthorized")
        return redirect(url_for('index'))
    users = User.query.filter_by(is_ldap=False).all()
    return render_template('admin.html', users=users)

@app.route('/admin/create_user', methods=['POST'])
@login_required
def admin_create_user():
    if current_user.username != 'admin':
        return "Unauthorized", 403
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email')
    
    if local_provider.create_user(username, password, email):
        flash("User {} created.".format(username))
    else:
        flash("User already exists.")
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.username != 'admin' and not current_user.is_admin:
        return "Unauthorized", 403
    
    user = User.query.get(user_id)
    if user:
        if user.username == 'admin':
            flash("Cannot delete default admin.")
        else:
            db.session.delete(user)
            db.session.commit()
            flash("User deleted.")
    return redirect(url_for('admin_panel'))

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    if current_user.username != 'admin' and not current_user.is_admin:
        return "Unauthorized", 403
        
    user = User.query.get(user_id)
    if not user:
        flash("User not found")
        return redirect(url_for('admin_panel'))
        
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        
        # Optional password update
        password = request.form.get('password')
        if password:
            user.set_password(password)
            
        db.session.commit()
        flash("User updated.")
        return redirect(url_for('admin_panel'))
        
    return render_template('edit_user.html', user=user)

@app.route('/purge/<pdf_id>', methods=['POST'])
@login_required
def purge_file(pdf_id):
    # Verify Permissions
    meta = PDFMetadata.query.get(pdf_id)
    if not meta:
        filename = pdf_id + ".pdf" # Fallback if ID is just UUID part
        # Try finding by filename if ID lookup fails (legacy support?)
        # For now assume ID matches.
        return "File not found", 404
        
    if not current_user.is_admin and current_user.id != meta.owner_id:
        log_audit('ACCESS_DENIED', {'action': 'PURGE', 'file_id': pdf_id})
        return "Unauthorized", 403
        
    # Perform Purge
    # 1. Delete physical file
    storage.delete(meta.filename)
    
    meta.is_purged = True
    
    # Ledger
    block_data = {
        'action': 'PURGE',
        'file_id': pdf_id,
        'by_user': current_user.id,
        'timestamp': time.time()
    }
    block = ledger.add_block(block_data)
    
    log_audit('PURGE', {'file_id': pdf_id, 'ledger_hash': block.hash})
    db.session.commit()
    
    flash("File permanently purged.")
    return redirect(url_for('index'))

# --- AD Management Routes ---
@app.route('/admin/ad')
@login_required
def admin_ad_panel():
    if current_user.username != 'admin' and not current_user.is_admin:
        return "Unauthorized", 403
    return render_template('admin_ad.html')

@app.route('/admin/ad/create_user', methods=['POST'])
@login_required
def ad_create_user():
    if current_user.username != 'admin' and not current_user.is_admin:
        return "Unauthorized", 403
        
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email')
    firstname = request.form.get('firstname')
    lastname = request.form.get('lastname')
    
    # Use global composite_provider.ldap or create new instance?
    # composite_provider is global.
    success, msg = composite_provider.ldap.create_ad_user(username, password, email, firstname, lastname)
    if success:
        flash("AD User Created: {}".format(username))
    else:
        flash("Error: {}".format(msg))
    return redirect(url_for('admin_ad_panel'))

@app.route('/admin/ad/create_group', methods=['POST'])
@login_required
def ad_create_group():
    if current_user.username != 'admin' and not current_user.is_admin:
        return "Unauthorized", 403
        
    groupname = request.form.get('groupname')
    success, msg = composite_provider.ldap.create_ad_group(groupname)
    if success:
        flash("AD Group Created: {}".format(groupname))
    else:
        flash("Error: {}".format(msg))
    return redirect(url_for('admin_ad_panel'))

@app.route('/admin/ad/add_to_group', methods=['POST'])
@login_required
def ad_add_to_group():
    if current_user.username != 'admin' and not current_user.is_admin:
        return "Unauthorized", 403
        
    username = request.form.get('username')
    groupname = request.form.get('groupname')
    
    success, msg = composite_provider.ldap.add_user_to_group(username, groupname)
    if success:
        flash("Added {} to group {}".format(username, groupname))
    else:
        flash("Error: {}".format(msg))
    return redirect(url_for('admin_ad_panel'))

    return redirect(url_for('admin_panel'))

@app.route('/view_shared/<token>')
def view_shared(token):
    # 1. Validate Token
    link = SecureLink.query.get(token)
    if not link or not link.is_valid():
        flash("Invalid or expired link.")
        return redirect(url_for('index'))
    
    # 2. Authentication Required
    if not current_user.is_authenticated:
        return redirect(url_for('login', next=request.url))
        
    # 3. Authorization Check (Identity Verification)
    # Check if current user email matches granted email
    # Note: AD users might have email populated. Local users definitely do if set.
    user_email = current_user.email
    if not user_email or user_email.lower() != link.granted_to_email.lower():
        # Fallback: Maybe they used username? But we granted to email.
        # Strict security: Deny.
        log_audit('ACCESS_DENIED', {'token': token, 'reason': 'Email mismatch', 'user': current_user.username})
        flash("Access Denied. You are logged in as {}, but this link is for {}.".format(current_user.username, link.granted_to_email))
        return redirect(url_for('index'))

    # 4. Success -> Redirect to Editor
    log_audit('LINK_ACCESS', {'token': token, 'file': link.file_id})
    return redirect(url_for('editor', filename=link.file_id))

if __name__ == '__main__':
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
