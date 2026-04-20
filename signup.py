import streamlit as st
from config import supabase
from db_utils import db_create_customer, db_create_employee, db_log_activity

def log_activity(message):
    user  = st.session_state.current_user
    email = user["email"] if user else "system"
    db_log_activity(email, message)

def signup_screen():
    st.title("LendGuard")
    st.markdown("### Create account")

    # --- THE ROLE TOGGLE ---
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
                # 1. Create the Auth User
                auth_response = supabase.auth.sign_up({"email": email, "password": password})

                if not auth_response.user:
                    st.error("Signup failed. Please try again.")
                    return

                # 2. SAVE DATABASE RECORD IMMEDIATELY
                record_saved = False
                user_data = None
                
                if role_choice == "Customer":
                    record = db_create_customer(fname, lname, email, phone)
                    if record:
                        record_saved = True
                        user_data = {
                            "name":        f"{fname} {lname}",
                            "email":       email,
                            "role":        "Customer",
                            "customer_id": record["customer_id"],
                        }
                elif role_choice == "Underwriter":
                    record = db_create_employee(fname, lname, email, phone)
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

                # 3. Check Session for Auto-Login vs Email Confirmation
                session = auth_response.session
                if session is not None:
                    # Email confirmation is OFF -> Auto-login
                    st.session_state.supabase_session = session
                    supabase.auth.set_session(session.access_token, session.refresh_token)
                    
                    st.session_state.current_user = user_data
                    log_activity(f"{role_choice} account created successfully")
                    
                    st.session_state.screen = "dashboard"
                    st.rerun()
                else:
                    # Email confirmation is ON -> Wait for user to verify
                    st.success("✅ Account created! Please check your email to confirm, then log in.")

            except Exception as e:
                st.error(f"Signup error: {e}")

    if st.button("Already have an account? Log in"):
        st.session_state.screen = "login"
        st.rerun()