import streamlit as st
from db import supabase, db_log_activity


def log_activity(message):
    user = st.session_state.current_user
    email = user["email"] if user else "system"
    db_log_activity(email, message)


def logout():
    try:
        supabase.auth.sign_out()
    except:
        pass
    st.session_state.current_user = None
    st.session_state.supabase_session = None
    st.session_state.screen = "welcome"
    st.rerun()