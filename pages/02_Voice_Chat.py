import os
import io
import streamlit as st
import openai
from st_audiorec import st_audiorec

st.title("🗣️ French Voice Conversation")

# openai.api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar.form("persona_form"):
    st.header("Conversation Setup")
    name = st.text_input("Name", "Paul")
    age = st.text_input("Age", "30")
    city = st.text_input("City", "Paris")
    background = st.text_area("Other details")
    mode = st.radio("Mode", ["Friend", "Teacher"])
    submitted = st.form_submit_button("Start / Reset")

if submitted:
    persona = f"You are {name}, a {age} year old from {city}. {background}".strip()
    intro = (
        f"Act as {name}, a native French speaker from {city}. Begin the conversation "
        f"in French and reference a recent news headline from {city}."
    )
    if mode == "Teacher":
        intro += (" Correct the user's most important mistakes when it is your turn "
                   "to speak.")
    st.session_state.messages = [{"role": "system", "content": persona + " " + intro}]

for msg in st.session_state.messages[1:]:
    speaker = "You" if msg["role"] == "user" else name
    st.markdown(f"**{speaker}:** {msg['content']}")
    if msg.get("audio"):
        st.audio(msg["audio"], format="audio/mp3")

st.subheader("🎙️ Speak")
# audio_data = st_audiorec(key="aud")
audio_data = st_audiorec()
send_button = st.button("Send", disabled=audio_data is None)
if audio_data is not None and send_button:
    audio_file = io.BytesIO(audio_data)
    audio_file.name = "speech.wav"
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    user_text = transcript["text"].strip()
    display_text = user_text

    if mode == "Friend":
        correction = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Correct the grammar and spelling of this French text without changing its meaning."},
                {"role": "user", "content": user_text}
            ]
        )
        display_text = correction.choices[0].message.content.strip()
        user_text = display_text

    st.session_state.messages.append({"role": "user", "content": display_text})

    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=st.session_state.messages
    )
    reply = completion.choices[0].message.content.strip()
    speech = openai.audio.speech.create(model="tts-1", voice="nova", input=reply)
    st.session_state.messages.append({"role": "assistant", "content": reply, "audio": speech.content})
    st.rerun()