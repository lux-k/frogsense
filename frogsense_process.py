from datetime import datetime
import string
import json
import re
import frogsense_common
import frogsense_config
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from openai import OpenAI
import markdown
import os

def get_server_tz():
    localtime_path = '/etc/localtime'
    if os.path.islink(localtime_path):
        target = os.readlink(localtime_path)
        # Target usually looks like: /usr/share/zoneinfo/America/New_York
        if 'zoneinfo/' in target:
            return target.split('zoneinfo/')[-1]
    return None    

def get_utc_ts():
    return int(datetime.now(timezone.utc).timestamp())

def process(input="", cfg={}, uid=0, subjects={}, ts=0, output_file=frogsense_config.OUTPUT_FILE, write=True, id=None ):
    result = {"input_raw": input, "timestamp_int": ts, "signals": [], "uid": uid}

    if result["timestamp_int"] == 0:
        result["timestamp_int"] = get_utc_ts()
        
    # rewrites the time on updated text
    if id is not None:
        result["id"] = id

    input = ' ' + input + ' '

    translator = str.maketrans('', '', string.punctuation)
    input = input.translate(translator)
    input = input.lower()

    #for subject in cfg["subjects"]:
    for subj in subjects["id"]:
        #subj is the sid
        if "config" in subjects["id"][subj]:
            #has a config.. 
            if "aliases" in subjects["id"][subj]["config"]:
                for alias in subjects["id"][subj]["config"]["aliases"]:
                    if (' ' + alias + ' ').lower() in input:
                        result["subject"] = subjects["id"][subj]["name"]
                        result["subject_raw"] = alias
                        result["sid"] = subj
                        break
        if "subject" in result:
            break;
    
    for signal in cfg["signals"]:
        event = {}

        for keyword in cfg["signals"][signal]["keywords"]:
            if (' ' + keyword + ' ').lower() in input:
                event["type"] = signal
                
                #extractors
                if "extract" in cfg["signals"][signal]:
                    for e in cfg["signals"][signal]["extract"]:
                        if e["extractor"] == "number":
                            event[e["label"]] = extract_number(input)
                
                #contextualizers
                
                if "contextualizers" in cfg["signals"][signal]:
                    
                    for c in cfg["signals"][signal]["contextualizers"]:
                        found = False
                        for ctx in cfg["contextualizers"][c]:
                            for label in cfg["contextualizers"][c][ctx]:
                                if (' ' + label + ' ').lower() in input:
                                    event[c] = ctx
                                    found = True
                        if not found:
                            #check for defaults
                            if "species" in subjects["id"][ result["sid"] ]["config"]:
                                species = subjects["id"][ result["sid"] ]["config"]["species"]
                                if species in cfg["species"] and "defaults" in cfg["species"][species] and c in cfg["species"][species]["defaults"]:
                                    event[c] = cfg["species"][species]["defaults"][c]
                            
                #modifiers
                if "modifiers" in cfg["signals"][signal]:
                    for mod_group in cfg["signals"][signal]["modifiers"]:
                        # these are arrays
                        found = False
                        for m in mod_group:
                            for mod in cfg["modifiers"][m]:
                                if (' ' + mod + ' ').lower() in input:
                                    if "modifiers" not in event:
                                        event["modifiers"] = []
                                    event["modifiers"].append(m)
                                    found = True
                            if found:
                                break
                        if found:
                            break
                        


                if "default_modifiers" in cfg["signals"][signal]:
                    #"default_modifiers": [ {"modifier": "present", "unless": ["absent"]} ]
                    for dm in cfg["signals"][signal]["default_modifiers"]:
                        found = False
                        for v in dm["unless"]:
                            if "modifiers" in event and v in event["modifiers"]:
                                found = True
                        if not found:
                            if "modifiers" not in event:
                                event["modifiers"] = []
                            event["modifiers"].append(dm["modifier"])

        if "type" in event or "subject" in event:
            result["signals"].append(event)
            
        if len(result["signals"]) >= 1:
            break;
        
    if False and write:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result) + '\n')
    if write:
        observation_save( result )

    return result

def extract_number(input):
    numbers = re.findall(r'-?\d+\.?\d*', input)
    if len(numbers) > 0:
        return float(numbers[0])
    else:
        return None

