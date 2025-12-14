
import sys
import os
import io
import unittest
sys.path.append(r'c:\Users\me\Documents\PDFReductor\pdf-redactor\web_app')

from app import app, db, User
from storage import storage

class TestIntegration(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['ENABLE_MINIO'] = False # Force local for test
        self.app = app.test_client()
        self.ctx = app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_user_creation_and_auth(self):
        u = User(username='testuser', is_ldap=False)
        u.set_password('password')
        db.session.add(u)
        db.session.commit()
        
        found = User.query.filter_by(username='testuser').first()
        self.assertIsNotNone(found)
        self.assertTrue(found.check_password('password'))
        self.assertFalse(found.check_password('wrong'))
        print("\n[PASS] User Creation and Auth")

    def test_storage(self):
        # Determine test filename
        fname = "test_file.txt"
        content = b"Content"
        
        # Save
        storage.save_file(io.BytesIO(content), fname)
        
        # Check exists
        self.assertTrue(storage.exists(fname))
        
        # Check content via read
        fpath = storage.get_file_path(fname)
        with open(fpath, 'rb') as f:
            self.assertEqual(f.read(), content)
            
        # Clean up
        storage.delete(fname)
        self.assertFalse(storage.exists(fname))
        print("\n[PASS] Storage Manager (Save, Exists, Retrieve, Delete)")

if __name__ == '__main__':
    unittest.main()
