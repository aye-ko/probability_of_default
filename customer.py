import re
import streamlit as st
from config import supabase
from db_utils import (
    db_get_applications_by_customer, db_save_application,
    db_get_next_app_id, db_get_underwriter_email, db_log_activity
)
from email_utils import send_risk_result_to_underwriter
from functions import predict_new_loan


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


def customer_dashboard():
    user = st.session_state.current_user
    st.title("LendGuard")
    st.markdown(f"### Good to see you, {user['name']} 👋")

    apps = db_get_applications_by_customer(user["customer_id"])
    active = [a for a in apps if not a.get("decision")]
    decided = [a for a in apps if a.get("decision")]

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(f"📁 Past Applications: {len(decided)}", use_container_width=True):
            st.session_state.screen = "loans"
            st.rerun()
    with col2:
        if st.button(f"⚡ Pending: {len(active)}", use_container_width=True):
            st.session_state.screen = "active"
            st.rerun()
    with col3:
        if st.button("➕ Apply for a Loan", use_container_width=True):
            st.session_state.screen = "customer_application"
            st.rerun()

    st.markdown("### Recent Activity")
    logs = db_log_activity and db_get_activity_logs_for_display(user["email"])
    if logs:
        for item in logs:
            ts = item["created_at"][:16].replace("T", " ")
            st.write(f"✅ {item['message']} — {ts}")
    else:
        st.write("No activity yet.")

    if st.button("Log Out"):
        logout()


def db_get_activity_logs_for_display(email):
    from db_utils import db_get_activity_logs
    return db_get_activity_logs(email)


def customer_application_screen():
    st.title("Loan Application")
    st.write("Fill in the details below to apply for a loan.")

    user = st.session_state.current_user

    customer_phone = st.text_input("Your Phone Number", placeholder="(123) 456-7890", max_chars=15)

    loan_amnt = st.number_input("Loan Amount ($)", min_value=500, max_value=50000, value=10000, step=500)
    monthly_debt = st.number_input("Monthly Bills and Spending ($)", min_value=0, max_value=20000, value=500, step=500)
    fico_range_low = st.number_input("FICO Score", min_value=300, max_value=850, value=680, step=1)
    annual_inc = st.number_input("Annual Income ($)", min_value=1000, max_value=1000000, value=60000, step=1000)
    dti = monthly_debt / (annual_inc / 12) * 100 if annual_inc > 0 else 0
    pub_rec_bankruptcies = st.number_input("Number of Public Record Bankruptcies", min_value=0, max_value=10, value=0, step=1)
    tax_liens = st.number_input("Number of Tax Liens", min_value=0, max_value=10, value=0, step=1)
    credit_card_debt = st.number_input("Credit Card Balance ($)", min_value=0, max_value=1000000, value=1000, step=100)
    credit_card_limit = st.number_input("Credit Card Limit ($)", min_value=0, max_value=1000000, value=5000, step=100)
    total_il_high_credit_limit = st.number_input("Total Installment Credit Limit ($)", min_value=0, max_value=1000000, value=20000, step=1000)
    revol_util = credit_card_debt / credit_card_limit * 100 if credit_card_limit > 0 else 0

    term = st.selectbox("Loan Term", options=["36 months", "60 months"])
    emp_length = st.selectbox("Employment Length", options=[
        "< 1 year", "1 year", "2 years", "3 years", "4 years", "5 years",
        "6 years", "7 years", "8 years", "9 years", "10+ years", "nan"
    ])
    home_ownership = st.selectbox("Home Ownership", options=["RENT", "OWN", "MORTGAGE", "OTHER"])
    purpose = st.selectbox("Purpose of Loan", options=[
        "debt_consolidation", "credit_card", "home_improvement", "major_purchase",
        "small_business", "car", "wedding", "medical", "moving", "vacation",
        "house", "educational", "renewable_energy", "other"
    ])
    verification_status = st.selectbox("Verification Status", options=["Verified", "Source Verified", "Not Verified"])

    if st.button("Submit Application", use_container_width=True):
        if len(customer_phone) < 10:
            st.error("Enter a valid phone number.")
        else:
            with st.spinner("Analyzing your application..."):
                prob_default, expected_loss, recommendation, input_df = predict_new_loan(
                    loan_amnt, dti, fico_range_low, annual_inc, revol_util,
                    pub_rec_bankruptcies, tax_liens, total_il_high_credit_limit,
                    term, emp_length, home_ownership, purpose, verification_status
                )

                app_data = {
                    "customer_id": user["customer_id"],
                    "loan_amount": loan_amnt,
                    "dti": round(dti, 2),
                    "fico_range_low": fico_range_low,
                    "annual_inc": annual_inc,
                    "revol_util": round(revol_util, 2),
                    "pub_rec_bankruptcies": pub_rec_bankruptcies,
                    "tax_liens": tax_liens,
                    "emp_length": emp_length,
                    "home_ownership": home_ownership,
                    "purpose": purpose,
                    "verification_status": verification_status,
                    "term": term,
                }

                saved = db_save_application(app_data)

                if saved:
                    app_id = saved["application_id"]
                    log_activity(f"Loan application {app_id} submitted")
                    st.success("✅ Your application has been submitted successfully!")
                    st.info(f"**Application ID:** {app_id}\n\nOur team will review your application shortly.")

                    underwriter_email = db_get_underwriter_email()
                    if underwriter_email:
                        sent = send_risk_result_to_underwriter(
                            underwriter_email, app_id,
                            user["name"], user["customer_id"],
                            customer_phone, user["email"],
                            loan_amnt, dti,
                            prob_default, expected_loss, recommendation
                        )
                        log_activity("Risk report emailed to underwriter ✅" if sent else "Failed to email underwriter ⚠️")
                    else:
                        log_activity("No underwriter found ⚠️")
                else:
                    st.error("Failed to save application. Please try again.")

    if st.button("← Back to Dashboard"):
        st.session_state.screen = "dashboard"
        st.rerun()


