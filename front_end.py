import streamlit as st
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import joblib
import re
from supabase import create_client, Client
 
# --- Page Config ---
st.set_page_config(page_title="LendGuard", page_icon="⚡", layout="wide")
 
# --- Supabase Client ---
SUPABASE_URL = "https://ikmuhwmtkrvzgembhnsh.supabase.co"
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
 
model, scaler, binner, imputer, columns, numeric_cols = load_ml_assets()
 
# --- ML Helpers ---
def get_recommendation(prob_default):
    if prob_default <= 0.35:
        return "Low Risk — Recommend Approval"
    elif prob_default <= 0.55:
        return "Moderate Risk — Recommend Further Review"
    else:
        return "High Risk — Recommend Decline"
 
def calculate_expected_loss(loan_amnt, prob_default, lgd=0.50):
    return loan_amnt * prob_default * lgd
 
def predict_new_loan(
    loan_amnt, dti, fico_range_low, annual_inc, revol_util,
    pub_rec_bankruptcies, tax_liens, total_il_high_credit_limit,
    term, emp_length, home_ownership, purpose, verification_status
):
    input_df = pd.DataFrame(0, index=[0], columns=columns)
    input_df['loan_amnt'] = loan_amnt
    input_df['dti'] = dti
    input_df['fico_range_low'] = fico_range_low
    input_df['annual_inc'] = annual_inc
    input_df['revol_util'] = revol_util
    input_df['pub_rec_bankruptcies'] = pub_rec_bankruptcies
    input_df['tax_liens'] = tax_liens
 
    if term == "60 months":
        input_df['term_ 60 months'] = 1
 
    emp_col = f'emp_length_{emp_length}'
    if emp_col in input_df.columns:
        input_df[emp_col] = 1
 
    home_col = f'home_ownership_{home_ownership}'
    if home_col in input_df.columns:
        input_df[home_col] = 1
 
    purpose_col = f'purpose_{purpose}'
    if purpose_col in input_df.columns:
        input_df[purpose_col] = 1
 
    ver_col = f'verification_status_{verification_status}'
    if ver_col in input_df.columns:
        input_df[ver_col] = 1
 
    til_bin = binner.transform(pd.Series([total_il_high_credit_limit]), metric='bins')[0]
    if til_bin == "[214.00, inf)":
        input_df['til_binned_[214.00, inf)'] = 1
    elif til_bin == "Missing":
        input_df['til_binned_Missing'] = 1
 
    input_df = input_df.rename(columns={
        'emp_length_less_than_1_year': 'emp_length_< 1 year',
        'til_binned_214_plus': 'til_binned_[214.00, inf)'
    })
 
    input_df[numeric_cols] = scaler.transform(input_df[numeric_cols])
    prob_default = model.predict_proba(input_df)[:, 1][0]
    expected_loss = calculate_expected_loss(loan_amnt, prob_default)
    recommendation = get_recommendation(prob_default)
    return prob_default, expected_loss, recommendation
 
# --- Supabase Helpers ---
def db_create_user(name, email, role):
    try:
        supabase.table("users").upsert({
            "name": name,
            "email": email,
            "role": role,
        }).execute()
        return True
    except Exception as e:
        print(f"DB user error: {e}")
        return False
 
def db_get_user(email):
    try:
        res = supabase.table("users").select("*").eq("email", email).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"DB get user error: {e}")
        return None
 
def db_get_underwriter_email():
    try:
        res = supabase.table("users").select("email").eq("role", "Underwriter").limit(1).execute()
        return res.data[0]["email"] if res.data else None
    except Exception as e:
        print(f"DB underwriter email error: {e}")
        return None
 
def db_log_activity(user_email, message):
    try:
        supabase.table("activity_logs").insert({
            "user_email": user_email,
            "message": message,
        }).execute()
    except Exception as e:
        print(f"DB log error: {e}")
 
def db_get_activity_logs(user_email=None):
    try:
        query = supabase.table("activity_logs").select("*").order("created_at", desc=True).limit(20)
        if user_email:
            query = query.eq("user_email", user_email)
        res = query.execute()
        return res.data or []
    except Exception as e:
        print(f"DB get logs error: {e}")
        return []
 
def db_save_application(app_data):
    try:
        supabase.table("applications").insert(app_data).execute()
        return True
    except Exception as e:
        print(f"DB save app error: {e}")
        return False
 
def db_get_applications():
    try:
        res = supabase.table("applications").select("*").order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"DB get apps error: {e}")
        return []
 
