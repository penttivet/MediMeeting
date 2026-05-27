import os
import json
import logging
import secrets
import hashlib
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, render_template_string, session, redirect
import requests
import stripe

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@medimeeting.app")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "")

REDIS_HEADERS = {
    "Authorization": f"Bearer {UPSTASH_TOKEN}",
    "Content-Type": "application/json"
}

def redis_get(key):
    try:
        r = requests.post(UPSTASH_URL, headers=REDIS_HEADERS, json=["GET", key], timeout=5)
        data = r.json()
        return json.loads(data["result"]) if data.get("result") else None
    except Exception as e:
        log.error(f"Redis get error: {e}")
        return None

def redis_set(key, value):
    try:
        requests.post(UPSTASH_URL, headers=REDIS_HEADERS, json=["SET", key, json.dumps(value)], timeout=5)
    except Exception as e:
        log.error(f"Redis set error: {e}")

def redis_keys(pattern):
    try:
        r = requests.post(UPSTASH_URL, headers=REDIS_HEADERS, json=["KEYS", pattern], timeout=5)
        data = r.json()
        return data.get("result", [])
    except:
        return []

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_email" not in session:
            return redirect("/login")
        user = redis_get(f"mm:user:{session['user_email']}")
        if not user or user.get("status") != "approved":
            session.clear()
            return redirect("/login?msg=pending")
        return f(*args, **kwargs)
    return decorated

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>MediMeeting</title>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0f1117">
<link rel="apple-touch-icon" href="/icon">
<link rel="manifest" href="/manifest.json">
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap');
  :root { --bg:#0f1117; --surface:#1a1d27; --surface2:#22263a; --accent:#4f8ef7; --accent2:#7c6af7; --text:#e8eaf0; --text2:#8b90a8; --success:#4fca7a; --danger:#f74f6a; --border:rgba(255,255,255,0.07); }
  * { margin:0; padding:0; box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  body { font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; display:flex; flex-direction:column; align-items:center; }
  .header { width:100%; padding:20px 24px 16px; display:flex; align-items:center; gap:12px; border-bottom:1px solid var(--border); background:var(--surface); }
  .logo { width:38px; height:38px; background:linear-gradient(135deg,var(--accent),var(--accent2)); border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:18px; }
  .header-text h1 { font-family:'DM Serif Display',serif; font-size:20px; letter-spacing:-0.3px; }
  .header-text p { font-size:12px; color:var(--text2); font-weight:300; }
  .nav-links { margin-left:auto; display:flex; gap:8px; }
  .nav-link { font-size:13px; color:var(--text2); text-decoration:none; padding:6px 12px; border-radius:8px; background:var(--surface2); border:1px solid var(--border); }
  .container { width:100%; max-width:480px; padding:24px 16px; flex:1; display:flex; flex-direction:column; gap:16px; }
  .card { background:var(--surface); border-radius:16px; padding:20px; border:1px solid var(--border); }
  .card-title { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:1.2px; color:var(--text2); margin-bottom:14px; }
  input, select { background:var(--surface2); border:1px solid var(--border); border-radius:10px; padding:13px 16px; color:var(--text); font-family:'DM Sans',sans-serif; font-size:15px; width:100%; outline:none; }
  input:focus, select:focus { border-color:var(--accent); }
  input::placeholder { color:var(--text2); }
  .record-section { display:flex; flex-direction:column; align-items:center; gap:16px; padding:8px 0; }
  .record-btn { width:88px; height:88px; border-radius:50%; border:none; background:linear-gradient(135deg,var(--accent),var(--accent2)); cursor:pointer; display:flex; align-items:center; justify-content:center; font-size:32px; box-shadow:0 8px 32px rgba(79,142,247,0.35); }
  .record-btn:active { transform:scale(0.94); }
  .record-btn.recording { background:linear-gradient(135deg,var(--danger),#f7924f); animation:pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{box-shadow:0 8px 32px rgba(247,79,106,0.4);}50%{box-shadow:0 8px 48px rgba(247,79,106,0.7);} }
  .timer { font-family:'DM Serif Display',serif; font-size:28px; display:none; }
  .timer.visible { display:block; }
  .btn { width:100%; padding:15px; border-radius:12px; border:none; font-family:'DM Sans',sans-serif; font-size:15px; font-weight:600; cursor:pointer; }
  .btn-primary { background:linear-gradient(135deg,var(--accent),var(--accent2)); color:white; }
  .btn-secondary { background:var(--surface2); color:var(--text); border:1px solid var(--border); }
  .result { display:none; margin-top:16px; }
  .result.visible { display:block; }
  .summary-box { background:var(--surface2); border-radius:10px; padding:14px; font-size:14px; line-height:1.6; color:var(--text); border:1px solid var(--border); white-space:pre-wrap; max-height:200px; overflow-y:auto; margin-top:12px; }
  .error-msg { background:rgba(247,79,106,0.12); border:1px solid rgba(247,79,106,0.3); border-radius:10px; padding:12px 14px; font-size:13px; color:var(--danger); display:none; }
  .error-msg.visible { display:block; }
  .tabs { display:flex; gap:8px; margin-bottom:8px; }
  .tab-btn { flex:1; padding:12px; border-radius:10px; border:1px solid var(--border); background:var(--surface2); color:var(--text2); font-weight:600; cursor:pointer; }
  .tab-btn.active { background:linear-gradient(135deg,var(--accent),var(--accent2)); color:white; }
  .tab-content { display:none; }
  .tab-content.active { display:block; }
</style>
</head>
<body>
<div class="header">
  <div class="logo">🤝</div>
  <div class="header-text"><h1>MediMeeting</h1><p>Meetings & Calls</p></div>
  <div class="nav-links">
    <a href="/logout" class="nav-link">Sign out</a>
  </div>
</div>

<div class="container">
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('meeting')">🤝 Meeting</button>
    <button class="tab-btn" onclick="switchTab('call')">☎️ Call</button>
  </div>

  <!-- MEETING TAB -->
  <div id="meeting" class="tab-content active">
    <div class="card">
      <div class="card-title">Meeting Info</div>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <input type="text" id="meetingTitle" placeholder="Meeting title" />
        <select id="meetingLang">
          <option value="en">English</option>
          <option value="fi">Suomi</option>
        </select>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Recording</div>
      <div class="record-section">
        <div class="timer" id="meetingTimer">00:00</div>
        <button class="record-btn" id="meetingBtn" onclick="toggleRecord('meeting')">🎙️</button>
        <div id="meetingStatus">Press to record</div>
      </div>
    </div>

    <div class="error-msg" id="meetingError"></div>
    <button class="btn btn-primary" id="meetingGenBtn" onclick="generate('meeting')" disabled>✨ Create summary</button>
    
    <div class="result" id="meetingResult">
      <div class="card">
        <div class="card-title">Summary</div>
        <div class="summary-box" id="meetingSummary"></div>
      </div>
      <button class="btn btn-secondary" onclick="reset('meeting')">New meeting</button>
    </div>
  </div>

  <!-- CALL TAB -->
  <div id="call" class="tab-content">
    <div class="card">
      <div class="card-title">Call Info</div>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <input type="text" id="callWith" placeholder="Call with (person/company)" />
        <input type="text" id="callTopic" placeholder="Call topic" />
        <select id="callLang">
          <option value="en">English</option>
          <option value="fi">Suomi</option>
        </select>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Recording</div>
      <div class="record-section">
        <div class="timer" id="callTimer">00:00</div>
        <button class="record-btn" id="callBtn" onclick="toggleRecord('call')">🎙️</button>
        <div id="callStatus">Press to record</div>
      </div>
    </div>

    <div class="error-msg" id="callError"></div>
    <button class="btn btn-primary" id="callGenBtn" onclick="generate('call')" disabled>✨ Create summary</button>
    
    <div class="result" id="callResult">
      <div class="card">
        <div class="card-title">Summary</div>
        <div class="summary-box" id="callSummary"></div>
      </div>
      <button class="btn btn-secondary" onclick="reset('call')">New call</button>
    </div>
  </div>
</div>

<script>
let mediaRecorder = null, audioChunks = [], isRecording = false, timerInterval = null, seconds = 0;
let meetingAudio = null, callAudio = null;

function switchTab(tab) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById(tab).classList.add('active');
  event.target.classList.add('active');
}

function updateTimer(type) {
  seconds++;
  const m = String(Math.floor(seconds/60)).padStart(2,'0');
  const s = String(seconds%60).padStart(2,'0');
  document.getElementById(type + 'Timer').textContent = m + ':' + s;
}

async function toggleRecord(type) {
  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio: true});
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunks, {type: 'audio/webm'});
        if (type === 'meeting') meetingAudio = blob;
        else callAudio = blob;
        document.getElementById(type + 'GenBtn').disabled = false;
      };
      mediaRecorder.start();
      isRecording = true;
      seconds = 0;
      timerInterval = setInterval(() => updateTimer(type), 1000);
      document.getElementById(type + 'Btn').classList.add('recording');
      document.getElementById(type + 'Btn').textContent = '⏹️';
      document.getElementById(type + 'Status').textContent = 'Recording...';
      document.getElementById(type + 'Timer').classList.add('visible');
    } catch (e) {
      showError(type, 'Microphone error');
    }
  } else {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
    isRecording = false;
    clearInterval(timerInterval);
    document.getElementById(type + 'Btn').classList.remove('recording');
    document.getElementById(type + 'Btn').textContent = '🎙️';
    document.getElementById(type + 'Status').textContent = 'Done (' + document.getElementById(type + 'Timer').textContent + ')';
  }
}