def loans_screen():
    user = st.session_state.current_user
    st.title("📁 Past Applications")
    apps = db_get_applications_by_customer(user["customer_id"])
    decided = [a for a in apps if a.get("decision")]
    if decided:
        for app in decided:
            dec = app["decision"][0] if isinstance(app.get("decision"), list) else app.get("decision", {})
            status = "✅ Approved" if dec.get("is_approved") else "❌ Denied"
            with st.expander(f"App #{app['application_id']} — ${app['loan_amount']:,.0f} — {status}"):
                st.write(f"**Loan Amount:** ${app['loan_amount']:,.0f}")
                st.write(f"**Purpose:** {app.get('purpose', 'N/A')}")
                st.write(f"**Term:** {app.get('term', 'N/A')}")
                st.write(f"**Decision:** {status}")
                if dec.get("reason"):
                    st.write(f"**Reason:** {dec['reason']}")
    else:
        st.write("No decided applications yet.")
    if st.button("← Back to Dashboard"):
        st.session_state.screen = "dashboard"
        st.rerun()


def active_screen():
    user = st.session_state.current_user
    st.title("⚡ Pending Applications")
    apps = db_get_applications_by_customer(user["customer_id"])
    active = [a for a in apps if not a.get("decision") or len(a.get("decision", [])) == 0]
    if active:
        for app in active:
            with st.expander(f"App #{app['application_id']} — ${app['loan_amount']:,.0f} — {app.get('purpose', '')}"):
                st.write(f"**Loan Amount:** ${app['loan_amount']:,.0f}")
                st.write(f"**Term:** {app.get('term', 'N/A')}")
                st.write(f"**Purpose:** {app.get('purpose', 'N/A')}")
                st.write(f"**Status:** Pending Review")
    else:
        st.write("No pending applications.")
    if st.button("← Back to Dashboard"):
        st.session_state.screen = "dashboard"
        st.rerun()