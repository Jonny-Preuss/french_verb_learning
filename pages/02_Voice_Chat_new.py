# app.py
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide")
st.title("Realtime Console in Streamlit")
components.iframe("http://localhost:3000", height=820)  # console dev server
