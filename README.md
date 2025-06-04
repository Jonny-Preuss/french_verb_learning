# 🇫🇷 French Verb Conjugation Trainer

This Streamlit app helps you practice and memorize the conjugations of the 1000 most common French verbs — across various tenses and subject pronouns — in an interactive and gamified way.

## 📦 Features

- Picks a **random verb** that hasn't been completed yet
- Shows a **random tense and subject pronoun**
- Lets you input your conjugation and **checks it against a solution sheet**
- Gives **immediate feedback**:
  - ✅ Correct: Green background
  - ❌ Incorrect: Red background and shows the correct answer
- Empties the cell input when progressing to the next verb
- Saves all answers directly into the Excel file
- Tracks completion status per verb
- Supports restarting or moving to the next verb interactively

## 📁 Project Structure
french_verb_learning/ <br>
├── data/ # --> data input folder with file with "UserInput" and "Solutions" sheets <br>
├── data_prep/ # --> preparatory work to get the correct conjugations for the top-1000 verbs <br>
├── src/ <br>
│ ├── config.py # --> constants and column setup <br>
│ ├── load_data.py # --> Excel loading helpers <br>
│ └── select_input.py # --> random task selector <br>
├── main.py <br>

## 🚀 How to Run

1. 📦 **Install dependencies** (ideally in a virtualenv or conda environment):

   ```bash
   pip install streamlit pandas openpyxl

2. ▶️ Run the app:

    ```bash
    streamlit run main.py

3. 🎯 Follow the on-screen prompts to start conjugating!


## ✨ Future Features (Planned)

- Error-tracking log for a quick review of (repeated) mistakes
- Request example sentences per tense/subject/verb to better imagine the verb in use (practice LLM calling with a pre-defined prompt on a free tier)
- Web-based correctness checking via Le Conjugueur or Reverso (practice agentic tool-use features)

## 📚 License

MIT License. Built for personal learning and language practice.