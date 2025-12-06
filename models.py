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
    url_pattern = db.Column(db.String(500), nullable=True) # Added url_pattern
    title_xpath = db.Column(db.Text, nullable=True)
    content_xpath = db.Column(db.Text, nullable=True)
    headers = db.Column(db.Text, nullable=True) # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CrawlerRule {self.domain}>'

    def to_dict(self):
        return {
            'id': self.id,
            'rule_name': self.rule_name,
            'domain': self.domain,
            'site_name': self.site_name,
            'url_pattern': self.url_pattern,
            'title_xpath': self.title_xpath,
            'content_xpath': self.content_xpath,
            'headers': self.headers,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

class CrawlerDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    crawler_result_id = db.Column(db.Integer, db.ForeignKey('crawler_result.id'), nullable=False)
    rule_id = db.Column(db.Integer, db.ForeignKey('crawler_rule.id'), nullable=True)
    clean_title = db.Column(db.String(500), nullable=True)
    clean_content = db.Column(db.Text, nullable=True)
    raw_html = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    crawler_result = db.relationship('CrawlerResult', backref=db.backref('details', lazy=True))
    rule = db.relationship('CrawlerRule', backref=db.backref('details', lazy=True))

class AIModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False) # Display Name
    provider = db.Column(db.String(100), nullable=True) # e.g., SiliconFlow, OpenAI
    api_base = db.Column(db.String(500), nullable=False)
    api_key = db.Column(db.String(500), nullable=False)
    model_name = db.Column(db.String(200), nullable=False) # Actual model ID string
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'provider': self.provider,
            'api_base': self.api_base,
            'api_key': self.api_key, # Should be masked in frontend usually, but for edit we might need it
            'model_name': self.model_name,
            'description': self.description,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else ''
        }

class TokenUsageLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey('ai_model.id'), nullable=False)
    tokens_used = db.Column(db.Integer, default=0)
    request_type = db.Column(db.String(50), default='chat')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    model = db.relationship('AIModel', backref=db.backref('usage_logs', lazy=True))

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
