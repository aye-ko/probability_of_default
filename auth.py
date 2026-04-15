import streamlit as st
from config import supabase
from db_utils import db_get_customer_by_email, db_create_customer, db_get_employee_by_email, db_log_activity


def log_activity(message):
    user = st.session_state.current_user
    email = user["email"] if user else "system"
    db_log_activity(email, message)


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


def signup_screen():
    st.title("LendGuard")
    st.markdown("### Create account")
    st.info("Note: Underwriter accounts must be created directly in the database by an admin.")
    fname = st.text_input("First Name")
    lname = st.text_input("Last Name")
    phone = st.text_input("Phone Number", placeholder="(123) 456-7890")
    email = st.text_input("Email address")
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
                auth_response = supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })
                if auth_response.user:
                    customer = db_create_customer(fname, lname, email, phone)
                    if customer:
                        st.session_state.current_user = {
                            "name": f"{fname} {lname}",
                            "email": email,
                            "role": "Customer",
                            "customer_id": customer["customer_id"],
                        }
                        st.session_state.supabase_session = auth_response.session
                        log_activity("Account created successfully")
                        st.session_state.screen = "dashboard"
                        st.rerun()
                    else:
                        st.error("Auth succeeded but customer record failed. Try logging in.")
                else:
                    st.error("Signup failed. Please try again.")
            except Exception as e:
                st.error(f"Signup error: {e}")

    if st.button("Already have an account? Log in"):
        st.session_state.screen = "login"
        st.rerun()


def login_screen():
    st.title("LendGuard")
    st.markdown("### Welcome back.")
    email = st.text_input("Email address")
    password = st.text_input("Password", type="password")

    if st.button("Log In", use_container_width=True):
        if not email or not password:
            st.error("Please fill in all fields.")
        elif "@" not in email:
            st.error("Enter a valid email address.")
        else:
            try:
                auth_response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                if auth_response.user:
                    # Check if employee (underwriter) first
                    employee = db_get_employee_by_email(email)
                    if employee:
                        st.session_state.current_user = {
                            "name": f"{employee['employee_fname']} {employee['employee_lname']}",
                            "email": email,
                            "role": "Underwriter",
                            "employee_id": employee["employee_id"],
                        }
                    else:
                        # Check customer table
                        customer = db_get_customer_by_email(email)
                        if customer:
                            st.session_state.current_user = {
                                "name": f"{customer['customer_fname']} {customer['customer_lname']}",
                                "email": email,
                                "role": "Customer",
                                "customer_id": customer["customer_id"],
                            }
                        else:
                            st.error("Account not found in the system. Please sign up or contact your admin.")
                            return

                    st.session_state.supabase_session = auth_response.session
                    log_activity(f"Logged in as {email}")
                    st.session_state.screen = "dashboard"
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
            except Exception as e:
                st.error(f"Login error: {e}")

    if st.button("No account yet? Sign up"):
        st.session_state.screen = "signup"
        st.rerun()