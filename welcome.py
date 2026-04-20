import streamlit as st

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