# --- Streamlit Voice Tab (drop-in) ---
import streamlit as st
import asyncio, base64, json, os, sys, threading, queue, time, signal
import numpy as np
import sounddevice as sd
import websockets
import queue
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# ---------- minimal reuse of your classes ----------
class AudioPlayer:
    def __init__(self, samplerate: int, output_device=None, log_q: queue.Queue|None=None):
        self.sr = samplerate
        self.output_device = output_device
        self.q: "queue.Queue[bytes|None]" = queue.Queue()
        self._stop = threading.Event()
        self._thr = threading.Thread(target=self._run, daemon=True)
        self.log_q = log_q

    def start(self):
        self._thr.start()

    def stop(self):
        self._stop.set()
        self.q.put(None)
        self._thr.join(timeout=1.0)

    def enqueue(self, pcm_bytes: bytes):
        self.q.put(pcm_bytes)

    def clear(self):
        with self.q.mutex:
            self.q.queue.clear()

    def _run(self):
        try:
            if self.output_device is not None:
                sd.default.device = (sd.default.device[0], self.output_device)
        except Exception as e:
            if self.log_q: self.log_q.put(f"[player] device set error: {e}")
        while not self._stop.is_set():
            item = self.q.get()
            if item is None: break
            try:
                arr = np.frombuffer(item, dtype=np.int16)
                sd.play(arr, self.sr, blocking=True)
            except Exception as e:
                if self.log_q: self.log_q.put(f"[player] playback error: {e}")

class MicStream:
    def __init__(self, samplerate: int, chunk_ms: int = 50, device=None):
        self.sr = samplerate
        self.chunk_ms = chunk_ms
        self.device = device
        self.q: asyncio.Queue[bytes] = asyncio.Queue()
        self.stream = None

    def _cb(self, indata, frames, time_info, status):
        if status: pass
        self.q.put_nowait(bytes(indata))

    def start(self):
        blocksize = int(self.sr * (self.chunk_ms/1000.0))
        self.stream = sd.RawInputStream(
            samplerate=self.sr, channels=1, dtype='int16',
            callback=self._cb, blocksize=blocksize, device=self.device
        )
        self.stream.start()

    def stop(self):
        if self.stream:
            self.stream.stop(); self.stream.close(); self.stream = None

