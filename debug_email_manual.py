
import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Mock Config to avoid Flask app context issues if not needed
class Config:
    ENABLE_EMAIL = os.environ.get('ENABLE_EMAIL', 'False').lower() == 'true'
    SMTP_SERVER = os.environ.get('SMTP_SERVER')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'True').lower() == 'true'
    SMTP_DEFAULT_SENDER = os.environ.get('SMTP_DEFAULT_SENDER')

from dotenv import load_dotenv
load_dotenv()

def test_send_email(to_email):
    print("Testing email to: {}".format(to_email))
    print("SMTP Server: {}:{}".format(os.environ.get('SMTP_SERVER'), os.environ.get('SMTP_PORT')))
    print("SMTP User: {}".format(os.environ.get('SMTP_USERNAME')))

    try:
        msg = MIMEMultipart()
        msg['From'] = os.environ.get('SMTP_DEFAULT_SENDER')
        msg['To'] = to_email
        msg['Subject'] = "Test Email from PDF Redactor Debugger"
        msg.attach(MIMEText("This is a test email to verify SMTP configuration.", 'plain'))

        server = smtplib.SMTP(os.environ.get('SMTP_SERVER'), int(os.environ.get('SMTP_PORT', 587)))
        server.set_debuglevel(1) # Show SMTP interaction
        
        if os.environ.get('SMTP_USE_TLS', 'True').lower() == 'true':
            print("Starting TLS...")
            server.starttls()
        
        username = os.environ.get('SMTP_USERNAME')
        password = os.environ.get('SMTP_PASSWORD')
        
        if username and password:
            print("Logging in...")
            server.login(username, password)
        
        print("Sending message...")
        server.send_message(msg)
        server.quit()
        print("SUCCESS: Email sent to {}".format(to_email))
    except Exception as e:
        print("FAILURE: {}".format(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_send_email(sys.argv[1])
    else:
        test_send_email("mail1@alkhairsoft.com")
