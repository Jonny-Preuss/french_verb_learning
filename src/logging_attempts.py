import pandas as pd
from datetime import datetime
import os

def log_incorrect_attempt(verb, tense, subject, user_input, correct_answer, log_path="error_log.csv"):
    """Append incorrect attempt to log"""
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d"),
        "verb": verb,
        "tense": tense,
        "subject": subject,
        "user_input": user_input,
        "correct_answer": correct_answer
    }

    log_df = pd.DataFrame([log_entry])
    if os.path.exists(log_path):
        log_df.to_csv(log_path, mode="a", header=False, index=False)
    else:
        log_df.to_csv(log_path, mode="w", header=True, index=False)