# ---------- runner (async) ----------
async def realtime_session_streamlit(
    api_key: str, model: str, voice: str, sr: int, chunk_ms: int,
    system_prompt: str, barge_in: bool, input_device: int|None, output_device: int|None,
    stop_flag: dict, log_q: queue.Queue, controls: dict
):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
    }
    url = f"wss://api.openai.com/v1/realtime?model={model}"

    # for clean shutdown from UI
    # def _sigint(*_): stop_flag["stop"] = True
    # signal.signal(signal.SIGINT, _sigint)

    async with websockets.connect(url, additional_headers=headers, ping_interval=20) as ws:
        # Configure session (accent/style lives in instructions)
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "voice": voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "instructions": system_prompt,
                # enable server-side input transcription if desired:
                # "input_audio_transcription": {"model": "gpt-4o-transcribe"},
            },
        }))

        player = AudioPlayer(sr, output_device=output_device, log_q=log_q); player.start()
        mic = MicStream(sr, chunk_ms=chunk_ms, device=input_device)

        recording = False
        expecting_audio = False
        audio_buf = bytearray()
        captured_ms = 0
        awaiting_response = False
        last_enter = 0.0
        send_lock = asyncio.Lock()

        # ---- recv loop ----
        async def recv_loop():
            nonlocal expecting_audio, awaiting_response
            current_chunks = []
            while not stop_flag["stop"]:
                msg_raw = await ws.recv()
                if isinstance(msg_raw, (bytes, bytearray)):
                    continue
                msg = json.loads(msg_raw)
                t = msg.get("type")

                if t == "error":
                    err = msg.get("error", {})
                    code = err.get("code")
                    if code != "response_cancel_not_active":
                        log_q.put(f"[error] {msg}")
                    if code == "input_audio_buffer_commit_empty":
                        awaiting_response = False
                    continue

                # audio out (both shapes)
                if t in ("response.audio.delta", "output_audio.delta"):
                    expecting_audio = True
                    b64 = msg.get("delta") or msg.get("audio")
                    if b64:
                        current_chunks.append(base64.b64decode(b64))
                    continue

                if t in ("response.audio.done", "output_audio.done"):
                    if current_chunks:
                        pcm = b"".join(current_chunks); current_chunks = []
                        player.enqueue(pcm)
                    continue

                if t in ("response.completed", "response.done"):
                    expecting_audio = False
                    awaiting_response = False
                    continue

                if t == "input_audio_buffer.committed":
                    log_q.put(f"[server] committed: {msg.get('item_id')}")
                    continue

                if t.endswith("transcript.done"):
                    log_q.put(f"[transcript] {msg.get('transcript')}")
                    continue

                if t.startswith("response."):
                    log_q.put(f"[debug] {t}")

        # ---- mic loop ----
        async def mic_loop():
            nonlocal recording, audio_buf, captured_ms
            while not stop_flag["stop"]:
                if recording:
                    try:
                        chunk = await asyncio.wait_for(mic.q.get(), timeout=0.2)
                    except asyncio.TimeoutError:
                        await asyncio.sleep(0)
                        continue
                    if chunk:
                        audio_buf += chunk
                        captured_ms += chunk_ms
                else:
                    await asyncio.sleep(0.01)

        # ---- UI control (push-to-talk) via Streamlit buttons ----
        # We read session_state flags that the Streamlit UI toggles.
        async def control_loop():
            nonlocal recording, audio_buf, captured_ms, expecting_audio, awaiting_response, last_enter
            while not stop_flag["stop"]:
                await asyncio.sleep(0.05)

                # start recording when record event is set
                if (not recording) and controls.get("record", False):
                    controls["record"] = False
                    if awaiting_response:
                        log_q.put("[debug] response in progress; wait.")
                        continue
                    if barge_in and expecting_audio:
                        await ws.send(json.dumps({"type": "response.cancel"}))
                        player.clear()
                    mic.start()
                    recording = True
                    audio_buf = bytearray(); captured_ms = 0
                    log_q.put("[rec] start")

                # stop & send when send event is set
                if recording and controls.get("send", False):
                    controls["send"] = False
                    recording = False
                    mic.stop()
                    min_ms = max(100, 200)
                    if captured_ms < min_ms or len(audio_buf) < int(sr * (min_ms/1000)) * 2:
                        log_q.put(f"[rec] too short ({captured_ms} ms) -> discard")
                        audio_buf = bytearray(); captured_ms = 0
                        continue

                    async with send_lock:
                        if awaiting_response:
                            log_q.put("[debug] response in progress; skip send")
                            audio_buf = bytearray(); captured_ms = 0
                            continue
                        awaiting_response = True

                        await ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(audio_buf).decode("ascii")
                        }))
                        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                        log_q.put(f"[rec] sent {captured_ms} ms")
                        await ws.send(json.dumps({
                            "type": "response.create",
                            "response": {"modalities": ["audio", "text"]}
                        }))

                    audio_buf = bytearray(); captured_ms = 0


        tasks = [
            asyncio.create_task(recv_loop()),
            asyncio.create_task(mic_loop()),
            asyncio.create_task(control_loop()),
        ]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        player.stop()

# ---------- Thread wrapper (so Streamlit stays responsive) ----------
def run_loop_in_thread(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro)
    finally:
        loop.stop()
        loop.close()

# ================== STREAMLIT TAB ==================
voice_tab = st.tabs(["Voice Assistant"])[0]

