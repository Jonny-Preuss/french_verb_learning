
#!/usr/bin/env python3
"""
Desktop Realtime Voice (Push-to-Talk) for OpenAI Realtime API (Fixed)
- Callback-based microphone (reliable on macOS)
- Push-to-talk on Enter
- Optional barge-in: cancel model speech only if audio is playing
- Requests BOTH audio and text back
- Guards against empty/too-short audio commits
"""

import asyncio, base64, json, os, sys, threading, getpass, queue, signal, argparse
import numpy as np
import sounddevice as sd
import websockets

DEFAULT_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")
DEFAULT_VOICE = os.getenv("OPENAI_REALTIME_VOICE", "verse")
DEFAULT_SR    = int(os.getenv("OPENAI_REALTIME_SR", "16000"))

def get_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    return getpass.getpass("Enter OPENAI_API_KEY: ")

class AudioPlayer:
    """Plays PCM16 mono at a fixed sample rate in a background thread."""
    def __init__(self, samplerate: int):
        self.sr = samplerate
        self.q: "queue.Queue[bytes|None]" = queue.Queue()
        self._stop = threading.Event()
        self._thr = threading.Thread(target=self._run, daemon=True)

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
        while not self._stop.is_set():
            item = self.q.get()
            if item is None:
                break
            try:
                arr = np.frombuffer(item, dtype=np.int16)
                sd.play(arr, self.sr, blocking=True)
            except Exception as e:
                print(f"[player] playback error: {e}", file=sys.stderr)

# --- Callback mic ---
class MicStream:
    """Raw callback mic -> asyncio.Queue of PCM16 bytes."""
    def __init__(self, samplerate: int, chunk_ms: int = 50, device=None):
        self.sr = samplerate
        self.chunk_ms = chunk_ms
        self.bytes_per_chunk = int(self.sr * (chunk_ms/1000.0)) * 2  # 16-bit mono
        self.device = device
        self.q: asyncio.Queue[bytes] = asyncio.Queue()
        self.stream = None

    def _cb(self, indata, frames, time_info, status):
        if status:
            # print(status)  # uncomment for troubleshooting
            pass
        self.q.put_nowait(bytes(indata))

    def start(self):
        self.stream = sd.RawInputStream(
            samplerate=self.sr, channels=1, dtype='int16',
            callback=self._cb, blocksize=int(self.sr*0.02),  # 20ms
            device=self.device
        )
        self.stream.start()

    def stop(self):
        if self.stream:
            self.stream.stop(); self.stream.close(); self.stream = None

async def user_input(prompt: str = "") -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: input(prompt))

