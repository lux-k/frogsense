from flask import Flask, send_from_directory, request, redirect, url_for, flash, get_flashed_messages, send_file
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
import turtlepond.storage
import turtlepond.html
from werkzeug.datastructures import FileStorage

CONFIG = None

STATUS = {}

TZ = os.getenv("TZ", frogsense_process.get_server_tz())

def get_uid():
    return 1

def get_tz():
    global TZ
    return TZ

def load_schema():
    return frogsense_process.schema_load(uid=get_uid())

def load_config(file=frogsense_config.SCHEMA_FILE):
    with open(file, 'r', encoding='utf-8') as input:
        cfg = json.load(input)

    return cfg

model = WhisperModel("base")  # or "small", "medium"

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


def dropdown( dictionary = {}, name = "", key = "", must_have=None ):
    html = f"<select name=\"{name}\">"
    for s in sorted(dictionary[key].keys()):
        if must_have == None or must_have in dictionary[key][s]:
            html += f"<option>{s}</option>"
    html += "</select>"
    return html
    
    
def default_page(content="", title = "Home", include=True):
    global CONFIG

    html = f"<html><head><title>FrogSense v{frogsense_config.VERSION}: {title}</title>"
    html += f"<link rel=\"stylesheet\" href=\"{ url_for('assets', filename='frogsense.css') }\">"
    html += f"<link rel=\"apple-touch-icon\" sizes=\"180x180\" href=\"{request.script_root}/web_assets/icons/apple-touch-icon.png\">"
    html += f"<link rel=\"icon\" type=\"image/png\" sizes=\"32x32\" href=\"{request.script_root}/web_assets/icons/favicon-32x32.png\">"
    html += f"<link rel=\"icon\" type=\"image/png\" sizes=\"16x16\" href=\"{request.script_root}/web_assets/icons/favicon-16x16.png\">"
    html += f"<link rel=\"manifest\" href=\"{ url_for('manifest') }\">"


    html += "</head><body>"

    messages = get_flashed_messages()
    html += f"<div id=\"toast\""
    if messages:
        html += ">"
        for m in messages:
            html += f"{m}<br>"
    else:
        html += " style=\"display: none\">"
    html += "</div>"

    html += """
    """

    html += f"<script> const BASEURL = '{request.script_root}'; </script>"
    html += f'<script src="{request.script_root}/web_assets/frogsense.js" defer></script>'
    html += """
<dialog id="attachments">
    <h2>Observation Attachments</h2>
    <ul><span id="attachment_observation_text"></span>
    
    <h3>Current attachments</h3>
    <ul><span id="attachment_list"></span></ul>
    <h3>Upload New</h3>
    <form>
    <input type="hidden" id="attachment_observation_id" name="observation_id">
    <input type="file" id="attachment_file" capture="environment">
    <button type="button" onclick="uploadAttachment()">Upload</button>
    </form>
    </ul>
    <br><br><center>
    <button type="button" onclick="this.closest('dialog').close()">Close</button>
    </center>
</dialog>

 """    

    html +="<div style=\"width: 100%; margin-bottom: 20px; text-align: center;\">"
    html += f"<a href=\"{ url_for('index') }\"><img style=\" border-radius: 20px;\" src=\"{request.script_root}/web_assets/frogsense_logo_small2.png\"></a></div><br>"
    html += content

    if include:
        html += "<div class=\"maingrid\">"
        html += "<div class=\"maincard\"><h1>Recent Observations</h1><div id=\"recent\"></div></div>"

        html += f"<div class=\"maincard\"><h1>Capture Observations</h1><ul><form method=\"POST\" action=\"{ url_for('observation_create') }\">"
        html += "<h2>Text</h2><ul>"
        html += "<input type=\"hidden\" name=\"type\" value=\"text\"><input name=\"input\"> "
        html += "<button type=\"submit\">Capture</button></form></ul>"
        html += "<h2>Audio</h2><ul>"
        html += "<button type=\"button\" class=\"foo\" id=\"recordBtn\">Record</button> <button type=\"button\" id=\"stopBtn\" disabled>Stop</button><br><audio id=\"playback\"></audio></ul>"
        html += "<h2>Picture</h2><ul>"
        html += f"<form method=\"POST\" enctype=\"multipart/form-data\" action=\"{url_for('observation_create')}\"><input type=\"hidden\" name=\"type\" value=\"picture\">"
        html += "Subject " + subject_dropdown()  + " for signal "
        html +=  dropdown(CONFIG, "signal", "signals", "llm_prompt")  + "<br>"
        html += "<input name=\"file\" type=\"file\" capture=\"environment\" accept=\"image/*\"><button>Upload</button>"
        html += "</form></ul>"
        html += "</ul>"
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
    html += f"FrogSense by <a href=\"mailto:kevin@turtlepond.us\">Kevin Lux</a>; Settings <a href=\"{request.script_root}/setup\">&#x2699;</a>; Github <a href=\"https://github.com/lux-k/frogsense\"><img height=\"15\" width=\"15\" src=\"{request.script_root}/web_assets/github.svg\"></a>; <a href=\"https://turtlepond.us\">TurtlePond.us</a><br>"
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
    
    backend = next(iter(frogsense_config.STORAGE_CFG))
    values = dict(frogsense_config.STORAGE_CFG[backend])
    values["backend"] = backend
    html += setup_storage_form(values)
    
    html += setup_subjects_form()

    html += "</ul>"
    return default_page(html,include=False)