async function generate(type) {
  const audio = type === 'meeting' ? meetingAudio : callAudio;
  if (!audio) return;
  
  const lang = document.getElementById(type + 'Lang').value;
  const title = type === 'meeting' ? document.getElementById('meetingTitle').value : document.getElementById('callTopic').value;
  
  const formData = new FormData();
  formData.append('audio', audio, 'recording.webm');
  formData.append('title', title);
  formData.append('language', lang);
  
  try {
    const resp = await fetch('/transcribe', {method: 'POST', body: formData});
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Failed');
    
    const resp2 = await fetch('/summarize', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({transcript: data.transcript, language: lang})
    });
    const data2 = await resp2.json();
    if (!resp2.ok) throw new Error(data2.error || 'Failed');
    
    document.getElementById(type + 'Summary').textContent = data2.summary;
    document.getElementById(type + 'Result').classList.add('visible');
  } catch (e) {
    showError(type, e.message);
  }
}

function reset(type) {
  if (type === 'meeting') meetingAudio = null;
  else callAudio = null;
  document.getElementById(type + 'Result').classList.remove('visible');
  document.getElementById(type + 'GenBtn').disabled = true;
}

function showError(type, msg) {
  const el = document.getElementById(type + 'Error');
  el.textContent = '⚠️ ' + msg;
  el.classList.add('visible');
}
</script>
</body>
</html>"""

AUTH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MediMeeting</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap');
  :root {{ --bg:#0f1117; --surface:#1a1d27; --surface2:#22263a; --accent:#4f8ef7; --accent2:#7c6af7; --text:#e8eaf0; --text2:#8b90a8; --success:#4fca7a; --danger:#f74f6a; --border:rgba(255,255,255,0.07); }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; }}
  .logo {{ width:48px; height:48px; background:linear-gradient(135deg,var(--accent),var(--accent2)); border-radius:14px; display:flex; align-items:center; justify-content:center; font-size:24px; }}
  .card {{ background:var(--surface); border-radius:20px; padding:28px; width:100%; max-width:380px; border:1px solid var(--border); }}
  h1 {{ font-family:'DM Serif Display',serif; font-size:24px; margin-bottom:24px; }}
  .field {{ display:flex; flex-direction:column; gap:6px; margin-bottom:14px; }}
  label {{ font-size:12px; color:var(--text2); font-weight:500; text-transform:uppercase; }}
  input {{ background:var(--surface2); border:1px solid var(--border); border-radius:10px; padding:13px 16px; color:var(--text); font-size:15px; width:100%; outline:none; }}
  input:focus {{ border-color:var(--accent); }}
  .btn {{ width:100%; padding:15px; border-radius:12px; border:none; font-size:15px; font-weight:600; cursor:pointer; background:linear-gradient(135deg,var(--accent),var(--accent2)); color:white; margin-top:8px; }}
  .msg {{ padding:12px 14px; border-radius:10px; font-size:13px; margin-bottom:16px; }}
  .msg.error {{ background:rgba(247,79,106,0.12); color:var(--danger); }}
  .msg.success {{ background:rgba(79,202,122,0.12); color:var(--success); }}
  .link {{ text-align:center; margin-top:16px; font-size:13px; color:var(--text2); }}
  .link a {{ color:var(--accent); text-decoration:none; }}
  .wrap {{ display:flex; flex-direction:column; align-items:center; gap:20px; }}
</style>
</head>
<body>
<div class="wrap">
  <div style="display:flex;align-items:center;gap:12px;">
    <div class="logo">🤝</div>
    <h1>MediMeeting</h1>
  </div>
  <div class="card">
    <h2 style="font-size:18px;margin-bottom:20px;">{title}</h2>
    {msg}
    {form}
  </div>
  <div class="link">{link}</div>
</div>
</body>
</html>"""

