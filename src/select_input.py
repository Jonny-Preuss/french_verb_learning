import random
from src import config as con
import plotly.graph_objects as go
import streamlit as st

# --- SELECT RANDOM VERB AND COLUMN ---
def get_random_task(ws, selected_filter=None, selected_tenses=None):
    rows = range(con.START_ROW, ws.max_row + 1)
    available_rows = []
    for r in rows:
        status = str(ws[f"{con.STATUS_COL}{r}"].value).strip().lower()
        if status == "true":
            continue

        filter_value = ws[f"{con.FILTER_COL}{r}"].value
        if selected_filter and selected_filter != "(All)":
            if not filter_value or filter_value.strip() != selected_filter:
                continue

        available_rows.append(r)

    if not available_rows:
        return None, None, None, None

    row = random.choice(available_rows)
    if selected_tenses:
        possible_cols = set()
        for tense in selected_tenses:
            if tense in con.TENSE_COL_MAP:
                possible_cols.update(con.TENSE_COL_MAP[tense])
        if not possible_cols:
            possible_cols = con.CONJUGATION_COLS
        else:
            possible_cols = list(possible_cols)
    else:
        possible_cols = con.CONJUGATION_COLS

    col = random.choice(possible_cols)

    verb = ws[f"{con.VERB_COL}{row}"].value
    translation = ws[f"{con.TRANSLATION_COL}{row}"].value
    tense = ws[f"{col}1"].value
    subject = ws[f"{col}2"].value
    return row, col, verb, f"{tense} — {subject}", translation





def show_conjugation_position(selected_tense, selected_pronoun):
    # Base tense list
    base_tenses = ["Présent", "Imparfait", "Futur", "Conditionnel", "Subjonctif", "Impératif"]
    tenses = base_tenses + ["Other"]

    # Pronoun list
    pronouns = ["je", "tu", "il/elle/on", "nous", "vous", "ils/elles"]

    # TENSE bar
    tense_index = tenses.index(selected_tense) if selected_tense in base_tenses else len(tenses) - 1
    tense_colors = ["#1f77b4" if i == tense_index else "#d3d3d3" for i in range(len(tenses))]
    tense_labels = ["🔺" if i == tense_index else "" for i in range(len(tenses))]

    tense_bar = go.Figure()
    tense_bar.add_trace(go.Bar(
        x=tenses,
        y=[1] * len(tenses),
        marker_color=tense_colors,
        text=tense_labels,
        textposition="outside",
    ))
    tense_bar.update_layout(
        title="Tense Position",
        height=150,
        yaxis=dict(showticklabels=False),
        margin=dict(t=40, b=20, l=20, r=20),
    )

    st.plotly_chart(tense_bar, use_container_width=True)

    # PRONOUN bar
    pronoun_index = pronouns.index(selected_pronoun) if selected_pronoun in pronouns else None
    pronoun_colors = ["#e1210c" if i == pronoun_index else "#d3d3d3" for i in range(len(pronouns))]
    pronoun_labels = ["🔺" if i == pronoun_index else "" for i in range(len(pronouns))]

    pronoun_bar = go.Figure()
    pronoun_bar.add_trace(go.Bar(
        x=pronouns,
        y=[1] * len(pronouns),
        marker_color=pronoun_colors,
        text=pronoun_labels,
        textposition="outside",
    ))
    pronoun_bar.update_layout(
        title="Pronoun Position",
        height=150,
        yaxis=dict(showticklabels=False),
        margin=dict(t=40, b=20, l=20, r=20),
    )

    st.plotly_chart(pronoun_bar, use_container_width=True)
