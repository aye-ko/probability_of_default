import streamlit as st
from config import supabase
from db_utils import db_log_activity


def log_activity(engine, message):
    user  = st.session_state.current_user
    email = user["email"] if user else "system"
    db_log_activity(engine, email, message)


def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.current_user     = None
    st.session_state.supabase_session = None
    st.session_state.screen           = "welcome"
    st.rerun()