@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        user = redis_get(f"mm:user:{email}")
        if not user or user.get("password") != hash_password(password):
            msg = '<div class="msg error">❌ Wrong email or password</div>'
        elif user.get("status") != "approved":
            msg = '<div class="msg error">⏳ Waiting for approval</div>'
        else:
            session["user_email"] = email
            if email == ADMIN_EMAIL:
                return redirect("/admin")
            return redirect("/")
    form = '''<form method="POST">
      <div class="field"><label>Email</label><input type="email" name="email" required></div>
      <div class="field"><label>Password</label><input type="password" name="password" required></div>
      <button class="btn" type="submit">Sign in</button>
    </form>'''
    return render_template_string(AUTH_HTML.format(title="Sign in", msg=msg, form=form, link='<a href="/register">No account? Register</a>'))

@app.route("/register", methods=["GET", "POST"])
def register():
    msg = ""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        if redis_get(f"mm:user:{email}"):
            msg = '<div class="msg error">❌ Email already in use</div>'
        elif len(password) < 8:
            msg = '<div class="msg error">❌ Min 8 characters</div>'
        else:
            redis_set(f"mm:user:{email}", {
                "name": name, "email": email,
                "password": hash_password(password),
                "status": "pending",
                "created": datetime.now().isoformat()
            })
            msg = '<div class="msg success">✅ Registered! Waiting for approval</div>'
    form = '''<form method="POST">
      <div class="field"><label>Name</label><input type="text" name="name" required></div>
      <div class="field"><label>Email</label><input type="email" name="email" required></div>
      <div class="field"><label>Password</label><input type="password" name="password" required></div>
      <button class="btn" type="submit">Register</button>
    </form>'''
    return render_template_string(AUTH_HTML.format(title="Create account", msg=msg, form=form, link='<a href="/login">Have account? Sign in</a>'))

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/admin")
def admin():
    if session.get("user_email") != ADMIN_EMAIL:
        return redirect("/login")
    keys = redis_keys("mm:user:*")
    users_html = ""
    for key in keys:
        user = redis_get(key)
        if user:
            email = user.get("email", "")
            name = user.get("name", "")
            status = user.get("status", "pending")
            approve = f'<form method="POST" action="/admin/approve" style="display:inline"><input type="hidden" name="email" value="{email}"><button class="btn" type="submit" style="background:green;color:white;width:auto;padding:6px 12px;">✓ Approve</button></form>' if status == "pending" else ""
            users_html += f'<p>{name} ({email}) - {status} {approve}</p>'
    return f'<h1>Admin</h1><a href="/logout">Logout</a><a href="/" style="margin-left:10px;">App</a><div style="margin-top:20px;">{users_html}</div>'

