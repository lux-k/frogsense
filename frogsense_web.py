from flask import Flask, send_from_directory, request, redirect, url_for, flash, get_flashed_messages
import json
import os
import frogsense_process
import frogsense_common
from werkzeug.middleware.proxy_fix import ProxyFix
from faster_whisper import WhisperModel
import uuid
import threading
from safedict import SafeDict
from datetime import datetime
from pathlib import Path

CONFIG_FILE = "config.json"
OUTPUT_FILE = "output.json"
RECORD_DIR = "recordings"

# docker envs default to /data otherwise expect a directory in path
if Path("/.dockerenv").exists():
    CONFIG_FILE = "/data/config.json"
    OUTPUT_FILE = "/data/output.json"
    RECORD_DIR = "/data/recordings"

CONFIG = None

STATUS = {}

def load_config(file=CONFIG_FILE):
    with open(file, 'r', encoding='utf-8') as input:
        cfg = json.load(input)

    return cfg

CONFIG = load_config()

app = Flask(__name__)
app.secret_key = "super secret key"
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_prefix=1,
    x_proto=1,
    x_host=1
)
os.makedirs(RECORD_DIR, exist_ok=True)    

def dropdown( dictionary = {}, name = "", key = "" ):
    html = f"<select name=\"{name}\">"
    for s in sorted(dictionary[key].keys()):
        html += f"<option>{s}</option>"
    html += "</select>"
    return html
    
    
def default_page(content="", title = "Home"):
    global CONFIG

    html = f"<html><head><title>FrogSense {title}</title>"
    html += f"<link rel=\"stylesheet\" href=\"{ url_for('assets', filename='frogsense.css') }\">"
    html += f"<link rel=\"manifest\" href=\"{ url_for('manifest') }\">"

    html += """
<script>
setTimeout(() => {{
    const t = document.getElementById("toast");
    if (t) t.style.display = "none";
}}, 5000);
</script>    
"""
    html += "</head><body>"

    messages = get_flashed_messages()
  
    if messages:
        html += f"<div class=\"toast\">"
        for m in messages:
            html += f"{m}<br>"
        html += "</div>"

    
    html +="<div style=\"width: 100%; margin-bottom: 20px; text-align: center;\">"
    html += f"<a href=\"{ url_for('index') }\"><img style=\" border-radius: 20px;\" src=\"web_assets/frogsense_logo_small2.png\"></a></div><br>"
    html += content

    html += "<div class=\"maingrid\">"
    html += "<div class=\"maincard\"><h1>Recent Observations</h1><div id=\"recent\"></div></div>"

    html += f"<div class=\"maincard\"><h1>Capture Text</h1><form method=\"POST\" action=\"{ url_for('record_text') }\">"
    html += "Message: <input name=\"input\"><br>"
    html += "<button type=\"submit\">Capture</button></form>"
    html += "<h1>Capture Audio</h1>"
    html += "<button type=\"button\" id=\"recordBtn\">Record</button> <button type=\"button\" id=\"stopBtn\" disabled>Stop</button><br><audio id=\"playback\"></audio>"
    html += """
<script>
let mediaRecorder;
let audioChunks = [];

const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");

recordBtn.onclick = async () => {

  try {
     const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
     console.log("Mic access granted");
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];

      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunks, { type: "audio/webm" });
        const audioURL = URL.createObjectURL(blob);
        document.getElementById("playback").src = audioURL;

        uploadAudio(blob);
      };

      mediaRecorder.start();
      recordBtn.disabled = true;
      stopBtn.disabled = false;

  } catch (err) {
    console.error("Mic error:", err);
    alert(`${err.name}: ${err.message}`);
  }

};

stopBtn.onclick = () => {
  mediaRecorder.stop();
  recordBtn.disabled = false;
  stopBtn.disabled = true;
};

async function uploadAudio(blob) {
  const formData = new FormData();
  formData.append("audio", blob, "recording.webm");

  const response = await fetch("record_audio", {
    method: "POST",
    body: formData
  });

  const { id } = await response.json()
  poll(id)  
}

async function poll(id) {
  const res = await fetch(`status/${id}`);
  const data = await res.json();

  if (data.status === "done") {
    showToast(data.text);
    loadRecent()
  } else {
    setTimeout(() => poll(id), 1000);
  }
}

function showToast(text) {
  const div = document.createElement("div");
  div.className = "toast";
  div.innerHTML = text;
  document.body.appendChild(div);

  setTimeout(() => div.remove(), 5000);
}

async function updateEntry(id, m) {
    try {
        const res = await fetch("update", {
              method: "POST",
              headers: {
                "Content-Type": "application/json"
              },
              body: JSON.stringify({ id: id, message: document.getElementById(id + "_message").value})
            });
        console.log(res); // Process data
        await loadRecent();
    } catch (error) {
        console.error(error); // Handle errors
    }  
}

async function loadRecent() {
  const res = await fetch("recent");
  const data = await res.json();

  const container = document.getElementById("recent");
  container.innerHTML = "";

  data.forEach(entry => {
    const div = document.createElement("div");
    div.className = "entry";
    div.innerHTML = `
      <div>🕒 ${entry.timestamp}
      &#128211; ${entry.subject}
      ${entry.icon} ${entry.formatted} 
      &#128064; <form style="display: inline" onSubmit="updateEntry('${entry.id}', this); return false"><input id="${entry.id}_message" name="foo" value="${entry.message}"></form></div>
    `;
    container.appendChild(div);
  });
}

loadRecent();

if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register(
"""
    html += f"     '{request.script_root}/web_assets/sw.js'"
    html += """
    )
    .then(reg => console.log('SW registered', reg))
    .catch(err => console.error('SW registration failed', err));
}

</script>
"""    

    html += "</div>"
    html += "<div class=\"maincard\">"
    html += f"<h1>Search</h1><form method=\"POST\" action=\"{ url_for('search') }\">"
    html += "Subject: " + dropdown(CONFIG, "subject", "subjects") + "<br>"
    html += "Signal: " + dropdown(CONFIG, "signal", "signals") + "<br>"
    html += "<button type=\"submit\">Search</button></form></div>"

    html += "<div class=\"maincard\">"
    html += f"<h1>Dashboard</h1>"
    html += render_dashboard() + "</div>"
    html += "</div>"

    html += "<br><center><div style=\"width: 100%; margin-bottom: 20px;\">"
    html += f"FrogSense by <a href=\"mailto:kevin@turtlepond.us\">Kevin Lux</a>; Settings <a href=\"setup\">&#x2699;</a>; Github <a href=\"https://github.com/lux-k/frogsense\"><img height=\"15\" width=\"15\" src=\"web_assets/github.svg\"></a>; <a href=\"https://turtlepond.us\">TurtlePond.us</a><br>"
    html += "</div></center>"
    html += "</body></html>"


    
    return html
    
