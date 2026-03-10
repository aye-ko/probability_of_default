import streamlit as st
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Page Config ---
st.set_page_config(page_title="LendGuard", page_icon="⚡", layout="wide")

# --- Email Function ---
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
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 500px; margin: auto; background: white; border-radius: 12px; padding: 30px;">
            <h1 style="color: #1F3864;">⚡ LendGuard</h1>
            <h2>Welcome, {name}!</h2>
            <p>Your account has been created successfully as a <strong>{role}</strong>.</p>
            <p>You can now log in and access your dashboard.</p>
            <br>
            <p style="color: #888;">If you did not create this account, please ignore this email.</p>
        </div>
    </body>
    </html>
    """
    return send_email(email, subject, body)

def send_application_email(underwriter_email, applicant, amount, app_id):
    subject = f"New Application Submitted — {app_id}"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 500px; margin: auto; background: white; border-radius: 12px; padding: 30px;">
            <h1 style="color: #1F3864;">⚡ LendGuard</h1>
            <h2>New Application Submitted</h2>
            <p><strong>Application ID:</strong> {app_id}</p>
            <p><strong>Applicant:</strong> {applicant}</p>
            <p><strong>Loan Amount:</strong> ${amount:,}</p>
            <p>Log in to your dashboard to review this application.</p>
        </div>
    </body>
    </html>
    """
    return send_email(underwriter_email, subject, body)

# --- Session State ---
if "screen" not in st.session_state:
    st.session_state.screen = "welcome"
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "activity_log" not in st.session_state:
    st.session_state.activity_log = []
if "applications" not in st.session_state:
    st.session_state.applications = [
        {"id": "APP-001", "applicant": "Maria Lopez", "amount": 25000, "status": "Paid Off", "return": 8.2},
        {"id": "APP-002", "applicant": "James Carter", "amount": 10000, "status": "Paid Off", "return": 6.5},
        {"id": "APP-003", "applicant": "Sara Kim", "amount": 50000, "status": "Active", "return": 9.1},
        {"id": "APP-004", "applicant": "Tom Reed", "amount": 15000, "status": "Active", "return": 7.3},
    ]

# --- Helper Functions ---
def log_activity(message):
    timestamp = datetime.now().strftime("%I:%M %p")
    st.session_state.activity_log.insert(0, {"text": message, "time": timestamp})

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
    st.write("Join us today. Its free.")
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
            st.session_state.current_user = {"name": name, "email": email, "role": role}
            log_activity("Account created successfully")
            log_activity(f"Joined as {role}")
            # Send real welcome email
            sent = send_welcome_email(name, email, role)
            if sent:
                log_activity("Welcome email sent ✅")
            else:
                log_activity("Welcome email failed to send ⚠️")
            st.session_state.screen = "dashboard"
            st.rerun()
    if st.button("Already have an account? Log in"):
        st.session_state.screen = "login"
        st.rerun()

# --- Login Screen ---
def login_screen():
    st.title("LendGuard")
    st.markdown("### Welcome back.")
    st.write("Log in to your account.")
    role = st.selectbox("I am a...", ["Customer", "Underwriter"])
    email = st.text_input("Email address")
    password = st.text_input("Password", type="password")
    if st.button("Log In", use_container_width=True):
        if not email or not password:
            st.error("Please fill in all fields.")
        elif "@" not in email:
            st.error("Enter a valid email address.")
        else:
            st.session_state.current_user = {"name": email.split("@")[0], "email": email, "role": role}
            log_activity(f"Logged in as {email}")
            st.session_state.screen = "dashboard"
            st.rerun()
    if st.button("No account yet? Sign up"):
        st.session_state.screen = "signup"
        st.rerun()

# --- Dashboard Router ---
def dashboard_screen():
    user = st.session_state.current_user
    role = user.get("role", "Customer")
    if role == "Underwriter":
        underwriter_dashboard()
    else:
        customer_dashboard()

# --- Customer Dashboard ---
def customer_dashboard():
    user = st.session_state.current_user
    st.title("LendGuard")
    st.markdown(f"### Good to see you, {user['name']} 👋")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📁 Loans: 24", use_container_width=True):
            st.session_state.screen = "loans"
            st.rerun()
    with col2:
        if st.button("⚡ Active Applications: 8", use_container_width=True):
            st.session_state.screen = "active"
            st.rerun()
    with col3:
        st.metric("Uptime", "99%")

    st.markdown("### Recent Activity")
    if st.session_state.activity_log:
        for item in st.session_state.activity_log:
            st.write(f"✅ {item['text']} — {item['time']}")
    else:
        st.write("No activity yet.")

    if st.button("Log Out"):
        st.session_state.current_user = None
        st.session_state.screen = "welcome"
        st.rerun()

