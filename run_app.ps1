# Run the Secure PDF Redactor Web App
Write-Host "Starting Secure PDF Redactor..."
$env:FLASK_APP = "web_app/app.py"
$env:FLASK_ENV = "development"
python web_app/app.py
