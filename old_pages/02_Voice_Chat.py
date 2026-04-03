"""
Voice Chat Tab for French Verb Learning
Uses OpenAI API for low-latency voice conversations in French
"""

import streamlit as st
import os
from openai import OpenAI
import tempfile
import audio_recorder_streamlit as recorder

# Page config
st.set_page_config(page_title="Voice Chat", page_icon="🎙️", layout="wide")

st.title("🎙️ Voice Chat - Parlez Français!")

# Initialize session state
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "audio_response" not in st.session_state:
    st.session_state.audio_response = None
if "processing" not in st.session_state:
    st.session_state.processing = False
if "last_audio_bytes" not in st.session_state:
    st.session_state.last_audio_bytes = None
if "status_message" not in st.session_state:
    st.session_state.status_message = None

# Information section at the top
with st.expander("ℹ️ How to use"):
    st.markdown("""
    1. **Record**: Click the microphone button on the left and speak in French
    2. **Stop**: The recording will auto-stop after ~3 seconds of silence
    3. **Listen**: The AI's response plays at the top of the conversation
    4. **Continue**: Keep the conversation going!
    
    **Tips:**
    - Speak clearly and at a normal pace
    - The AI understands casual French conversation
    - You can ask for corrections, explanations, or just chat
    - Use the Clear History button to start fresh
    
    **Troubleshooting:**
    - If audio won't play, check your API key in Settings
    - Make sure you have sufficient OpenAI credits
    - Refresh the page if something seems stuck
    """)

# Get API key
api_key = os.getenv("OPENAI_API_KEY", "")

# Settings expander
with st.expander("⚙️ Settings", expanded=not api_key):
    api_key_input = st.text_input(
        "OpenAI API Key",
        value=api_key,
        type="password",
        help="Enter your OpenAI API key. Get one at https://platform.openai.com/api-keys"
    )
    if api_key_input:
        api_key = api_key_input
    
    voice_option = st.selectbox(
        "Voice",
        ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        index=0,
        help="Choose the voice for the AI assistant"
    )
    
    model_option = st.selectbox(
        "Model",
        ["gpt-4o", "gpt-4-turbo"],
        index=0,
        help="Choose the model for generating responses"
    )
    
    system_prompt = st.text_area(
        "System Prompt",
        value="""Tu es un professeur de français sympathique et patient. Parle avec un accent parisien naturel et agréable à comprendre. 
        
Utilise un vocabulaire quotidien et des expressions françaises courantes. Sois encourageant et aide l'étudiant à améliorer son français de manière naturelle et décontractée.

Parle à un rythme normal, comme un vrai Parisien de 30 ans. N'hésite pas à corriger gentiment les erreurs et à proposer des alternatives plus naturelles.""",
        height=120
    )

# Check if API key is available
if not api_key:
    st.warning("⚠️ Please enter your OpenAI API key in the Settings section above.")
    st.stop()

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

st.markdown("### 🎤 Recording")

# Styled recorder box with background
audio_bytes = recorder.audio_recorder(
    text="Click to record",
    recording_color="#ff4b4b",
    neutral_color="#d3d3d3",
    icon_name="microphone",
    icon_size="3x",
)

# Status container for messages
status_container = st.container()


st.markdown("### 💬 Conversation")

# Play the latest audio response (always show)
if st.session_state.audio_response:
    st.markdown("**🔊 Latest response:**")
    try:
        # Audio player with autoplay
        st.audio(st.session_state.audio_response, format="audio/mpeg", autoplay=True)
    except Exception as e:
        st.error(f"❌ Could not play audio. Error: {str(e)}")
        st.info("Make sure your OpenAI API key is valid and has access to the text-to-speech API.")

st.markdown("---")

