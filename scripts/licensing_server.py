import os
import sys
import json
import sqlite3
import datetime
from pathlib import Path

# Insert parent directory in path to share licensing logic
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_DIR))

# PostgreSQL Database Wrapper for sqlite3 compatibility in cloud hosting environments
DATABASE_URL = os.environ.get("DATABASE_URL")
IS_POSTGRES = DATABASE_URL is not None

class PostgresCursorWrapper:
    def __init__(self, pg_cursor):
        self.pg_cursor = pg_cursor
        
    def execute(self, sql, params=()):
        # Convert SQLite ? placeholders to PostgreSQL %s placeholders
        sql = sql.replace("?", "%s")
        # Convert SQLite auto-increment syntax to PostgreSQL serial syntax
        if "INTEGER PRIMARY KEY AUTOINCREMENT" in sql:
            sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        # Convert SQLite-specific INSERT OR IGNORE syntax
        if "INSERT OR IGNORE" in sql:
            sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            sql += " ON CONFLICT (license_key) DO NOTHING"
        # Convert SQLite-specific INSERT OR REPLACE syntax
        elif "INSERT OR REPLACE" in sql:
            sql = sql.replace("INSERT OR REPLACE INTO", "INSERT INTO")
            sql += """ ON CONFLICT (machine_id) DO UPDATE SET 
                       images_processed = EXCLUDED.images_processed,
                       duplicates_removed = EXCLUDED.duplicates_removed,
                       best_shots_selected = EXCLUDED.best_shots_selected,
                       processing_time = EXCLUDED.processing_time,
                       sessions = EXCLUDED.sessions,
                       last_updated = EXCLUDED.last_updated"""
        self.pg_cursor.execute(sql, params)
        return self
        
    def fetchone(self):
        return self.pg_cursor.fetchone()
        
    def fetchall(self):
        return self.pg_cursor.fetchall()
        
    def __iter__(self):
        return iter(self.pg_cursor)

class PostgresConnectionWrapper:
    def __init__(self, pg_conn):
        self.pg_conn = pg_conn
        
    def cursor(self):
        return PostgresCursorWrapper(self.pg_conn.cursor())
        
    def execute(self, sql, params=()):
        cursor = self.cursor()
        cursor.execute(sql, params)
        return cursor
        
    def commit(self):
        self.pg_conn.commit()
        
    def rollback(self):
        self.pg_conn.rollback()
        
    def close(self):
        self.pg_conn.close()
        
    def __enter__(self):
        self.pg_conn.__enter__()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.pg_conn.__exit__(exc_type, exc_val, exc_tb)

_orig_sqlite_connect = sqlite3.connect

def connect_wrapper(database_path):
    if IS_POSTGRES:
        import psycopg2
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return PostgresConnectionWrapper(psycopg2.connect(url))
    else:
        return _orig_sqlite_connect(database_path)

# Monkeypatch sqlite3.connect to automatically wrap Postgres connection when in production
sqlite3.connect = connect_wrapper

import bottle
from licensing import LicenseManager

app = bottle.Bottle()
DB_PATH = WORKSPACE_DIR / "server_activations.db"
FEEDBACK_PATH = WORKSPACE_DIR / "server_feedback.json"

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    with conn:
        # Create licenses table
        conn.execute('''CREATE TABLE IF NOT EXISTS licenses (
                        license_key TEXT PRIMARY KEY,
                        name TEXT,
                        email TEXT,
                        company TEXT,
                        country TEXT,
                        photography_type TEXT,
                        fingerprint TEXT,
                        activated_at TEXT,
                        expires_at TEXT,
                        status TEXT)''')
        
        # Create usage_analytics table
        conn.execute('''CREATE TABLE IF NOT EXISTS usage_analytics (
                        machine_id TEXT PRIMARY KEY,
                        images_processed INTEGER,
                        duplicates_removed INTEGER,
                        best_shots_selected INTEGER,
                        processing_time REAL,
                        sessions INTEGER,
                        last_updated TEXT)''')
        
        # Create feature_requests table
        conn.execute('''CREATE TABLE IF NOT EXISTS feature_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        machine_id TEXT,
                        feature TEXT,
                        priority TEXT,
                        workflow_impact TEXT,
                        timestamp TEXT)''')
        
        # Create crash_reports table
        conn.execute('''CREATE TABLE IF NOT EXISTS crash_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        machine_id TEXT,
                        app_version TEXT,
                        error TEXT,
                        stacktrace TEXT,
                        timestamp TEXT)''')

        # Create feedback table
        conn.execute('''CREATE TABLE IF NOT EXISTS feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        machine_id TEXT,
                        name TEXT,
                        company TEXT,
                        event_type TEXT,
                        images_processed INTEGER,
                        satisfaction_score INTEGER,
                        comments TEXT,
                        timestamp TEXT)''')
        
        # Seed 50 trial keys if the table is empty
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM licenses")
        if cursor.fetchone()[0] == 0:
            import random
            import string
            
            def gen_token():
                # Format: QC-XXXX-XXXX-XXXX
                part1 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
                part2 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
                part3 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
                return f"QC-{part1}-{part2}-{part3}"
                
            seeded_keys = []
            for _ in range(50):
                k = gen_token()
                while k in seeded_keys:
                    k = gen_token()
                seeded_keys.append(k)
            
            # Always seed a test license key for unit and manual testing
            seeded_keys.append("QC-TRIAL-TEST-1234")
                
            for k in seeded_keys:
                conn.execute("INSERT OR IGNORE INTO licenses (license_key, status) VALUES (?, ?)", (k, 'unactivated'))
            
            print(f"[Server DB Init] Seeded {len(seeded_keys)} pilot licenses successfully.")
        
        # Always ensure specific test/pilot keys exist
        conn.execute("INSERT OR IGNORE INTO licenses (license_key, status) VALUES (?, ?)", ("QC-TRIAL-TEST-1234", 'unactivated'))
        conn.execute("INSERT OR IGNORE INTO licenses (license_key, status) VALUES (?, ?)", ("QC-PILOT-001", 'unactivated'))
    conn.close()

