import os
from pathlib import Path
from dotenv import load_dotenv, set_key
import json
import turtlepond.storage

VERSION = 0.02

load_dotenv()

DATA_DIR = None

# docker envs default to /data otherwise expect a directory in path
if Path("/.dockerenv").exists():
    DATA_DIR = "/data"
else:
    DATA_DIR = "."

# you can override the defaults with this env variable
DATA_DIR = os.getenv("FROGSENSE_DATA_DIR", DATA_DIR)
CONFIG_FILE = os.path.join(DATA_DIR, "frogsense.config")
SCHEMA_FILE = os.path.join(DATA_DIR, "config.json")
RECORD_DIR = os.path.join(DATA_DIR, "recordings")
OUTPUT_FILE = os.path.join(DATA_DIR, "output.json")

# the rest of these values require a restart
DB_FILE = os.path.join(DATA_DIR, "observations.db")

TURTLEPOND_KEY = None
TURTLEPOND = None
STORAGE_CFG = None
STORAGE = None

def reload():
    global TURTLEPOND_KEY
    global TURTLEPOND
    global STORAGE_CFG
    global STORAGE

    load_dotenv(CONFIG_FILE, override=True)

    TURTLEPOND_KEY = os.getenv("FROGSENSE_TURTLEPOND_KEY", "")
    TURTLEPOND = os.getenv("FROGSENSE_TURTLEPOND", "https://turtlepond.us/heket/device/")
    STORAGE_CFG = json.loads(os.getenv("FROGSENSE_STORAGE_CFG", '{"fs": {"root": "' + DATA_DIR + '"}}'))

    backend = next(iter(STORAGE_CFG))
    #print("Backend is", STORAGE_CFG[backend])
    STORAGE = turtlepond.storage.create(type=backend, configuration=STORAGE_CFG[backend])

reload()

print("FrogSense: Ephemeral Note Distiller", VERSION)
print()
print("Data:")
print(f"      DB: {DB_FILE}")
print(f"  CONFIG: {CONFIG_FILE}")
print(f"  SCHEMA: {SCHEMA_FILE}")
print(f"   AUDIO: {RECORD_DIR}")

def save_config_value(name, value):
    global CONFIG_FILE
    cf = Path(CONFIG_FILE)
    cf.touch(exist_ok=True)

    set_key(dotenv_path=cf, key_to_set=name, value_to_set=value)