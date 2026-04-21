import os
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine
from supabase import create_client, Client

load_dotenv()

# ── Supabase Auth Client ───────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ── SQLAlchemy Engine ──────────────────────────────────────────────────────────

def create_db_connection():
    # NO @st.cache_resource — removed to force a fresh connection every time
    host   = os.getenv("supabase_host", "").strip()
    port   = int(os.getenv("supabase_port", "5432").strip())
    dbname = os.getenv("supabase_dbname", "").strip()
    user   = os.getenv("supabase_user", "").strip()
    pwd    = os.getenv("supabase_pwd", "").strip().strip("'\"")

    # Print to terminal so you can confirm exact values being used
    print(f"[DB] host={host} port={port} dbname={dbname} user={user} pwd_len={len(pwd)}")

    engine = create_engine(
        "postgresql+psycopg2://",
        connect_args={
            "host":     host,
            "port":     port,
            "dbname":   dbname,
            "user":     user,
            "password": pwd,
            "sslmode":  "require",
        },
        pool_pre_ping=True,
    )
    return engine


# ── Session State Init ─────────────────────────────────────────────────────────

def init_session_state():
    defaults = {
        "screen":           "welcome",
        "current_user":     None,
        "supabase_session": None,
        "engine":           None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val