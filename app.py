import streamlit as st
from config import init_session_state, create_db_connection
from auth import welcome_screen, login_screen, signup_screen
from customer import customer_dashboard, customer_application_screen, loans_screen, active_screen
from underwriter import underwriter_dashboard, all_applications_screen

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="LendGuard", page_icon="⚡", layout="wide")

# ── Session State Init ─────────────────────────────────────────────────────────
init_session_state()

# ── Engine — created once, shared across every rerun via session_state ─────────
if st.session_state.engine is None:
    st.session_state.engine = create_db_connection()

engine = st.session_state.engine

# ── Router ─────────────────────────────────────────────────────────────────────
screen = st.session_state.screen

if screen == "welcome":
    welcome_screen()
elif screen == "signup":
    signup_screen(engine)
elif screen == "login":
    login_screen(engine)
elif screen == "dashboard":
    role = st.session_state.current_user.get("role", "Customer")
    if role == "Underwriter":
        underwriter_dashboard(engine)
    else:
        customer_dashboard(engine)
elif screen == "customer_application":
    customer_application_screen(engine)
elif screen == "loans":
    loans_screen(engine)
elif screen == "active":
    active_screen(engine)
elif screen == "all_applications":
    all_applications_screen(engine)