import streamlit as st
from config import supabase
from db_utils import (
    db_get_applications, db_get_portfolio_metrics,
    db_save_decision, db_delete_application,
    db_get_activity_logs, db_log_activity,
)
from email_utils import send_decision_to_customer


def log_activity(message):
    user  = st.session_state.current_user
    email = user["email"] if user else "system"
    db_log_activity(email, message)


def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.current_user     = None
    st.session_state.supabase_session = None
    st.session_state.screen           = "welcome"
    st.rerun()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_decision(app):
    dec = app.get("decision")
    if isinstance(dec, list):
        return dec[0] if dec else None
    return dec or None


def _get_customer(app):
    c = app.get("customer", {})
    return (c[0] if isinstance(c, list) and c else c) or {}


def _risk_badge(prob):
    """Returns a coloured label string for the probability of default."""
    if prob is None:
        return "N/A"
    if prob <= 0.35:
        return f"🟢 {prob:.2%} — Low Risk"
    elif prob <= 0.55:
        return f"🟡 {prob:.2%} — Moderate Risk"
    else:
        return f"🔴 {prob:.2%} — High Risk"


def _render_app_details(app):
    dec      = _get_decision(app)
    customer = _get_customer(app)

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Application ID:** {app['application_id']}")
        st.write(f"**Customer:** {customer.get('customer_fname','')} {customer.get('customer_lname','')}")
        st.write(f"**Email:** {customer.get('customer_email', 'N/A')}")
        st.write(f"**Loan Amount:** ${app.get('loan_amount', 0):,.0f}")
        st.write(f"**Term:** {app.get('term', 'N/A')}")
        st.write(f"**Purpose:** {app.get('purpose', 'N/A')}")
        st.write(f"**DTI:** {app.get('dti', 'N/A')}%")
    with col2:
        st.write(f"**FICO Score:** {app.get('fico_range_low', 'N/A')}")
        st.write(f"**Annual Income:** ${app.get('annual_inc', 0):,.0f}")
        st.write(f"**Revol. Utilization:** {app.get('revol_util', 'N/A')}%")
        st.write(f"**Employment Length:** {app.get('emp_length', 'N/A')}")
        st.write(f"**Home Ownership:** {app.get('home_ownership', 'N/A')}")
        st.write(f"**Verification:** {app.get('verification_status', 'N/A')}")
        if dec:
            status = "✅ Approved" if dec.get("is_approved") else "❌ Denied"
            st.write(f"**Decision:** {status}")
            if dec.get("reason"):
                st.write(f"**Reason:** {dec['reason']}")

    # ── ML Risk Results ──────────────────────────────────────────────────────
    prob = app.get("prob_default")
    loss = app.get("expected_loss")
    rec  = app.get("recommendation")

    if prob is not None:
        st.divider()
        st.markdown("**📊 ML Risk Assessment**")
        r1, r2, r3 = st.columns(3)
        r1.metric("Probability of Default", _risk_badge(prob))
        r2.metric("Estimated Loss", f"${loss:,.2f}" if loss is not None else "N/A")
        r3.metric("Recommendation", rec or "N/A")
    else:
        st.divider()
        st.caption("⚠️ ML risk scores not available for this application. Run the SQL migration to add these columns.")