#obsolete
def search(subject, signal, data_file = frogsense_config.OUTPUT_FILE, reverse = False, required_modifiers = None, limit = None):
    src = load_all(data_file)
    res = []
    for l in src:
        if "subject" in l and l["subject"] == subject and len(l["signals"]) > 0 and "type" in l["signals"][0] and l["signals"][0]["type"] == signal:
            if required_modifiers is None or len(required_modifiers) == 0:
                res.append(l)
            else:
                ok = True
                if "modifiers" in l["signals"][0] and len(l["signals"][0]["modifiers"]) > 0:
                    for mod in required_modifiers:
                        if mod not in l["signals"][0]["modifiers"]:
                            ok = False
                            break
                if ok:
                    res.append(l)
#        if limit is not None and len(res) >= limit:
#            break

    if reverse:
        res.reverse()
    
    return res

#obsolete
def load_all(data_file=frogsense_config.OUTPUT_FILE):
    results = []
    
    with open(data_file, 'r', encoding='utf-8') as f:
          results = [json.loads(line) for line in f]

    return results

#obsolete
def update(data_file=frogsense_config.OUTPUT_FILE, tracking_id = None, new_record=None):
    results = load_all(data_file)
    with open(data_file, 'w', encoding='utf-8') as f:
        for l in results:
            if "id" in l and l["id"] == tracking_id:
                if "subject" in new_record:
                    l["subject"] = new_record["subject"]
                    l["subject_raw"] = new_record["subject_raw"]
                l["signals"] = new_record["signals"]
                l["input_corrected"] = new_record["input_raw"]
            f.write(json.dumps(l) + '\n')

def schema_load(uid=0):
    db = frogsense_common.get_db()
    cur = db.cursor()
    cur.execute("select config from users where uid = ?", [uid])
    return json.loads(cur.fetchall()[0][0])

def schema_save(uid=0,schema=""):
    db = frogsense_common.get_db()
    cur = db.cursor()
    cur.execute("update users set config = ? where uid = ?", [schema, uid])
    db.commit()

def subject_save(uid=0,sid=0,name="",config="{}"):
    db = frogsense_common.get_db()
    cur = db.cursor()
    if sid == 0:
        #new subject.. add and then grant permission to user
        cur.execute("insert into subjects (name, data) values (?,?)", [name, config])
        sid = cur.lastrowid
        cur.execute("insert into user_subjects (uid, sid) values (?,?)", [uid, sid])
    else:
        cur.execute("select count(*) from user_subjects where uid = ? and sid = ?", [uid, sid])
        if cur.fetchall()[0][0]:
            cur.execute("update subjects set name = ?, data = ? where sid = ?", [name, config, sid])
    db.commit()

def subject_get(uid=0,sid=None):
    db = frogsense_common.get_db()
    cur = db.cursor()
    cur.execute("select subjects.sid, subjects.name, subjects.data from subjects, user_subjects where user_subjects.uid = ? and user_subjects.sid=subjects.sid", [uid])
    rows = cur.fetchall()
    ret_val = {"id": {}, "name_idx": {}}
    for r in rows:    
        data = {"name": r[1], "config": json.loads(r[2])}
        ret_val["id"][r[0]] = data
        ret_val["name_idx"][r[1]] = r[0]
    return ret_val

def observation_save(observation):
    db = frogsense_common.get_db()
    cur = db.cursor()

    if "id" not in observation:
        #insert
        observation["id"] = str(uuid.uuid4())
        cur.execute("insert into observations (oid, input_raw, ts_int, data, sid, subject_raw) values (?,?,?,?,?,?)",
            [observation["id"], observation["input_raw"], observation["timestamp_int"], json.dumps(observation["signals"]), observation["sid"], observation["subject_raw"]])
    else:
        #update
        sql = "update observations set input_updated = ?, "
        args = [observation["input_raw"]]
        if observation["timestamp_int"] is not None:
            sql += "ts_int = ?, "
            args.append(observation["timestamp_int"])
        sql += "data = ?,  sid = ?, subject_raw =? where oid = ?"
        args.extend( [json.dumps(observation["signals"]), observation["sid"], observation["subject_raw"], observation["id"]] )
        cur.execute(sql, args)
    
    db.commit()

    return observation

def observation_update_ts(uid=0,id=None,ts="",tz="America/New_York"):
        dt = datetime.fromisoformat(ts)
        dt = dt.replace(tzinfo=ZoneInfo(tz))

        db = frogsense_common.get_db()
        cur = db.cursor()

        sql = "update observations set ts_int = ? where oid = ?"
        args = [int(dt.timestamp()),id]
        cur.execute(sql, args)
        
        db.commit()

