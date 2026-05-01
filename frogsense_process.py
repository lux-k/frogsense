from datetime import datetime
import string
import json
import re
import jellyfish

def process(input="", cfg={}, output_file="output.json", write=True, tracking_id=None ):
    result = {"input_raw": input, "timestamp": datetime.now().isoformat(), "signals": []}
    print(f"Input is: {input}")
    input = ' ' + input + ' '

    translator = str.maketrans('', '', string.punctuation)
    input = input.translate(translator)
    input = input.lower()

    for subject in cfg["subjects"]:
        for alias in cfg["subjects"][subject]["aliases"]:
            if (' ' + alias + ' ').lower() in input:
                result["subject"] = subject
                result["subject_raw"] = alias
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
                        for ctx in cfg["contextualizers"][c]:
                            for label in cfg["contextualizers"][c][ctx]:
                                if (' ' + label + ' ').lower() in input:
                                    event[c] = ctx
                                
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
        
    if tracking_id is not None:
        result["id"] = tracking_id

    if write:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result) + '\n')    
    return result

def search(subject, signal, data_file, reverse = False, required_modifiers = None, limit = None):
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
    
def extract_number(input):
    numbers = re.findall(r'-?\d+\.?\d*', input)
    if len(numbers) > 0:
        return float(numbers[0])
    else:
        return None

def load_all(data_file):
    results = []
    
    with open(data_file, 'r', encoding='utf-8') as f:
        results = [json.loads(line) for line in f]

    return results

def update(data_file="", tracking_id = None, new_record=None):
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

def load_config(file="config.json"):
    with open(file, 'r', encoding='utf-8') as input:
        cfg = json.load(input)

    return cfg

def test(input):

    CONFIG = load_config()

    print(process(input=input,cfg=CONFIG,write=False))

#test("Doodle ate 18 dubia")
#update(data_file="output.json",tracking_id="08b6ac07-d47f-4ea4-890b-33ce5e113f6d",new_record=process(input="Doodle shit",cfg=load_config(),write=False))