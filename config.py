import os
import streamlit as st
import joblib
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine
from supabase import create_client, Client

load_dotenv()

# ── Supabase Auth Client (still needed for sign-up / sign-in / RLS sessions) ──
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ── SQLAlchemy Engine ──────────────────────────────────────────────────────────

def create_db_connection():
    """Create a SQLAlchemy engine using PostgreSQL credentials from .env.
    The service role key doubles as the DB password — no separate supabase_pw needed."""
    supabase_pwd  = quote_plus(os.getenv("supabase_pwd"))
    supabase_user = os.getenv("supabase_user")
    supabase_host = os.getenv("supabase_host")
    supabase_port = os.getenv("supabase_port")
    supabase_name = os.getenv("supabase_dbname")

    engine = create_engine(
        f"postgresql://{supabase_user}:{supabase_pwd}@{supabase_host}:{supabase_port}/{supabase_name}"
    )
    return engine


# ── Load ML Assets (cached so pkl files only load once) ───────────────────────

@st.cache_resource
def load_ml_assets():
    model        = joblib.load("model.pkl")
    scaler       = joblib.load("scaler.pkl")
    binner       = joblib.load("binner.pkl")
    imputer      = joblib.load("imputer.pkl")
    columns      = joblib.load("columns.pkl")
    numeric_cols = joblib.load("numeric_cols.pkl")
    return model, scaler, binner, imputer, columns, numeric_cols


# ── Session State Init ────────────────────────────────────────────────────────

def init_session_state():
    defaults = {
        "screen":           "welcome",
        "current_user":     None,
        "supabase_session": None,
        "pending_customer": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val