def db_get_next_app_id():
    try:
        res = supabase.table("applications").select("id").execute()
        return f"APP-{len(res.data) + 1:03}" if res.data else "APP-001"
    except:
        return "APP-001"
 
# --- Email Helpers ---
def send_email(to_email, subject, body):
    try:
        sender = st.secrets["EMAIL"]
        password = st.secrets["EMAIL_PASSWORD"]
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False
 
def send_welcome_email(name, email, role):
    subject = "Welcome to LendGuard ⚡"
    body = f"""
    <html><body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 500px; margin: auto; background: white; border-radius: 12px; padding: 30px;">
            <h1 style="color: #1F3864;">⚡ LendGuard</h1>
            <h2>Welcome, {name}!</h2>
            <p>Your account has been created successfully as a <strong>{role}</strong>.</p>
            <p>You can now log in and access your dashboard.</p>
            <br><p style="color: #888;">If you did not create this account, please ignore this email.</p>
        </div>
    </body></html>
    """
    return send_email(email, subject, body)
 
def send_risk_result_to_underwriter(
    underwriter_email, app_id, customer_name, customer_id,
    customer_phone, customer_email, loan_amnt, dti,
    prob_default, expected_loss, recommendation
):
    if prob_default <= 0.35:
        risk_color, risk_label = "#22c55e", "LOW RISK"
    elif prob_default <= 0.55:
        risk_color, risk_label = "#f59e0b", "MODERATE RISK"
    else:
        risk_color, risk_label = "#ef4444", "HIGH RISK"
 
    subject = f"⚡ New Loan Application [{risk_label}] — {app_id}"
    body = f"""
    <html><body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 580px; margin: auto; background: white; border-radius: 12px; padding: 30px;">
            <h1 style="color: #1F3864;">⚡ LendGuard</h1>
            <h2>New Loan Application — {app_id}</h2>
            <h3 style="border-bottom: 1px solid #eee; padding-bottom: 8px;">👤 Customer Information</h3>
            <p><strong>Name:</strong> {customer_name}</p>
            <p><strong>Customer ID:</strong> {customer_id}</p>
            <p><strong>Phone:</strong> {customer_phone}</p>
            <p><strong>Email:</strong> {customer_email}</p>
            <h3 style="border-bottom: 1px solid #eee; padding-bottom: 8px;">💰 Loan Details</h3>
            <p><strong>Loan Amount:</strong> ${loan_amnt:,.0f}</p>
            <p><strong>Debt-to-Income Ratio:</strong> {dti:.1f}%</p>
            <h3 style="border-bottom: 1px solid #eee; padding-bottom: 8px;">📊 Risk Assessment</h3>
            <p><strong>Probability of Default:</strong> {prob_default:.2%}</p>
            <p><strong>Estimated Loss:</strong> ${expected_loss:,.2f}</p>
            <p><strong>Recommendation:</strong> <span style="color: {risk_color}; font-weight: bold;">{recommendation}</span></p>
            <div style="margin-top: 24px; padding: 16px; border-radius: 8px; background: {risk_color}22; border-left: 4px solid {risk_color};">
                <strong style="color: {risk_color};">{risk_label}</strong>
            </div>
            <br><p style="color: #888; font-size: 12px;">Log in to LendGuard to view the full application and take action.</p>
        </div>
    </body></html>
    """
    return send_email(underwriter_email, subject, body)
 
# --- Session State ---
if "screen" not in st.session_state:
    st.session_state.screen = "welcome"
if "current_user" not in st.session_state:
    st.session_state.current_user = None
 
def log_activity(message):
    user = st.session_state.current_user
    email = user["email"] if user else "system"
    db_log_activity(email, message)
 
# --- Welcome Screen ---
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
 
# --- Signup Screen ---
def signup_screen():
    st.title("LendGuard")
    st.markdown("### Create account")
    role = st.selectbox("I am a...", ["Customer", "Underwriter"])
    name = st.text_input("Full name")
    email = st.text_input("Email address")
    password = st.text_input("Password", type="password")
    if st.button("Create Account", use_container_width=True):
        if not name or not email or not password:
            st.error("Please fill in all fields.")
        elif len(password) < 8:
            st.error("Password must be at least 8 characters.")
        elif "@" not in email:
            st.error("Enter a valid email address.")
        else:
            db_create_user(name, email, role)
            st.session_state.current_user = {"name": name, "email": email, "role": role}
            log_activity("Account created successfully")
            log_activity(f"Joined as {role}")
            sent = send_welcome_email(name, email, role)
            log_activity("Welcome email sent ✅" if sent else "Welcome email failed ⚠️")
            st.session_state.screen = "dashboard"
            st.rerun()
    if st.button("Already have an account? Log in"):
        st.session_state.screen = "login"
        st.rerun()
 
