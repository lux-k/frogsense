from flask import Flask, send_from_directory, request, redirect, url_for, flash, get_flashed_messages
import json
import os
import frogsense_process
import frogsense_common
import frogsense_config
from werkzeug.middleware.proxy_fix import ProxyFix
from faster_whisper import WhisperModel
import uuid
import threading
from datetime import datetime
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

CONFIG = None

STATUS = {}

def get_uid():
    return 1

def load_schema():
    return frogsense_process.schema_load(uid=get_uid())

def load_config(file=frogsense_config.SCHEMA_FILE):
    with open(file, 'r', encoding='utf-8') as input:
        cfg = json.load(input)

    return cfg

CONFIG = load_schema()

app = Flask(__name__)
app.secret_key = "super secret key"
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_prefix=1,
    x_proto=1,
    x_host=1
)

os.makedirs(frogsense_config.RECORD_DIR, exist_ok=True)    
frogsense_common.db_setup()


def dropdown( dictionary = {}, name = "", key = "" ):
    html = f"<select name=\"{name}\">"
    for s in sorted(dictionary[key].keys()):
        html += f"<option>{s}</option>"
    html += "</select>"
    return html
    
    
def default_page(content="", title = "Home", include=True):
    global CONFIG

    html = f"<html><head><title>FrogSense v{frogsense_config.VERSION}: {title}</title>"
    html += f"<link rel=\"stylesheet\" href=\"{ url_for('assets', filename='frogsense.css') }\">"
    html += f"<link rel=\"manifest\" href=\"{ url_for('manifest') }\">"


    html += "</head><body>"

    messages = get_flashed_messages()
  
    if messages:
        html += f"<div class=\"toast\" id=\"toast\">"
        for m in messages:
            html += f"{m}<br>"
        html += "</div>"
        html += """
    <script>
    setTimeout(() => {{
        const t = document.getElementById("toast");
        if (t) t.style.display = "none";
    }}, 5000);
    </script>    
    """

    html +="<div style=\"width: 100%; margin-bottom: 20px; text-align: center;\">"
    html += f"<a href=\"{ url_for('index') }\"><img style=\" border-radius: 20px;\" src=\"web_assets/frogsense_logo_small2.png\"></a></div><br>"
    html += content

    if include:
        html += "<div class=\"maingrid\">"
        html += "<div class=\"maincard\"><h1>Recent Observations</h1><div id=\"recent\"></div></div>"

        html += f"<div class=\"maincard\"><h1>Capture Observations</h1><ul><form method=\"POST\" action=\"{ url_for('record_text') }\">"
        html += "<h2>Text</h2><ul>"
        html += "<input name=\"input\"> "
        html += "<button type=\"submit\">Capture</button></form></ul>"
        html += "<h2>Audio</h2><ul>"
        html += "<button type=\"button\" class=\"foo\" id=\"recordBtn\">Record</button> <button type=\"button\" id=\"stopBtn\" disabled>Stop</button><br><audio id=\"playback\"></audio></ul></ul>"
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

async function updateObservation(id, m) {
    try {
        const res = await fetch("observation_update", {
              method: "POST",
              headers: {
                "Content-Type": "application/json"
              },
              body: JSON.stringify({ id: id, field: m, value: document.getElementById(id + "_" + m).value})
            });
        console.log(res); // Process data
        await loadRecent();
    } catch (error) {
        console.error(error); // Handle errors
    }  
}

async function loadRecent() {
  const res = await fetch("observations_recent");
  const data = await res.json();

  const container = document.getElementById("recent");
  container.innerHTML = "";

  data.forEach(entry => {
    const div = document.createElement("div");
    var r = ""
    if (entry.icon != null)
        r += `${entry.icon} ${entry.formatted} `

    div.className = "entry";
    div.innerHTML = `
      <div>
    <a href="#" onclick="deleteObservation('${entry.id}')">🗑️</a> 
    🕒 <form style="display: inline" onSubmit="updateObservation('${entry.id}', 'ts'); return false"><input onfocus="this.dataset.original=this.value" onblur="if (this.value !== this.dataset.original) this.form.requestSubmit()" style="display: inline" type="datetime-local" id="${entry.id}_ts" value="${entry.timestamp}"></form>
      &#128211; ${entry.subject}
      ${r}
<span class="raw-observation">
    <input type="checkbox" id="${entry.id}_message_cb" class="raw-toggle">
    <label for="${entry.id}_message_cb">💬</label>
    <form class="raw-input" id="style="display: inline" onSubmit="updateObservation('${entry.id}', 'message'); return false"><input id="${entry.id}_message" value="${entry.message}"></form>
</span>      



      
      </div>
    `;
    // 
    container.appendChild(div);
  });
}

