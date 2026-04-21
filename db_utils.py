"""
db_utils.py — All database access via SQLAlchemy (no Supabase RLS client).

Every public function accepts `engine` as its first argument so callers
control the connection and there are no hidden global side-effects.
"""

import pandas as pd
import streamlit as st
from sqlalchemy import text


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row(result):
    """Return the first row of a CursorResult as a plain dict, or None."""
    row = result.fetchone()
    return dict(row._mapping) if row else None

def _rows(result):
    """Return all rows of a CursorResult as a list of plain dicts."""
    return [dict(r._mapping) for r in result.fetchall()]


# ── Customer ───────────────────────────────────────────────────────────────────

def db_get_customer_by_email(engine, email):
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM customer WHERE customer_email = :email LIMIT 1"),
                {"email": email},
            )
            return _row(result)
    except Exception as e:
        print(f"db_get_customer_by_email error: {e}")
        return None


def db_create_customer(engine, fname, lname, email, phone):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO customer
                        (customer_fname, customer_lname, customer_email, customer_phone, company_id)
                    VALUES
                        (:fname, :lname, :email, :phone, 1)
                    RETURNING *
                """),
                {"fname": fname, "lname": lname, "email": email, "phone": phone},
            )
            return _row(result)
    except Exception as e:
        st.error(f"db_create_customer error: {e}")
        return None


# ── Employee ───────────────────────────────────────────────────────────────────

def db_get_employee_by_email(engine, email):
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM employee WHERE employee_email = :email LIMIT 1"),
                {"email": email},
            )
            return _row(result)
    except Exception as e:
        print(f"db_get_employee_by_email error: {e}")
        return None


def db_create_employee(engine, fname, lname, email, phone):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO employee
                        (employee_fname, employee_lname, employee_email,
                         employee_phone, company_id, is_manager)
                    VALUES
                        (:fname, :lname, :email, :phone, 1, false)
                    RETURNING *
                """),
                {"fname": fname, "lname": lname, "email": email, "phone": phone},
            )
            return _row(result)
    except Exception as e:
        st.error(f"db_create_employee error: {e}")
        return None


def db_get_underwriter_email(engine):
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT employee_email FROM employee LIMIT 1")
            )
            row = _row(result)
            return row["employee_email"] if row else None
    except Exception as e:
        print(f"db_get_underwriter_email error: {e}")
        return None


# ── Applications ───────────────────────────────────────────────────────────────

def db_save_application(engine, app_data: dict):
    """
    Insert a new loan application row.
    `app_data` keys must match the `application` table columns exactly.
    Returns the inserted row as a dict, or None on failure.
    """
    try:
        cols   = list(app_data.keys())
        fields = ", ".join(cols)
        params = ", ".join(f":{c}" for c in cols)

        with engine.begin() as conn:
            result = conn.execute(
                text(f"INSERT INTO application ({fields}) VALUES ({params}) RETURNING *"),
                app_data,
            )
            return _row(result)
    except Exception as e:
        st.error(f"db_save_application error: {e}")
        return None


def db_get_applications(engine):
    """
    Returns all applications with joined customer info and decision.
    Each row is a dict; 'customer' and 'decision' are nested dicts (or None).
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    a.*,
                    row_to_json(c)  AS customer,
                    row_to_json(d)  AS decision
                FROM application a
                LEFT JOIN customer c ON c.customer_id = a.customer_id
                LEFT JOIN decision d ON d.application_id = a.application_id
                ORDER BY a.application_id DESC
            """))
            rows = _rows(result)

        # row_to_json returns a dict already when psycopg2 / asyncpg parses JSONB;
        # wrap in a list to match the shape the UI helpers expect.
        for row in rows:
            if row.get("customer") and not isinstance(row["customer"], list):
                row["customer"] = [row["customer"]]
            if row.get("decision") and not isinstance(row["decision"], list):
                row["decision"] = [row["decision"]]
        return rows
    except Exception as e:
        print(f"db_get_applications error: {e}")
        return []


def db_get_applications_by_customer(engine, customer_id):
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT
                        a.*,
                        row_to_json(d) AS decision
                    FROM application a
                    LEFT JOIN decision d ON d.application_id = a.application_id
                    WHERE a.customer_id = :cid
                    ORDER BY a.application_id DESC
                """),
                {"cid": customer_id},
            )
            rows = _rows(result)

        for row in rows:
            if row.get("decision") and not isinstance(row["decision"], list):
                row["decision"] = [row["decision"]]
        return rows
    except Exception as e:
        print(f"db_get_applications_by_customer error: {e}")
        return []


def get_loan_application(engine, application_id):
    """Used by ml.py to fetch a single application for scoring."""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM application WHERE application_id = :aid LIMIT 1"),
                {"aid": application_id},
            )
            row = _row(result)
        if row:
            return True, row
        return False, "Application not found"
    except Exception as e:
        return False, f"get_loan_application error: {e}"


# ── Decisions ──────────────────────────────────────────────────────────────────

def db_save_decision(engine, application_id, employee_id, is_approved, reason=""):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO decision
                        (application_id, employee_id, is_approved, reason)
                    VALUES
                        (:app_id, :emp_id, :approved, :reason)
                    RETURNING *
                """),
                {
                    "app_id":   application_id,
                    "emp_id":   employee_id,
                    "approved": is_approved,
                    "reason":   reason,
                },
            )
            return _row(result)
    except Exception as e:
        st.error(f"db_save_decision error: {e}")
        return None


def approve_loan_application(engine, application_id, employee_id=None):
    return db_save_decision(engine, application_id, employee_id, is_approved=True)


def deny_loan_application(engine, application_id, employee_id=None, reason=""):
    return db_save_decision(engine, application_id, employee_id, is_approved=False, reason=reason)


def delete_loan_application(engine, application_id):
    try:
        with engine.begin() as conn:
            # Delete child decision rows first (FK constraint)
            conn.execute(
                text("DELETE FROM decision WHERE application_id = :aid"),
                {"aid": application_id},
            )
            conn.execute(
                text("DELETE FROM application WHERE application_id = :aid"),
                {"aid": application_id},
            )
        return True
    except Exception as e:
        st.error(f"delete_loan_application error: {e}")
        return False


# ── Activity Logs ──────────────────────────────────────────────────────────────

def db_log_activity(engine, user_email, message):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO activity_logs (user_email, message) VALUES (:email, :msg)"),
                {"email": user_email, "msg": message},
            )
    except Exception as e:
        print(f"db_log_activity error: {e}")


def db_get_activity_logs(engine, user_email=None):
    try:
        with engine.connect() as conn:
            if user_email:
                result = conn.execute(
                    text("""
                        SELECT * FROM activity_logs
                        WHERE user_email = :email
                        ORDER BY created_at DESC
                        LIMIT 20
                    """),
                    {"email": user_email},
                )
            else:
                result = conn.execute(
                    text("""
                        SELECT * FROM activity_logs
                        ORDER BY created_at DESC
                        LIMIT 20
                    """)
                )
            return _rows(result)
    except Exception as e:
        print(f"db_get_activity_logs error: {e}")
        return []


# ── Portfolio Metrics ──────────────────────────────────────────────────────────

def db_get_portfolio_metrics(engine):
    try:
        with engine.connect() as conn:
            apps_result = conn.execute(
                text("SELECT loan_amount, dti, fico_range_low, annual_inc, revol_util, purpose FROM application")
            )
            apps = _rows(apps_result)

            dec_result = conn.execute(
                text("SELECT is_approved FROM decision")
            )
            decisions = _rows(dec_result)

        if not apps:
            return None

        df = pd.DataFrame(apps)

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