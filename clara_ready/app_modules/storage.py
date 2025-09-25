import sqlite3, os
from typing import Dict, Any, List, Optional
from datetime import datetime

DB_PATH = os.getenv("CLARA_DB_PATH", "clara.db")

def init_db():
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS analyses(
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, meta TEXT, ts TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS subscribers(
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, name TEXT,
        stripe_session_id TEXT, stripe_customer_id TEXT, ts TEXT)""")
    conn.commit(); conn.close()

def log_analysis_event(email: str, meta: Dict[str,Any]):
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("INSERT INTO analyses(email, meta, ts) VALUES(?,?,?)",
                (email, str(meta), datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

def log_subscriber(email: str, name: str, stripe_session_id: str, stripe_customer_id: str):
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("""INSERT OR REPLACE INTO subscribers(email, name, stripe_session_id, stripe_customer_id, ts)
                   VALUES(?,?,?,?,?)""",
                (email, name, stripe_session_id, stripe_customer_id, datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

def list_subscribers() -> List[Dict[str,Any]]:
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("SELECT email, name, stripe_customer_id, ts FROM subscribers ORDER BY ts DESC")
    rows = cur.fetchall(); conn.close()
    return [{"email": r[0], "name": r[1], "stripe_customer_id": r[2], "created_at": r[3]} for r in rows]

def get_subscriber_by_email(email: str) -> Optional[Dict[str,Any]]:
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("SELECT email, name, stripe_customer_id FROM subscribers WHERE email=?", (email,))
    row = cur.fetchone(); conn.close()
    return {"email": row[0], "name": row[1], "stripe_customer_id": row[2]} if row else None