@app.route("/")
def index():
    print(request.url)
    html = default_page()
    return html

@app.route("/record_text", methods=["POST"])
def record_text():
    global OUTPUT_FILE
    global CONFIG
    input = request.form["input"]
    frogsense_process.process(input=input, cfg=CONFIG, output_file=OUTPUT_FILE, tracking_id=str(uuid.uuid4()))
    return default_page("Your message was recorded.")

@app.route("/search", methods=["POST"])
def search():
    global OUTPUT_FILE
    subj = request.form["subject"]
    sign = request.form["signal"]
    
    results = frogsense_process.search( subject=subj, signal=sign, data_file=OUTPUT_FILE )

    html = f"<h1>Results</h1>Searching for subject {subj} and signal {sign}:<br><br>"
    for l in results:
        if l["subject"] == subj and l["signals"][0]["type"] == sign:
            html += l["timestamp"] + ": " + l["subject"] + " " + format_response( l["signals"][0] ) + " (Original message: " + l["input_raw"] + ")<br>"

    return default_page(html)
    
def format_response( signal ):
    if signal["type"] == "bm":
        if "unknown" in signal["modifiers"]:
            return "Might have pooped"
        elif "present" in signal["modifiers"]:
            return "Did poop"
        else:
            return "Didn't poop"
    elif signal["type"] == "weight":
        return "Weighed " + str(signal["weight"]) + " " + signal["weight_unit"]
    elif signal["type"] == "consumed":
        return "Ate " + str(signal["quantity"]) + " " + signal["food_type"]
    
    return "n/a"
    
