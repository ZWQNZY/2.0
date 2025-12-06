from flask import render_template, request, redirect, url_for, session, flash, jsonify, Response, stream_with_context
from models import app, db, User, CrawlerResult, CrawlerRule, CrawlerDetail, AIModel, TokenUsageLog
from sqlalchemy import text
from baidu_crawler import search_baidu
from sina_crawler import search_sina
from sogou_crawler import search_sogou
from datetime import datetime
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
import json
from urllib.parse import urlparse
from lxml import html as lxml_html

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
    start_date = ""
    end_date = ""
    source = "baidu"
    
    if request.method == 'POST':
        keyword = request.form.get('keyword', '')
        start_date = request.form.get('start_date', '')
        end_date = request.form.get('end_date', '')
        source = request.form.get('source', 'baidu')
        
        if keyword:
            if source == 'sina':
                results = search_sina(keyword, start_date, end_date)
            elif source == 'sogou':
                results = search_sogou(keyword, start_date, end_date)
            else:
                results = search_baidu(keyword, start_date, end_date)
            # Temporarily store results in session or just render them
            # For simplicity, we'll render them directly. 
            # To support saving, we need to send them back or keep track.
            # We will pass them to the template, and the save action will accept the data to save.
            
    return render_template('dashboard.html', results=results, keyword=keyword, start_date=start_date, end_date=end_date, source=source)

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