# --- Login Screen ---
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
            user = db_get_user(email)
            if user:
                st.session_state.current_user = {
                    "name": user["name"],
                    "email": user["email"],
                    "role": user["role"]
                }
            else:
                st.error("No account found with that email. Please sign up first.")
                return
            log_activity(f"Logged in as {email}")
            st.session_state.screen = "dashboard"
            st.rerun()
    if st.button("No account yet? Sign up"):
        st.session_state.screen = "signup"
        st.rerun()
 
# --- Dashboard Router ---
def dashboard_screen():
    role = st.session_state.current_user.get("role", "Customer")
    if role == "Underwriter":
        underwriter_dashboard()
    else:
        customer_dashboard()
 
# --- Customer Dashboard ---
def customer_dashboard():
    user = st.session_state.current_user
    st.title("LendGuard")
    st.markdown(f"### Good to see you, {user['name']} 👋")
 
    apps = db_get_applications()
    user_apps = [a for a in apps if a.get("submitted_by") == user["email"]]
    active_count = len([a for a in user_apps if a["status"] == "Active"])
    paid_count = len([a for a in user_apps if a["status"] == "Paid Off"])
 
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(f"📁 Loans: {paid_count}", use_container_width=True):
            st.session_state.screen = "loans"
            st.rerun()
    with col2:
        if st.button(f"⚡ Active Applications: {active_count}", use_container_width=True):
            st.session_state.screen = "active"
            st.rerun()
    with col3:
        if st.button("➕ Apply for a Loan", use_container_width=True):
            st.session_state.screen = "customer_application"
            st.rerun()
 
    st.markdown("### Recent Activity")
    logs = db_get_activity_logs(user["email"])
    if logs:
        for item in logs:
            ts = item["created_at"][:16].replace("T", " ")
            st.write(f"✅ {item['message']} — {ts}")
    else:
        st.write("No activity yet.")
 
    if st.button("Log Out"):
        st.session_state.current_user = None
        st.session_state.screen = "welcome"
        st.rerun()
 