with voice_tab:
    st.subheader("🎙️ Speak to AI")
    if "voice_thread" not in st.session_state:
        st.session_state.voice_thread = None
    if "voice_stop" not in st.session_state:
        st.session_state.voice_stop = {"stop": False}
    if "voice_log" not in st.session_state:
        st.session_state.voice_log = []
    if "voice_log_q" not in st.session_state:
        st.session_state.voice_log_q = queue.Queue()
    # if "voice_log" not in st.session_state:
    #     st.session_state.voice_log = []
    # if "voice_pushtotalk" not in st.session_state:
    #     st.session_state.voice_pushtotalk = False
    # TODO: CHECK IF THIS IS NEEDED

    # Control channel from UI -> worker (don't touch Streamlit from worker)
    if "voice_controls" not in st.session_state:
        st.session_state.voice_controls = {"record": False, "send": False} # push-to-talk flag

    # def _on_ptt_change():
        # Mirror widget value into thread-safe dict
        # st.session_state.voice_controls["ptt"] = st.session_state.voice_ptt

    # --- Controls ---
    with st.expander("Options", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            api_key = st.text_input("OPENAI_API_KEY", type="password", value=os.getenv("OPENAI_API_KEY",""))
            model = st.selectbox("Model", ["gpt-4o-realtime-preview"], index=0)
            voice = st.selectbox("Voice", ["verse", "alloy", "aria", "sage"], index=0)
        with col2:
            sr = st.selectbox("Sample rate", [24000, 16000], index=0)
            chunk_ms = st.slider("Mic chunk (ms)", 10, 100, 20, step=10)
            barge_in = st.checkbox("Barge-in (cancel current speech on talk)", value=True)
        with col3:
            input_dev = st.number_input("Input device index", value=0, step=1)
            output_dev = st.number_input("Output device index", value=sd.default.device[1] if sd.default.device else 0, step=1)
            st.caption("Use `python -c 'import sounddevice as sd; print(sd.query_devices())'` to find indexes.")

        system_prompt = st.text_area(
            "System instructions (accent/style etc.)",
            value="Speak French with a nicely understandable Parisian accent. Don't talk too slow, talk like a regular Parisian, use slang if known to you. " \
                    "Be nice, supportive and talkative like a French teacher."
        )

        # Push-to-talk button (hold-to-speak feel: toggle on while pressed)
        # Streamlit buttons are click events; emulate a hold with a toggle.
    # talk = st.toggle("Hold to talk (press to start, press again to send)",
    #                value=False,
    #                # key="voice_pushtotalk" # TODO: CHECK IF THIS IS NEEDED
    #                key="voice_ptt",
    #                on_change=_on_ptt_change,
    #                )

    colA, colB = st.columns(2)
    with colA:
        if st.button("🎙️ Talk", disabled=st.session_state.voice_thread is None):
            st.session_state.voice_controls["record"] = True
    with colB:
        if st.button("📤 Send", disabled=st.session_state.voice_thread is None):
            st.session_state.voice_controls["send"] = True

    session_active = st.toggle("Session active", value=st.session_state.voice_thread is not None)

    # --- Start / Stop behavior ---
    if session_active and st.session_state.voice_thread is None:
        if not api_key:
            st.error("Provide OPENAI_API_KEY.")
        else:
            st.session_state.voice_stop = {"stop": False}
            args = dict(
                api_key=api_key, model=model, voice=voice, sr=int(sr), chunk_ms=int(chunk_ms),
                system_prompt=system_prompt, barge_in=barge_in,
                input_device=int(input_dev) if input_dev is not None else None,
                output_device=int(output_dev) if output_dev is not None else None,
                stop_flag=st.session_state.voice_stop,
                log_q=st.session_state.voice_log_q,
                controls=st.session_state.voice_controls,
            )
            st.session_state.voice_thread = threading.Thread(
                target=run_loop_in_thread,
                args=(realtime_session_streamlit(**args),),
                daemon=True
            )
            st.session_state.voice_thread.start()
            st.success("Session started. Use **Talk** then **Send** to speak.")

    if (not session_active) and st.session_state.voice_thread is not None:
        st.session_state.voice_stop["stop"] = True
        st.session_state.voice_thread.join(timeout=2.0)
        st.session_state.voice_thread = None
        st.session_state.voice_controls["record"] = False
        st.session_state.voice_controls["send"] = False
        st.success("Session stopped.")

    # live log
    # Optional auto-refresh for smoother logs
    if st_autorefresh:
        st_autorefresh(interval=500, key="voice_log_refresh")  # every 0.5s

    # Drain background log queue into the UI list
    q = st.session_state.voice_log_q
    while not q.empty():
        try:
            st.session_state.voice_log.append(q.get_nowait())
        except queue.Empty:
            break
    st.divider()
    st.caption("Session log")
    st.code("\n".join(st.session_state.voice_log[-200:]) or "(no messages yet)", language="text")




# FEATURE IDEAS
# Fix cackling sound output
# Make responses come in quicker (if possible)
# Make the persona more Parisian-like of a 30-something year old.
# Set further instruction options such as teaching style (corrections or not, vocabulary tips, etc.)
# Integrate knowledge of current events, weather and so on
# Maybe move sound in-/output to browser instead of machine
# Fix the button styles for a easier flow of conversation
# Allow for direct voice detection instead of taking turns based on clicks?