@app.route('/delete_result/<int:id>', methods=['POST'])
def delete_result(id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    result = CrawlerResult.query.get(id)
    if result:
        db.session.delete(result)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Not found'}), 404

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
    
    # Create a map of domain -> rule_name
    rules = CrawlerRule.query.all()
    domain_rule_map = {rule.domain: rule.rule_name for rule in rules}
    
    # Group by date for display if needed, or just list them
    return render_template('data_management.html', saved_data=saved_data, domain_rule_map=domain_rule_map)

@app.route('/collect_result/<int:id>', methods=['POST'])
def collect_result(id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    result = CrawlerResult.query.get(id)
    if not result:
        return jsonify({'status': 'error', 'message': 'Not found'}), 404

    try:
        # 1. Check for Rule
        domain = urlparse(result.url).netloc
        rule = CrawlerRule.query.filter_by(domain=domain).first()
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        if rule and rule.headers:
            try:
                custom_headers = json.loads(rule.headers)
                # Filter out HTTP/2 pseudo-headers starting with ':'
                filtered_headers = {k: v for k, v in custom_headers.items() if not k.startswith(':')}
                headers.update(filtered_headers)
            except:
                pass
        
        # 2. Fetch Content
        try:
            response = requests.get(result.url, headers=headers, timeout=15)
            response.encoding = response.apparent_encoding
            html_content = response.text
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Request failed: {str(e)}'}), 500
        
        # 3. Parse Content using shared logic
        clean_title, clean_content, parsed_by_rule = parse_html_content(html_content, rule)

        # 4. Save to CrawlerDetail
        detail = CrawlerDetail.query.filter_by(crawler_result_id=id).first()
        if not detail:
            detail = CrawlerDetail(crawler_result_id=id)
            db.session.add(detail)
        
        detail.rule_id = rule.id if rule else None
        detail.clean_title = clean_title
        detail.clean_content = clean_content
        detail.raw_html = html_content
        detail.created_at = datetime.utcnow()
        
        # Update legacy content field
        result.content = html_content
        
        db.session.commit()
        
        msg = '采集完成'
        if parsed_by_rule:
            msg += ' (已应用规则)'
        else:
            msg += ' (无规则，仅保存源码)'

        return jsonify({'status': 'success', 'message': msg})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

import re

def parse_html_content(html_content, rule=None):
    """
    Shared logic for parsing HTML content to clean title and content.
    Can use a specific rule if provided, otherwise falls back to heuristics.
    Returns: (clean_title, clean_content, parsed_by_rule)
    """
    clean_title = ""
    clean_content = ""
    parsed_by_rule = False
    
    # 1. Rule-based Parsing
    if rule and (rule.title_xpath or rule.content_xpath):
        try:
            tree = lxml_html.fromstring(html_content)
            
            if rule.title_xpath:
                titles = tree.xpath(rule.title_xpath)
                if titles:
                    if hasattr(titles[0], 'text_content'):
                        clean_title = titles[0].text_content().strip()
                    elif isinstance(titles[0], str):
                        clean_title = titles[0].strip()
            
            if rule.content_xpath:
                contents = tree.xpath(rule.content_xpath)
                if contents:
                    if hasattr(contents[0], 'text_content'):
                        clean_content = contents[0].text_content().strip()
                    elif isinstance(contents[0], str):
                        clean_content = contents[0].strip()
            parsed_by_rule = True
        except Exception as e:
            print(f"XPath parsing error: {e}")
    
    # 2. Heuristic Parsing (Fallback)
    # Even if parsed by rule, if title/content is missing, try to fill it? 
    # Or strictly follow rule? Usually, if rule fails, we want fallback.
    
    if not clean_title or not clean_content:
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # --- CRITICAL CLEANUP ---
            # Remove all script and style elements before extraction
            for script in soup(["script", "style", "noscript", "iframe", "header", "footer", "nav", "svg"]):
                script.decompose()
            
            # --- Title Fallback ---
            if not clean_title:
                if soup.title:
                    clean_title = soup.title.get_text().strip()
                
                # Check for blocking/error pages
                if clean_title:
                    bad_titles = ["404", "Not Found", "百度安全验证", "Security Verification", "访问报错", "出错啦"]
                    for bad in bad_titles:
                        if bad in clean_title:
                            clean_title = f"[INVALID] {clean_title}"
                            clean_content = "Blocked or Error Page"
                            return clean_title, clean_content, parsed_by_rule

            # --- Content Fallback ---
            if not clean_content:
                # Reuse the scoring logic if possible, or just grab body text
                # We can reuse the logic from sniff_result if we move it out, 
                # but for now let's do a simple density check or just text.
                # Actually, let's use a simplified version of the scoring logic here.
                
                # Find the best div/article
                candidates = soup.find_all(['div', 'article', 'section', 'main', 'td'])
                best_node = None
                best_score = 0
                
                for node in candidates:
                    # Simple score: text length - link text length
                    text = node.get_text(" ", strip=True)
                    if not text: continue
                    
                    text_len = len(text)
                    link_len = sum([len(a.get_text(strip=True)) for a in node.find_all('a')])
                    
                    # Heuristic score
                    score = text_len - (link_len * 2) # Penalize links heavily
                    
                    if score > best_score:
                        best_score = score
                        best_node = node
                
                if best_node:
                    clean_content = best_node.get_text("\n", strip=True)
                else:
                    # Fallback to body text
                    if soup.body:
                        clean_content = soup.body.get_text("\n", strip=True)

        except Exception as e:
            print(f"Heuristic parsing error: {e}")

    # Final Cleanup: Remove common JS artifacts that might have leaked through
    if clean_content:
        lines = clean_content.split('\n')
        cleaned_lines = []
        for line in lines:
            l = line.strip()
            # Skip lines that look like JS code
            if (l.startswith('var ') or 
                l.startswith('let ') or 
                l.startswith('const ') or 
                'document.write' in l or 
                'window.location' in l or 
                'console.log' in l or
                l.startswith('function') or
                l.startswith('if(') or l.startswith('if (') or
                l.startswith('for(') or l.startswith('for (') or
                l.startswith('while(') or l.startswith('while (') or
                l.startswith('try{') or l.startswith('try {') or
                l.startswith('catch(') or l.startswith('catch (') or
                l.startswith('else') or
                'unescape(' in l or
                'eval(' in l or
                'wd_paramtracker(' in l):
                continue
            cleaned_lines.append(line)
        clean_content = "\n".join(cleaned_lines).strip()

    return clean_title, clean_content, parsed_by_rule

def get_xpath(element):
    """
    Generate a robust XPath for a BeautifulSoup element.
    """
    if element is None:
        return ""
    components = []
    child = element if element.name else element.parent
    for parent in child.parents:
        siblings = parent.find_all(child.name, recursive=False)
        c_tag = child.name
        if len(siblings) > 1:
            try:
                index = siblings.index(child) + 1
                c_tag = f"{c_tag}[{index}]"
            except ValueError:
                pass # Should not happen if tree is consistent
        components.append(c_tag)
        child = parent
    components.reverse()
    return "/" + "/".join(components)

def get_text_density(element):
    """Calculate text density: text_length / tags_count"""
    text_len = len(element.get_text(strip=True))
    tags_count = len(element.find_all())
    if tags_count == 0:
        return text_len
    return text_len / tags_count

def get_link_density(element):
    """Calculate link density: link_text_length / total_text_length"""
    links = element.find_all('a')
    if not links:
        return 0
    link_len = sum([len(a.get_text(strip=True)) for a in links])
    total_len = len(element.get_text(strip=True))
    if total_len == 0:
        return 1
    return link_len / total_len

def score_node(element):
    """Heuristic scoring for content candidates"""
    score = 0
    
    # 1. Class/ID weight
    weight = 0
    attributes = ""
    if element.get('class'):
        attributes += " ".join(element.get('class')).lower()
    if element.get('id'):
        attributes += " " + str(element.get('id')).lower()
        
    if attributes:
        if re.search(r'article|body|content|entry|hentry|main|page|pagination|post|text|blog|story|detail', attributes):
            weight += 30
        if re.search(r'combx|comment|community|disqus|extra|foot|header|menu|remark|rss|shoutbox|sidebar|sponsor|ad|meta|nav|copyright|recommend', attributes):
            weight -= 25
    
    score += weight
    
    # 2. Paragraphs and Text
    paragraphs = element.find_all('p', recursive=False)
    for p in paragraphs:
        text = p.get_text(strip=True)
        if len(text) > 50:
            score += 10
        # Punctuation boost
        score += (text.count(',') + text.count('，')) * 0.5
        score += (text.count('.') + text.count('。')) * 0.5
    
    # Direct text content (for div-soup sites)
    direct_text = "".join([t for t in element.contents if isinstance(t, NavigableString)]).strip()
    if len(direct_text) > 100:
        score += 10
        score += (direct_text.count(',') + direct_text.count('，')) * 0.5

    return score

@app.route('/sniff_result/<int:id>', methods=['POST'])
def sniff_result(id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    result = CrawlerResult.query.get(id)
    if not result:
        return jsonify({'status': 'error', 'message': 'Not found'}), 404

    try:
        # 1. Fetch Content
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        html_content = ""
        if result.content:
            html_content = result.content
        else:
            response = requests.get(result.url, headers=headers, timeout=15)
            response.encoding = response.apparent_encoding
            html_content = response.text
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 2. Media Sniffing (Legacy)
        resources = []
        videos = soup.find_all('video')
        for video in videos:
            src = video.get('src')
            if src: resources.append({'type': 'video', 'url': src})
        
        # 3. Advanced Rule Sniffing
        
        # --- A. Title Detection ---
        title_xpath = ""
        
        # Step 1: Check Open Graph Title
        og_title = soup.find('meta', property='og:title')
        target_title_text = ""
        if og_title and og_title.get('content'):
            target_title_text = og_title.get('content').strip()
        
        if not target_title_text:
            # Step 2: Check <title> tag
            page_title = soup.find('title')
            if page_title and page_title.get_text():
                target_title_text = page_title.get_text().strip()
                # Remove likely site name suffix (e.g., "My Article - SiteName")
                if '-' in target_title_text:
                    target_title_text = target_title_text.split('-')[0].strip()
                elif '|' in target_title_text:
                    target_title_text = target_title_text.split('|')[0].strip()
                elif '_' in target_title_text:
                    target_title_text = target_title_text.split('_')[0].strip()
        
        # Step 3: Find DOM element matching this text
        best_title_el = None
        
        if target_title_text:
            # Look for h1-h3 that contains this text
            headings = soup.find_all(['h1', 'h2', 'h3'])
            for h in headings:
                h_text = h.get_text(strip=True)
                # Check similarity or inclusion
                if target_title_text in h_text or h_text in target_title_text:
                    # Prefer exact match or high overlap
                    best_title_el = h
                    if h.name == 'h1': # h1 is golden standard
                        break
        
        # Fallback: Just take the first h1
        if not best_title_el:
            best_title_el = soup.find('h1')
            
        if best_title_el:
            title_xpath = get_xpath(best_title_el)
        
        # --- B. Content Detection (Score Propagation) ---
        content_xpath = ""
        
        # Candidates: Containers that might hold content
        candidates = soup.find_all(['div', 'article', 'section', 'main', 'td'])
        
        scored_candidates = []
        
        for node in candidates:
            # Pre-filter: Skip elements with negative class names
            # (Already handled in score_node, but we can skip calculation for hidden ones)
            if node.has_attr('style') and 'display:none' in node['style'].replace(" ", "").lower():
                continue
                
            score = score_node(node)
            
            # Penalize link density (navigation menus often have high text score but high link density)
            link_d = get_link_density(node)
            if link_d > 0.5: # More than 50% text is links
                score *= 0.2 # Heavy penalty
            elif link_d > 0.2:
                score *= 0.6
            
            scored_candidates.append((score, node))
        
        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        if scored_candidates:
            best_content_el = scored_candidates[0][1]
            # Sanity check: is there a parent with slightly higher score?
            # Sometimes the inner div has score X, parent has X (same text), but parent covers more?
            # Actually, we want the tightest wrapper. The score function favors text nodes.
            # If parent has same text as child, score is same.
            # Let's stick to the highest score.
            content_xpath = get_xpath(best_content_el)
            
        # 4. Prepare Rule Suggestion (Do NOT save automatically)
        domain = urlparse(result.url).netloc
        
        # Check if a rule already exists to pre-fill info
        existing_rule = CrawlerRule.query.filter_by(domain=domain).first()
        rule_name = existing_rule.rule_name if existing_rule else f"{domain} 默认规则"
        
        return jsonify({
            'status': 'success', 
            'message': '深度嗅探完成，请确认规则',
            'rule': {
                'domain': domain,
                'rule_name': rule_name,
                'url_pattern': result.url,
                'title_xpath': title_xpath,
                'content_xpath': content_xpath,
                'headers': json.dumps(headers)
            },
            'resources': resources
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/save_rule', methods=['POST'])
def save_rule():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
    data = request.json
    domain = data.get('domain')
    
    if not domain:
         return jsonify({'status': 'error', 'message': 'Domain is required'}), 400
         
    try:
        rule = CrawlerRule.query.filter_by(domain=domain).first()
        if not rule:
            rule = CrawlerRule(domain=domain)
            db.session.add(rule)
            
        rule.rule_name = data.get('rule_name')
        rule.title_xpath = data.get('title_xpath')
        rule.content_xpath = data.get('content_xpath')
        rule.headers = data.get('headers')
        # site_name reused for url_pattern in frontend logic but we also have url_pattern field now
        # let's assume frontend sends 'site_name' as the field for pattern for now or update frontend
        # The user asked to change "Site Name" to "URL Pattern" in UI. 
        # So data.get('site_name') likely contains the pattern now.
        # But we added a new column url_pattern. Let's use it if provided, else fallback.
        
        # Note: The frontend JS in rule_management.html sends:
        # site_name: document.getElementById('rule_site_name').value
        # So we map site_name from request to url_pattern in DB, 
        # AND also keep site_name in DB populated just in case.
        
        val = data.get('site_name')
        rule.site_name = val 
        rule.url_pattern = val
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': '规则保存成功'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/rules')
def rule_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    rules = CrawlerRule.query.order_by(CrawlerRule.created_at.desc()).all()
    return render_template('rule_management.html', rules=rules)

@app.route('/content_management')
def content_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    keyword = request.args.get('keyword', '')
    query = CrawlerDetail.query
    
    if keyword:
        query = query.filter(CrawlerDetail.clean_title.contains(keyword) | CrawlerDetail.clean_content.contains(keyword))
        
    contents = query.order_by(CrawlerDetail.created_at.desc()).all()
    return render_template('content_management.html', contents=contents)

@app.route('/content/get/<int:id>')
def get_content(id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    content = CrawlerDetail.query.get(id)
    if content:
        return jsonify({
            'status': 'success',
            'data': {
                'id': content.id,
                'clean_title': content.clean_title,
                'clean_content': content.clean_content
            }
        })
    return jsonify({'status': 'error', 'message': 'Content not found'}), 404

@app.route('/content/edit/<int:id>', methods=['POST'])
def edit_content(id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    content = CrawlerDetail.query.get(id)
    if not content:
        return jsonify({'status': 'error', 'message': 'Content not found'}), 404
        
    data = request.json
    try:
        content.clean_title = data.get('clean_title')
        content.clean_content = data.get('clean_content')
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Content updated'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/content/delete/<int:id>', methods=['POST'])
def delete_content(id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    content = CrawlerDetail.query.get(id)
    if content:
        db.session.delete(content)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Content deleted'})
    return jsonify({'status': 'error', 'message': 'Content not found'}), 404

@app.route('/rules/add', methods=['POST'])
def add_rule():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
    data = request.json
    domain = data.get('domain')
    
    if not domain:
        return jsonify({'status': 'error', 'message': 'Domain is required'}), 400
        
    if CrawlerRule.query.filter_by(domain=domain).first():
        return jsonify({'status': 'error', 'message': '该域名的规则已存在，请使用编辑功能'}), 400
        
    try:
        val = data.get('site_name')
        rule = CrawlerRule(
            rule_name=data.get('rule_name'),
            domain=domain,
            site_name=val,
            url_pattern=val, # Populate url_pattern
            title_xpath=data.get('title_xpath'),
            content_xpath=data.get('content_xpath'),
            headers=data.get('headers')
        )
        db.session.add(rule)
        db.session.commit()
        return jsonify({'status': 'success', 'message': '规则添加成功'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/rules/edit/<int:id>', methods=['POST'])
def edit_rule(id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
    rule = CrawlerRule.query.get(id)
    if not rule:
        return jsonify({'status': 'error', 'message': 'Rule not found'}), 404
        
    data = request.json
    try:
        rule.rule_name = data.get('rule_name')
        # rule.domain = data.get('domain') # Domain usually shouldn't be changed or needs unique check
        # Let's allow domain change but check uniqueness if it changed
        new_domain = data.get('domain')
        if new_domain and new_domain != rule.domain:
             if CrawlerRule.query.filter_by(domain=new_domain).first():
                 return jsonify({'status': 'error', 'message': '新域名已存在其他规则'}), 400
             rule.domain = new_domain
             
        val = data.get('site_name')
        rule.site_name = val
        rule.url_pattern = val # Populate url_pattern
        rule.title_xpath = data.get('title_xpath')
        rule.content_xpath = data.get('content_xpath')
        rule.headers = data.get('headers')
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': '规则更新成功'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/rules/delete/<int:id>', methods=['POST'])
def delete_rule(id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
    rule = CrawlerRule.query.get(id)
    if rule:
        db.session.delete(rule)
        db.session.commit()
        return jsonify({'status': 'success', 'message': '规则删除成功'})
    return jsonify({'status': 'error', 'message': 'Rule not found'}), 404

@app.route('/preview_pdf', methods=['POST'])
def preview_pdf():
    # Placeholder for AI/PDF generation
    return "PDF Generation Feature Coming Soon (Waiting for AI instructions)"

# --- AI Engine Routes ---

@app.route('/ai_engine')
def ai_engine():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    models = AIModel.query.order_by(AIModel.created_at.desc()).all()
    return render_template('ai_engine.html', models=models)

@app.route('/ai_engine/add', methods=['POST'])
def add_model():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    data = request.json
    try:
        model = AIModel(
            name=data['name'],
            provider=data['provider'],
            api_base=data['api_base'],
            api_key=data['api_key'],
            model_name=data['model_name'],
            description=data.get('description')
        )
        db.session.add(model)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/ai_engine/edit/<int:id>', methods=['POST'])
def edit_model(id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    model = AIModel.query.get(id)
    if not model:
        return jsonify({'status': 'error', 'message': 'Not found'}), 404
        
    data = request.json
    try:
        model.name = data['name']
        model.provider = data['provider']
        model.api_base = data['api_base']
        model.api_key = data['api_key']
        model.model_name = data['model_name']
        model.description = data.get('description')
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/ai_engine/delete/<int:id>', methods=['POST'])
def delete_model(id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    model = AIModel.query.get(id)
    if model:
        TokenUsageLog.query.filter_by(model_id=id).delete()
        db.session.delete(model)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Not found'}), 404

@app.route('/ai_engine/stats')
def ai_stats():
    if 'user_id' not in session:
         return jsonify({'total_tokens': 0})
         
    total_tokens = db.session.query(db.func.sum(TokenUsageLog.tokens_used)).scalar() or 0
    return jsonify({'total_tokens': total_tokens})

@app.route('/ai_engine/test', methods=['POST'])
def test_model():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    model_id = data.get('model_id')
    user_message = data.get('message')
    
    model = AIModel.query.get(model_id)
    if not model:
        return jsonify({'error': 'Model not found'}), 404
        
    def generate():
        headers = {
            "Authorization": f"Bearer {model.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model.model_name,
            "messages": [{"role": "user", "content": user_message}],
            "stream": True,
            "max_tokens": 512,
            "stream_options": {"include_usage": True}
        }
        
        url = model.api_base.rstrip('/') + '/chat/completions'
        
        try:
            with requests.post(url, headers=headers, json=payload, stream=True) as response:
                if response.status_code != 200:
                    yield f"data: {json.dumps({'error': f'API Error: {response.status_code} {response.text}'})}\n\n"
                    return

                generated_text = ""
                usage_found = False
                
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            if line_str == 'data: [DONE]':
                                yield "data: [DONE]\n\n"
                                break
                            
                            try:
                                json_str = line_str[6:]
                                chunk = json.loads(json_str)
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    delta = chunk['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        generated_text += content
                                        yield f"data: {json.dumps({'content': content})}\n\n"
                                        
                                if 'usage' in chunk and chunk['usage']:
                                    usage_found = True
                                    total_tokens = chunk['usage'].get('total_tokens', 0)
                                    with app.app_context():
                                        log = TokenUsageLog(model_id=model.id, tokens_used=total_tokens)
                                        db.session.add(log)
                                        db.session.commit()
                            except:
                                pass
                
                if not usage_found:
                    input_tokens = len(user_message)
                    output_tokens = len(generated_text)
                    total_tokens = input_tokens + output_tokens
                    with app.app_context():
                        log = TokenUsageLog(model_id=model.id, tokens_used=total_tokens)
                        db.session.add(log)
                        db.session.commit()
                    
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/ai_analysis')
def ai_analysis():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    models = AIModel.query.all()
    return render_template('ai_analysis.html', models=models)

@app.route('/ai_analysis/chat', methods=['POST'])
def ai_analysis_chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    model_id = data.get('model_id')
    user_message = data.get('message')
    
    model = AIModel.query.get(model_id)
    if not model:
        return jsonify({'error': 'Model not found'}), 404
        
    def generate():
        schema_info = """
Table: crawler_rule
Columns: id (INTEGER), domain (VARCHAR), site_name (VARCHAR), title_xpath (TEXT), content_xpath (TEXT), headers (TEXT), created_at (DATETIME), rule_name (TEXT)

Table: crawler_result
Columns: id (INTEGER), keyword (VARCHAR), url (TEXT), title (TEXT), summary (TEXT), content (TEXT), source (VARCHAR), created_at (DATETIME)
"""
        system_prompt = f"""You are an expert data analyst. You have access to a SQLite database.
Schema:
{schema_info}

To answer user questions, you can query the database.
You must first output a plan or thought, and then if you need data, output a JSON object to execute SQL.
Format for SQL execution:
```json
{{"action": "query", "sql": "SELECT ... "}}
```
Only use SELECT statements. Limit results to 20 rows max.
After you get the data, analyze it and provide a final answer.
If you don't need data, just answer directly.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        headers = {
            "Authorization": f"Bearer {model.api_key}",
            "Content-Type": "application/json"
        }
        api_url = model.api_base.rstrip('/') + '/chat/completions'

        max_turns = 5
        current_turn = 0
        
        while current_turn < max_turns:
            current_turn += 1
            
            # Notify frontend: Thinking
            yield f"data: {json.dumps({'type': 'step', 'status': 'thinking', 'title': f'Step {current_turn}: Thinking...'})}\n\n"
            
            # Call LLM (Non-stream for logic)
            payload = {
                "model": model.model_name,
                "messages": messages,
                "stream": False,
                "temperature": 0.1
            }
            
            try:
                resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
                if resp.status_code != 200:
                    yield f"data: {json.dumps({'error': f'API Error: {resp.status_code} {resp.text}'})}\n\n"
                    return
                
                resp_data = resp.json()
                if 'choices' not in resp_data or not resp_data['choices']:
                     yield f"data: {json.dumps({'error': 'No response from model'})}\n\n"
                     return
                     
                content = resp_data['choices'][0]['message']['content']
                
                # Check for Tool Call
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                
                if json_match:
                    tool_json_str = json_match.group(1)
                    try:
                        tool_data = json.loads(tool_json_str)
                        if tool_data.get('action') == 'query':
                            sql = tool_data.get('sql')
                            
                            # Notify frontend: Querying
                            yield f"data: {json.dumps({'type': 'step', 'status': 'querying', 'title': 'Executing SQL', 'detail': sql})}\n\n"
                            
                            # Execute SQL
                            try:
                                with app.app_context():
                                    # Simple safety check
                                    if not sql.strip().upper().startswith('SELECT'):
                                         raise Exception("Only SELECT queries are allowed.")
                                         
                                    result = db.session.execute(text(sql))
                                    keys = result.keys()
                                    rows = result.fetchall()
                                    
                                    # Format result as text table
                                    result_str = ",".join(keys) + "\n"
                                    for row in rows:
                                        result_str += ",".join([str(x) for x in row]) + "\n"
                                    
                                    if not rows:
                                        result_str = "No results found."
                                        
                                    # Truncate if too long
                                    if len(result_str) > 2000:
                                        result_str = result_str[:2000] + "\n...(truncated)"
                                        
                            except Exception as e:
                                result_str = f"SQL Error: {str(e)}"
                                yield f"data: {json.dumps({'type': 'step', 'status': 'error', 'title': 'SQL Error', 'detail': str(e)})}\n\n"

                            # Add to history
                            messages.append({"role": "assistant", "content": content})
                            messages.append({"role": "user", "content": f"SQL Result:\n{result_str}"})
                            
                            # Notify frontend: Analyzed
                            yield f"data: {json.dumps({'type': 'step', 'status': 'analyzing', 'title': 'Data Received', 'detail': result_str[:200] + '...'})}\n\n"
                            
                            continue # Loop again
                            
                    except json.JSONDecodeError:
                        pass # Failed to parse JSON, treat as text
                
                # If no tool call, this is the final answer
                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                
                # Also log usage if available
                if 'usage' in resp_data:
                    total_tokens = resp_data['usage'].get('total_tokens', 0)
                    with app.app_context():
                        log = TokenUsageLog(model_id=model.id, tokens_used=total_tokens)
                        db.session.add(log)
                        db.session.commit()
                        
                break # Exit loop
                
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
