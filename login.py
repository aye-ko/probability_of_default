import streamlit as st
from config import supabase
from db_utils import db_get_customer_by_email, db_get_employee_by_email, db_log_activity

def log_activity(message):
    user  = st.session_state.current_user
    email = user["email"] if user else "system"
    db_log_activity(email, message)

def login_screen():
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

                # Apply session
                st.session_state.supabase_session = auth_response.session
                supabase.auth.set_session(
                    auth_response.session.access_token,
                    auth_response.session.refresh_token,
                )

                # --- CHECK UNDERWRITER FIRST, THEN CUSTOMER ---
                employee = db_get_employee_by_email(email)
                
                if employee:
                    st.session_state.current_user = {
                        "name":        f"{employee['employee_fname']} {employee['employee_lname']}",
                        "email":       email,
                        "role":        "Underwriter",
                        "employee_id": employee["employee_id"],
                    }
                else:
                    customer = db_get_customer_by_email(email)
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

                log_activity(f"Logged in as {email}")
                st.session_state.screen = "dashboard"
                st.rerun()

            except Exception as e:
                st.error(f"Login error: {e}")

    if st.button("No account yet? Sign up"):
        st.session_state.screen = "signup"
        st.rerun()