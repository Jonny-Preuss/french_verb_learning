import pandas as pd
from openpyxl import load_workbook
import streamlit as st
from src import config as con


# --- FUNCTIONS ---
@st.cache_data
def load_dataframe():
    df = pd.read_excel(con.EXCEL_FILE, header=[0, 1], engine="openpyxl")
    return df

def load_workbook_sheet():
    wb = load_workbook(con.EXCEL_FILE)
    ws = wb.active
    return wb, ws