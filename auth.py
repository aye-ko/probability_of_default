import requests
import streamlit as st

def login_user(email, password):
    api_key = st.secrets["FIREBASE_API_KEY"]

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"

    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        return response.json()
    return None