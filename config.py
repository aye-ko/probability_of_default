import streamlit as st
import joblib
from supabase import create_client, Client

# --- Supabase Client ---
SUPABASE_URL = "https://ohvhzrjwqoiolfxikbei.supabase.co"
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# --- Load ML Assets ---
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
    if "screen" not in st.session_state:
        st.session_state.screen = "welcome"
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "supabase_session" not in st.session_state:
        st.session_state.supabase_session = None