import streamlit as st
import pandas as pd
import os

# --------- COLOUR SCHEME ---------

st.markdown("""
    <style>
    div.stButton > button {
        background-color: #f0f0f0 !important;
        color: black !important;
        border: 1px solid #ccc !important;
        padding: 0.5em 1.2em !important;
        border-radius: 6px !important;
        font-size: 1rem !important;
    }

    div.stButton > button:hover {
        background-color: #d6e4ff !important;  /* light blue */
        color: black !important;
        border-color: #a0c4ff !important;
    }
    </style>
""", unsafe_allow_html=True)



# -------- APP ---------
st.title("📉 Mistakes Log")

log_path = "error_log.csv"

if os.path.exists("error_log.csv"):
    df = pd.read_csv("error_log.csv")
    st.dataframe(df.style.set_properties(**{
        'text-align': 'left',
        'background-color': '#fdfdfd'
    }).highlight_null(None, color="red"), use_container_width=True)

    st.download_button("Download log as CSV", data=df.to_csv(index=False), file_name="error_log.csv")

else:
    st.info("No mistakes logged yet. Perfect streak! 🥳")

# TODO: Highlight incorrect answers in red
# TODO: Allow filtering by verb or date
