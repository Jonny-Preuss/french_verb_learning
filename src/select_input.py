import random
from src import config as con
import plotly.graph_objects as go
import streamlit as st

# --- SELECT RANDOM VERB AND COLUMN ---
def get_random_task(ws):
    rows = range(con.START_ROW, ws.max_row + 1)
    available_rows = [r for r in rows if str(ws[f"{con.STATUS_COL}{r}"].value).strip().lower() != "true"]
    if not available_rows:
        return None, None, None, None

    row = random.choice(available_rows)
    col = random.choice(con.CONJUGATION_COLS)

    verb = ws[f"{con.VERB_COL}{row}"].value
    tense = ws[f"{col}1"].value
    subject = ws[f"{col}2"].value
    return row, col, verb, f"{tense} — {subject}"



# def show_conjugation_position(selected_tense, selected_pronoun):
#     # Example full lists — match these to your Excel headers if different
#     tenses = ["Présent", "Imparfait", "Futur", "Conditionnel", "Subjonctif", "Impératif"]
#     pronouns = ["je", "tu", "il/elle/on", "nous", "vous", "ils/elles"]

#     # Map selected values to indices
#     try:
#         tense_index = tenses.index(selected_tense)
#         pronoun_index = pronouns.index(selected_pronoun)
#     except ValueError:
#         st.warning("Selected tense or pronoun not found in reference list.")
#         return

#     # Create top trace (TENSES)
#     tense_bar = go.Figure()
#     tense_bar.add_trace(go.Bar(
#         x=tenses,
#         y=[1]*len(tenses),
#         marker_color=["#1f77b4" if i == tense_index else "#d3d3d3" for i in range(len(tenses))],
#         text=["🔺" if i == tense_index else "" for i in range(len(tenses))],
#         textposition="outside",
#         hoverinfo="x",
#     ))
#     tense_bar.update_layout(
#         title="Tense Position",
#         height=150,
#         yaxis=dict(showticklabels=False),
#         margin=dict(t=40, b=20, l=20, r=20),
#     )

#     # Create bottom trace (PRONOUNS)
#     pronoun_bar = go.Figure()
#     pronoun_bar.add_trace(go.Bar(
#         x=pronouns,
#         y=[1]*len(pronouns),
#         marker_color=["#e1210c" if i == pronoun_index else "#d3d3d3" for i in range(len(pronouns))],
#         text=["🔺" if i == pronoun_index else "" for i in range(len(pronouns))],
#         textposition="outside",
#         hoverinfo="x",
#     ))
#     pronoun_bar.update_layout(
#         title="Pronoun Position",
#         height=150,
#         yaxis=dict(showticklabels=False),
#         margin=dict(t=40, b=20, l=20, r=20),
#     )

#     # Display both charts
#     st.plotly_chart(tense_bar, use_container_width=True)
#     st.plotly_chart(pronoun_bar, use_container_width=True)



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
