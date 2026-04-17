import streamlit as st
import joblib
from supabase import create_client, Client

# --- Supabase Client (anon key — RLS-protected queries) ---
SUPABASE_URL = "https://ohvhzrjwqoiolfxikbei.supabase.co"
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Supabase Admin Client (service role — bypasses RLS for signup inserts) ---
SUPABASE_SERVICE_KEY = st.secrets["SUPABASE_SERVICE_KEY"]
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_authed_client() -> Client:
    """Returns the Supabase client with the current user's session applied."""
    session = st.session_state.get("supabase_session")
    if session:
        try:
            supabase.auth.set_session(session.access_token, session.refresh_token)
        except Exception:
            pass
    return supabase


# --- Load ML Assets (cached so pkl files only load once) ---
@st.cache_resource
def load_ml_assets():
    model = joblib.load('model.pkl')
    scaler = joblib.load('scaler.pkl')
    binner = joblib.load('binner.pkl')
    imputer = joblib.load('imputer.pkl')
    columns = joblib.load('columns.pkl')
    numeric_cols = joblib.load('numeric_cols.pkl')
    return model, scaler, binner, imputer, columns, numeric_cols


# --- Session State Init ---
def init_session_state():
    defaults = {
        "screen": "welcome",
        "current_user": None,
        "supabase_session": None,
        "pending_customer": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val