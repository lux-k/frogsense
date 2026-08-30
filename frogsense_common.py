import shutil
import os
import frogsense_config
import sqlite3
from pathlib import Path

def delete_file(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass  # already gone, no big deal
    except Exception as e:
        print(f"Error deleting {path}: {e}")

def move_file(src, dst):
    try:
        shutil.move(src, dst)
    except Exception as e:
        print(f"Error moving {src} → {dst}: {e}")
        
def get_db():
    return sqlite3.connect(frogsense_config.DB_FILE)

def ensure_column(conn, table, column, col_type):
    cur = conn.cursor()

    # Get existing columns
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]  # row[1] = column name

    if column not in cols:
        print(f"Adding column {column} to {table}")
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    else:
        print(f"Column {column} already exists")

def db_setup():
    CONN = get_db()
    
    cur = CONN.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        uid INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT,
        config TEXT
    )
    """)
    
    
    cur.execute("""select count(*) from users""")
    if cur.fetchall()[0][0] == 0:
        print("Inserting default user")
        cur.execute("""insert into users (user_name, config) values (?,?)""",["default","{}"])
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        sid INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        data TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_subjects (
        uid INTEGER,
        sid INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS observations (
        oid TEXT PRIMARY KEY,
        input_raw TEXT,
        input_updated TEXT,
        ts TEXT,
        ts_int INTEGER,
        data TEXT,
        sid INTEGER,
        subject_raw text
    )
    """)

#    ensure_column(CONN, "detections", "labeled", "TEXT")
    
    CONN.commit()
    CONN.close()        

class SafeDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'