@app.route("/web_assets/<path:filename>")
def assets(filename):
    return send_from_directory("web_assets", filename)

model = WhisperModel("base")  # or "small", "medium"

def transcribe(path):
    segments, _ = model.transcribe(path)
    text = (" ".join([seg.text for seg in segments])).lstrip()
    return text

@app.route("/status/<id>")
def get_status(id):
    global STATUS
    if id in STATUS:
        return STATUS[id]
    return {"status": "unknown"}

def process_audio(my_id, tmp_file, wav_file):
    global CONFIG
    global OUTPUT_FILE
    print(f"Transcoding to {wav_file}")
    os.system(f"ffmpeg -i {tmp_file} -ar 16000 -ac 1 {wav_file}")
    frogsense_common.delete_file(tmp_file)
    
    text = transcribe(wav_file)
    resp = frogsense_process.process(input=text, cfg=CONFIG, output_file=OUTPUT_FILE, tracking_id=my_id)
    
    if len(resp["signals"]) == 1 and "type" in resp["signals"][0]:
        STATUS[my_id] = {"status": "done", "text": f"; {text}<br>&#129504; Signal " + resp["signals"][0]["type"]}
    else:
        STATUS[my_id] = {"status": "done", "text": f"&#128066; {text}"}

@app.route("/record_audio", methods=["POST"])
def record_audio():
    global RECORD_DIR
    global STATUS
    
    file = request.files["audio"]
    
    my_id = str(uuid.uuid4())
    tmp_file = "/tmp/" + my_id
    file.save(tmp_file)
    
    wav_file = os.path.join(RECORD_DIR, my_id + ".wav")
    
    STATUS[my_id] = {"status": "processing"}
    
    proc = threading.Thread(target=process_audio, args=(my_id, tmp_file, wav_file), daemon=True)
    proc.start()
    return {"id": my_id, "status": "processing"}

@app.route("/update", methods=["POST"])
def update():
    data = request.get_json()
    global OUTPUT_FILE
    global CONFIG
    input = data["message"]
    my_id = data["id"]
    
    frogsense_process.update(data_file=OUTPUT_FILE,tracking_id=my_id,new_record=frogsense_process.process(input=input,cfg=CONFIG,write=True))
    return {"ok": "ok"}

@app.route("/recent")
def recent():
    global CONFIG
    global OUTPUT_FILE
    results = []
    
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        src = [json.loads(line) for line in f]

    while len(src) > 0 and len(results) < 5:
        l = src.pop()
        if "id" in l:
            subj = "?"
            if "subject" in l:
                subj = l["subject"]

            signal = "?"
            formatted = None
            icon = None

            if len(l["signals"]) > 0  and "type" in l["signals"][0]:
                formatted, icon = format_signal( l["signals"][0] )

                signal = l["signals"][0]["type"]
                if "formatter" in CONFIG["signals"][signal] and False:
                    #{"input_raw": "Doodle crapped.", "timestamp": "2026-04-26T22:22:54.796504", "signals": [{"type": "bm", "modifiers": ["present"]}], "subject": "Doodle", "subject_raw": "Doodle"}
                    #{"input_raw": "Doodle weighs 515 grams.", "timestamp": "2026-04-26T22:35:41.930160", "signals": [{"type": "weight", "weight": 515.0, "weight_unit": "g"}], "subject": "Doodle", "subject_raw": "Doodle", "id": "b0936ab1-d3c4-4a9e-b882-96c12440708b"}
                    fmt_dict = l["signals"][0]
                    
                    icon = CONFIG["signals"][signal]["formatter"]["icon"]

                    if "modifiers" in l["signals"][0]:
                        fmt_dict["modifiers"] = ",".join(l["signals"][0]["modifiers"])
                        
                    fmt = CONFIG["signals"][signal]["formatter"]["message"]
                    formatted = fmt.format_map(SafeDict(fmt_dict))
                

            message = l["input_raw"]
            if "input_corrected" in l:
                message = l["input_corrected"]

            
                    
            results.append( {"id": l["id"], "timestamp": l["timestamp"][:19], "subject": subj, "signal": signal, "message": message, "formatted": formatted, "icon": icon} )
    
    return results