async def realtime_session(args):
    api_key = get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
    }
    url = f"wss://api.openai.com/v1/realtime?model={args.model}"

    stop_flag = {"stop": False}
    def _sigint(*_):
        stop_flag["stop"] = True
    signal.signal(signal.SIGINT, _sigint)

    # websockets v15+ uses additional_headers
    async with websockets.connect(url, additional_headers=headers, ping_interval=20) as ws:
        # Configure session
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "voice": args.voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "instructions": args.system_prompt,
            },
        }))
        print(f"Connected. Model={args.model}, Voice={args.voice}, SR={args.sr}\n")
        print("Controls:\n  Enter = start/stop talking (push-to-talk)\n  /s = stop current model speech (barge-in)\n  /q = quit\n")

        player = AudioPlayer(args.sr); player.start()
        mic = MicStream(args.sr, chunk_ms=args.chunk_ms, device=args.input_device)

        # State
        recording = False
        expecting_audio = False
        audio_buf = bytearray()
        captured_ms = 0
        awaiting_response = False

        async def recv_loop():
            nonlocal expecting_audio, awaiting_response
            current_chunks = []
            while True:
                msg_raw = await ws.recv()
                if isinstance(msg_raw, (bytes, bytearray)):
                    continue
                msg = json.loads(msg_raw)
                t = msg.get("type")

                if t == "error":
                    err = msg.get("error", {})
                    code = err.get("code")
                    if code == "response_cancel_not_active":
                        continue
                    print(f"[error] {msg}", file=sys.stderr)

                elif t == "output_audio.delta":
                    expecting_audio = True
                    b = base64.b64decode(msg["audio"])
                    current_chunks.append(b)

                elif t == "output_audio.done":
                    pcm = b"".join(current_chunks); current_chunks = []
                    player.enqueue(pcm)

                elif t in ("response.completed", "response.done"):
                    expecting_audio = False
                    awaiting_response = False

                elif t.startswith("response."):
                    print("[debug]", t, msg)

        async def mic_loop():
            nonlocal recording, audio_buf, captured_ms
            while True:
                if recording:
                    try:
                        chunk = await asyncio.wait_for(mic.q.get(), timeout=0.2)
                    except asyncio.TimeoutError:
                        await asyncio.sleep(0)
                        continue
                    if chunk:
                        audio_buf += chunk
                        captured_ms += 20  # 20ms per callback block
                else:
                    await asyncio.sleep(0.01)

        async def control_loop():
            nonlocal recording, audio_buf, captured_ms, expecting_audio, awaiting_response
            while True:
                cmd = (await user_input(">> ")).strip()
                if cmd == "":
                    if not recording:
                        # Start recording
                        if args.barge_in and expecting_audio:
                            await ws.send(json.dumps({"type": "response.cancel"}))
                            player.clear()
                        mic.start()
                        recording = True
                        audio_buf = bytearray()
                        captured_ms = 0
                        print("[rec] ... speak ... (press Enter to send)")
                    else:
                        # Stop, commit, request response
                        recording = False
                        mic.stop()

                        min_ms = max(100, args.min_ms)  # server wants >=100ms
                        if captured_ms < min_ms or len(audio_buf) < int(args.sr * min_ms/1000) * 2:
                            print(f"[rec] too little audio recorded ({captured_ms} ms), discarded.")
                            audio_buf = bytearray()
                            continue

                        # 1) Send the full buffered audio once
                        await ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(audio_buf).decode("ascii")
                        }))
                        # 2) Commit
                        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                        print(f"[rec] sent {captured_ms} ms ({len(audio_buf)} bytes). Waiting for reply...")

                        # 3) Create ONE response
                        if not awaiting_response:
                            awaiting_response = True
                            await ws.send(json.dumps({
                                "type": "response.create",
                                "response": {"modalities": ["audio", "text"]}
                            }))
                        else:
                            print("[debug] skipped response.create (already awaiting).")
                        # reset local buffer for next turn
                        audio_buf = bytearray()
                        captured_ms = 0
                elif cmd == "/s":
                    if expecting_audio:
                        await ws.send(json.dumps({"type": "response.cancel"}))
                        player.clear()
                        print("[barge-in] canceled model speech.")
                    else:
                        print("[barge-in] nothing to cancel.")
                elif cmd == "/q":
                    print("Exiting...")
                    break
                else:
                    print("Unknown command. Use Enter, /s, or /q.")

        tasks = [
            asyncio.create_task(recv_loop()),
            asyncio.create_task(mic_loop()),
            asyncio.create_task(control_loop()),
        ]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        player.stop()

def main():
    p = argparse.ArgumentParser(description="Desktop Realtime Voice (Push-to-Talk)")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Realtime model name")
    p.add_argument("--voice", default=DEFAULT_VOICE, help="Realtime voice (e.g., verse, alloy)")
    p.add_argument("--sr", type=int, default=DEFAULT_SR, help="Sample rate (Hz)")
    p.add_argument("--chunk-ms", type=int, default=50, help="Mic chunk size (ms)")
    p.add_argument("--barge-in", action="store_true", help="Allow Enter to cancel model speech and start recording")
    p.add_argument("--system-prompt", default="Be concise and helpful.", help="System instructions")
    p.add_argument("--input-device", type=int, default=None, help="Input device index (see sd.query_devices())")
    p.add_argument("--min-ms", type=int, default=200, help="Minimum audio duration to accept (ms)")
    args = p.parse_args()
    asyncio.run(realtime_session(args))

if __name__ == "__main__":
    main()