# --- Customer Loan Application Screen ---
def customer_application_screen():
    st.title("LendGuard")
    st.markdown("### ➕ Apply for a Loan")
    st.write("Fill in your details below. Your application will be reviewed by an underwriter.")
 
    st.markdown("#### 👤 Personal Information")
    customer_name = st.text_input("Full Name", placeholder="John Doe", max_chars=50)
    customer_id = st.text_input("Customer ID", placeholder="123456", max_chars=50)
    customer_phone = st.text_input("Phone Number", placeholder="(123) 456-7890", max_chars=15)
    customer_email = st.text_input("Email Address", placeholder="xxx@xxx.xxx", max_chars=50)
 
    st.markdown("#### 💰 Loan Details")
    loan_amnt = st.number_input("Loan Amount ($)", min_value=500, max_value=50000, step=500, value=10000)
    term = st.selectbox("Loan Term", ["36 months", "60 months"])
    purpose = st.selectbox("Purpose of Loan", [
        "debt_consolidation", "credit_card", "home_improvement", "major_purchase",
        "small_business", "car", "wedding", "medical", "moving", "vacation",
        "house", "educational", "renewable_energy", "other"
    ])
 
    st.markdown("#### 🏠 Financial Information")
    annual_inc = st.number_input("Annual Income ($)", min_value=1000, max_value=1000000, step=1000, value=60000)
    monthly_debt = st.number_input("Monthly Debt ($)", min_value=0, max_value=20000, step=100, value=500)
    dti = (monthly_debt / (annual_inc / 12) * 100) if annual_inc > 0 else 0
    st.info(f"Calculated Debt-to-Income Ratio: **{dti:.1f}%**")
 
    home_ownership = st.selectbox("Home Ownership", ["RENT", "OWN", "MORTGAGE", "OTHER"])
    emp_length = st.selectbox("Employment Length", [
        "< 1 year", "1 year", "2 years", "3 years", "4 years", "5 years",
        "6 years", "7 years", "8 years", "9 years", "10+ years", "nan"
    ])
    verification_status = st.selectbox("Income Verification Status", ["Verified", "Source Verified", "Not Verified"])
 
    st.markdown("#### 📊 Credit Information")
    fico_range_low = st.number_input("FICO Score", min_value=300, max_value=850, step=1, value=680)
    revol_util = st.number_input("Revolving Line Utilization Rate (%)", min_value=0.0, max_value=200.0, step=0.1, value=30.0)
    pub_rec_bankruptcies = st.number_input("Number of Public Record Bankruptcies", min_value=0, max_value=10, step=1, value=0)
    tax_liens = st.number_input("Number of Tax Liens", min_value=0, max_value=10, step=1, value=0)
    total_il_high_credit_limit = st.number_input("Total Installment Credit Limit ($)", min_value=0, max_value=1000000, step=1000, value=20000)
 
    st.divider()
 
    if st.button("Submit Application", use_container_width=True):
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(email_pattern, customer_email):
            st.error("Invalid email format.")
        elif len(customer_name) < 2:
            st.error("Please enter a valid full name.")
        elif len(customer_id) < 2:
            st.error("Please enter a valid Customer ID.")
        elif len(customer_phone) < 10:
            st.error("Please enter a valid phone number.")
        else:
            with st.spinner("Analyzing your application..."):
                prob_default, expected_loss, recommendation = predict_new_loan(
                    loan_amnt, dti, fico_range_low, annual_inc, revol_util,
                    pub_rec_bankruptcies, tax_liens, total_il_high_credit_limit,
                    term, emp_length, home_ownership, purpose, verification_status
                )
 
            app_id = db_get_next_app_id()
            user = st.session_state.current_user
 
            app_data = {
                "id": app_id,
                "applicant": customer_name,
                "applicant_email": customer_email,
                "applicant_phone": customer_phone,
                "applicant_customer_id": customer_id,
                "amount": loan_amnt,
                "term": term,
                "purpose": purpose,
                "status": "Active",
                "expected_return": 0.0,
                "prob_default": round(float(prob_default), 4),
                "expected_loss": round(float(expected_loss), 2),
                "recommendation": recommendation,
                "dti": round(dti, 2),
                "submitted_by": user["email"],
            }
            saved = db_save_application(app_data)
            log_activity(f"Loan application {app_id} submitted")
 
            underwriter_email = db_get_underwriter_email()
            if underwriter_email:
                sent = send_risk_result_to_underwriter(
                    underwriter_email, app_id, customer_name, customer_id,
                    customer_phone, customer_email, loan_amnt, dti,
                    prob_default, expected_loss, recommendation
                )
                log_activity("Risk report emailed to underwriter ✅" if sent else "Failed to email underwriter ⚠️")
            else:
                log_activity("No underwriter found in database ⚠️")
 
            if saved:
                st.success(f"✅ Your application **{app_id}** has been submitted successfully!")
                st.info("An underwriter will review your application and be in touch soon.")
                st.balloons()
            else:
                st.error("There was an issue saving your application. Please try again.")
 
    if st.button("← Back to Dashboard"):
        st.session_state.screen = "dashboard"
        st.rerun()
 
# --- Underwriter Dashboard ---
def underwriter_dashboard():
    user = st.session_state.current_user
    st.title("LendGuard")
    st.markdown(f"### Welcome, {user['name']} 👋 — Underwriter Portal")
 
    apps = db_get_applications()
    active_apps = [a for a in apps if a["status"] == "Active"]
    paid_apps = [a for a in apps if a["status"] == "Paid Off"]
    avg_return = (sum(a.get("expected_return", 0) for a in apps) / len(apps)) if apps else 0
 
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Applications", len(apps))
    col2.metric("Active", len(active_apps))
    col3.metric("Paid Off", len(paid_apps))
    col4.metric("Avg Return", f"{avg_return:.1f}%")
 
    st.divider()
 
    if st.button("➕ Start New Application", use_container_width=True):
        st.session_state.screen = "new_application"
        st.rerun()
 
    st.divider()
 
    st.markdown("### ⚡ Active Applications")
    if active_apps:
        for app in active_apps:
            label = f"{app['id']} — {app['applicant']} — ${app['amount']:,.0f}"
            with st.expander(label):
                st.write(f"**Status:** {app['status']}")
                st.write(f"**Loan Amount:** ${app['amount']:,.0f}")
                st.write(f"**Term:** {app.get('term', 'N/A')}")
                st.write(f"**Purpose:** {app.get('purpose', 'N/A')}")
                if app.get("dti") is not None:
                    st.write(f"**DTI:** {app['dti']}%")
                if app.get("prob_default") is not None:
                    st.write(f"**Probability of Default:** {app['prob_default']:.2%}")
                    st.write(f"**Estimated Loss:** ${app['expected_loss']:,.2f}")
                    st.write(f"**Recommendation:** {app['recommendation']}")
                if app.get("applicant_email"):
                    st.write(f"**Applicant Email:** {app['applicant_email']}")
                if app.get("applicant_phone"):
                    st.write(f"**Applicant Phone:** {app['applicant_phone']}")
    else:
        st.write("No active applications.")
 
    st.divider()
 
    st.markdown("### ✅ Paid Off Applications")
    if paid_apps:
        for app in paid_apps:
            with st.expander(f"{app['id']} — {app['applicant']} — ${app['amount']:,.0f}"):
                st.write(f"**Status:** {app['status']}")
                st.write(f"**Loan Amount:** ${app['amount']:,.0f}")
                st.write(f"**Return Earned:** {app.get('expected_return', 0)}%")
    else:
        st.write("No paid off applications yet.")
 
    st.divider()
 
    st.markdown("### 🕐 Recent Activity")
    logs = db_get_activity_logs()
    if logs:
        for item in logs:
            ts = item["created_at"][:16].replace("T", " ")
            st.write(f"✅ {item['message']} — {ts}")
    else:
        st.write("No activity yet.")
 
    if st.button("Log Out"):
        st.session_state.current_user = None
        st.session_state.screen = "welcome"
        st.rerun()
 
