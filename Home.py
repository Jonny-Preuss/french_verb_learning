import streamlit as st

st.set_page_config(page_title="Welcome to the Trainer", layout="centered")

# st.title("🇫🇷 French Verb Conjugation Trainer")
st.write("Welcome! Start practicing or check your past mistakes in the sidebar.")

with open("README.md", "r", encoding="utf-8") as f:
    readme = f.read()

st.markdown(readme, unsafe_allow_html=True)