def format_signal(signal):
    global CONFIG

    if "formatter" in CONFIG["signals"][signal["type"]]:
        fmt_dict = signal
        icon = CONFIG["signals"][signal["type"]]["formatter"]["icon"]

        if "modifiers" in signal:
            fmt_dict["modifiers"] = ",".join(signal["modifiers"])
            
        fmt = CONFIG["signals"][signal["type"]]["formatter"]["message"]
        formatted = fmt.format_map(SafeDict(fmt_dict))

    return formatted, icon


def enricher_last_present(subject=None, signal = None, required_modifiers = None):
    global OUTPUT_FILE
    res = frogsense_process.search(subject = subject, signal = signal, data_file = OUTPUT_FILE, required_modifiers = required_modifiers, reverse = True, limit = 1)
    
    found_signal = None
    if res is not None and len(res) > 0:
        found_signal = res[0]

    if found_signal is not None:
        print(found_signal)
        date_obj = datetime.strptime(found_signal["timestamp"][:19], "%Y-%m-%dT%H:%M:%S")
        diff = datetime.now() - date_obj
        hours = int(diff.total_seconds() / 3600)
        return(f"{hours} hours ago")
    else:
        return "?"

def enricher_delta(subject=None, signal = None, field = None, required_modifiers = None):    
    global OUTPUT_FILE
    res = frogsense_process.search(subject = subject, signal = signal, data_file = OUTPUT_FILE, required_modifiers = required_modifiers, reverse = True, limit = 2)
    if res is not None and len(res) == 2:
        quantity = res[0]["signals"][0][field] - res[1]["signals"][0][field]
        
        if quantity < 0:
            arrow = "&#8595;"
        elif quantity > 0:
            arrow = "&#8593;"
        elif quantity == 0:
            arrow = ""
            
        quantity = abs(quantity)
        return " (" + arrow + " " + str(quantity) + ")"
    else:
        return ""

def render_dashboard():
    global CONFIG
    global OUTPUT_FILE
    
    html = ""
    
    dash_map = {"last_present": enricher_last_present, "delta": enricher_delta}
    
    for s in CONFIG["subjects"]:
        html += f"{s}<ul>"
        for sig in CONFIG["signals"]:
            res = frogsense_process.search(subject = s, signal = sig, data_file = OUTPUT_FILE, reverse = True, limit = 1)
            print(res)
            if res is not None and len(res) > 0:
                formatted, icon = format_signal( res[0]["signals"][0] )
                html += f"{icon} {formatted}"
                if "enrichers" in CONFIG["signals"][sig]:
                    for e in CONFIG["signals"][sig]["enrichers"]:
                        if e["function"] in dash_map:
                            conf = e.copy()
                            del conf["function"]
                            conf["subject"] = s
                            conf["signal"] = sig
                            print(CONFIG["signals"][sig]["enrichers"])
                            if "required_modifiers" in e:
                                conf["required_modifiers"] = e["required_modifiers"]
                            else:
                                conf["required_modifiers"] = None

                            #format_signal(
    #                        fmt = CONFIG["signals"][signal]["formatter"]["message"]
     #                       formatted = fmt.format_map(SafeDict(fmt_dict))
                            res = dash_map[e["function"]](**conf)
                            if len(res) > 0:
                                html += " - " + res
                            html += "<br>"
            
        
        html += "</ul>"
    
    return html

@app.route("/manifest.json")
def manifest():
    return {
        "name": "FrogSense",
        "short_name": "FrogSense",
        "start_url": request.script_root + "/",
        "scope": request.script_root + "/",
        "display": "standalone",
        "theme_color": "#2d5a27",
        "background_color": "#ffffff",
        "icons": [
            {
                "src": request.script_root + "/web_assets/icons/android-chrome-192x192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": request.script_root + "/web_assets/icons/android-chrome-512x512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000)

#process("Ricky pooped", cfg=cfg)
#process("Doodle bot didn't shit", cfg=cfg)
#process("Pebbles weighs 457.6 grams", cfg=cfg)
#process("I'm not sure if Smooch pooped.", cfg=cfg)
#process("Can't find smooch poop", cfg=cfg)
#process("DB ate 5 roaches", cfg=cfg)