def _app_actions(app, key_prefix):
    """Approve / Deny / Delete — writes to the `decision` table."""
    user        = st.session_state.current_user
    employee_id = user.get("employee_id")
    dec         = _get_decision(app)
    customer    = _get_customer(app)
    cust_email  = customer.get("customer_email")
    cust_name   = f"{customer.get('customer_fname','')} {customer.get('customer_lname','')}".strip()

    if not dec:
        reason = st.text_input(
            "Reason (optional)",
            key=f"{key_prefix}_reason_{app['application_id']}",
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("✅ Approve", key=f"{key_prefix}_approve_{app['application_id']}"):
                result = db_save_decision(app["application_id"], employee_id, True, reason)
                if result:
                    log_activity(f"Application {app['application_id']} approved")
                    if cust_email:
                        send_decision_to_customer(cust_email, cust_name, app["application_id"], "Approved")
                    st.success("Approved!")
                    st.rerun()
        with c2:
            if st.button("❌ Deny", key=f"{key_prefix}_deny_{app['application_id']}"):
                result = db_save_decision(app["application_id"], employee_id, False, reason)
                if result:
                    log_activity(f"Application {app['application_id']} denied")
                    if cust_email:
                        send_decision_to_customer(cust_email, cust_name, app["application_id"], "Denied")
                    st.success("Denied.")
                    st.rerun()
        with c3:
            if st.button("🗑️ Delete", key=f"{key_prefix}_delete_{app['application_id']}"):
                if db_delete_application(app["application_id"]):
                    log_activity(f"Application {app['application_id']} deleted")
                    st.warning("Deleted.")
                    st.rerun()
    else:
        if st.button("🗑️ Delete", key=f"{key_prefix}_delete_{app['application_id']}"):
            if db_delete_application(app["application_id"]):
                log_activity(f"Application {app['application_id']} deleted")
                st.rerun()


# ── Underwriter Dashboard ──────────────────────────────────────────────────────

def underwriter_dashboard():
    user = st.session_state.current_user
    st.title("LendGuard")
    st.markdown(f"### Welcome, {user['name']} 👋 — Underwriter Portal")

    apps = db_get_applications()

    pending  = [a for a in apps if not _get_decision(a)]
    decided  = [a for a in apps if _get_decision(a)]
    approved = [a for a in decided if _get_decision(a).get("is_approved")]
    denied   = [a for a in decided if not _get_decision(a).get("is_approved")]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total",          len(apps))
    col2.metric("Pending Review", len(pending))
    col3.metric("Approved",       len(approved))
    col4.metric("Denied",         len(denied))

    st.divider()

    if st.button("📋 View All Applications", use_container_width=True):
        st.session_state.screen = "all_applications"
        st.rerun()

    st.divider()

    st.markdown("### ⚡ Pending Applications")
    if pending:
        for app in pending:
            name = _customer_name(app)
            prob = app.get("prob_default")
            badge = _risk_badge(prob) if prob is not None else "No score"
            with st.expander(f"#{app['application_id']} — {name} — ${app.get('loan_amount',0):,.0f} — {badge}"):
                _render_app_details(app)
                st.markdown("**Actions:**")
                _app_actions(app, "pending")
    else:
        st.write("No pending applications.")

    st.divider()

    st.markdown("### ✅ Approved Applications")
    if approved:
        for app in approved:
            name = _customer_name(app)
            with st.expander(f"#{app['application_id']} — {name} — ${app.get('loan_amount',0):,.0f}"):
                _render_app_details(app)
                _app_actions(app, "approved")
    else:
        st.write("No approved applications yet.")

    st.divider()

    st.markdown("### ❌ Denied Applications")
    if denied:
        for app in denied:
            name = _customer_name(app)
            with st.expander(f"#{app['application_id']} — {name} — ${app.get('loan_amount',0):,.0f}"):
                _render_app_details(app)
                _app_actions(app, "denied")
    else:
        st.write("No denied applications.")

    st.divider()

    st.markdown("### 📊 Portfolio Metrics")
    metrics = db_get_portfolio_metrics()
    if metrics:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Applications", f"{metrics['total_apps']:,}")
        c2.metric("Avg Loan Amount",    f"${metrics['avg_loan']:,.0f}")
        c3.metric("Avg FICO Score",     f"{metrics['avg_fico']:.0f}")
        c4.metric(
            "Approval Rate",
            f"{metrics['approval_rate']:.1f}%" if metrics['approval_rate'] is not None else "N/A",
        )
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Avg DTI",            f"{metrics['avg_dti']:.1f}%")
        c6.metric("Avg Annual Income", f"${metrics['avg_income']:,.0f}")
        c7.metric("Avg Revol. Util.",   f"{metrics['avg_revol']:.1f}%")
        if metrics.get("top_purpose"):
            c8.metric("Top Purpose", metrics["top_purpose"].replace("_", " ").title())
    else:
        st.info("Portfolio data unavailable.")

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
        logout()


# ── All Applications Screen ────────────────────────────────────────────────────

def all_applications_screen():
    st.title("LendGuard — All Applications")

    apps = db_get_applications()
    if not apps:
        st.info("No applications yet.")
    else:
        filter_opt = st.selectbox("Filter", ["All", "Pending", "Approved", "Denied"])
        if filter_opt == "Pending":
            filtered = [a for a in apps if not _get_decision(a)]
        elif filter_opt == "Approved":
            filtered = [a for a in apps if _get_decision(a) and _get_decision(a).get("is_approved")]
        elif filter_opt == "Denied":
            filtered = [a for a in apps if _get_decision(a) and not _get_decision(a).get("is_approved")]
        else:
            filtered = apps

        st.markdown(f"Showing **{len(filtered)}** application(s)")
        st.divider()

        for app in filtered:
            name   = _customer_name(app)
            dec    = _get_decision(app)
            status = "Pending" if not dec else ("Approved" if dec.get("is_approved") else "Denied")
            with st.expander(f"#{app['application_id']} — {name} — ${app.get('loan_amount',0):,.0f} — {status}"):
                _render_app_details(app)
                st.markdown("**Actions:**")
                _app_actions(app, "all")

    if st.button("← Back to Dashboard"):
        st.session_state.screen = "dashboard"
        st.rerun()


# ── Private ────────────────────────────────────────────────────────────────────

def _customer_name(app):
    c = _get_customer(app)
    return f"{c.get('customer_fname','')} {c.get('customer_lname','')}".strip() or "Unknown"