import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


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
        print(f"Email sent successfully to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("Email auth failed — check EMAIL and EMAIL_PASSWORD in secrets.toml. EMAIL_PASSWORD must be a Gmail App Password.")
        return False
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


def send_decision_to_customer(customer_email, customer_name, app_id, decision):
    """Notify the customer when their application has been approved or denied."""
    if decision == "Approved":
        color = "#22c55e"
        headline = "🎉 Your Loan Has Been Approved!"
        message = "Congratulations! Your loan application has been reviewed and approved. Our team will be in touch with next steps."
    else:
        color = "#ef4444"
        headline = "Your Loan Application Was Not Approved"
        message = "Thank you for applying. After careful review, we are unable to approve your loan application at this time. You are welcome to reapply in the future."

    subject = f"LendGuard — Loan Application {decision}: {app_id}"
    body = f"""
<html><body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
<div style="max-width: 500px; margin: auto; background: white; border-radius: 12px; padding: 30px;">
<h1 style="color: #1F3864;">⚡ LendGuard</h1>
<h2 style="color: {color};">{headline}</h2>
<p>Dear {customer_name},</p>
<p>{message}</p>
<p><strong>Application ID:</strong> {app_id}</p>
<br><p style="color: #888; font-size: 12px;">If you have questions, please contact your loan officer.</p>
</div>
</body></html>
"""
    return send_email(customer_email, subject, body)