init_db()
lm = LicenseManager()

@app.hook('after_request')
def enable_cors():
    bottle.response.headers['Access-Control-Allow-Origin'] = '*'
    bottle.response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    bottle.response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With'

@app.route('/activate', method=['POST', 'OPTIONS'])
def activate():
    if bottle.request.method == 'OPTIONS':
        return {}
        
    try:
        data = bottle.request.json or {}
        license_key = data.get("license_key", "").strip().upper()
        machine_id = data.get("machine_id", "").strip()
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        company = data.get("company", "").strip()
        country = data.get("country", "").strip()
        photography_type = data.get("photography_type", "").strip()
        
        if not license_key or not machine_id:
            bottle.response.status = 400
            return {"success": False, "error": "Missing license_key or machine_id"}
            
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # 1. Look up the key in the licenses table
        cursor.execute("SELECT name, email, company, country, photography_type, fingerprint, activated_at, expires_at, status FROM licenses WHERE license_key=?", (license_key,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            bottle.response.status = 400
            return {"success": False, "error": f"Invalid license key '{license_key}'. Check your key and try again."}
            
        db_name, db_email, db_company, db_country, db_type, db_fingerprint, db_activated, db_expires, db_status = row
        
        # 2. Check if already activated by this machine (Reinstallation recovery)
        if db_fingerprint == machine_id and db_status == 'active':
            # Reconstruct signed license
            payload = {
                "fingerprint": machine_id,
                "license_key": license_key,
                "activation_date": db_activated,
                "expiry_date": db_expires,
                "license_type": "trial"
            }
            encrypted_license = lm.encrypt_license(payload, machine_id)
            conn.close()
            print(f"[Server] Restored license for key {license_key} on machine {machine_id[:8]}...")
            return {"success": True, "license_data": encrypted_license, "message": "License restored successfully"}
            
        # 3. Check if key is already activated by a DIFFERENT machine (1 device limit)
        if db_fingerprint and db_fingerprint != machine_id:
            conn.close()
            bottle.response.status = 400
            return {"success": False, "error": "This license key is already activated on another device (1-device limit)."}
            
        # 4. Check if this machine is already using another key
        cursor.execute("SELECT license_key FROM licenses WHERE fingerprint=?", (machine_id,))
        dup_machine_row = cursor.fetchone()
        if dup_machine_row and dup_machine_row[0] != license_key:
            conn.close()
            bottle.response.status = 400
            return {"success": False, "error": "This device has already activated another trial license."}
            
        # 5. Activate the license key
        now = datetime.datetime.now()
        expiry = now + datetime.timedelta(days=30)
        
        with conn:
            conn.execute('''UPDATE licenses SET 
                            name=?, email=?, company=?, country=?, photography_type=?, 
                            fingerprint=?, activated_at=?, expires_at=?, status=? 
                            WHERE license_key=?''',
                         (name, email, company, country, photography_type, 
                          machine_id, now.isoformat(), expiry.isoformat(), 'active', license_key))
        
        # Return new signed license payload
        payload = {
            "fingerprint": machine_id,
            "license_key": license_key,
            "activation_date": now.isoformat(),
            "expiry_date": expiry.isoformat(),
            "license_type": "trial"
        }
        encrypted_license = lm.encrypt_license(payload, machine_id)
        conn.close()
        
        print(f"[Server] Activated license key {license_key} for {name} ({company}). Expiry: {expiry}")
        return {"success": True, "license_data": encrypted_license, "message": "Activation successful"}
        
    except Exception as e:
        bottle.response.status = 500
        return {"success": False, "error": f"Internal server error: {str(e)}"}

@app.route('/validate', method=['POST', 'OPTIONS'])
def validate():
    if bottle.request.method == 'OPTIONS':
        return {}
    return {"success": True, "message": "Server validation online"}

@app.route('/feedback', method=['POST', 'OPTIONS'])
def feedback():
    if bottle.request.method == 'OPTIONS':
        return {}
        
    try:
        data = bottle.request.json or {}
        machine_id = data.get("machine_id", "").strip()
        name = data.get("name", "").strip()
        company = data.get("company", "").strip()
        event_type = data.get("event_type", "").strip()
        images_processed = int(data.get("images_processed", 0))
        satisfaction_score = int(data.get("satisfaction_score", 5))
        comments = data.get("comments", "").strip()
        timestamp = datetime.datetime.now().isoformat()
        
        conn = sqlite3.connect(str(DB_PATH))
        with conn:
            conn.execute('''INSERT INTO feedback 
                            (machine_id, name, company, event_type, images_processed, satisfaction_score, comments, timestamp) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                         (machine_id, name, company, event_type, images_processed, satisfaction_score, comments, timestamp))
        conn.close()
        
        # Save to json array list as well
        feedbacks = []
        if FEEDBACK_PATH.exists():
            try:
                with open(FEEDBACK_PATH, "r", encoding="utf-8") as f:
                    feedbacks = json.load(f)
            except Exception:
                pass
                
        feedbacks.append({
            "timestamp": timestamp,
            "machine_id": machine_id,
            "name": name,
            "company": company,
            "event_type": event_type,
            "images_processed": images_processed,
            "satisfaction_score": satisfaction_score,
            "comments": comments
        })
        
        with open(FEEDBACK_PATH, "w", encoding="utf-8") as f:
            json.dump(feedbacks, f, indent=4)
            
        print(f"[Server] Received feedback from {name} ({company}). Score: {satisfaction_score}/5")
        return {"success": True, "message": "Feedback submitted successfully"}
        
    except Exception as e:
        bottle.response.status = 500
        return {"success": False, "error": f"Failed to submit feedback: {str(e)}"}

@app.route('/usage', method=['POST', 'OPTIONS'])
def usage():
    if bottle.request.method == 'OPTIONS':
        return {}
    try:
        data = bottle.request.json or {}
        machine_id = data.get("machine_id", "").strip()
        images_processed = int(data.get("images_processed", 0))
        duplicates_removed = int(data.get("duplicates_removed", 0))
        best_shots_selected = int(data.get("best_shots_selected", 0))
        processing_time = float(data.get("processing_time", 0.0))
        sessions = int(data.get("sessions", 0))
        
        if not machine_id:
            bottle.response.status = 400
            return {"success": False, "error": "Missing machine_id"}
            
        conn = sqlite3.connect(str(DB_PATH))
        with conn:
            conn.execute('''INSERT OR REPLACE INTO usage_analytics 
                            (machine_id, images_processed, duplicates_removed, best_shots_selected, processing_time, sessions, last_updated) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                         (machine_id, images_processed, duplicates_removed, best_shots_selected, processing_time, sessions, datetime.datetime.now().isoformat()))
        conn.close()
        return {"success": True, "message": "Usage metrics updated successfully"}
    except Exception as e:
        bottle.response.status = 500
        return {"success": False, "error": str(e)}

@app.route('/crash', method=['POST', 'OPTIONS'])
def crash():
    if bottle.request.method == 'OPTIONS':
        return {}
    try:
        data = bottle.request.json or {}
        machine_id = data.get("machine_id", "").strip()
        app_version = data.get("app_version", "").strip()
        error = data.get("error", "").strip()
        stacktrace = data.get("stacktrace", "").strip()
        
        if not machine_id:
            bottle.response.status = 400
            return {"success": False, "error": "Missing machine_id"}
            
        conn = sqlite3.connect(str(DB_PATH))
        with conn:
            conn.execute('''INSERT INTO crash_reports 
                            (machine_id, app_version, error, stacktrace, timestamp) 
                            VALUES (?, ?, ?, ?, ?)''',
                         (machine_id, app_version, error, stacktrace, datetime.datetime.now().isoformat()))
        conn.close()
        return {"success": True, "message": "Crash report uploaded successfully"}
    except Exception as e:
        bottle.response.status = 500
        return {"success": False, "error": str(e)}

@app.route('/feature_request', method=['POST', 'OPTIONS'])
def feature_request():
    if bottle.request.method == 'OPTIONS':
        return {}
    try:
        data = bottle.request.json or {}
        machine_id = data.get("machine_id", "").strip()
        feature = data.get("feature", "").strip()
        priority = data.get("priority", "").strip()
        workflow_impact = data.get("workflow_impact", "").strip()
        
        if not machine_id or not feature:
            bottle.response.status = 400
            return {"success": False, "error": "Missing machine_id or feature"}
            
        conn = sqlite3.connect(str(DB_PATH))
        with conn:
            conn.execute('''INSERT INTO feature_requests 
                            (machine_id, feature, priority, workflow_impact, timestamp) 
                            VALUES (?, ?, ?, ?, ?)''',
                         (machine_id, feature, priority, workflow_impact, datetime.datetime.now().isoformat()))
        conn.close()
        return {"success": True, "message": "Feature request submitted successfully"}
    except Exception as e:
        bottle.response.status = 500
        return {"success": False, "error": str(e)}

@app.route('/latest-version', method=['GET'])
def latest_version():
    host = bottle.request.headers.get('Host', 'localhost:5005')
    scheme = 'https' if any(x in host for x in ['onrender.com', 'koyeb.app', 'lhr.life', 'ngrok']) else 'http'
    return {
        "version": "1.1.0",
        "download_url": f"{scheme}://{host}/static/QuantileCull_Setup_v1.1.exe"
    }

@app.route('/admin', method=['GET'])
def admin():
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # 1. General Metrics
        cursor.execute("SELECT COUNT(*) FROM licenses WHERE fingerprint IS NOT NULL")
        total_activations = cursor.fetchone()[0]
        
        now_str = datetime.datetime.now().isoformat()
        cursor.execute("SELECT COUNT(*) FROM licenses WHERE status='active' AND expires_at > ?", (now_str,))
        active_trials = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM licenses WHERE status='active' AND expires_at <= ?", (now_str,))
        expired_trials = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(images_processed), SUM(images_processed), AVG(sessions) FROM usage_analytics")
        row = cursor.fetchone()
        avg_processed = round(row[0], 1) if row and row[0] is not None else 0
        total_processed = row[1] if row and row[1] is not None else 0
        avg_sessions = round(row[2], 1) if row and row[2] is not None else 0
        
        cursor.execute("SELECT COUNT(*) FROM feedback")
        feedback_count = cursor.fetchone()[0]
        
        # 2. Top Feature Requests
        cursor.execute("SELECT feature, MAX(priority) as priority, COUNT(*) as cnt FROM feature_requests GROUP BY feature ORDER BY cnt DESC LIMIT 5")
        feature_rows = cursor.fetchall()
        
        # 3. Active Licenses List
        cursor.execute("SELECT license_key, name, email, company, photography_type, expires_at FROM licenses WHERE fingerprint IS NOT NULL ORDER BY activated_at DESC")
        license_rows = cursor.fetchall()
        
        # 4. Recent Feedbacks
        cursor.execute("SELECT name, company, event_type, satisfaction_score, comments, timestamp FROM feedback ORDER BY timestamp DESC LIMIT 5")
        feedback_rows = cursor.fetchall()

        # 5. Recent Crashes
        cursor.execute("SELECT app_version, error, timestamp FROM crash_reports ORDER BY timestamp DESC LIMIT 5")
        crash_rows = cursor.fetchall()

        conn.close()
        
        # Render HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>QuantileCull Pilot Validation Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-dark: #0a0a0c;
            --bg-card: #15151a;
            --border: rgba(255, 255, 255, 0.08);
            --text-main: #f3f4f6;
            --text-secondary: #9ca3af;
            --cyan: #00d2ff;
            --blue: #007aff;
            --red: #ff453a;
            --green: #34c759;
        }}
        body {{
            background: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 2rem;
        }}
        h1, h2, h3 {{
            font-family: 'Outfit', sans-serif;
            margin-top: 0;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }}
        .logo {{
            font-size: 1.8rem;
            font-weight: 800;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .badge {{
            background: rgba(0, 210, 255, 0.1);
            color: var(--cyan);
            border: 1px solid rgba(0, 210, 255, 0.2);
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }}
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        }}
        .stat-card .label {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.5rem;
            font-weight: 600;
        }}
        .stat-card .value {{
            font-size: 2rem;
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            color: #fff;
        }}
        .dashboard-layout {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 2rem;
        }}
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 30px rgba(0,0,0,0.3);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            margin-top: 1rem;
        }}
        th {{
            border-bottom: 2px solid var(--border);
            padding: 0.75rem 1rem;
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
        }}
        td {{
            border-bottom: 1px solid var(--border);
            padding: 0.85rem 1rem;
            font-size: 0.9rem;
        }}
        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}
        .rating {{
            color: #ffd700;
            font-weight: bold;
        }}
        .priority-label {{
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .priority-critical {{ background: rgba(255,69,58,0.15); color: var(--red); }}
        .priority-high {{ background: rgba(255,159,10,0.15); color: #ff9f0a; }}
        .priority-medium {{ background: rgba(0,122,255,0.15); color: var(--blue); }}
        .priority-low {{ background: rgba(156,163,175,0.15); color: var(--text-secondary); }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <div class="logo">QuantileCull</div>
            <div style="color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.2rem;">Pilot Validation Server Panel</div>
        </div>
        <div class="badge">V1.1 ACTIVE</div>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">Activations</div>
            <div class="value" style="color: var(--cyan);">{total_activations}</div>
        </div>
        <div class="stat-card">
            <div class="label">Active Trials</div>
            <div class="value" style="color: var(--green);">{active_trials}</div>
        </div>
        <div class="stat-card">
            <div class="label">Expired Trials</div>
            <div class="value" style="color: var(--red);">{expired_trials}</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Images Scanned</div>
            <div class="value">{total_processed}</div>
        </div>
        <div class="stat-card">
            <div class="label">Avg Processed / Device</div>
            <div class="value">{avg_processed}</div>
        </div>
        <div class="stat-card">
            <div class="label">Feedbacks</div>
            <div class="value" style="color: var(--blue);">{feedback_count}</div>
        </div>
    </div>
    
    <div class="dashboard-layout">
        <div>
            <!-- Active Activations Table -->
            <div class="card">
                <h2>Registered Pilot Users & Activations</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Key</th>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Company</th>
                            <th>Type</th>
                            <th>Expires At</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(f"<tr><td><code>{r[0]}</code></td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5][:10]}</td></tr>" for r in license_rows) if license_rows else "<tr><td colspan='6' style='text-align:center; color:var(--text-secondary);'>No active installations recorded yet.</td></tr>"}
                    </tbody>
                </table>
            </div>
            
            <!-- Feedbacks Table -->
            <div class="card">
                <h2>Recent Feedback Submissions</h2>
                <table>
                    <thead>
                        <tr>
                            <th>User / Company</th>
                            <th>Event Category</th>
                            <th>Score</th>
                            <th>Comments</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(f"<tr><td><strong>{r[0]}</strong><br><span style='font-size:0.75rem; color:var(--text-secondary);'>{r[1]}</span></td><td>{r[2]}</td><td class='rating'>{'★' * r[3] + '☆' * (5 - r[3])}</td><td>{r[4]}</td></tr>" for r in feedback_rows) if feedback_rows else "<tr><td colspan='4' style='text-align:center; color:var(--text-secondary);'>No feedback submitted yet.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div>
            <!-- Top Requested Features -->
            <div class="card">
                <h2>Top Requested Features</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Feature</th>
                            <th>Priority</th>
                            <th>Requests</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(f"<tr><td>{r[0]}</td><td><span class='priority-label priority-{r[1].lower()}'>{r[1]}</span></td><td><strong>{r[2]}</strong></td></tr>" for r in feature_rows) if feature_rows else "<tr><td colspan='3' style='text-align:center; color:var(--text-secondary);'>No feature requests yet.</td></tr>"}
                    </tbody>
                </table>
            </div>

            <!-- Recent Crash Reports -->
            <div class="card">
                <h2>Recent System Crashes</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Version / Error</th>
                            <th>Timestamp</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(f"<tr><td><strong>v{r[0]}</strong><br><span style='color:var(--red); font-size:0.8rem;'>{r[1][:50]}...</span></td><td>{r[2][:16].replace('T', ' ')}</td></tr>" for r in crash_rows) if crash_rows else "<tr><td colspan='2' style='text-align:center; color:var(--text-secondary);'>No crashes recorded. (Stable Build!)</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""
        return html
    except Exception as e:
        bottle.response.status = 500
        return f"<h3>Admin Dashboard Error: {str(e)}</h3>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5005))
    host = os.environ.get("HOST", "0.0.0.0")
    print("=== QuantileCull Licensing & Activation Server ===")
    print(f"Running on http://{host}:{port}")
    bottle.run(app, host=host, port=port, quiet=True)