def setup_subjects_form(values={}, errors={}):
    global CONFIG
    html = ""
    html += "<h2>Modify Subjects</h2>"
    html += "<div class=\"config-form\">"
    html += f"<form action=\"{ url_for('subject_update') }\" method=\"POST\">"
    html += "Subject: " + subject_dropdown(new=True) + "<br>"
    html += """
    <script>
    document.getElementById("subject_id").addEventListener("change", async function () {
        const subjectId = this.value;

        if (!subjectId)
            return;
"""
    html += f"const response = await fetch(`{request.script_root}/api/subject/${{subjectId}}`)";
    html += """
        const data = await response.json();

        document.getElementById("subject_name").value = data.name ?? "";
        document.getElementById("subject_config").value = data.config ?? "";
    });
    </script>"""
    html += "Name: <input id=\"subject_name\" name=\"name\"><br>"
    html += f"Configuration (JSON):<br><textarea id=\"subject_config\" cols=\"100\" rows=\"10\" name=\"config\"></textarea><br><br>"
    html += "<button type=\"submit\">Save</button>"
    html += "</form></div>"

    return html
    
def setup_storage_form(values={}, errors={}):
    html = ""
    html += "<h2>Storage Setup</h2>"
    html += "<div class=\"config-form\">"
    html += f"<form action=\"{ url_for('storage_save') }\" method=\"POST\">"
    
    options = []
    divs = ""
    for key, value in turtlepond.storage.types().items():
        options.append( {"name": value["name"], "value": key} )
        divs += f"<div id=\"storage_{key}_div\">" + turtlepond.html.render_fields(turtlepond.storage.configuration(key),values,errors) + "</div>"

    html += turtlepond.html.render_fields(  {           "backend": {
                "type": "select",
                "label": "Backend",
                "required": True,
                "options": options,
                "onchange": "switchStorageBackend();"
            }},values,errors) + divs


    html += f'<script>function switchStorageBackend() {{ const type = document.getElementById("backend").value; document.getElementById("storage_fs_div").hidden = type !== "fs";  document.getElementById("storage_s3_div").hidden = type !== "s3" }} switchStorageBackend()</script>'
    html += "<br><button type=\"submit\">Save</button>"
    html += "</form></div>"
    return html

@app.route("/storage_save", methods=["POST"])
def storage_save():
    input_vals = request.form.to_dict()
    
    if request.form["backend"] == next(iter(frogsense_config.STORAGE_CFG)):
        for name, field in turtlepond.storage.configuration(request.form["backend"]).items():
            if (
                field["type"] == "password"
                and not input_vals.get(name)
                and name in frogsense_config.STORAGE_CFG[ request.form["backend"] ]
            ):
                input_vals[name] = frogsense_config.STORAGE_CFG[ request.form["backend"] ][name]
                
    values, errors = turtlepond.html.validate_fields(fields=turtlepond.storage.configuration(request.form["backend"]), values=input_vals)
    
    if errors:
        values["backend"] = input_vals["backend"]
        return default_page(setup_storage_form(values,errors),include=False)
    else:
        conf = {request.form["backend"]: values}
        flash("Configuration saved")
        frogsense_config.save_config_value('FROGSENSE_STORAGE_CFG', json.dumps(conf))
        frogsense_config.reload()
        return redirect(url_for("index"))
    
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
def subject_get(subject_id):
    subjs = frogsense_process.subject_get(uid=get_uid())

    if subject_id in subjs["id"]:
        return {"name": subjs["id"][subject_id]["name"], "config": json.dumps(subjs["id"][subject_id]["config"], indent=4)}
    else:
        return {}

@app.route("/subject_update", methods=["POST"])
def subject_update():
    config = request.form["config"]
    name = request.form["name"]
    sid = int(request.form["sid"])
    try:
        json.loads(config)
    except Exception as e:
        flash('Bad JSON')
    else:
        frogsense_process.subject_save(uid=get_uid(),sid=sid,name=name,config=config)
        flash('Updated subjects')
    return redirect(url_for("setup"))

@app.route("/api/observation/<oid>/attachments", methods=["POST"])
def attachment_add(oid):
    file = request.files["file"]

    frogsense_process.attachment_add(uid=get_uid(),oid=oid, file=file)

    return "", 204

