from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
from flask_bcrypt import Bcrypt
import sqlite3
import os
from dotenv import load_dotenv
from groq import Groq
from datetime import datetime, date, timedelta
import json
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)
app.secret_key = os.getenv('SECRET_KEY', 'cognify_secret_2024')

DB = 'database.db'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Safe Groq client init
groq_api_key = os.getenv('GROQ_API_KEY', '')
client = Groq(api_key=groq_api_key) if groq_api_key else None

# ── DATABASE ──────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    try:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                profile_photo TEXT DEFAULT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                memory_score REAL,
                reaction_time REAL,
                attention_score REAL,
                overall_score REAL,
                ai_insight TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS streaks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                last_test_date TEXT,
                total_sessions INTEGER DEFAULT 0,
                badges TEXT DEFAULT '[]'
            );
        ''')
        conn.commit()
    finally:
        conn.close()

init_db()

# ── HELPERS ───────────────────────────────────────────────
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def validate_score(value, min_val, max_val):
    try:
        v = float(value)
        return v if min_val <= v <= max_val else None
    except (TypeError, ValueError):
        return None

def compute_badges(username, memory, reaction, attention, overall, streak):
    conn = get_db()
    try:
        row = conn.execute('SELECT badges FROM streaks WHERE username=?', (username,)).fetchone()
        earned = json.loads(row['badges']) if row and row['badges'] else []
    finally:
        conn.close()

    candidates = [
        ('🥇', 'First Test',      'Complete your first session',   True),
        ('⚡', 'Speed Demon',     'Reaction time under 200ms',      reaction is not None and reaction < 200),
        ('🧠', 'Memory Master',   'Memory score 9 or above',        memory is not None and memory >= 9),
        ('🎯', 'Laser Focus',     'Attention accuracy 100%',        attention is not None and attention == 100),
        ('🔥', 'On Fire',         '3-day streak',                   streak >= 3),
        ('💎', 'Week Warrior',    '7-day streak',                   streak >= 7),
        ('🏆', 'Cognitive Elite', 'Overall score 90 or above',      overall is not None and overall >= 90),
        ('🌟', 'High Achiever',   'Overall score 80 or above',      overall is not None and overall >= 80),
    ]
    for icon, name, desc, condition in candidates:
        if condition and name not in [b['name'] for b in earned]:
            earned.append({'icon': icon, 'name': name, 'desc': desc})
    return earned

def update_streak(username):
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM streaks WHERE username=?', (username,)).fetchone()
        today = date.today().isoformat()
        if not row:
            conn.execute('INSERT INTO streaks (username, current_streak, longest_streak, last_test_date, total_sessions) VALUES (?,1,1,?,1)', (username, today))
            conn.commit()
            return 1
        last = row['last_test_date']
        streak = row['current_streak']
        longest = row['longest_streak']
        if last == today:
            return streak
        elif last == (date.today() - timedelta(days=1)).isoformat():
            streak += 1
        else:
            streak = 1
        longest = max(longest, streak)
        conn.execute('UPDATE streaks SET current_streak=?, longest_streak=?, last_test_date=?, total_sessions=total_sessions+1 WHERE username=?', (streak, longest, today, username))
        conn.commit()
        return streak
    finally:
        conn.close()

def compute_digital_twin(username):
    conn = get_db()
    try:
        rows = conn.execute('SELECT memory_score, reaction_time, attention_score, overall_score FROM scores WHERE username=? AND overall_score IS NOT NULL ORDER BY created_at DESC LIMIT 5', (username,)).fetchall()
    finally:
        conn.close()

    if len(rows) < 2:
        return None

    sessions = [dict(r) for r in rows][::-1]
    n = len(sessions)
    weights = list(range(1, n + 1))

    def wavg(key):
        vals = [s[key] for s in sessions if s[key] is not None]
        ws = weights[-len(vals):]
        return round(sum(v*w for v,w in zip(vals,ws))/sum(ws), 1) if vals else None

    pred_memory   = min(10, max(1, wavg('memory_score') or 5))
    pred_reaction = max(150, wavg('reaction_time') or 300)
    pred_attention= min(100, max(0, wavg('attention_score') or 50))
    pred_overall  = min(100, max(0, wavg('overall_score') or 50))

    mid = n // 2
    first_avg  = sum(s['overall_score'] for s in sessions[:mid]) / max(mid, 1)
    second_avg = sum(s['overall_score'] for s in sessions[mid:]) / max(n - mid, 1)
    trend = 'improving' if second_avg > first_avg + 2 else 'declining' if second_avg < first_avg - 2 else 'stable'

    return {
        'pred_memory': pred_memory, 'pred_reaction': pred_reaction,
        'pred_attention': pred_attention, 'pred_overall': pred_overall,
        'trend': trend, 'sessions_used': n
    }

# ── ERROR HANDLERS ────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template('login.html', error='Page not found.'), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Something went wrong. Please try again.'}), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 5MB.'}), 413

# ── AUTH ROUTES ───────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not all([username, email, password]):
            return render_template('register.html', error='All fields are required.')
        if len(password) < 6:
            return render_template('register.html', error='Password must be at least 6 characters.')
        if len(username) < 3:
            return render_template('register.html', error='Username must be at least 3 characters.')

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        conn = get_db()
        try:
            existing = conn.execute('SELECT id FROM users WHERE username=? OR email=?', (username, email)).fetchone()
            if existing:
                return render_template('register.html', error='Username or email already exists.')
            conn.execute('INSERT INTO users (username, email, password) VALUES (?,?,?)', (username, email, hashed))
            conn.commit()
        finally:
            conn.close()

        session['username'] = username
        session['profile_photo'] = None
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        try:
            user = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        finally:
            conn.close()
        if user and bcrypt.check_password_hash(user['password'], password):
            session['username'] = username
            session['profile_photo'] = user['profile_photo']
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    username = session['username']
    if request.method == 'POST':
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = secure_filename(f"{username}_photo.{ext}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                conn = get_db()
                try:
                    conn.execute('UPDATE users SET profile_photo=? WHERE username=?', (filename, username))
                    conn.commit()
                finally:
                    conn.close()
                session['profile_photo'] = filename
                return redirect(url_for('profile'))

    conn = get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        scores = conn.execute('SELECT * FROM scores WHERE username=? ORDER BY created_at DESC LIMIT 5', (username,)).fetchall()
        streak_row = conn.execute('SELECT * FROM streaks WHERE username=?', (username,)).fetchone()
    finally:
        conn.close()
    return render_template('profile.html', user=user, scores=scores, streak=streak_row)

# ── MAIN ROUTES ───────────────────────────────────────────
@app.route('/')
@login_required
def index():
    return render_template('index.html', username=session.get('username'), photo=session.get('profile_photo'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session.get('username'), photo=session.get('profile_photo'))

# ── API ROUTES ────────────────────────────────────────────
@app.route('/api/save_score', methods=['POST'])
def save_score():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data received'}), 400

    username  = session['username']
    memory    = validate_score(data.get('memory_score'), 0, 10)
    reaction  = validate_score(data.get('reaction_time'), 50, 5000)
    attention = validate_score(data.get('attention_score'), 0, 100)

    overall = None
    if None not in (memory, reaction, attention):
        mem_pct   = (memory / 10) * 100
        react_pct = max(0, min(100, 100 - ((reaction - 150) / 4)))
        overall   = round((mem_pct + react_pct + attention) / 3)

    conn = get_db()
    try:
        cursor = conn.execute(
            'INSERT INTO scores (username, memory_score, reaction_time, attention_score, overall_score) VALUES (?,?,?,?,?)',
            (username, memory, reaction, attention, overall)
        )
        score_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    streak = update_streak(username)
    badges = compute_badges(username, memory, reaction, attention, overall, streak)

    conn = get_db()
    try:
        conn.execute('UPDATE streaks SET badges=? WHERE username=?', (json.dumps(badges), username))
        conn.commit()
    finally:
        conn.close()

    return jsonify({'status': 'ok', 'overall_score': overall, 'score_id': score_id, 'streak': streak, 'badges': badges})

@app.route('/api/ai_insight', methods=['POST'])
def ai_insight():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    data     = request.get_json()
    memory   = data.get('memory_score')
    reaction = data.get('reaction_time')
    attention= data.get('attention_score')
    overall  = data.get('overall_score')
    username = session.get('username', 'the user')
    score_id = data.get('score_id')

    prompt = f"""You are a cognitive performance analyst. Analyze these test results for {username} and give a short, personalized insight in 4-5 sentences. Be specific about their numbers, encouraging but honest. Mention what their strongest cognitive skill is, what to improve, and one practical tip.
Results:
- Memory Score: {memory}/10
- Reaction Time: {reaction}ms (average human is 250ms, excellent is under 200ms)
- Attention Accuracy: {attention}% (excellent is above 90%)
- Overall Cognitive Score: {overall}/100
Write directly to {username}. No bullet points. Conversational tone. Max 5 sentences."""

    try:
        if not client:
            raise Exception("Groq API key not configured.")
        chat = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        insight_text = chat.choices[0].message.content.strip()
        if score_id:
            conn = get_db()
            try:
                conn.execute('UPDATE scores SET ai_insight=? WHERE id=?', (insight_text, score_id))
                conn.commit()
            finally:
                conn.close()
        return jsonify({'status': 'ok', 'insight': insight_text})
    except Exception as e:
        return jsonify({'status': 'error', 'insight': f'Could not generate insight: {str(e)}'})

@app.route('/api/digital_twin/<username>')
def digital_twin(username):
    twin = compute_digital_twin(username)
    if not twin:
        return jsonify({'status': 'insufficient_data', 'message': 'Complete at least 2 full sessions to activate your Digital Twin.'})
    return jsonify({'status': 'ok', 'twin': twin})

@app.route('/api/gamification/<username>')
def gamification(username):
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM streaks WHERE username=?', (username,)).fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({'streak': 0, 'longest_streak': 0, 'total_sessions': 0, 'badges': []})
    return jsonify({
        'streak': row['current_streak'],
        'longest_streak': row['longest_streak'],
        'total_sessions': row['total_sessions'],
        'badges': json.loads(row['badges'] or '[]')
    })

@app.route('/api/leaderboard')
def leaderboard():
    conn = get_db()
    try:
        rows = conn.execute('SELECT username, MAX(overall_score) as overall_score FROM scores WHERE overall_score IS NOT NULL GROUP BY username ORDER BY overall_score DESC LIMIT 10').fetchall()
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/history')
def history():
    conn = get_db()
    try:
        rows = conn.execute('SELECT id, username, memory_score, reaction_time, attention_score, overall_score, ai_insight, created_at FROM scores ORDER BY created_at DESC LIMIT 20').fetchall()
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/stats')
def stats():
    conn = get_db()
    try:
        row = conn.execute('''
            SELECT COUNT(*) as total_sessions,
                   ROUND(AVG(memory_score),1) as avg_memory,
                   ROUND(AVG(reaction_time),0) as avg_reaction,
                   ROUND(AVG(attention_score),1) as avg_attention,
                   ROUND(AVG(overall_score),1) as avg_overall,
                   MAX(overall_score) as best_score
            FROM scores WHERE overall_score IS NOT NULL
        ''').fetchone()
    finally:
        conn.close()
    return jsonify(dict(row))

@app.route('/api/user_history/<username>')
def user_history(username):
    conn = get_db()
    try:
        rows = conn.execute(
            'SELECT memory_score, reaction_time, attention_score, overall_score, created_at FROM scores WHERE username=? AND overall_score IS NOT NULL ORDER BY created_at ASC',
            (username,)
        ).fetchall()
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])

if __name__ == '__main__':
    app.run(debug=True, port=5000)
