import streamlit as st
from config import supabase
from sqlalchemy import text
from db_utils import (
    db_get_customer_by_email, db_create_customer,
    db_get_employee_by_email, db_create_employee,
    db_log_activity,
)


def _log(engine, message):
    user  = st.session_state.current_user
    email = user["email"] if user else "system"
    db_log_activity(engine, email, message)


# ── Welcome ────────────────────────────────────────────────────────────────────

def welcome_screen():
    st.title("LendGuard")
    st.markdown("### Welcome.")
    st.write("Sign in to continue or create a new account.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Log In", use_container_width=True):
            st.session_state.screen = "login"
            st.rerun()
    with col2:
        if st.button("Create Account", use_container_width=True):
            st.session_state.screen = "signup"
            st.rerun()


# ── Sign Up ────────────────────────────────────────────────────────────────────

def signup_screen(engine):
    st.title("LendGuard")
    st.markdown("### Create account")

    role_choice = st.radio("I am registering as a:", ["Customer", "Underwriter"], horizontal=True)
    st.divider()

    fname    = st.text_input("First Name")
    lname    = st.text_input("Last Name")
    phone    = st.text_input("Phone Number", placeholder="(123) 456-7890")
    email    = st.text_input("Email address")
    password = st.text_input("Password", type="password")

    if st.button("Create Account", use_container_width=True):
        if not fname or not lname or not email or not password:
            st.error("Please fill in all fields.")
        elif len(password) < 8:
            st.error("Password must be at least 8 characters.")
        elif "@" not in email:
            st.error("Enter a valid email address.")
        else:
            try:
                auth_response = supabase.auth.sign_up({"email": email, "password": password})
                if not auth_response.user:
                    st.error("Signup failed. Please try again.")
                    return

                record_saved = False
                if role_choice == "Customer":
                    record = db_create_customer(engine, fname, lname, email, phone)
                    if record:
                        record_saved = True
                        user_data = {
                            "name":        f"{fname} {lname}",
                            "email":       email,
                            "role":        "Customer",
                            "customer_id": record["customer_id"],
                        }
                elif role_choice == "Underwriter":
                    record = db_create_employee(engine, fname, lname, email, phone)
                    if record:
                        record_saved = True
                        user_data = {
                            "name":        f"{fname} {lname}",
                            "email":       email,
                            "role":        "Underwriter",
                            "employee_id": record["employee_id"],
                        }

                if not record_saved:
                    st.error("Auth succeeded but database profile failed to save.")
                    return

                session = auth_response.session
                if session is not None:
                    st.session_state.supabase_session = session
                    supabase.auth.set_session(session.access_token, session.refresh_token)
                    st.session_state.current_user = user_data
                    _log(engine, f"{role_choice} account created successfully")
                    st.session_state.screen = "dashboard"
                    st.rerun()
                else:
                    st.success("✅ Account created! Please check your email to confirm, then log in.")

            except Exception as e:
                st.error(f"Signup error: {e}")

    if st.button("Already have an account? Log in"):
        st.session_state.screen = "login"
        st.rerun()


# ── Log In ─────────────────────────────────────────────────────────────────────

def login_screen(engine):
    st.title("LendGuard")
    st.markdown("### Welcome back.")
    email    = st.text_input("Email address")
    password = st.text_input("Password", type="password")

    if st.button("Log In", use_container_width=True):
        if not email or not password:
            st.error("Please fill in all fields.")
        elif "@" not in email:
            st.error("Enter a valid email address.")
        else:
            try:
                auth_response = supabase.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                if not auth_response.user:
                    st.error("Invalid email or password.")
                    return

                st.session_state.supabase_session = auth_response.session
                supabase.auth.set_session(
                    auth_response.session.access_token,
                    auth_response.session.refresh_token,
                )

                employee = db_get_employee_by_email(engine, email)
                if employee:
                    st.session_state.current_user = {
                        "name":        f"{employee['employee_fname']} {employee['employee_lname']}",
                        "email":       email,
                        "role":        "Underwriter",
                        "employee_id": employee["employee_id"],
                    }
                else:
                    customer = db_get_customer_by_email(engine, email)
                    if customer:
                        st.session_state.current_user = {
                            "name":        f"{customer['customer_fname']} {customer['customer_lname']}",
                            "email":       email,
                            "role":        "Customer",
                            "customer_id": customer["customer_id"],
                        }
                    else:
                        st.error("Account not found in the database. Please contact admin.")
                        return

                _log(engine, f"Logged in as {email}")
                st.session_state.screen = "dashboard"
                st.rerun()

            except Exception as e:
                st.error(f"Login error: {e}")

    if st.button("No account yet? Sign up"):
        st.session_state.screen = "signup"
        st.rerun()