@app.route("/admin/approve", methods=["POST"])
def admin_approve():
    if session.get("user_email") != ADMIN_EMAIL:
        return redirect("/login")
    email = request.form.get("email")
    user = redis_get(f"mm:user:{email}")
    if user:
        user["status"] = "approved"
        redis_set(f"mm:user:{email}", user)
    return redirect("/admin")

@app.route("/")
@login_required
def index():
    return render_template_string(HTML)

@app.route("/transcribe", methods=["POST"])
@login_required
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio"}), 400
    try:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": ("recording.webm", request.files["audio"].read(), "audio/webm")},
            data={"model": "whisper-1"},
            timeout=60
        )
        if not resp.ok:
            return jsonify({"error": "Transcription failed"}), 500
        return jsonify({"transcript": resp.json().get("text", "")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/summarize", methods=["POST"])
@login_required
def summarize():
    data = request.json
    transcript = data.get("transcript", "")
    language = data.get("language", "en")
    
    system = "Summarize this meeting/call transcript in 2-3 sentences. Focus on key points and decisions." if language == "en" else "Yhteenveto kokouksesta/puhelusta 2-3 lauseessa. Keskity tärkeisiin asioihin."
    
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "system": system,
                "messages": [{"role": "user", "content": transcript}]
            },
            timeout=30
        )
        summary = resp.json()["content"][0]["text"].strip()
        return jsonify({"summary": summary})
    except Exception as e:
        log.error(f"Summarize error: {e}")
        return jsonify({"error": "Summary failed"}), 500

@app.route("/icon")
def icon():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192"><rect width="192" height="192" rx="40" fill="#1a1d27"/><text x="96" y="130" font-size="100" text-anchor="middle">🤝</text></svg>'
    return svg, 200, {"Content-Type": "image/svg+xml"}

@app.route("/manifest.json")
def manifest():
    return jsonify({"name": "MediMeeting", "short_name": "MediMeeting", "display": "standalone", "start_url": "/"})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

def ensure_admin():
    try:
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@medimeeting.app")
        admin_hash = os.environ.get("ADMIN_PASSWORD_HASH", "b473debca72c06e903436ef305caa697ae7c50a03025e668a6a75eef96afe10f")
        existing = redis_get(f"mm:user:{admin_email}")
        if not existing:
            redis_set(f"mm:user:{admin_email}", {
                "name": "Admin", "email": admin_email,
                "password": admin_hash, "status": "approved", "role": "admin",
                "created": datetime.now().isoformat()
            })
            log.info(f"Admin created: {admin_email}")
    except Exception as e:
        log.error(f"Admin error: {e}")

with app.app_context():
    ensure_admin()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