# --- Underwriter New Application Screen ---
def new_application_screen():
    st.title("LendGuard")
    st.markdown("### ➕ New Application (Underwriter)")
    applicant = st.text_input("Applicant Name")
    applicant_email = st.text_input("Applicant Email")
    amount = st.number_input("Loan Amount ($)", min_value=1000, max_value=1000000, step=1000)
    expected_return = st.slider("Expected Return (%)", min_value=1.0, max_value=20.0, step=0.1)
    if st.button("Submit Application", use_container_width=True):
        if not applicant:
            st.error("Please enter an applicant name.")
        else:
            app_id = db_get_next_app_id()
            user = st.session_state.current_user
            app_data = {
                "id": app_id,
                "applicant": applicant,
                "applicant_email": applicant_email,
                "amount": amount,
                "status": "Active",
                "expected_return": expected_return,
                "submitted_by": user["email"],
            }
            db_save_application(app_data)
            log_activity(f"New application {app_id} submitted for {applicant}")
            st.session_state.screen = "dashboard"
            st.rerun()
    if st.button("← Back to Dashboard"):
        st.session_state.screen = "dashboard"
        st.rerun()
 
# --- Customer Loans Screen ---
def loans_screen():
    user = st.session_state.current_user
    st.title("📁 Loans")
    apps = db_get_applications()
    paid = [a for a in apps if a.get("submitted_by") == user["email"] and a["status"] == "Paid Off"]
    if paid:
        for app in paid:
            with st.expander(f"{app['id']} — ${app['amount']:,.0f}"):
                st.write(f"**Status:** {app['status']}")
                st.write(f"**Amount:** ${app['amount']:,.0f}")
    else:
        st.write("No completed loans yet.")
    if st.button("← Back to Dashboard"):
        st.session_state.screen = "dashboard"
        st.rerun()
 
# --- Customer Active Applications Screen ---
def active_screen():
    user = st.session_state.current_user
    st.title("⚡ Active Applications")
    apps = db_get_applications()
    active = [a for a in apps if a.get("submitted_by") == user["email"] and a["status"] == "Active"]
    if active:
        for app in active:
            with st.expander(f"{app['id']} — ${app['amount']:,.0f} — {app.get('purpose', '')}"):
                st.write(f"**Status:** {app['status']}")
                st.write(f"**Amount:** ${app['amount']:,.0f}")
                st.write(f"**Term:** {app.get('term', 'N/A')}")
                ts = app["created_at"][:10] if app.get("created_at") else "N/A"
                st.write(f"**Submitted:** {ts}")
    else:
        st.write("No active applications yet.")
    if st.button("← Back to Dashboard"):
        st.session_state.screen = "dashboard"
        st.rerun()
 
# --- Router ---
if st.session_state.screen == "welcome":
    welcome_screen()
elif st.session_state.screen == "signup":
    signup_screen()
elif st.session_state.screen == "login":
    login_screen()
elif st.session_state.screen == "dashboard":
    dashboard_screen()
elif st.session_state.screen == "customer_application":
    customer_application_screen()
elif st.session_state.screen == "loans":
    loans_screen()
elif st.session_state.screen == "active":
    active_screen()
elif st.session_state.screen == "new_application":
    new_application_screen()
 