from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from urllib.parse import urlparse

import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('TEST_DATABASE_URL', 'sqlite:///data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'supersecretkey'  # Needed for session management

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

class CrawlerResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    url = db.Column(db.Text, nullable=False)
    cover_url = db.Column(db.Text, nullable=True)
    content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def domain(self):
        try:
            return urlparse(self.url).netloc
        except:
            return ""

    def __repr__(self):
        return f'<CrawlerResult {self.title}>'

class CrawlerRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rule_name = db.Column(db.String(100), nullable=True) # Added rule_name
    domain = db.Column(db.String(200), unique=True, nullable=False)
    site_name = db.Column(db.String(200), nullable=True)
    title_xpath = db.Column(db.Text, nullable=True)
    content_xpath = db.Column(db.Text, nullable=True)
    headers = db.Column(db.Text, nullable=True) # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CrawlerRule {self.domain}>'

def init_db():
    with app.app_context():
        db.create_all()
        # Create default admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password='admin888')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created.")
        else:
            print("Admin user already exists.")

if __name__ == "__main__":
    init_db()