def observation_delete(uid=0,id=None):
        db = frogsense_common.get_db()
        cur = db.cursor()

        sql = "delete from observations where oid = ?"
        args = [id]
        cur.execute(sql, args)
        
        db.commit()
        
def observation_load(uid=0,sort_ts=True,limit=None,sid=None,required_modifiers=None,signal=None,tz="America/New_York"):
    db = frogsense_common.get_db()
    cur = db.cursor()
    
    sql = """select observations.oid, observations.input_raw, observations.input_updated, observations.ts_int, observations.data, observations.sid, observations.subject_raw, subjects.name
            from observations, user_subjects, subjects where
               user_subjects.uid = ? and subjects.sid = user_subjects.sid and observations.sid = user_subjects.sid """
    args = [uid]
    
    if sid is not None:
        sql += " and subjects.sid = ? "
        args.append(sid)

    if signal is not None:
        sql += """ and EXISTS ( SELECT 1 FROM json_each(observations.data) AS signal  WHERE json_extract(signal.value, '$.type') = ? ) """
        args.append(signal)

    if required_modifiers is not None and len(required_modifiers) > 0:
        for mod in required_modifiers:
            sql += """ and EXISTS ( SELECT 1 FROM json_each(observations.data) AS signal JOIN json_each(signal.value, '$.modifiers') as modifier WHERE json_extract(signal.value, '$.type') = ? and modifier.value = ?) """
            args.append(signal, mod)

    sql += " order by observations.ts_int desc"

    if limit is not None:
        sql += " limit " + str(limit)

    cur.execute(sql, args)
    
    results = []

    rows = cur.fetchall()
    for r in rows:
        dt = datetime.fromtimestamp(r[3], tz=ZoneInfo(tz))
        rec = {"id": r[0], "input_raw": r[1], "timestamp_int": r[3], "timestamp": dt.strftime("%Y-%m-%dT%H:%M"), "signals": json.loads(r[4]), "subject": r[7], "subject_raw": r[6], "sid": r[5]}
        if r[2] is not None:
            rec["input_corrected"] = r[2]
        results.append(rec)

    return results
    
def test(input):

    CONFIG = load_config()

    print(process(input=input,cfg=CONFIG,write=False))

def import_old(file="/storage/turtlevid/archie/output.json"):
    rows = load_all(data_file=file)
    
    subjs = subject_get(1)
    
    for r in rows:
        if r.get("id") is None:
            continue
            
        dt = datetime.fromisoformat(r["timestamp"])
        dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))

        r["timestamp_int"] = int(dt.timestamp())
        del r["timestamp"]
        del r["id"]
        
        r["sid"] = subjs["name_idx"][r["subject"]]
        
        observation_save(r)
        
    if False:
        ts = "2026-07-26T14:49:10.359738"

def ai_summary(uid, sid, question=""):
    subjs = subject_get(uid=uid, sid=sid)
    client = OpenAI()

    payload = {
        "subject": subjs["id"][sid],
        "observations": observation_load(uid=uid,sid=sid,limit=100)
    }

    #print(payload)

    q = "Identify meaningful patterns, trends, changes, and notable events."
    if len(question) > 0:
        q = f"Address this specific question only if relates to the subject. Otherwise respond that the question can't be answered: {question}" 

    response = client.responses.create(
        model="gpt-5.6-luna",
        instructions=f"""
    You are reviewing subject facts and longitudinal observation data for a particular subject.

    {q}

    Important rules:
    - Prefer structured signals over raw input when both describe the same fact.
    - Use raw input to identify context or details not represented by structured signals.
    - Do not override or contradict a structured signal based solely on the raw input.
    - An observation may contain useful information that has no corresponding structured signal.
    - Absence of a structured signal does not mean the event or behavior did not occur.
    - Do not assume that an event did not occur merely because it was not recorded.
    - Do not invent missing observations.
    - Distinguish recorded facts from your interpretation.
    - Point out apparent inconsistencies in the data.
    - Consider the relevant subject's data (e.g. species, gender, etc.) when interpreting observations.
    - Do not diagnose medical conditions.
    - Keep the analysis concise and useful to the requestor.
    """,
        input=json.dumps(payload, separators=(',', ':'))
    )

    analysis = response.output_text    
    analysis_html = markdown.markdown(
        analysis,
        extensions=["extra"]
    )    
    return analysis_html

#import_old()

#test("Doodle ate 18 dubia")
#update(data_file="output.json",tracking_id="08b6ac07-d47f-4ea4-890b-33ce5e113f6d",new_record=process(input="Doodle shit",cfg=load_config(),write=False))