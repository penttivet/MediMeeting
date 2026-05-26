import os
import io
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
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "")
UPSTASH_URL       = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN     = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
RESEND_API_KEY    = os.environ.get("RESEND_API_KEY", "")
ADMIN_EMAIL       = os.environ.get("ADMIN_EMAIL", "")

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

def send_email_notification(name, email, clinic):
    try:
        if not RESEND_API_KEY or not ADMIN_EMAIL:
            return
        requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={
                "from": "MediMeeting <onboarding@resend.dev>",
                "to": ADMIN_EMAIL,
                "subject": f"MediMeeting: New registration - {name}",
                "text": f"Hello!\n\nA new user has registered to MediMeeting and is waiting for approval.\n\nName: {name}\nEmail: {email}\nClinic: {clinic or 'Not specified'}\n\nApprove or reject the user in the admin panel:\nhttps://medimeeting-production.up.railway.app/admin\n\nBest regards,\nMediMeeting"
            }
        )
        log.info(f"Email notification sent for {email}")
    except Exception as e:
        log.error(f"Email error: {e}")

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

MAIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>MediMeeting</title>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="MediMeeting">
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
  .nav-links { margin-left:auto; display:flex; gap:8px; flex-wrap:wrap; }
  .nav-link { font-size:13px; color:var(--text2); text-decoration:none; padding:6px 12px; border-radius:8px; background:var(--surface2); border:1px solid var(--border); }
  .container { width:100%; max-width:480px; padding:24px 16px; flex:1; display:flex; flex-direction:column; gap:16px; }
  .card { background:var(--surface); border-radius:16px; padding:20px; border:1px solid var(--border); }
  .card-title { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:1.2px; color:var(--text2); margin-bottom:14px; }
  input, select, textarea { background:var(--surface2); border:1px solid var(--border); border-radius:10px; padding:13px 16px; color:var(--text); font-family:'DM Sans',sans-serif; font-size:15px; width:100%; outline:none; transition:border-color 0.2s; }
  input:focus, select:focus, textarea:focus { border-color:var(--accent); }
  input::placeholder, textarea::placeholder { color:var(--text2); }
  select option { background:var(--surface2); }
  textarea { resize:vertical; min-height:80px; line-height:1.5; }
  .record-section { display:flex; flex-direction:column; align-items:center; gap:16px; padding:8px 0; }
  .record-btn { width:88px; height:88px; border-radius:50%; border:none; background:linear-gradient(135deg,var(--accent),var(--accent2)); cursor:pointer; display:flex; align-items:center; justify-content:center; font-size:32px; transition:transform 0.2s,box-shadow 0.2s; box-shadow:0 8px 32px rgba(79,142,247,0.35); }
  .record-btn:active { transform:scale(0.94); }
  .record-btn.recording { background:linear-gradient(135deg,var(--danger),#f7924f); box-shadow:0 8px 32px rgba(247,79,106,0.4); animation:pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{box-shadow:0 8px 32px rgba(247,79,106,0.4);}50%{box-shadow:0 8px 48px rgba(247,79,106,0.7);} }
  .record-status { font-size:14px; color:var(--text2); text-align:center; min-height:20px; }
  .record-status.active { color:var(--danger); font-weight:500; }
  .timer { font-family:'DM Serif Display',serif; font-size:28px; color:var(--text); letter-spacing:2px; display:none; }
  .timer.visible { display:block; }
  .wave { display:none; gap:3px; align-items:flex-end; height:24px; }
  .wave.visible { display:flex; }
  .wave span { width:4px; background:var(--danger); border-radius:2px; animation:wave 0.8s ease-in-out infinite; }
  .wave span:nth-child(2){animation-delay:0.1s;}.wave span:nth-child(3){animation-delay:0.2s;}.wave span:nth-child(4){animation-delay:0.3s;}.wave span:nth-child(5){animation-delay:0.4s;}
  @keyframes wave{0%,100%{height:6px;}50%{height:20px;}}
  .btn { width:100%; padding:15px; border-radius:12px; border:none; font-family:'DM Sans',sans-serif; font-size:15px; font-weight:600; cursor:pointer; transition:opacity 0.2s,transform 0.1s; display:flex; align-items:center; justify-content:center; gap:8px; }
  .btn:active { transform:scale(0.98); }
  .btn:disabled { opacity:0.45; cursor:not-allowed; }
  .btn-primary { background:linear-gradient(135deg,var(--accent),var(--accent2)); color:white; }
  .btn-secondary { background:var(--surface2); color:var(--text); border:1px solid var(--border); }
  .btn-danger { background:rgba(247,79,106,0.15); color:var(--danger); border:1px solid rgba(247,79,106,0.3); }
  .progress-section { display:none; flex-direction:column; gap:12px; }
  .progress-section.visible { display:flex; }
  .progress-step { display:flex; align-items:center; gap:12px; padding:14px 16px; background:var(--surface2); border-radius:10px; font-size:14px; opacity:0.4; transition:all 0.3s ease; border:1px solid transparent; }
  .progress-step.active { opacity:1; background:linear-gradient(135deg,rgba(79,142,247,0.1),rgba(124,106,247,0.1)); border:1px solid rgba(79,142,247,0.3); }
  .progress-step.done { opacity:1; color:var(--success); background:rgba(79,202,122,0.08); border:1px solid rgba(79,202,122,0.2); }
  .step-icon { font-size:20px; width:28px; text-align:center; font-weight:600; }
  .spinner { width:20px; height:20px; border:2.5px solid rgba(79,142,247,0.2); border-top-color:var(--accent); border-radius:50%; animation:spin 0.7s linear infinite; box-shadow:0 0 8px rgba(79,142,247,0.3); }
  @keyframes spin{to{transform:rotate(360deg);}}
  .result-section { display:none; }
  .result-section.visible { display:flex; flex-direction:column; gap:12px; }
  .summary-box { background:var(--surface2); border-radius:12px; padding:16px; font-size:14px; line-height:1.7; color:var(--text); border:1px solid var(--border); white-space:pre-wrap; max-height:300px; overflow-y:auto; }
  .action-items { background:var(--surface2); border-radius:12px; padding:16px; border:1px solid var(--border); }
  .action-item { display:flex; gap:10px; padding:8px 0; border-bottom:1px solid var(--border); font-size:14px; }
  .action-item:last-child { border-bottom:none; }
  .action-num { color:var(--accent); font-weight:600; min-width:20px; }
  .transcript-box { background:var(--surface2); border-radius:10px; padding:14px; font-size:13px; line-height:1.6; color:var(--text2); max-height:120px; overflow-y:auto; border:1px solid var(--border); }
  .error-msg { background:rgba(247,79,106,0.12); border:1px solid rgba(247,79,106,0.3); border-radius:10px; padding:12px 14px; font-size:13px; color:var(--danger); display:none; }
  .error-msg.visible { display:block; }
  .copy-btn { background:var(--surface2); border:1px solid var(--border); border-radius:8px; padding:8px 14px; color:var(--text2); font-size:13px; cursor:pointer; font-family:'DM Sans',sans-serif; }
  .section-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
  .tag { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:1px; color:var(--text2); }
  .brief-section { display:none; flex-direction:column; gap:8px; margin-top:8px; }
  .brief-section.visible { display:flex; }
  .brief-box { background:var(--surface2); border-radius:10px; padding:14px; font-size:14px; line-height:1.6; color:var(--text); border:1px solid var(--accent); white-space:pre-wrap; }
</style>
</head>
<body>
<div class="header">
  <div class="logo">🤝</div>
  <div class="header-text"><h1>MediMeeting</h1><p>Record and summarize</p></div>
  <div class="nav-links">
    <a href="/pricing" class="nav-link">💳 Pricing</a>
    <a href="/logout" class="nav-link">Sign out</a>
  </div>
</div>
<div class="container">
  <div class="card">
    <div class="card-title">Meeting details (optional)</div>
    <div style="display:flex;flex-direction:column;gap:10px;">
      <input type="text" id="meetingTitle" placeholder="Topic / title" />
      <input type="text" id="participants" placeholder="Participants (optional)" />
      <select id="meetingLanguage">
        <option value="en">🇬🇧 English</option>
        <option value="fi">🇫🇮 Suomi</option>
        <option value="sv">🇸🇪 Svenska</option>
        <option value="de">🇩🇪 Deutsch</option>
        <option value="ar">🇸🇦 العربية</option>
      </select>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Recording</div>
    <div class="record-section">
      <div class="timer" id="timer">00:00</div>
      <button class="record-btn" id="recordBtn" onclick="handleRecordBtn()">🎙️</button>
      <div class="wave" id="wave"><span></span><span></span><span></span><span></span><span></span></div>
      <div class="record-status" id="recordStatus">Press button to start recording</div>
    </div>
  </div>
  <div class="error-msg" id="errorMsg"></div>
  <div class="card progress-section" id="progressSection">
    <div class="card-title">Processing...</div>
    <div class="progress-step" id="step1"><span class="step-icon">🎙️</span><span style="font-weight:500;">Converting speech to text</span></div>
    <div class="progress-step" id="step2" style="padding:16px 18px;"><span class="step-icon">⚡</span><span style="font-weight:500;">Creating summary and key points</span></div>
  </div>
  <div class="result-section" id="resultSection">
    <div class="card">
      <div class="section-header"><span class="tag">📝 Summary</span><button class="copy-btn" onclick="copyText('summaryBox')">Copy</button></div>
      <div class="summary-box" id="summaryBox"></div>
    </div>
    <div class="card">
      <div class="section-header"><span class="tag">⭐ Key points</span><button class="copy-btn" onclick="copyText('keyPointsBox')">Copy</button></div>
      <div class="action-items" id="keyPointsBox"></div>
    </div>
    <div class="card">
      <div class="section-header"><span class="tag">✅ Action items</span><button class="copy-btn" onclick="copyText('actionBox')">Copy</button></div>
      <div class="action-items" id="actionBox"></div>
    </div>
    <div class="card">
      <div class="section-header"><span class="tag">🎙️ Transcript</span><button class="copy-btn" onclick="copyText('transcriptBox')">Copy</button></div>
      <div class="transcript-box" id="transcriptBox"></div>
    </div>
    <div class="card">
      <div class="card-title">📄 Create brief</div>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <textarea id="briefRequest" placeholder="What kind of brief do you need? e.g. 'short executive summary' or '3 bullet points for management'"></textarea>
        <button class="btn btn-secondary" onclick="createBrief()">✨ Generate brief</button>
      </div>
      <div class="brief-section" id="briefSection">
        <div class="section-header"><span class="tag">📄 Brief</span><button class="copy-btn" onclick="copyText('briefBox')">Copy</button></div>
        <div class="brief-box" id="briefBox"></div>
      </div>
    </div>
    <button class="btn btn-secondary" onclick="resetAll()">🔄 New meeting</button>
    <button class="btn btn-danger" onclick="deleteRecording()">🗑️ Delete & start over</button>
  </div>
  <button class="btn btn-primary" id="generateBtn" onclick="generate()" disabled>✨ Create summary</button>
</div>
<script>
let mediaRecorder=null,audioChunks=[],isRecording=false,timerInterval=null,seconds=0,audioBlob=null,currentTranscript='';
function handleRecordBtn(){toggleRecording().catch(e=>showError('Microphone error: '+e.name+' - '+e.message));}
function updateTimer(){seconds++;const m=String(Math.floor(seconds/60)).padStart(2,'0');const s=String(seconds%60).padStart(2,'0');document.getElementById('timer').textContent=m+':'+s;}
async function toggleRecording(){
  if(!isRecording){
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    mediaRecorder=new MediaRecorder(stream);audioChunks=[];
    mediaRecorder.ondataavailable=e=>audioChunks.push(e.data);
    mediaRecorder.onstop=()=>{audioBlob=new Blob(audioChunks,{type:'audio/webm'});document.getElementById('generateBtn').disabled=false;};
    mediaRecorder.start();isRecording=true;seconds=0;timerInterval=setInterval(updateTimer,1000);
    document.getElementById('recordBtn').classList.add('recording');document.getElementById('recordBtn').textContent='⏹️';
    document.getElementById('recordStatus').textContent='Recording...';document.getElementById('recordStatus').classList.add('active');
    document.getElementById('timer').classList.add('visible');document.getElementById('wave').classList.add('visible');
  }else{
    mediaRecorder.stop();mediaRecorder.stream.getTracks().forEach(t=>t.stop());isRecording=false;clearInterval(timerInterval);
    document.getElementById('recordBtn').classList.remove('recording');document.getElementById('recordBtn').textContent='🎙️';
    document.getElementById('recordStatus').textContent='Recording done ('+document.getElementById('timer').textContent+')';
    document.getElementById('recordStatus').classList.remove('active');document.getElementById('wave').classList.remove('visible');
  }
}
function setStep(num,status){const el=document.getElementById('step'+num);el.classList.remove('active','done');if(status==='active'){el.classList.add('active');el.querySelector('.step-icon').innerHTML='<div class="spinner"></div>';}else if(status==='done'){el.classList.add('done');el.querySelector('.step-icon').textContent='✅';}}
async function generate(){
  if(!audioBlob)return;hideError();
  document.getElementById('generateBtn').style.display='none';document.getElementById('progressSection').classList.add('visible');document.getElementById('resultSection').classList.remove('visible');
  setStep(1,'active');setStep(2,'');
  const formData=new FormData();formData.append('audio',audioBlob,'recording.webm');
  formData.append('meeting_title',document.getElementById('meetingTitle').value);
  formData.append('participants',document.getElementById('participants').value);
  formData.append('language',document.getElementById('meetingLanguage').value);
  try{
    const resp=await fetch('/transcribe',{method:'POST',body:formData});const data=await resp.json();if(!resp.ok)throw new Error(data.error||'Transcription failed');
    setStep(1,'done');setStep(2,'active');document.getElementById('transcriptBox').textContent=data.transcript;currentTranscript=data.transcript;
    const resp2=await fetch('/summarize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({transcript:data.transcript,meeting_title:document.getElementById('meetingTitle').value,participants:document.getElementById('participants').value,language:document.getElementById('meetingLanguage').value})});
    const data2=await resp2.json();if(!resp2.ok)throw new Error(data2.error||'Summary failed');
    setStep(2,'done');
    document.getElementById('summaryBox').textContent=data2.summary;
    const keyBox=document.getElementById('keyPointsBox');keyBox.innerHTML='';
    if(data2.key_points&&data2.key_points.length>0){data2.key_points.forEach((item,i)=>{const div=document.createElement('div');div.className='action-item';div.innerHTML='<span class="action-num">'+( i+1)+'.</span><span>'+item+'</span>';keyBox.appendChild(div);});}
    else{keyBox.innerHTML='<div style="color:var(--text2);font-size:14px">No key points identified.</div>';}
    const actionBox=document.getElementById('actionBox');actionBox.innerHTML='';
    if(data2.action_items&&data2.action_items.length>0){data2.action_items.forEach((item,i)=>{const div=document.createElement('div');div.className='action-item';div.innerHTML='<span class="action-num">'+(i+1)+'.</span><span>'+item+'</span>';actionBox.appendChild(div);});}
    else{actionBox.innerHTML='<div style="color:var(--text2);font-size:14px">No action items identified.</div>';}
    setTimeout(()=>{document.getElementById('progressSection').classList.remove('visible');document.getElementById('resultSection').classList.add('visible');},600);
  }catch(e){document.getElementById('progressSection').classList.remove('visible');document.getElementById('generateBtn').style.display='flex';showError(e.message);}
}
async function createBrief(){
  const request=document.getElementById('briefRequest').value.trim();
  if(!request||!currentTranscript){showError('Please record a meeting first and describe what brief you need.');return;}
  const btn=document.querySelector('[onclick="createBrief()"]');btn.disabled=true;btn.textContent='Generating...';
  try{
    const resp=await fetch('/brief',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({transcript:currentTranscript,request,language:document.getElementById('meetingLanguage').value})});
    const data=await resp.json();if(!resp.ok)throw new Error(data.error||'Brief failed');
    document.getElementById('briefBox').textContent=data.brief;
    document.getElementById('briefSection').classList.add('visible');
  }catch(e){showError(e.message);}
  btn.disabled=false;btn.textContent='✨ Generate brief';
}
function copyText(id){const el=document.getElementById(id);let text=el.textContent||el.innerText;if(id==='actionBox'||id==='keyPointsBox'){text=Array.from(el.querySelectorAll('.action-item')).map(a=>a.textContent.trim()).join('\\n');}navigator.clipboard.writeText(text).then(()=>{const btn=el.closest('.card').querySelector('.copy-btn');if(btn){btn.textContent='Copied!';setTimeout(()=>btn.textContent='Copy',2000);}});}
function deleteRecording(){if(confirm('Delete this recording and start over?')){resetAll();}}
function resetAll(){audioBlob=null;currentTranscript='';seconds=0;document.getElementById('timer').textContent='00:00';document.getElementById('timer').classList.remove('visible');document.getElementById('recordStatus').textContent='Press button to start recording';document.getElementById('recordStatus').classList.remove('active');document.getElementById('generateBtn').disabled=true;document.getElementById('generateBtn').style.display='flex';document.getElementById('resultSection').classList.remove('visible');document.getElementById('progressSection').classList.remove('visible');document.getElementById('briefSection').classList.remove('visible');hideError();}
function showError(msg){const el=document.getElementById('errorMsg');el.textContent='⚠️ '+msg;el.classList.add('visible');}
function hideError(){document.getElementById('errorMsg').classList.remove('visible');}
</script>
</body>
</html>"""

SUMMARY_SYSTEM = """You are a professional meeting assistant. You are given a transcript of a meeting.

Always respond in the same language as the transcript. If mixed languages, use the dominant one.

Return ONLY this JSON:
{
  "summary": "Clear summary of the meeting (3-6 sentences). Cover main topics, decisions and key discussion points.",
  "key_points": [
    "Key point 1",
    "Key point 2"
  ],
  "action_items": [
    "Action item 1 - who does what",
    "Action item 2 - who does what"
  ]
}

key_points are the most important facts or decisions from the meeting.
action_items are concrete tasks agreed upon. Return empty list [] if none.
Respond ONLY with JSON, no other text."""

BRIEF_SYSTEM = """You are a professional meeting assistant. Create a brief based on the meeting transcript and the user's request.

Always respond in the same language as the transcript.
Be concise and professional.
Respond with only the brief text, no preamble."""

AUTH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MediMeeting — {title}</title>
<meta name="theme-color" content="#0f1117">
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap');
  :root {{ --bg:#0f1117; --surface:#1a1d27; --surface2:#22263a; --accent:#4f8ef7; --accent2:#7c6af7; --text:#e8eaf0; --text2:#8b90a8; --success:#4fca7a; --danger:#f74f6a; --border:rgba(255,255,255,0.07); }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:24px; }}
  .logo-wrap {{ display:flex; align-items:center; gap:12px; margin-bottom:32px; }}
  .logo {{ width:48px; height:48px; background:linear-gradient(135deg,var(--accent),var(--accent2)); border-radius:14px; display:flex; align-items:center; justify-content:center; font-size:24px; }}
  h1 {{ font-family:'DM Serif Display',serif; font-size:24px; }}
  .card {{ background:var(--surface); border-radius:20px; padding:28px; width:100%; max-width:380px; border:1px solid var(--border); }}
  .card h2 {{ font-size:18px; margin-bottom:20px; }}
  .field {{ display:flex; flex-direction:column; gap:6px; margin-bottom:14px; }}
  label {{ font-size:12px; color:var(--text2); font-weight:500; text-transform:uppercase; letter-spacing:0.8px; }}
  input {{ background:var(--surface2); border:1px solid var(--border); border-radius:10px; padding:13px 16px; color:var(--text); font-family:'DM Sans',sans-serif; font-size:15px; width:100%; outline:none; }}
  input:focus {{ border-color:var(--accent); }}
  .btn {{ width:100%; padding:15px; border-radius:12px; border:none; font-family:'DM Sans',sans-serif; font-size:15px; font-weight:600; cursor:pointer; background:linear-gradient(135deg,var(--accent),var(--accent2)); color:white; margin-top:8px; }}
  .msg {{ padding:12px 14px; border-radius:10px; font-size:13px; margin-bottom:16px; }}
  .msg.error {{ background:rgba(247,79,106,0.12); border:1px solid rgba(247,79,106,0.3); color:var(--danger); }}
  .msg.success {{ background:rgba(79,202,122,0.12); border:1px solid rgba(79,202,122,0.3); color:var(--success); }}
  .link {{ text-align:center; margin-top:16px; font-size:13px; color:var(--text2); }}
  .link a {{ color:var(--accent); text-decoration:none; }}
</style>
</head>
<body>
<div class="logo-wrap"><div class="logo">🤝</div><h1>MediMeeting</h1></div>
<div class="card"><h2>{title}</h2>{msg}{form}</div>
<div class="link">{link}</div>
</body>
</html>"""

ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MediMeeting — Admin</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&display=swap');
  :root {{ --bg:#0f1117; --surface:#1a1d27; --surface2:#22263a; --accent:#4f8ef7; --text:#e8eaf0; --text2:#8b90a8; --success:#4fca7a; --danger:#f74f6a; --border:rgba(255,255,255,0.07); }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text); padding:24px; }}
  h1 {{ font-size:22px; margin-bottom:24px; }}
  .card {{ background:var(--surface); border-radius:16px; padding:20px; margin-bottom:16px; border:1px solid var(--border); }}
  .user-row {{ display:flex; align-items:center; justify-content:space-between; padding:12px 0; border-bottom:1px solid var(--border); flex-wrap:wrap; gap:8px; }}
  .user-row:last-child {{ border-bottom:none; }}
  .user-info {{ font-size:14px; }}
  .user-info .email {{ color:var(--text2); font-size:12px; }}
  .status {{ font-size:11px; padding:3px 8px; border-radius:6px; font-weight:600; }}
  .status.pending {{ background:rgba(255,200,0,0.15); color:#ffc800; }}
  .status.approved {{ background:rgba(79,202,122,0.15); color:var(--success); }}
  .btn {{ padding:8px 14px; border-radius:8px; border:none; font-size:13px; font-weight:600; cursor:pointer; }}
  .btn-approve {{ background:var(--success); color:#000; }}
  .btn-reject {{ background:var(--danger); color:#fff; margin-left:6px; }}
  .logout {{ float:right; padding:8px 16px; background:var(--surface2); border:1px solid var(--border); border-radius:8px; color:var(--text); text-decoration:none; font-size:13px; }}
  .open-app {{ float:right; padding:8px 16px; background:linear-gradient(135deg,#4f8ef7,#7c6af7); border-radius:8px; color:white; text-decoration:none; font-size:13px; font-weight:600; margin-right:8px; }}
</style>
</head>
<body>
<a href="/logout" class="logout">Sign out</a>
<a href="/" class="open-app">🤝 Open app</a>
<h1>🤝 MediMeeting Admin</h1>
<div class="card">
  <h3 style="margin-bottom:16px;font-size:15px;color:#8b90a8;text-transform:uppercase;letter-spacing:1px;">Users</h3>
  {users}
</div>
</body>
</html>"""

PRICING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MediMeeting — Pricing</title>
<script src="https://js.stripe.com/v3/"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap');
  :root { --bg:#0f1117; --surface:#1a1d27; --surface2:#22263a; --accent:#4f8ef7; --accent2:#7c6af7; --text:#e8eaf0; --text2:#8b90a8; --success:#4fca7a; --danger:#f74f6a; --border:rgba(255,255,255,0.07); }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'DM Sans',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
  .header { width:100%; padding:20px 24px 16px; display:flex; align-items:center; gap:12px; border-bottom:1px solid var(--border); background:var(--surface); }
  .logo { width:38px; height:38px; background:linear-gradient(135deg,var(--accent),var(--accent2)); border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:18px; }
  .header-text h1 { font-family:'DM Serif Display',serif; font-size:20px; }
  .header-text p { font-size:12px; color:var(--text2); }
  .nav-links { margin-left:auto; display:flex; gap:8px; }
  .nav-link { font-size:13px; color:var(--text2); text-decoration:none; padding:6px 12px; border-radius:8px; background:var(--surface2); border:1px solid var(--border); }
  .container { max-width:900px; margin:0 auto; padding:48px 24px; }
  h2 { font-family:'DM Serif Display',serif; font-size:32px; text-align:center; margin-bottom:8px; }
  .subtitle { text-align:center; color:var(--text2); margin-bottom:48px; }
  .plans { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:24px; }
  .plan { background:var(--surface); border-radius:20px; padding:32px; border:1px solid var(--border); display:flex; flex-direction:column; position:relative; }
  .plan.popular { border-color:var(--accent); }
  .popular-badge { position:absolute; top:-12px; left:50%; transform:translateX(-50%); background:linear-gradient(135deg,var(--accent),var(--accent2)); color:white; padding:4px 16px; border-radius:20px; font-size:12px; font-weight:600; white-space:nowrap; }
  .plan-name { font-size:14px; font-weight:600; text-transform:uppercase; letter-spacing:1px; color:var(--text2); margin-bottom:8px; }
  .plan-price { font-family:'DM Serif Display',serif; font-size:48px; margin-bottom:4px; }
  .plan-price span { font-size:18px; font-family:'DM Sans',sans-serif; color:var(--text2); }
  .plan-desc { font-size:13px; color:var(--text2); margin-bottom:24px; }
  .features { list-style:none; margin-bottom:32px; flex:1; }
  .features li { padding:8px 0; font-size:14px; border-bottom:1px solid var(--border); display:flex; gap:8px; }
  .features li:last-child { border-bottom:none; }
  .check { color:var(--success); }
  .btn { width:100%; padding:14px; border-radius:12px; border:none; font-family:'DM Sans',sans-serif; font-size:15px; font-weight:600; cursor:pointer; }
  .btn-primary { background:linear-gradient(135deg,var(--accent),var(--accent2)); color:white; }
  .btn:disabled { opacity:0.6; cursor:not-allowed; }
  .current-plan { text-align:center; padding:8px; background:rgba(79,202,122,0.15); border-radius:8px; color:var(--success); font-size:13px; font-weight:600; margin-top:8px; }
</style>
</head>
<body>
<div class="header">
  <div class="logo">🤝</div>
  <div class="header-text"><h1>MediMeeting</h1><p>Record and summarize</p></div>
  <div class="nav-links">
    <a href="/" class="nav-link">🤝 App</a>
    <a href="/logout" class="nav-link">Sign out</a>
  </div>
</div>
<div class="container">
  <h2>Simple, transparent pricing</h2>
  <p class="subtitle">Start free, upgrade when you're ready</p>
  <div class="plans">
    <div class="plan">
      <div class="plan-name">Starter</div>
      <div class="plan-price">49€<span>/mo</span></div>
      <div class="plan-desc">Perfect for individual use</div>
      <ul class="features">
        <li><span class="check">✓</span> Unlimited recordings</li>
        <li><span class="check">✓</span> AI meeting summaries</li>
        <li><span class="check">✓</span> Key points extraction</li>
        <li><span class="check">✓</span> Action items</li>
        <li><span class="check">✓</span> Custom briefs</li>
        <li><span class="check">✓</span> 5 languages</li>
      </ul>
      <button class="btn btn-primary" onclick="subscribe('starter')">Get started</button>
    </div>
    <div class="plan popular">
      <div class="popular-badge">Most popular</div>
      <div class="plan-name">Pro</div>
      <div class="plan-price">89€<span>/mo</span></div>
      <div class="plan-desc">For teams and organizations</div>
      <ul class="features">
        <li><span class="check">✓</span> Everything in Starter</li>
        <li><span class="check">✓</span> Up to 5 users</li>
        <li><span class="check">✓</span> Priority support</li>
        <li><span class="check">✓</span> Custom branding</li>
        <li><span class="check">✓</span> Usage analytics</li>
        <li><span class="check">✓</span> Export to PDF/Word</li>
      </ul>
      <button class="btn btn-primary" onclick="subscribe('pro')">Get started</button>
    </div>
  </div>
</div>
<script>
const stripe = Stripe('{{ stripe_public_key }}');
async function subscribe(plan){
  const btn=event.target;btn.disabled=true;btn.textContent='Loading...';
  try{
    const resp=await fetch('/create-checkout-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan})});
    const data=await resp.json();
    if(data.url)window.location.href=data.url;else throw new Error(data.error||'Error');
  }catch(e){alert('Error: '+e.message);btn.disabled=false;btn.textContent='Get started';}
}
</script>
</body>
</html>"""


@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if request.args.get("msg") == "pending":
        msg = '<div class="msg error">⏳ Your account is pending approval.</div>'
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        user = redis_get(f"mm:user:{email}")
        if not user or user.get("password") != hash_password(password):
            msg = '<div class="msg error">❌ Incorrect email or password.</div>'
        elif user.get("status") != "approved":
            msg = '<div class="msg error">⏳ Your account is pending approval.</div>'
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
        clinic = request.form.get("clinic", "").strip()
        if redis_get(f"mm:user:{email}"):
            msg = '<div class="msg error">❌ Email is already in use.</div>'
        elif len(password) < 8:
            msg = '<div class="msg error">❌ Password must be at least 8 characters.</div>'
        else:
            redis_set(f"mm:user:{email}", {
                "name": name, "email": email,
                "password": hash_password(password),
                "clinic": clinic, "status": "pending",
                "created": datetime.now().isoformat()
            })
            send_email_notification(name, email, clinic)
            msg = '<div class="msg success">✅ Registration successful! You will be notified when your account is approved.</div>'
    form = '''<form method="POST">
      <div class="field"><label>Name</label><input type="text" name="name" required></div>
      <div class="field"><label>Email</label><input type="email" name="email" required></div>
      <div class="field"><label>Clinic / Organization</label><input type="text" name="clinic" placeholder="Optional"></div>
      <div class="field"><label>Password (min. 8 characters)</label><input type="password" name="password" required></div>
      <button class="btn" type="submit">Register</button>
    </form>'''
    return render_template_string(AUTH_HTML.format(title="Create account", msg=msg, form=form, link='<a href="/login">Already have an account? Sign in</a>'))


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
        if not user:
            continue
        email = user.get("email", "")
        name = user.get("name", "")
        clinic = user.get("clinic", "")
        status = user.get("status", "pending")
        status_class = "approved" if status == "approved" else "pending"
        status_label = "Approved" if status == "approved" else "Pending"
        approve_btn = f'<form method="POST" action="/admin/approve" style="display:inline"><input type="hidden" name="email" value="{email}"><button class="btn btn-approve" type="submit">✓ Approve</button></form>' if status == "pending" else ""
        reject_btn = f'<form method="POST" action="/admin/reject" style="display:inline"><input type="hidden" name="email" value="{email}"><button class="btn btn-reject" type="submit">✗ Remove</button></form>'
        users_html += f'<div class="user-row"><div class="user-info"><div>{name} {f"({clinic})" if clinic else ""}</div><div class="email">{email}</div></div><div style="display:flex;align-items:center;gap:8px"><span class="status {status_class}">{status_label}</span>{approve_btn}{reject_btn}</div></div>'
    if not users_html:
        users_html = '<p style="color:#8b90a8;font-size:14px">No users yet.</p>'
    return render_template_string(ADMIN_HTML.format(users=users_html))


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


@app.route("/admin/reject", methods=["POST"])
def admin_reject():
    if session.get("user_email") != ADMIN_EMAIL:
        return redirect("/login")
    email = request.form.get("email")
    try:
        requests.post(UPSTASH_URL, headers=REDIS_HEADERS, json=["DEL", f"mm:user:{email}"], timeout=5)
    except:
        pass
    return redirect("/admin")


@app.route("/")
@login_required
def index():
    return render_template_string(MAIN_HTML)


@app.route("/pricing")
@login_required
def pricing():
    user_email = session.get("user_email", "")
    user = redis_get(f"mm:user:{user_email}")
    plan = user.get("plan", "none") if user else "none"
    return render_template_string(PRICING_HTML, stripe_public_key=STRIPE_PUBLIC_KEY, plan=plan)


@app.route("/create-checkout-session", methods=["POST"])
@login_required
def create_checkout_session():
    plan = request.json.get("plan", "starter")
    user_email = session.get("user_email", "")
    prices = {"starter": 4900, "pro": 8900}
    price = prices.get(plan, 4900)
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price_data": {"currency": "eur", "product_data": {"name": f"MediMeeting {plan.capitalize()}"}, "unit_amount": price, "recurring": {"interval": "month"}}, "quantity": 1}],
            mode="subscription",
            success_url="https://medimeeting-production.up.railway.app/payment-success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://medimeeting-production.up.railway.app/pricing",
            customer_email=user_email,
        )
        return jsonify({"url": checkout_session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/payment-success")
@login_required
def payment_success():
    session_id = request.args.get("session_id")
    user_email = session.get("user_email", "")
    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        if checkout_session.payment_status == "paid":
            user = redis_get(f"mm:user:{user_email}")
            if user:
                user["plan"] = "active"
                redis_set(f"mm:user:{user_email}", user)
    except Exception as e:
        log.error(f"Payment success error: {e}")
    return redirect("/")


@app.route("/transcribe", methods=["POST"])
@login_required
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400
    audio_file = request.files["audio"]
    language = request.form.get("language", "en")
    try:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": ("recording.webm", audio_file.read(), "audio/webm")},
            data={"model": "whisper-1", "language": language},
            timeout=60
        )
        if not resp.ok:
            return jsonify({"error": "Speech recognition failed"}), 500
        return jsonify({"transcript": resp.json().get("text", "")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/summarize", methods=["POST"])
@login_required
def summarize():
    data = request.json
    transcript = data.get("transcript", "")
    meeting_title = data.get("meeting_title", "")
    participants = data.get("participants", "")
    language = data.get("language", "en")
    context = ""
    if meeting_title:
        context += f"Meeting topic: {meeting_title}\n"
    if participants:
        context += f"Participants: {participants}\n"
    if context:
        context += "\n"
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={"model": "claude-sonnet-4-20250514", "max_tokens": 1500, "system": SUMMARY_SYSTEM, "messages": [{"role": "user", "content": f"{context}Transcript:\n\n{transcript}"}]},
            timeout=30
        )
        raw = resp.json()["content"][0]["text"].strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        return jsonify({"summary": result.get("summary", ""), "key_points": result.get("key_points", []), "action_items": result.get("action_items", [])})
    except Exception as e:
        log.error(f"Summarize error: {e}")
        return jsonify({"error": "Summary creation failed"}), 500


@app.route("/brief", methods=["POST"])
@login_required
def brief():
    data = request.json
    transcript = data.get("transcript", "")
    brief_request = data.get("request", "")
    language = data.get("language", "en")
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={"model": "claude-sonnet-4-20250514", "max_tokens": 1000, "system": BRIEF_SYSTEM, "messages": [{"role": "user", "content": f"Meeting transcript:\n\n{transcript}\n\nBrief request: {brief_request}"}]},
            timeout=30
        )
        brief_text = resp.json()["content"][0]["text"].strip()
        return jsonify({"brief": brief_text})
    except Exception as e:
        log.error(f"Brief error: {e}")
        return jsonify({"error": "Brief creation failed"}), 500


@app.route("/manifest.json")
def manifest():
    return jsonify({"name": "MediMeeting", "short_name": "MediMeeting", "description": "Record and summarize meetings", "start_url": "/", "display": "standalone", "background_color": "#0f1117", "theme_color": "#0f1117", "orientation": "portrait", "icons": [{"src": "/icon", "sizes": "192x192", "type": "image/png"}]})


@app.route("/icon")
def icon():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192"><rect width="192" height="192" rx="40" fill="#1a1d27"/><text x="96" y="130" font-size="100" text-anchor="middle">🤝</text></svg>'
    return svg, 200, {"Content-Type": "image/svg+xml"}


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


def ensure_admin():
    try:
        admin_hash = os.environ.get("ADMIN_PASSWORD_HASH", "b473debca72c06e903436ef305caa697ae7c50a03025e668a6a75eef96afe10f")
        existing = redis_get(f"mm:user:{ADMIN_EMAIL}")
        if not existing:
            redis_set(f"mm:user:{ADMIN_EMAIL}", {"name": "Admin", "email": ADMIN_EMAIL, "password": admin_hash, "clinic": "", "status": "approved", "role": "admin", "created": datetime.now().isoformat()})
            log.info(f"Admin created: {ADMIN_EMAIL}")
        elif existing.get("status") != "approved":
            existing["status"] = "approved"
            existing["password"] = admin_hash
            redis_set(f"mm:user:{ADMIN_EMAIL}", existing)
    except Exception as e:
        log.error(f"ensure_admin error: {e}")


with app.app_context():
    ensure_admin()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
