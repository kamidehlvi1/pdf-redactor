
import os
import sys
import uuid
import json
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash

# Add parent directory to path to import local modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import rect_redactor
from secure_redact import decrypt_data
import zipfile
import io

app = Flask(__name__)
app.secret_key = "supersecretkey" # For flash messages

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'pdf_file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    file = request.files['pdf_file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))
    if file:
        filename = str(uuid.uuid4()) + ".pdf"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return redirect(url_for('editor', filename=filename))

@app.route('/editor/<filename>')
def editor(filename):
    return render_template('index.html', filename=filename)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/redact', methods=['POST'])
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
    
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # We want to overwrite or chain redactions. 
    # If filename starts with "redacted_", we keep using it.
    # If not, we switch to "redacted_" version.
    
    if filename.startswith("redacted_"):
        output_filename = filename
    else:
        output_filename = "redacted_" + filename
        
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
    
    try:
        if os.path.exists(output_path) and output_filename == filename:
            # In-place update (we are editing the redacted file)
            temp_out = output_path + ".tmp"
            
            # Perform redaction to temp file
            rect_redactor.redact_regions(output_path, temp_out, page - 1, zones)
            
            # Move temp PDF to real output
            os.remove(output_path)
            os.rename(temp_out, output_path)
            
            # Handle Sidecar:
            # rect_redactor appends to "temp_out + .secure"
            # We need to merge this into "output_path + .secure"
            temp_secure = temp_out + ".secure"
            real_secure = output_path + ".secure"
             
            if os.path.exists(temp_secure):
                 # Load new entries from temp secure
                 with open(temp_secure, "r") as f:
                     new_data = json.load(f)
                 os.remove(temp_secure)
                 
                 # Append to real secure file
                 existing = []
                 if os.path.exists(real_secure):
                      with open(real_secure, "r") as f:
                          try: existing = json.load(f)
                          except: pass
                 
                 existing.extend(new_data)
                 with open(real_secure, "w") as f:
                     json.dump(existing, f)
            
        else:
            # First time redaction (Input -> Output)
            rect_redactor.redact_regions(input_path, output_path, page - 1, zones)
            
        return redirect(url_for('editor', filename=output_filename))
    except Exception as e:
        flash(str(e))
        return redirect(url_for('editor', filename=filename))

# New API to checking if secure file exists and getting regions
@app.route('/api/secure_metadata/<filename>')
def secure_metadata(filename):
    secure_path = os.path.join(app.config['UPLOAD_FOLDER'], filename + ".secure")
    if os.path.exists(secure_path):
        try:
            with open(secure_path, "r") as f:
                data = json.load(f)
            return {"zones": data}
        except:
             return {"zones": []} # Corrupt or empty
    return {"zones": []}

@app.route('/api/decrypt_zone', methods=['POST'])
def decrypt_zone():
    encrypted_content = request.json['content'] # The blob
    password = request.json['password']
    
    try:
        # Our secure_redact.decrypt_data returns string
        # encrypt_data output was b64 string.
        # decrypt_data takes b64 string.
        decrypted = decrypt_data(encrypted_content, password)
        
        if decrypted.startswith("Decryption Failed") or decrypted.startswith("Error"):
             return {"error": "Incorrect Password"}, 401
             
        # Result might be JSON string if we encrypted json.dumps(text)
        try:
            val = json.loads(decrypted)
            return {"text": val} 
        except:
            return {"text": decrypted}
            
    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/download_bundle/<filename>')
def download_bundle(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    secure_path = file_path + ".secure"
    
    if not os.path.exists(file_path):
        flash("File not found")
        return redirect(url_for('index'))
        
    # Create in-memory zip
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        # Add PDF
        zf.write(file_path, filename)
        
        # Add Secure Sidecar (if exists)
        if os.path.exists(secure_path):
            zf.write(secure_path, filename + ".secure")
            
        # Add Instructions
        readme_content = """SECURE REDACTION VIEWER INSTRUCTIONS
====================================

1. This package contains a Redacted PDF and a Secure Data file (.secure).
2. To view the original content of the redacted areas, you must use the Secure Viewer Web App.
3. Open the Web App and Upload this PDF.
4. Click on any redacted area (black box).
5. Enter the password provided to you by the document owner.

NOTE: Each redacted area may have a DIFFERENT password.
"""
        zf.writestr("README.txt", readme_content)
        
    memory_file.seek(0)
    
    from flask import send_file
    return send_file(memory_file, 
                     attachment_filename="secure_bundle_" + filename + ".zip", 
                     as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
