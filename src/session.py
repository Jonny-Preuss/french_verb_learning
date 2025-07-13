import streamlit as st

def init_session_state():
    defaults = {
        "attempts": 0,
        "reset_input": False,
        "last_verb": None,
        "clear_input": False, 
        # "last_tense_selection": selected_tenses
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value