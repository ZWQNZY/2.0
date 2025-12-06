from flask import render_template, request, redirect, url_for, session, flash, jsonify
from models import app, db, User, CrawlerResult
from baidu_crawler import search_baidu
from datetime import datetime

# --- Routes ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    results = []
    keyword = ""
    
    if request.method == 'POST':
        keyword = request.form['keyword']
        if keyword:
            results = search_baidu(keyword)
            # Temporarily store results in session or just render them
            # For simplicity, we'll render them directly. 
            # To support saving, we need to send them back or keep track.
            # We will pass them to the template, and the save action will accept the data to save.
            
    return render_template('dashboard.html', results=results, keyword=keyword)

@app.route('/save_results', methods=['POST'])
def save_results():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    data = request.json
    keyword = data.get('keyword')
    items = data.get('items', [])
    
    count = 0
    for item in items:
        # Check if already exists to avoid duplicates (optional, based on URL)
        exists = CrawlerResult.query.filter_by(url=item['url']).first()
        if not exists:
            new_result = CrawlerResult(
                keyword=keyword,
                title=item['title'],
                summary=item['summary'],
                url=item['url'],
                cover_url=item['cover_url']
            )
            db.session.add(new_result)
            count += 1
    
    db.session.commit()
    return jsonify({'status': 'success', 'count': count})

@app.route('/data_management')
def data_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    keyword_filter = request.args.get('keyword', '')
    date_filter = request.args.get('date', '') # Format YYYY-MM-DD
    
    query = CrawlerResult.query
    
    if keyword_filter:
        query = query.filter(CrawlerResult.keyword.contains(keyword_filter) | CrawlerResult.title.contains(keyword_filter))
    
    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            # Filter by date (ignoring time)
            query = query.filter(db.func.date(CrawlerResult.created_at) == date_obj)
        except ValueError:
            pass # Ignore invalid date format

    saved_data = query.order_by(CrawlerResult.created_at.desc()).all()
    
    # Group by date for display if needed, or just list them
    return render_template('data_management.html', saved_data=saved_data)

@app.route('/preview_pdf', methods=['POST'])
def preview_pdf():
    # Placeholder for AI/PDF generation
    return "PDF Generation Feature Coming Soon (Waiting for AI instructions)"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
