from flask import Flask, render_template_string, request, jsonify
import requests
import os
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>MediMeeting</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 100%; height: 100%; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #0f1117;
  color: #e8eaf0;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow-y: auto;
}
.header {
  width: 100%;
  padding: 20px;
  background: #1a1d27;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  text-align: center;
}
.header h1 { font-size: 22px; margin-bottom: 4px; }
.header p { font-size: 12px; color: #8b90a8; }
.container {
  max-width: 480px;
  width: 100%;
  padding: 20px;
  flex: 1;
}
.tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}
.tab-btn {
  flex: 1;
  padding: 12px;
  border: 1px solid rgba(255,255,255,0.07);
  background: #1a1d27;
  color: #8b90a8;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 14px;
}
.tab-btn.active {
  background: linear-gradient(135deg, #4f8ef7, #7c6af7);
  color: white;
  border-color: #4f8ef7;
}
.tab-content { display: none; }
.tab-content.active { display: block; }
.card {
  background: #1a1d27;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}
.card h3 { font-size: 12px; text-transform: uppercase; color: #8b90a8; margin-bottom: 12px; font-weight: 600; }
input {
  width: 100%;
  padding: 12px;
  margin-bottom: 10px;
  background: #22263a;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 8px;
  color: #e8eaf0;
  font-size: 14px;
}
input:focus { outline: none; border-color: #4f8ef7; }
.record-area {
  text-align: center;
  padding: 20px 0;
}
.record-btn {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #4f8ef7, #7c6af7);
  color: white;
  font-size: 28px;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(79,142,247,0.3);
  margin: 0 auto 10px;
  display: block;
}
.record-btn:active { transform: scale(0.92); }
.record-btn.recording {
  background: linear-gradient(135deg, #f74f6a, #f7924f);
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 8px 24px rgba(247,79,106,0.3); }
  50% { box-shadow: 0 8px 32px rgba(247,79,106,0.6); }
}
.status { font-size: 13px; color: #8b90a8; }
.status.active { color: #f74f6a; font-weight: 600; }
.timer { font-size: 24px; display: none; margin-bottom: 8px; }
.timer.show { display: block; }
.btn {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: 8px;
}
.btn-primary {
  background: linear-gradient(135deg, #4f8ef7, #7c6af7);
  color: white;
}
.btn-secondary {
  background: #22263a;
  color: #e8eaf0;
  border: 1px solid rgba(255,255,255,0.07);
}
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.result { display: none; margin-top: 16px; }
.result.show { display: block; }
.summary {
  background: #22263a;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
  line-height: 1.6;
  max-height: 150px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
</head>
<body>

<div class="header">
  <h1>🤝 MediMeeting</h1>
  <p>Record meetings and calls</p>
</div>

<div class="container">
  <div class="tabs">
    <button class="tab-btn active" onclick="tab('meeting')">🤝 Meeting</button>
    <button class="tab-btn" onclick="tab('call')">☎️ Call</button>
  </div>

  <!-- MEETING -->
  <div id="meeting" class="tab-content active">
    <div class="card">
      <h3>Details</h3>
      <input type="text" id="meet_title" placeholder="Meeting title" />
    </div>
    <div class="card">
      <h3>Recording</h3>
      <div class="record-area">
        <div class="timer" id="meet_timer">00:00</div>
        <button class="record-btn" id="meet_btn" onclick="record('meeting')">🎙️</button>
        <div class="status" id="meet_status">Press to record</div>
      </div>
    </div>
    <button class="btn btn-primary" id="meet_gen" onclick="gen('meeting')" disabled>✨ Create summary</button>
    <div class="result" id="meet_result">
      <div class="card">
        <h3>Summary</h3>
        <div class="summary" id="meet_summary"></div>
      </div>
      <button class="btn btn-secondary" onclick="reset('meeting')">New meeting</button>
    </div>
  </div>

  <!-- CALL -->
  <div id="call" class="tab-content">
    <div class="card">
      <h3>Details</h3>
      <input type="text" id="call_with" placeholder="Call with" />
      <input type="text" id="call_topic" placeholder="Topic" />
    </div>
    <div class="card">
      <h3>Recording</h3>
      <div class="record-area">
        <div class="timer" id="call_timer">00:00</div>
        <button class="record-btn" id="call_btn" onclick="record('call')">🎙️</button>
        <div class="status" id="call_status">Press to record</div>
      </div>
    </div>
    <button class="btn btn-primary" id="call_gen" onclick="gen('call')" disabled>✨ Create summary</button>
    <div class="result" id="call_result">
      <div class="card">
        <h3>Summary</h3>
        <div class="summary" id="call_summary"></div>
      </div>
      <button class="btn btn-secondary" onclick="reset('call')">New call</button>
    </div>
  </div>
</div>

<script>
let recorder = null, chunks = [], recording = false, timer = null, secs = 0;
let audio_meet = null, audio_call = null;

function tab(t) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById(t).classList.add('active');
  event.target.classList.add('active');
}

function tick(t) {
  secs++;
  const m = String(Math.floor(secs/60)).padStart(2,'0');
  const s = String(secs%60).padStart(2,'0');
  document.getElementById(t + '_timer').textContent = m + ':' + s;
}

async function record(t) {
  if (!recording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio: true});
      recorder = new MediaRecorder(stream);
      chunks = [];
      recorder.ondataavailable = e => chunks.push(e.data);
      recorder.onstop = () => {
        const blob = new Blob(chunks, {type: 'audio/webm'});
        if (t === 'meeting') audio_meet = blob;
        else audio_call = blob;
        document.getElementById(t + '_gen').disabled = false;
      };
      recorder.start();
      recording = true;
      secs = 0;
      timer = setInterval(() => tick(t), 1000);
      document.getElementById(t + '_btn').classList.add('recording');
      document.getElementById(t + '_btn').textContent = '⏹️';
      document.getElementById(t + '_status').textContent = 'Recording...';
      document.getElementById(t + '_status').classList.add('active');
      document.getElementById(t + '_timer').classList.add('show');
    } catch (e) {
      alert('Mic error: ' + e.message);
    }
  } else {
    recorder.stop();
    recorder.stream.getTracks().forEach(x => x.stop());
    recording = false;
    clearInterval(timer);
    document.getElementById(t + '_btn').classList.remove('recording');
    document.getElementById(t + '_btn').textContent = '🎙️';
    document.getElementById(t + '_status').textContent = 'Done';
    document.getElementById(t + '_status').classList.remove('active');
  }
}

async function gen(t) {
  const audio = t === 'meeting' ? audio_meet : audio_call;
  if (!audio) return;
  
  const form = new FormData();
  form.append('audio', audio, 'rec.webm');
  
  document.getElementById(t + '_gen').disabled = true;
  document.getElementById(t + '_gen').textContent = '⏳ Processing...';
  
  try {
    const r1 = await fetch('/api/transcribe', {method: 'POST', body: form});
    const d1 = await r1.json();
    if (!r1.ok) throw new Error(d1.error);
    
    const r2 = await fetch('/api/summarize', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: d1.text})
    });
    const d2 = await r2.json();
    if (!r2.ok) throw new Error(d2.error);
    
    document.getElementById(t + '_summary').textContent = d2.summary;
    document.getElementById(t + '_result').classList.add('show');
  } catch (e) {
    alert('Error: ' + e.message);
  } finally {
    document.getElementById(t + '_gen').disabled = false;
    document.getElementById(t + '_gen').textContent = '✨ Create summary';
  }
}

function reset(t) {
  if (t === 'meeting') audio_meet = null;
  else audio_call = null;
  document.getElementById(t + '_result').classList.remove('show');
  document.getElementById(t + '_gen').disabled = true;
  document.getElementById(t + '_timer').classList.remove('show');
}
</script>

</body>
</html>"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/api/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio"}), 400
    
    try:
        r = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": ("rec.webm", request.files["audio"].read(), "audio/webm")},
            data={"model": "whisper-1"},
            timeout=60
        )
        if not r.ok:
            return jsonify({"error": "Transcription failed"}), 500
        return jsonify({"text": r.json().get("text", "")})
    except Exception as e:
        log.error(f"Transcribe error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/summarize", methods=["POST"])
def summarize():
    data = request.json
    text = data.get("text", "")
    
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "system": "Summarize this in 2-3 sentences. Focus on key points and decisions.",
                "messages": [{"role": "user", "content": text}]
            },
            timeout=30
        )
        if not r.ok:
            return jsonify({"error": "Summary failed"}), 500
        summary = r.json()["content"][0]["text"]
        return jsonify({"summary": summary})
    except Exception as e:
        log.error(f"Summarize error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