async function deleteObservation(id) {
    if (!confirm("Really delete this observation?"))
        return;

    const response = await fetch(`/api/observation/${id}`, {
        method: "DELETE"
    });

    await loadRecent();
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
        html += "Subject " + subject_dropdown() + " for "
        html += "signal " + dropdown(CONFIG, "signal", "signals") + " "
        html += "<button type=\"submit\">Search</button></form></div>"

        html += "<div class=\"maincard\">"
        html += f"<h1>Dashboard</h1>"
        html += render_dashboard() + "</div>"

        html += ai_card()

    html += "<br><center><div style=\"width: 100%; margin-bottom: 20px;\">"
    html += f"FrogSense by <a href=\"mailto:kevin@turtlepond.us\">Kevin Lux</a>; Settings <a href=\"setup\">&#x2699;</a>; Github <a href=\"https://github.com/lux-k/frogsense\"><img height=\"15\" width=\"15\" src=\"web_assets/github.svg\"></a>; <a href=\"https://turtlepond.us\">TurtlePond.us</a><br>"
    html += "</div></center>"
    html += "</body></html>"


    
    return html

def ai_card():
    html = ""
    html += "<div class=\"maincard\">"
    html += f"<h1>AI Analysis</h1><ul><form method=\"POST\" action=\"{ url_for('ai_analyze') }\">"
    html += "Subject " + subject_dropdown() + "<br><br>"
    html += "Question<br><input name=\"question\"><br>(leave blank for analysis)<br><br>"
    html += "<button type=\"submit\">Analyze</button></form></div>"
    html += "</ul></div>"
    html += "</div>"
    
    return html    
    
@app.route("/")
def index():
    print(request.url)
    html = default_page()
    return html

@app.route("/setup", methods=["GET"])
def setup():
    global CONFIG
    long_size = 75
    html = ""
    html += "<h1>Setup FrogSense</h1>"
    html += "<ul>"
    html += "<h2>Observation Schema</h2>"
    html += f"<form action=\"{ url_for('setup_save') }\" method=\"POST\">"
    html += f"Configuration (JSON):<br><textarea cols=\"100\" rows=\"50\" name=\"config\">{ json.dumps(CONFIG, indent=4) }</textarea><br><br>"
    html += "<button type=\"submit\">Save</button>"
    html += "</form>"
    if False:
        html += "<h2>Add Subject</h2>"
        html += f"<form action=\"{ url_for('subject_add') }\" method=\"POST\">"
        html += "Name: <input name=\"name\"><br>"
        html += f"Configuration (JSON):<br><textarea cols=\"100\" rows=\"10\" name=\"config\"></textarea><br><br>"
        html += "<button type=\"submit\">Save</button>"
        html += "</form>"
    html += "<h2>Modify Subjects</h2>"
    html += f"<form action=\"{ url_for('subject_update') }\" method=\"POST\">"
    html += "Subject: " + subject_dropdown(new=True) + "<br>"
    html += """
    <script>
    document.getElementById("subject_id").addEventListener("change", async function () {
        const subjectId = this.value;

        if (!subjectId)
            return;

        const response = await fetch(`/api/subject/${subjectId}`);
        const data = await response.json();

        document.getElementById("subject_name").value = data.name ?? "";
        document.getElementById("subject_config").value = data.config ?? "";
    });
    </script>"""
    html += "Name: <input id=\"subject_name\" name=\"name\"><br>"
    html += f"Configuration (JSON):<br><textarea id=\"subject_config\" cols=\"100\" rows=\"10\" name=\"config\"></textarea><br><br>"
    html += "<button type=\"submit\">Save</button>"
    html += "</form>"

    html += "</ul>"
    return default_page(html,include=False)

def subject_dropdown(name="sid",id="subject_id",new=False):
    html = f"<select id=\"{id}\" name=\"{name}\">"
    if new:
        html += "<option value=\"0\">&lt; new &gt;</opton>"
    subjs = frogsense_process.subject_get(uid=get_uid())
    for name in sorted(subjs["name_idx"]):
        html += f"<option value=\"{subjs['name_idx'][name]}\">{name}</option>"
    html += "</select>"
    return html
    
@app.route("/api/subject/<int:subject_id>")
def get_subject(subject_id):
    subjs = frogsense_process.subject_get(uid=get_uid())

    if subject_id in subjs["id"]:
        return {"name": subjs["id"][subject_id]["name"], "config": json.dumps(subjs["id"][subject_id]["config"], indent=4)}
    else:
        return {}


@app.route("/api/observation/<oid>", methods=["DELETE"])
def delete_observation(oid):
    # verify ownership, then delete
    frogsense_process.observation_delete(uid=get_uid(),id=oid)

    return "", 204

@app.route("/setup_save", methods=["POST"])
def setup_save():
    config = request.form["config"]
    frogsense_process.schema_save(uid=get_uid(),schema=config)

    return redirect(url_for("index"))

@app.route("/subject_update", methods=["POST"])
def subject_update():
    config = request.form["config"]
    name = request.form["name"]
    sid = int(request.form["sid"])
    frogsense_process.subject_save(uid=get_uid(),sid=sid,name=name,config=config)
    flash('Updated subjects')
    return redirect(url_for("setup"))

@app.route("/record_text", methods=["POST"])
def record_text():
    global CONFIG
    input = request.form["input"]
    frogsense_process.process(input=input, uid=get_uid(), cfg=CONFIG, subjects=frogsense_process.subject_get(uid=get_uid()))
    return default_page("Your message was recorded.")

@app.route("/search", methods=["POST"])
def search():
    sid = int(request.form["sid"])
    sign = request.form["signal"]
    
    results = frogsense_process.observation_load(uid=get_uid(),sid=sid)
    #results = frogsense_process.search(subject=subj, signal=sign)

    html = f"<h1>Results</h1>Searching for subject {str(sid)} and signal {sign}:<br><br>"
    for l in results:
        if  "type" in l["signals"][0] and l["signals"][0]["type"] == sign:
            html += l["timestamp"] + ": " + l["subject"] + " " + format_signal( l["signals"][0] )[0] + " (Original message: " + l["input_raw"] + ")<br>"

    return default_page(html)

@app.route("/ai_analyze", methods=["POST"])
def ai_analyze():
    sid = int(request.form["sid"])
    question = request.form["question"]
    
    results = frogsense_process.ai_summary(uid=get_uid(),sid=sid,question=question)
    #results = frogsense_process.search(subject=subj, signal=sign)

    html = f"<h1>AI Results</h1>" + results
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
    print(f"Transcoding to {wav_file}")
    os.system(f"ffmpeg -i {tmp_file} -ar 16000 -ac 1 {wav_file}")
    frogsense_common.delete_file(tmp_file)
    
    text = transcribe(wav_file)
    resp = frogsense_process.process(input=text, uid=get_uid(), cfg=CONFIG, subjects=frogsense_process.subject_get(uid=get_uid()))
    #resp = frogsense_process.process(input=text, cfg=CONFIG, tracking_id=my_id)
    
    if len(resp["signals"]) == 1 and "type" in resp["signals"][0]:
        STATUS[my_id] = {"status": "done", "text": f"; {text}<br>&#129504; Signal " + resp["signals"][0]["type"]}
    else:
        STATUS[my_id] = {"status": "done", "text": f"&#128066; {text}"}

@app.route("/record_audio", methods=["POST"])
def record_audio():
    global STATUS
    
    file = request.files["audio"]
    
    my_id = str(uuid.uuid4())
    tmp_file = "/tmp/" + my_id
    file.save(tmp_file)
    
    wav_file = os.path.join(frogsense_config.RECORD_DIR, my_id + ".wav")
    
    STATUS[my_id] = {"status": "processing"}
    
    proc = threading.Thread(target=process_audio, args=(my_id, tmp_file, wav_file), daemon=True)
    proc.start()
    return {"id": my_id, "status": "processing"}

@app.route("/observation_update", methods=["POST"])
def observation_update():
    data = request.get_json()
    global CONFIG
 
    value = data["value"]
    field = data["field"]
    my_id = data["id"]
    
    if field == "message":
        frogsense_process.process(input=value, uid=get_uid(), ts=None, cfg=CONFIG, subjects=frogsense_process.subject_get(uid=get_uid()), id=my_id)
    elif field == "ts":
        frogsense_process.observation_update_ts(uid=get_uid(), id=my_id, ts=value)

    #frogsense_process.observation_save(tracking_id=my_id,new_record=frogsense_process.process(uid=get_uid(),input=input,cfg=CONFIG,write=True))
    return {"ok": True}

@app.route("/observations_recent")
def observations_recent():
    global CONFIG
    results = []
    
    src = frogsense_process.observation_load(uid=get_uid(),limit=10)
    for l in src:
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
                    fmt_dict = l["signals"][0]
                    
                    icon = CONFIG["signals"][signal]["formatter"]["icon"]

                    if "modifiers" in l["signals"][0]:
                        fmt_dict["modifiers"] = ",".join(l["signals"][0]["modifiers"])
                        
                    fmt = CONFIG["signals"][signal]["formatter"]["message"]
                    formatted = fmt.format_map(frogsense_common.SafeDict(fmt_dict))
                

            message = l["input_raw"]
            if "input_corrected" in l:
                message = l["input_corrected"]
                    
            results.append( {"id": l["id"], "timestamp": l["timestamp"], "subject": subj, "signal": signal, "message": message, "formatted": formatted, "icon": icon} )
    
    return results

def format_signal(signal):
    global CONFIG

    if "formatter" in CONFIG["signals"][signal["type"]]:
        fmt_dict = signal
        icon = CONFIG["signals"][signal["type"]]["formatter"]["icon"]

        if "modifiers" in signal:
            fmt_dict["modifiers"] = ",".join(signal["modifiers"])
            
        fmt = CONFIG["signals"][signal["type"]]["formatter"]["message"]

        formatted = fmt.format_map(frogsense_common.SafeDict(fmt_dict))

    return formatted, icon


def enricher_last_present(sid=None, signal = None, required_modifiers = None):
    #res = frogsense_process.search(subject = subject, signal = signal, required_modifiers = required_modifiers, reverse = True, limit = 1)
    res = frogsense_process.observation_load(uid=get_uid(), sid=sid, signal=signal, limit=1)
    
    found_signal = None
    if res is not None and len(res) > 0:
        found_signal = res[0]

    if found_signal is not None:
        #int(datetime.now(timezone.utc).timestamp())
        #date_obj = datetime.strptime(found_signal["timestamp"][:19], "%Y-%m-%dT%H:%M:%S")
        #diff = datetime.now() - date_obj
        diff = int(datetime.now(timezone.utc).timestamp()) - found_signal["timestamp_int"]
        hours = int(diff / 3600)
        return(f"{hours} hours ago")
    else:
        return "?"

def enricher_delta(sid=None, signal = None, field = None, required_modifiers = None):    
#    res = frogsense_process.search(subject = subject, signal = signal, required_modifiers = required_modifiers, reverse = True, limit = 2)
    res = frogsense_process.observation_load(uid=get_uid(), sid=sid, signal=signal, limit = 2)

    if res is not None and len(res) >= 2:
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
    
    html = ""
    
    dash_map = {"last_present": enricher_last_present, "delta": enricher_delta}
    
    subjs = frogsense_process.subject_get(uid=get_uid()) 
    html += "<ul>"
    for s in sorted(subjs["name_idx"]):
        html += f"<b>{s}</b><ul>"
        for sig in CONFIG["signals"]:
            sid = subjs["name_idx"][s]
            res = frogsense_process.observation_load(uid=get_uid(), sid=sid, signal=sig, limit=1)

            if res is not None and len(res) > 0:
                formatted, icon = format_signal( res[0]["signals"][0] )
                html += f"{icon} {formatted}"
                if "enrichers" in CONFIG["signals"][sig]:
                    for e in CONFIG["signals"][sig]["enrichers"]:
                        if e["function"] in dash_map:
                            conf = e.copy()
                            del conf["function"]
                            #conf["subject"] = s
                            conf["sid"] = sid
                            conf["signal"] = sig
                            if "required_modifiers" in e:
                                conf["required_modifiers"] = e["required_modifiers"]
                            else:
                                conf["required_modifiers"] = None

                            res = dash_map[e["function"]](**conf)
                            if len(res) > 0:
                                html += " - " + res
                        
                html += "<br>"
            
        
        html += "</ul>"
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

