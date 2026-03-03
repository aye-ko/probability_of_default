import firebase_admin
from firebase_admin import credentials, auth
import streamlit as st
import json

if not firebase_admin._apps:
    cred_dict = json.loads(st.secrets["FIREBASE_SERVICE_ACCOUNT"])
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

def verify_token(id_token):
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except:
        return None