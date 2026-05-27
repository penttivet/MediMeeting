from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MediMeeting</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { 
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #0f1117;
  color: #e8eaf0;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.header {
  padding: 20px;
  background: #1a1d27;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  text-align: center;
}
.header h1 { font-size: 24px; }
.header p { font-size: 12px; color: #8b90a8; }
.container {
  max-width: 480px;
  margin: 20px auto;
  padding: 20px;
  flex: 1;
}
.card {
  background: #1a1d27;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}
.card h2 { font-size: 14px; text-transform: uppercase; color: #8b90a8; margin-bottom: 16px; }
input, select {
  width: 100%;
  padding: 12px;
  margin-bottom: 10px;
  background: #22263a;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 8px;
  color: #e8eaf0;
  font-family: inherit;
}
input:focus { outline: none; border-color: #4f8ef7; }
.record-btn {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #4f8ef7, #7c6af7);
  color: white;
  font-size: 32px;
  cursor: pointer;
  display: block;
  margin: 20px auto;
  box-shadow: 0 8px 32px rgba(79,142,247,0.35);
}
.record-btn:active { transform: scale(0.94); }
.record-btn.recording {
  background: linear-gradient(135deg, #f74f6a, #f7924f);
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 8px 32px rgba(247,79,106,0.4); }
  50% { box-shadow: 0 8px 48px rgba(247,79,106,0.7); }
}
.status { text-align: center; font-size: 14px; color: #8b90a8; margin: 10px 0; }
.status.active { color: #f74f6a; font-weight: 500; }
.timer { text-align: center; font-size: 24px; display: none; }
.timer.visible { display: block; }
.btn {
  width: 100%;
  padding: 14px;
  border-radius: 10px;
  border: none;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
}
.btn-primary {
  background: linear-gradient(135deg, #4f8ef7, #7c6af7);
  color: white;
  margin-bottom: 10px;
}
.btn-secondary {
  background: #22263a;
  color: #e8eaf0;
  border: 1px solid rgba(255,255,255,0.07);
}
.result { display: none; }
.result.visible { display: block; }
.summary-box {
  background: #22263a;
  padding: 14px;
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.07);
  font-size: 13px;
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 10px 0;
}
.hidden { display: none; }
</style>
</head>
<body>
<div class="header">
  <h1>🤝 MediMeeting</h1>
  <p>Record meetings and calls</p>
</div>

<div class="container">
  <div class="card">
    <h2>Meeting</h2>
    <input type="text" id="meetingTitle" placeholder="Meeting title" />
    <div style="text-align: center;">
      <div class="timer" id="meetingTimer">00:00</div>
      <button class="record-btn" id="meetingBtn" onclick="toggleRecord('meeting')">🎙️</button>
      <div class="status" id="meetingStatus">Press to record</div>
    </div>
    <button class="btn btn-primary" id="meetingGenBtn" onclick="showResult('meeting')" disabled>✨ Show summary</button>
    <div class="result" id="meetingResult">
      <h3 style="margin-bottom:10px;">Summary</h3>
      <div class="summary-box" id="meetingSummary">Meeting recorded. Summary will appear here.</div>
      <button class="btn btn-secondary" onclick="resetMeeting()" style="margin-top: 10px;">New meeting</button>
    </div>
  </div>

  <div class="card">
    <h2>Call</h2>
    <input type="text" id="callWith" placeholder="Call with" />
    <input type="text" id="callTopic" placeholder="Call topic" />
    <div style="text-align: center;">
      <div class="timer" id="callTimer">00:00</div>
      <button class="record-btn" id="callBtn" onclick="toggleRecord('call')">🎙️</button>
      <div class="status" id="callStatus">Press to record</div>
    </div>
    <button class="btn btn-primary" id="callGenBtn" onclick="showResult('call')" disabled>✨ Show summary</button>
    <div class="result" id="callResult">
      <h3 style="margin-bottom:10px;">Summary</h3>
      <div class="summary-box" id="callSummary">Call recorded. Summary will appear here.</div>
      <button class="btn btn-secondary" onclick="resetCall()" style="margin-top: 10px;">New call</button>
    </div>
  </div>
</div>

<script>
let mediaRecorder = null, audioChunks = [], isRecording = false, timerInterval = null, seconds = 0;
let meetingAudio = null, callAudio = null;

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
      document.getElementById(type + 'Status').classList.add('active');
      document.getElementById(type + 'Timer').classList.add('visible');
    } catch (e) {
      alert('Microphone error: ' + e.message);
    }
  } else {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
    isRecording = false;
    clearInterval(timerInterval);
    document.getElementById(type + 'Btn').classList.remove('recording');
    document.getElementById(type + 'Btn').textContent = '🎙️';
    document.getElementById(type + 'Status').textContent = 'Done (' + document.getElementById(type + 'Timer').textContent + ')';
    document.getElementById(type + 'Status').classList.remove('active');
  }
}

function showResult(type) {
  const resultDiv = document.getElementById(type + 'Result');
  resultDiv.classList.add('visible');
  
  const title = type === 'meeting' ? document.getElementById('meetingTitle').value : document.getElementById('callTopic').value;
  const summary = type === 'meeting' ? 
    'Meeting: ' + (title || 'Untitled') + '\\n\\nRecorded and ready for analysis.' :
    'Call: ' + (title || 'Untitled') + '\\n\\nRecorded and ready for analysis.';
  
  document.getElementById(type + 'Summary').textContent = summary;
}

function resetMeeting() {
  meetingAudio = null;
  document.getElementById('meetingResult').classList.remove('visible');
  document.getElementById('meetingGenBtn').disabled = true;
  document.getElementById('meetingTimer').textContent = '00:00';
  document.getElementById('meetingTimer').classList.remove('visible');
  document.getElementById('meetingStatus').textContent = 'Press to record';
  document.getElementById('meetingTitle').value = '';
}

function resetCall() {
  callAudio = null;
  document.getElementById('callResult').classList.remove('visible');
  document.getElementById('callGenBtn').disabled = true;
  document.getElementById('callTimer').textContent = '00:00';
  document.getElementById('callTimer').classList.remove('visible');
  document.getElementById('callStatus').textContent = 'Press to record';
  document.getElementById('callWith').value = '';
  document.getElementById('callTopic').value = '';
}
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