# Display conversation history in an expandable section
if st.session_state.conversation_history:
    with st.expander("📜 Full Conversation", expanded=False):
        # Show conversation
        for i, msg in enumerate(st.session_state.conversation_history):
            if msg["role"] == "user":
                st.markdown(f"**🗣️ You:** {msg['content']}")
            else:
                st.markdown(f"**🤖 Assistant:** {msg['content']}")
            
            if i < len(st.session_state.conversation_history) - 1:
                st.markdown("")
    
    st.markdown("---")
    
    # Clear History button
    if st.button("🗑️ Clear History", key="clear_history_btn", type="secondary", use_container_width=True):
        st.session_state.conversation_history = []
        st.session_state.audio_response = None
        st.session_state.processing = False
        st.session_state.last_audio_bytes = None
        st.session_state.status_message = None
        st.rerun()
else:
    st.info("👈 Start recording above to begin the conversation!")

# Handle audio processing (process immediately and update state)
if audio_bytes:
    # Check if this is a new recording (not the same as last time)
    if st.session_state.last_audio_bytes != audio_bytes and not st.session_state.get("processing", False):
        st.session_state.last_audio_bytes = audio_bytes
        st.session_state.processing = True
        st.session_state.status_message = None
        
        # Check if audio is long enough (minimum 0.1 seconds = ~3200 bytes at 16kHz)
        if len(audio_bytes) < 3200:
            st.session_state.status_message = "too_short"
            st.session_state.processing = False
        else:
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(audio_bytes)
                audio_file_path = tmp_file.name
            
            try:
                # Show success status
                with status_container:
                    st.success("✅ Audio recorded!")
                
                # Transcribe audio
                with st.spinner("🎤 Transcribing..."):
                    with open(audio_file_path, "rb") as audio_file:
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            language="fr"
                        )
                
                user_text = transcription.text
                
                # Only add to history if transcription is not empty
                if user_text.strip():
                    st.session_state.conversation_history.append({
                        "role": "user",
                        "content": user_text
                    })
                    
                    # Get response from GPT
                    messages = [
                        {"role": "system", "content": system_prompt}
                    ] + st.session_state.conversation_history
                    
                    with st.spinner("🤔 Thinking..."):
                        response = client.chat.completions.create(
                            model=model_option,
                            messages=messages,
                            max_tokens=500
                        )
                    
                    assistant_text = response.choices[0].message.content
                    st.session_state.conversation_history.append({
                        "role": "assistant",
                        "content": assistant_text
                    })
                    
                    # Generate speech
                    with st.spinner("🔊 Generating speech..."):
                        speech_response = client.audio.speech.create(
                            model="tts-1",
                            voice=voice_option,
                            input=assistant_text,
                            speed=1.0
                        )
                        
                        # Store audio response
                        st.session_state.audio_response = speech_response.content
                    
                    # Mark processing complete
                    st.session_state.processing = False
                    
                    # Force rerun to show results immediately
                    st.rerun()
                else:
                    st.session_state.status_message = "no_speech"
                    st.session_state.processing = False
                
                # Clean up temp file
                os.unlink(audio_file_path)
                
            except Exception as e:
                st.session_state.processing = False
                
                # Handle specific OpenAI errors
                error_msg = str(e)
                if "audio_too_short" in error_msg or "too short" in error_msg:
                    st.session_state.status_message = "too_short"
                elif "401" in error_msg or "Unauthorized" in error_msg or "invalid_api_key" in error_msg:
                    st.session_state.status_message = "invalid_key"
                else:
                    st.session_state.status_message = "error"
                
                if os.path.exists(audio_file_path):
                    os.unlink(audio_file_path)
        
        # Show status message if needed
        if st.session_state.status_message:
            with status_container:
                if st.session_state.status_message == "too_short":
                    st.warning("⚠️ Audio too short (min 0.1s)")
                elif st.session_state.status_message == "no_speech":
                    st.warning("⚠️ No speech detected")
                elif st.session_state.status_message == "invalid_key":
                    st.error("❌ Invalid API key")
                else:
                    st.error("❌ Processing error")

st.caption("💡 **Tip:** The AI is here to help you practice! Don't worry about mistakes - they're part of learning.")
