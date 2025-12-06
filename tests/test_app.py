import unittest
import sys
import os
import json

# Set environment variable for test database BEFORE importing app
os.environ['TEST_DATABASE_URL'] = 'sqlite:///:memory:'

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, User, CrawlerResult

class IntelligentObservationTestCase(unittest.TestCase):
    def setUp(self):
        """Set up test variables and initialize app."""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        
        db.create_all()
        
        # Create admin user
        # Check if exists first (though in memory it shouldn't)
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password='admin888')
            db.session.add(admin)
            db.session.commit()

    def tearDown(self):
        """Tear down database after tests."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, username, password):
        return self.app.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    def test_login_logout(self):
        """Test login and logout functionality."""
        # Test correct login
        rv = self.login('admin', 'admin888')
        # Check for UTF-8 bytes or decoded string
        self.assertIn('数据采集中心', rv.data.decode('utf-8'))
        
        # Test logout
        rv = self.logout()
        self.assertIn('智能瞭望', rv.data.decode('utf-8'))

        # Test incorrect login
        rv = self.login('admin', 'wrongpassword')
        self.assertIn('Invalid username or password', rv.data.decode('utf-8'))

    def test_dashboard_access(self):
        """Test dashboard access control."""
        # Access without login
        rv = self.app.get('/dashboard', follow_redirects=True)
        # Should redirect to login
        self.assertIn('登录', rv.data.decode('utf-8')) # Check for Chinese "Login"
        
        # Access with login
        self.login('admin', 'admin888')
        rv = self.app.get('/dashboard')
        self.assertEqual(rv.status_code, 200)

    def test_save_results(self):
        """Test saving results to database."""
        self.login('admin', 'admin888')
        
        data = {
            'keyword': 'test_keyword',
            'items': [
                {
                    'title': 'Test Title',
                    'summary': 'Test Summary',
                    'url': 'http://test.url',
                    'cover_url': 'http://test.cover'
                }
            ]
        }
        
        rv = self.app.post('/save_results', 
                           data=json.dumps(data), 
                           content_type='application/json')
        
        self.assertEqual(rv.status_code, 200)
        json_response = json.loads(rv.data)
        self.assertEqual(json_response['status'], 'success')
        self.assertEqual(json_response['count'], 1)
        
        # Verify in DB
        result = CrawlerResult.query.filter_by(url='http://test.url').first()
        self.assertIsNotNone(result)
        self.assertEqual(result.title, 'Test Title')

    def test_data_management(self):
        """Test data management page."""
        self.login('admin', 'admin888')
        
        # Add a sample result
        new_result = CrawlerResult(
            keyword='test_search', 
            title='Test Result', 
            summary='Summary', 
            url='http://example.com', 
            cover_url='http://cover.com'
        )
        db.session.add(new_result)
        db.session.commit()
        
        rv = self.app.get('/data_management')
        self.assertIn('Test Result', rv.data.decode('utf-8'))
        
        # Test filter
        rv = self.app.get('/data_management?keyword=Test')
        self.assertIn('Test Result', rv.data.decode('utf-8'))
        
        rv = self.app.get('/data_management?keyword=NotFound')
        self.assertNotIn('Test Result', rv.data.decode('utf-8'))

if __name__ == '__main__':
    unittest.main()