# --- Underwriter Dashboard ---
def underwriter_dashboard():
    user = st.session_state.current_user
    st.title("LendGuard")
    st.markdown(f"### Welcome, {user['name']} 👋 — Underwriter Portal")

    total_apps = len(st.session_state.applications)
    paid_off = len([a for a in st.session_state.applications if a["status"] == "Paid Off"])
    active = len([a for a in st.session_state.applications if a["status"] == "Active"])
    avg_return = sum(a["return"] for a in st.session_state.applications) / total_apps

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Applications", total_apps)
    col2.metric("Active", active)
    col3.metric("Paid Off", paid_off)
    col4.metric("Avg Return", f"{avg_return:.1f}%")

    st.divider()

    if st.button("➕ Start New Application", use_container_width=True):
        st.session_state.screen = "new_application"
        st.rerun()

    st.divider()

    st.markdown("### ⚡ Active Applications")
    active_apps = [a for a in st.session_state.applications if a["status"] == "Active"]
    if active_apps:
        for app in active_apps:
            with st.expander(f"{app['id']} — {app['applicant']} — ${app['amount']:,}"):
                st.write(f"**Status:** {app['status']}")
                st.write(f"**Loan Amount:** ${app['amount']:,}")
                st.write(f"**Expected Return:** {app['return']}%")
    else:
        st.write("No active applications.")

    st.divider()

    st.markdown("### ✅ Paid Off Applications")
    paid_apps = [a for a in st.session_state.applications if a["status"] == "Paid Off"]
    if paid_apps:
        for app in paid_apps:
            with st.expander(f"{app['id']} — {app['applicant']} — ${app['amount']:,}"):
                st.write(f"**Status:** {app['status']}")
                st.write(f"**Loan Amount:** ${app['amount']:,}")
                st.write(f"**Return Earned:** {app['return']}%")
    else:
        st.write("No paid off applications yet.")

    st.divider()

    st.markdown("### 🕐 Recent Activity")
    if st.session_state.activity_log:
        for item in st.session_state.activity_log:
            st.write(f"✅ {item['text']} — {item['time']}")
    else:
        st.write("No activity yet.")

    if st.button("Log Out"):
        st.session_state.current_user = None
        st.session_state.screen = "welcome"
        st.rerun()

# --- New Application Screen ---
def new_application_screen():
    st.title("LendGuard")
    st.markdown("### ➕ New Application")
    applicant = st.text_input("Applicant Name")
    applicant_email = st.text_input("Applicant Email")  # ← new
    amount = st.number_input("Loan Amount ($)", min_value=1000, max_value=1000000, step=1000)
    expected_return = st.slider("Expected Return (%)", min_value=1.0, max_value=20.0, step=0.1)
    if st.button("Submit Application", use_container_width=True):
        if not applicant:
            st.error("Please enter an applicant name.")
        else:
            new_app = {
                "id": f"APP-{len(st.session_state.applications) + 1:03}",
                "applicant": applicant,
                "amount": amount,
                "status": "Active",
                "return": expected_return
            }
            st.session_state.applications.append(new_app)
            log_activity(f"New application submitted for {applicant}")
            # Email the underwriter
            user = st.session_state.current_user
            sent = send_application_email(user["email"], applicant, amount, new_app["id"])
            if sent:
                log_activity(f"Application confirmation email sent ✅")
            else:
                log_activity(f"Confirmation email failed to send ⚠️")
            st.session_state.screen = "dashboard"
            st.rerun()
    if st.button("← Back to Dashboard"):
        st.session_state.screen = "dashboard"
        st.rerun()

# --- Customer Loans Screen ---
def loans_screen():
    st.title("📁 Loans")
    st.write("Your completed loans will show here.")
    if st.button("← Back to Dashboard"):
        st.session_state.screen = "dashboard"
        st.rerun()

# --- Customer Active Applications Screen ---
def active_screen():
    st.title("⚡ Active Applications")
    st.write("Your active applications will show here.")
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
elif st.session_state.screen == "loans":
    loans_screen()
elif st.session_state.screen == "active":
    active_screen()
elif st.session_state.screen == "new_application":
    new_application_screen()