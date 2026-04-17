import streamlit as st
import pandas as pd
import uuid
from config import supabase, supabase_admin


# ── Customer ──────────────────────────────────────────────────────────────────

def db_get_customer_by_email(email):
    try:
        res = supabase_admin.table("customer").select("*").eq("customer_email", email).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"db_get_customer_by_email error: {e}")
        return None


def db_create_customer(fname, lname, email, phone):
    try:
        res = supabase_admin.table("customer").insert({
            "customer_fname": fname,
            "customer_lname": lname,
            "customer_email": email,
            "customer_phone": phone,
        }).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        st.error(f"db_create_customer error: {e}")
        return None


# ── Employee (Underwriter) ─────────────────────────────────────────────────────

def db_get_employee_by_email(email):
    try:
        res = supabase_admin.table("employee").select("*").eq("employee_email", email).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"db_get_employee_by_email error: {e}")
        return None


def db_get_underwriter_email():
    try:
        res = supabase_admin.table("employee").select("employee_email").execute()
        return res.data[0]["employee_email"] if res.data else None
    except Exception as e:
        print(f"db_get_underwriter_email error: {e}")
        return None


# ── Applications ───────────────────────────────────────────────────────────────

def db_get_next_app_id():
    try:
        res = supabase_admin.table("application").select("application_id").execute()
        existing_ids = [row["application_id"] for row in res.data if row.get("application_id")]
        return max(existing_ids) + 1 if existing_ids else 1
    except:
        return 1


def db_save_application(app_data):
    try:
        if "application_id" not in app_data or app_data["application_id"] is None:
            app_data["application_id"] = db_get_next_app_id()
        res = supabase_admin.table("application").insert(app_data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        st.error(f"db_save_application error: {e}")
        return None


def db_get_applications():
    """All applications joined with customer info and decision status."""
    try:
        res = supabase_admin.table("application").select(
            "*, customer(customer_fname, customer_lname, customer_email), "
            "decision(decision_id, is_approved, reason, employee_id)"
        ).execute()
        return res.data or []
    except Exception as e:
        print(f"db_get_applications error: {e}")
        return []


def db_get_applications_by_customer(customer_id):
    try:
        res = supabase_admin.table("application").select(
            "*, decision(decision_id, is_approved, reason)"
        ).eq("customer_id", customer_id).execute()
        return res.data or []
    except Exception as e:
        print(f"db_get_applications_by_customer error: {e}")
        return []


# ── Decisions ──────────────────────────────────────────────────────────────────

def db_save_decision(application_id, employee_id, is_approved, reason=""):
    try:
        res = supabase_admin.table("decision").insert({
            # REMOVE THIS LINE: "decision_id": str(uuid.uuid4()),
            "application_id": application_id,
            "employee_id":    employee_id,
            "is_approved":    is_approved,
            "reason":         reason,
        }).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        st.error(f"db_save_decision error: {e}")
        return None

def db_delete_decision(application_id):
    try:
        supabase_admin.table("decision").delete().eq("application_id", application_id).execute()
        return True
    except Exception as e:
        print(f"db_delete_decision error: {e}")
        return False


def db_delete_application(application_id):
    """Deletes decision first (FK constraint), then the application."""
    try:
        db_delete_decision(application_id)
        supabase_admin.table("application").delete().eq("application_id", application_id).execute()
        return True
    except Exception as e:
        st.error(f"db_delete_application error: {e}")
        return False


# ── Activity Logs ──────────────────────────────────────────────────────────────

def db_log_activity(user_email, message):
    try:
        supabase_admin.table("activity_logs").insert({
            "user_email": user_email,
            "message":    message,
        }).execute()
    except Exception as e:
        print(f"db_log_activity error: {e}")


def db_get_activity_logs(user_email=None):
    try:
        query = (
            supabase_admin.table("activity_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(20)
        )
        if user_email:
            query = query.eq("user_email", user_email)
        res = query.execute()
        return res.data or []
    except Exception as e:
        print(f"db_get_activity_logs error: {e}")
        return []


# ── Portfolio Metrics ──────────────────────────────────────────────────────────

def db_get_portfolio_metrics():
    try:
        res = supabase_admin.table("application").select(
            "loan_amount, dti, fico_range_low, annual_inc, revol_util, purpose, home_ownership"
        ).execute()
        apps = res.data or []
        if not apps:
            return None

        df = pd.DataFrame(apps)

        dec_res   = supabase_admin.table("decision").select("is_approved").execute()
        decisions = dec_res.data or []

        total_apps = len(df)
        avg_loan   = df["loan_amount"].mean()    if "loan_amount"    in df.columns else 0
        avg_dti    = df["dti"].mean()            if "dti"            in df.columns else 0
        avg_fico   = df["fico_range_low"].mean() if "fico_range_low" in df.columns else 0
        avg_inc    = df["annual_inc"].mean()     if "annual_inc"     in df.columns else 0
        avg_revol  = df["revol_util"].mean()     if "revol_util"     in df.columns else 0

        top_purpose = None
        if "purpose" in df.columns and not df["purpose"].dropna().empty:
            top_purpose = df["purpose"].value_counts().idxmax()

        approval_rate = None
        if decisions:
            df_dec = pd.DataFrame(decisions)
            approval_rate = df_dec["is_approved"].mean() * 100

        return {
            "total_apps":    total_apps,
            "avg_loan":      avg_loan,
            "avg_dti":       avg_dti,
            "avg_fico":      avg_fico,
            "avg_income":    avg_inc,
            "avg_revol":     avg_revol,
            "top_purpose":   top_purpose,
            "approval_rate": approval_rate,
        }
    except Exception as e:
        print(f"db_get_portfolio_metrics error: {e}")
        return None