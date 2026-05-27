from flask import Flask, render_template_string, request, jsonify
import os
import requests

app = Flask(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MediMeeting</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e8eaf0; min-height: 100vh; display: flex; flex-direction: column; }
  .header { background: #1a1d27; padding: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: center; }
  .header h1 { font-size: 24px; margin-bottom: 5px; }
  .header p { font-size: 12px; color: #8b90a8; }
  .container { max-width: 500px; margin: 0 auto; padding: 20px; flex: 1; }
  .card { background: #1a1d27; border-radius: 12px; padding: 20px; margin-bottom: 16px; border: 1px solid rgba(255,255,255,0.1); }
  .card-title { font-size: 12px; font-weight: 600; text-transform: uppercase; color: #8b90a8; margin-bottom: 16px; letter-spacing: 1px; }
  input, select { width: 100%; padding: 12px; margin-bottom: 10px; background: #22263a; border: 1px solid rgba(255,255,255,0.1); color: #e8eaf0; border-radius: 8px; font-size: 14px; font-family: inherit; }
  input:focus, select:focus { outline: none; border-color: #4f8ef7; }
  .btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #4f8ef7, #7c6af7); color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 10px; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .record-area { text-align: center; padding: 20px 0; }
  .record-btn { width: 100px; height: 100px; border-radius: 50%; background: linear-gradient(135deg, #4f8ef7, #7c6af7); border: none; color: white; font-size: 40px; cursor: pointer; box-shadow: 0 8px 32px rgba(79,142,247,0.35); }
  .record-btn:active { transform: scale(0.95); }
  .record-btn.recording { background: linear-gradient(135deg, #f74f6a, #f7924f); animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%, 100% { box-shadow: 0 8px 32px rgba(247,79,106,0.4); } 50% { box-shadow: 0 8px 48px rgba(247,79,106,0.7); } }
  .timer { font-size: 32px; font-weight: bold; margin: 10px 0; font-family: monospace; }
  .status { font-size: 14px; color: #8b90a8; margin: 10px 0; }
  .status.active { color: #f74f6a; font-weight: 500; }
  .result { background: #1a1d27; border-radius: 8px; padding: 16px; margin-top: 16px; border: 1px solid rgba(255,255,255,0.1); }
  .result-title { font-size: 12px; font-weight: 600; color: #8b90a8; margin-bottom: 8px; text-transform: uppercase; }
  .result-text { font-size: 14px; line-height: 1.6; color: #e8eaf0; white-space: pre-wrap; max-height: 200px; overflow-y: auto; }
  .tabs { display: flex; gap: 8px; margin-bottom: 16px; }
  .tab { flex: 1; padding: 12px; background: #22263a; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; color: #8b90a8; cursor: pointer; font-weight: 600; text-align: center; }
  .tab.active { background: linear-gradient(135deg, #4f8ef7, #7c6af7); color: white; border-color: #4f8ef7; }
  .tab-content { display: none; }
  .tab-content.active { display: block; }
  .error { background: rgba(247, 79, 106, 0.1); border: 1px solid rgba(247, 79, 106, 0.3); color: #f74f6a; padding: 12px; border-radius: 8px; margin: 10px 0; display: none; }
  .error.visible { display: block; }
  .spacer { height: 20px; }
</style>
</head>
<body>
<div class="header">
  <h1>🤝 MediMeeting</h1>
  <p>Meetings & Calls</p>
</div>

<div class="container">
  <div class="tabs">
    <button class="tab active" onclick="switchTab('meeting')">🤝 Meeting</button>
    <button class="tab" onclick="switchTab('call')">☎️ Call</button>
  </div>

  <!-- MEETING -->
  <div id="meeting" class="tab-content active">
    <div class="card">
      <div class="card-title">Meeting Details</div>
      <input type="text" id="meetingTitle" placeholder="Meeting title (optional)" />
      <select id="meetingLang">
        <option value="en">English</option>
        <option value="fi">Suomi</option>
      </select>
    </div>

    <div class="card">
      <div class="card-title">Recording</div>
      <div class="record-area">
        <div class="timer" id="meetingTimer" style="display:none;">00:00</div>
        <button class="record-btn" id="meetingBtn" onclick="record('meeting')">🎙️</button>
        <div class="status" id="meetingStatus">Press to start</div>
      </div>
    </div>

    <div class="error" id="meetingError"></div>
    <button class="btn" id="meetingGen" onclick="generate('meeting')" disabled>✨ Create Summary</button>

    <div id="meetingResult" class="result" style="display:none;">
      <div class="result-title">Summary</div>
      <div class="result-text" id="meetingSummaryText"></div>
      <button class="btn" onclick="reset('meeting')" style="margin-top: 12px; background: #22263a; color: #e8eaf0;">New Meeting</button>
    </div>
  </div>

  <!-- CALL -->
  <div id="call" class="tab-content">
    <div class="card">
      <div class="card-title">Call Details</div>
      <input type="text" id="callWith" placeholder="Call with (optional)" />
      <input type="text" id="callTopic" placeholder="Call topic (optional)" />
      <select id="callLang">
        <option value="en">English</option>
        <option value="fi">Suomi</option>
      </select>
    </div>

    <div class="card">
      <div class="card-title">Recording</div>
      <div class="record-area">
        <div class="timer" id="callTimer" style="display:none;">00:00</div>
        <button class="record-btn" id="callBtn" onclick="record('call')">🎙️</button>
        <div class="status" id="callStatus">Press to start</div>
      </div>
    </div>

    <div class="error" id="callError"></div>
    <button class="btn" id="callGen" onclick="generate('call')" disabled>✨ Create Summary</button>

    <div id="callResult" class="result" style="display:none;">
      <div class="result-title">Summary</div>
      <div class="result-text" id="callSummaryText"></div>
      <button class="btn" onclick="reset('call')" style="margin-top: 12px; background: #22263a; color: #e8eaf0;">New Call</button>
    </div>
  </div>

  <div class="spacer"></div>
</div>

<script>
let mediaRecorder = null, audioChunks = [], isRecording = false, seconds = 0, timerInt = null;
let meetingAudio = null, callAudio = null;

function switchTab(tab) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById(tab).classList.add('active');
  event.target.classList.add('active');
}

function updateTimer(type) {
  const m = String(Math.floor(seconds/60)).padStart(2,'0');
  const s = String(seconds%60).padStart(2,'0');
  document.getElementById(type + 'Timer').textContent = m + ':' + s;
}

async function record(type) {
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
        document.getElementById(type + 'Gen').disabled = false;
      };
      mediaRecorder.start();
      isRecording = true;
      seconds = 0;
      timerInt = setInterval(() => { seconds++; updateTimer(type); }, 1000);
      document.getElementById(type + 'Btn').classList.add('recording');
      document.getElementById(type + 'Btn').textContent = '⏹️';
      document.getElementById(type + 'Status').textContent = 'Recording...';
      document.getElementById(type + 'Status').classList.add('active');
      document.getElementById(type + 'Timer').style.display = 'block';
    } catch (e) {
      showError(type, 'Microphone error');
    }
  } else {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
    isRecording = false;
    clearInterval(timerInt);
    document.getElementById(type + 'Btn').classList.remove('recording');
    document.getElementById(type + 'Btn').textContent = '🎙️';
    document.getElementById(type + 'Status').textContent = 'Done (' + document.getElementById(type + 'Timer').textContent + ')';
    document.getElementById(type + 'Status').classList.remove('active');
  }
}

async function generate(type) {
  const audio = type === 'meeting' ? meetingAudio : callAudio;
  if (!audio) return;

  const lang = document.getElementById(type + 'Lang').value;
  const title = type === 'meeting' ? document.getElementById('meetingTitle').value : document.getElementById('callTopic').value;

  const formData = new FormData();
  formData.append('audio', audio);
  formData.append('title', title);
  formData.append('language', lang);

  try {
    const r1 = await fetch('/transcribe', {method: 'POST', body: formData});
    const d1 = await r1.json();
    if (!r1.ok) throw new Error(d1.error || 'Failed');

    const r2 = await fetch('/summarize', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({transcript: d1.transcript, language: lang})
    });
    const d2 = await r2.json();
    if (!r2.ok) throw new Error(d2.error || 'Failed');

    document.getElementById(type + 'SummaryText').textContent = d2.summary;
    document.getElementById(type + 'Result').style.display = 'block';
  } catch (e) {
    showError(type, e.message);
  }
}

function reset(type) {
  if (type === 'meeting') meetingAudio = null;
  else callAudio = null;
  document.getElementById(type + 'Result').style.display = 'none';
  document.getElementById(type + 'Gen').disabled = true;
}

function showError(type, msg) {
  const el = document.getElementById(type + 'Error');
  el.textContent = '⚠️ ' + msg;
  el.classList.add('visible');
  setTimeout(() => el.classList.remove('visible'), 5000);
}
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/transcribe", methods=["POST"])
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
        return jsonify({"transcript": r.json().get("text", "")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/summarize", methods=["POST"])
def summarize():
    data = request.json
    transcript = data.get("transcript", "")
    language = data.get("language", "en")
    
    system = "Summarize this in 2-3 sentences. Focus on key points." if language == "en" else "Yhteenveto 2-3 lauseessa. Keskity tärkeisiin asioihin."
    
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "system": system,
                "messages": [{"role": "user", "content": transcript}]
            },
            timeout=30
        )
        summary = r.json()["content"][0]["text"].strip()
        return jsonify({"summary": summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
