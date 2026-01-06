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

# Get API key
api_key = os.getenv("OPENAI_API_KEY", "")

# Configuration section
with st.expander("⚙️ Configuration", expanded=not api_key):
    api_key_input = st.text_input(
        "OpenAI API Key",
        value=api_key,
        type="password",
        help="Enter your OpenAI API key. Get one at https://platform.openai.com/api-keys"
    )
    if api_key_input:
        api_key = api_key_input
    
    col1, col2 = st.columns(2)
    with col1:
        voice_option = st.selectbox(
            "Voice",
            ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
            index=0,
            help="Choose the voice for the AI assistant"
        )
    with col2:
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
        height=150
    )

# Check if API key is available
if not api_key:
    st.warning("⚠️ Please enter your OpenAI API key in the configuration section above.")
    st.info("""
    **To use this feature, you need:**
    1. An OpenAI API key (get one at https://platform.openai.com/api-keys)
    2. Set it as the environment variable `OPENAI_API_KEY` or enter it above
    """)
    st.stop()

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Main interface
st.markdown("---")
st.markdown("### 🎤 Record your message")

col1, col2 = st.columns([3, 1])

with col1:
    # Audio recording using audio-recorder-streamlit
    audio_bytes = recorder.audio_recorder(
        text="Click the mic button to record (don't press again to stop, just pause speaking)",
        recording_color="#ff4b4b",
        neutral_color="#d3d3d3",
        icon_name="microphone",
        icon_size="2x",
    )

with col2:
    if st.button("🗑️ Clear History", type="secondary"):
        st.session_state.conversation_history = []
        st.session_state.audio_response = None
        st.session_state.processing = False
        st.session_state.last_audio_bytes = None
        st.rerun()

# Create a container for status messages that we can clear
status_container = st.container()

# Handle audio processing
if audio_bytes:
    # Check if this is a new recording (not the same as last time)
    if st.session_state.last_audio_bytes != audio_bytes and not st.session_state.get("processing", False):
        st.session_state.last_audio_bytes = audio_bytes
        st.session_state.processing = True
        
        # Check if audio is long enough (minimum 0.1 seconds = ~3200 bytes at 16kHz)
        if len(audio_bytes) < 3200:
            st.warning("⚠️ Audio recording too short. Please record for at least 0.1 seconds.")
            st.session_state.processing = False
            st.session_state.last_audio_bytes = None
        else:
            with status_container:
                st.success("✅ Audio recorded!")
            
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(audio_bytes)
                audio_file_path = tmp_file.name
            
            try:
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
                    
                    # Clear status container after successful processing
                    status_container.empty()
                else:
                    status_container.empty()
                    st.warning("⚠️ No speech detected. Please try again.")
                
                st.session_state.processing = False
                
                # Clean up temp file
                os.unlink(audio_file_path)
                
            except Exception as e:
                st.session_state.processing = False
                status_container.empty()
                
                # Handle specific OpenAI errors
                error_msg = str(e)
                if "audio_too_short" in error_msg or "too short" in error_msg:
                    st.warning("⚠️ Audio recording too short. Please speak for at least 0.1 seconds.")
                elif "invalid_request_error" in error_msg:
                    st.error(f"❌ Audio processing error: {error_msg}")
                else:
                    st.error(f"❌ Error processing audio: {error_msg}")
                
                if os.path.exists(audio_file_path):
                    os.unlink(audio_file_path)

# Display conversation history
if st.session_state.conversation_history:
    st.markdown("---")
    st.markdown("### 💬 Conversation")
    
    # Show conversation
    for i, msg in enumerate(st.session_state.conversation_history):
        if msg["role"] == "user":
            st.markdown(f"**🗣️ You:** {msg['content']}")
        else:
            st.markdown(f"**🤖 Assistant:** {msg['content']}")
        
        if i < len(st.session_state.conversation_history) - 1:
            st.markdown("")
    
    # Play the latest audio response at the end
    if st.session_state.audio_response:
        st.markdown("---")
        st.markdown("**🔊 Listen to the response:**")
        st.audio(st.session_state.audio_response, format="audio/mp3")

# Information section
with st.expander("ℹ️ How to use"):
    st.markdown("""
    1. **Record**: Click the microphone button and speak in French
    2. **Stop**: Click the button again when done (or automatic silence detection will stop after ~3 seconds of quiet)
    3. **Listen**: The AI will respond in spoken French
    4. **Continue**: Keep the conversation going!
    
    **Tips:**
    - Speak clearly and at a normal pace
    - The AI understands casual French conversation
    - You can ask for corrections, explanations, or just chat
    - Use the Clear History button to start fresh
    - The recording will auto-stop after ~3 seconds of silence
    """)

st.markdown("---")
st.caption("💡 **Tip:** The AI is here to help you practice! Don't worry about mistakes - they're part of learning.")