@app.route("/api/observation/<oid>/attachments", methods=["GET"])
def attachment_list(oid):
    return frogsense_process.attachment_list(uid=get_uid(),oid=oid)

@app.route("/api/observation/<oid>/attachment/<aid>", methods=["GET"])
def attachment_get(oid, aid):
    attachment = frogsense_process.attachment_get(uid=get_uid(),oid=oid,aid=aid)
    
    stream = frogsense_config.STORAGE.open(frogsense_process.attachment_path(aid))

    return send_file(
        stream,
        mimetype=attachment["mime_type"],
        download_name=attachment["name"]
    )
    
    return frogsense_process.attachment_list(uid=get_uid(),oid=oid)

@app.route("/api/observation/<oid>/attachment/<aid>", methods=["DELETE"])
def attachment_delete(oid, aid):
    attachment = frogsense_process.attachment_delete(uid=get_uid(),oid=oid,aid=aid)
    return "", 410
    

@app.route("/setup_save", methods=["POST"])
def setup_save():
    config = request.form["config"]
    try:
        json.loads(config)
    except Exception as e:
        flash("Bad JSON")
    else:
        flash("Config saved")
        frogsense_process.schema_save(uid=get_uid(),schema=config)

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
    
    results = frogsense_process.observation_load(uid=get_uid(),sid=sid,tz=get_tz())
    #results = frogsense_process.search(subject=subj, signal=sign)

    html = f"<h1>Results</h1>Searching for subject {str(sid)} and signal {sign}:<br><br>"
    for l in results:
        if  "signals" in l and l["signals"] is not None and len(l["signals"]) > 0 and "type" in l["signals"][0] and l["signals"][0]["type"] == sign:
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
    if "id" in resp:
        frogsense_process.attachment_add(uid=get_uid(),oid=resp["id"],file=FileStorage(stream=open(wav_file, "rb"),
                        filename="audio.wav",
                        content_type="audio/wave"))

    frogsense_common.delete_file(wav_file)

    if len(resp["signals"]) == 1 and "type" in resp["signals"][0]:
        STATUS[my_id] = {"status": "done", "text": f"; {text}<br>&#129504; Signal " + resp["signals"][0]["type"]}
    else:
        STATUS[my_id] = {"status": "done", "text": f"&#128066; {text}"}

@app.route("/api/observation", methods=["POST"])
def observation_create():
    global CONFIG
    global STATUS

    type = request.form["type"]

    if type == "picture":
        file = request.files["file"]
        sid = request.form["sid"]
        signal = request.form["signal"]

        if frogsense_process.observation_from_picture(uid=get_uid,sid=sid,signal=signal,cfg=CONFIG,picture=file):
            return default_page("Your picture was recorded.")
        else:
            return default_page("Your picture couldn't be understood.")
    elif type == "text":
        input = request.form["input"]
        frogsense_process.process(input=input, uid=get_uid(), cfg=CONFIG, subjects=frogsense_process.subject_get(uid=get_uid()))
        return default_page("Your message was recorded.")        
    elif type == "audio":
        file = request.files["audio"]
        
        my_id = str(uuid.uuid4())
        tmp_file = "/tmp/" + my_id
        file.save(tmp_file)
        
        wav_file = os.path.join(frogsense_config.RECORD_DIR, my_id + ".wav")
        
        STATUS[my_id] = {"status": "processing"}
        
        proc = threading.Thread(target=process_audio, args=(my_id, tmp_file, wav_file), daemon=True)
        proc.start()
        return {"id": my_id, "status": "processing"}        

@app.route("/api/observation/<oid>", methods=["DELETE"])
def observation_delete(oid):
    # verify ownership, then delete
    frogsense_process.observation_delete(uid=get_uid(),id=oid)

    return "", 204

@app.route("/api/observation/<oid>", methods=["PATCH"])
def observation_update(oid):
    data = request.get_json()
    global CONFIG
 
    value = data["value"]
    field = data["field"]
    my_id = oid
    
    if field == "message":
        frogsense_process.process(input=value, uid=get_uid(), ts=None, cfg=CONFIG, subjects=frogsense_process.subject_get(uid=get_uid()), id=my_id)
    elif field == "ts":
        frogsense_process.observation_update_ts(uid=get_uid(), id=my_id, ts=value, tz=get_tz())

    return {"ok": True}

@app.route("/api/observations/recent")
def observations_recent():
    global CONFIG
    results = []
    
    src = frogsense_process.observation_load(uid=get_uid(),limit=10,tz=get_tz())
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
    res = frogsense_process.observation_load(uid=get_uid(), sid=sid, signal=signal, limit=1,tz=get_tz())
    
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
    res = frogsense_process.observation_load(uid=get_uid(), sid=sid, signal=signal, limit = 2,tz=get_tz())

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
            res = frogsense_process.observation_load(uid=get_uid(), sid=sid, signal=sig, limit=1,tz=get_tz())

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