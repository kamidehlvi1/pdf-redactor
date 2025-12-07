
import os
import sys
import uuid
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash

# Add parent directory to path to import local modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import rect_redactor
from secure_redact import decrypt_data

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
    password = request.form['password']
    page = int(request.form['page'])
    x = float(request.form['x'])
    y = float(request.form['y'])
    w = float(request.form['w'])
    h = float(request.form['h'])
    
    # Coordinates from frontend (PDF.js) are top-left based.
    # PyMuPDF Rect is (x0, y0, x1, y1)
    # Frontend sends x, y, w, h
    x0 = x
    y0 = y
    x1 = x + w
    y1 = y + h
    rect = (x0, y0, x1, y1)
    
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    output_filename = "redacted_" + filename
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
    
    try:
        # Redact
        secure_blob = rect_redactor.redact_region(input_path, output_path, page - 1, rect, password)
        
        # Save secure sidecar
        with open(output_path + ".secure", "w") as f:
            f.write(secure_blob)
            
        return redirect(url_for('view_secure', filename=output_filename))
    except Exception as e:
        flash(str(e))
        return redirect(url_for('editor', filename=filename))

@app.route('/view/<filename>')
def view_secure(filename):
    return render_template('view.html', filename=filename)

@app.route('/api/decrypt', methods=['POST'])
def decrypt():
    filename = request.json['filename']
    password = request.json['password']
    
    secure_path = os.path.join(app.config['UPLOAD_FOLDER'], filename + ".secure")
    
    if not os.path.exists(secure_path):
        return {"error": "Secure file not found"}, 404
        
    try:
        with open(secure_path, "r") as f:
            encrypted_blob = f.read()
            
        json_data = decrypt_data(encrypted_blob, password)
        
        if json_data.startswith("Decryption Failed") or json_data.startswith("Error"):
             return {"error": "Incorrect Password"}, 401
             
        import json
        items = json.loads(json_data)
        return {"text": items[0]} # We only stored one item in rect_redactor
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
