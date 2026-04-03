"""
Realtime voice chat tab built on OpenAI's WebRTC Realtime API.

This page intentionally lives alongside the legacy upload/transcribe/synthesize
tab so both experiences can be compared in the Streamlit sidebar.
"""

import json
import os
from typing import Any

import requests
import streamlit as st
import streamlit.components.v1 as components


DEFAULT_PROMPT = """Tu es Lucie, une partenaire de conversation francaise tres naturelle et chaleureuse.

Objectif:
- Aider l'utilisateur a parler francais de maniere fluide et detendue.
- Prioriser la conversation orale naturelle, pas les explications longues.
- Corriger seulement les erreurs importantes ou recurrentes, de facon breve et encourageante.
- Si un contexte d'actualite recente est fourni, commence par proposer trois sujets tires uniquement de ce contexte et demande lequel l'utilisateur veut choisir.

Style:
- Parle uniquement en francais sauf si l'utilisateur demande autre chose.
- Garde des reponses vocales plutot courtes, vivantes et conversationnelles.
- Pose souvent une question de suivi pour maintenir le rythme.
- Quand l'utilisateur hesite, aide-le doucement au lieu de changer de sujet.
- Si l'utilisateur parle d'un verbe ou fait une erreur de conjugaison, integre une mini-correction naturelle dans ta reponse.
- N'invente jamais une actualite recente si aucun contexte recent ne t'a ete fourni.
"""

VOICE_OPTIONS = [
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "sage",
    "shimmer",
    "verse",
]

TOPIC_OPTIONS = [
    "Politics",
    "Arts and culture",
    "Sports",
    "Business and economy",
    "Science and technology",
    "Environment",
    "Society",
    "Food and lifestyle",
]


def _build_live_context_search_prompt(
    *,
    focus_place: str,
    topic_labels: list[str],
    days_back: int,
    include_weather: bool,
) -> str:
    topic_text = ", ".join(topic_labels) if topic_labels else "general current affairs"
    place_text = focus_place.strip() or "France or Paris"
    weather_block = ""
    if include_weather:
        weather_block = f"""
Also find the current weather for {focus_place.strip() or "Paris, France"}.

Weather rules:
- Write one short sentence in natural French.
- Mention the overall conditions and, if available, the current temperature or a close approximation.
- Keep it under 22 words.
"""
    return f"""Find three distinct current news topics about {place_text} from the last {days_back} days that would work well as conversational openers for a French learner.

News rules:
- Exactly 3 topics.
- Write the titles and summaries in natural French.
- Each summary must be one sentence only.
- Keep each title under 16 words.
- Keep each summary under 28 words.
- Focus on topics that are understandable in a conversation setting.
- Prefer these topic areas when possible: {topic_text}.
{weather_block}
Return valid JSON only.
"""


def _extract_response_text(response_data: dict[str, Any]) -> str:
    output_text = response_data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    chunks: list[str] = []
    for item in response_data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            text_value = content.get("text")
            if isinstance(text_value, str) and text_value.strip():
                chunks.append(text_value)
    return "\n".join(chunks).strip()


def _parse_live_context(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_live_context(
    api_key: str,
    *,
    focus_place: str,
    topic_labels: list[str],
    days_back: int,
    include_weather: bool,
) -> dict[str, Any]:
    schema_properties: dict[str, Any] = {
        "topics": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title_fr": {"type": "string"},
                    "summary_fr": {"type": "string"},
                },
                "required": ["title_fr", "summary_fr"],
            },
        }
    }
    required_fields = ["topics"]
    if include_weather:
        schema_properties["weather_fr"] = {"type": "string"}
        required_fields.append("weather_fr")

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4.1-mini",
            "tools": [
                {
                    "type": "web_search",
                    "user_location": {
                        "type": "approximate",
                        "country": "FR",
                        "city": "Paris",
                        "region": "Ile-de-France",
                    },
                }
            ],
            "tool_choice": "required",
            "input": _build_live_context_search_prompt(
                focus_place=focus_place,
                topic_labels=topic_labels,
                days_back=days_back,
                include_weather=include_weather,
            ),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "live_practice_context",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": schema_properties,
                        "required": required_fields,
                    },
                }
            },
        },
        timeout=40,
    )

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("Could not decode the live practice context response.") from exc

    if response.status_code >= 400:
        message = data.get("error", {}).get("message") if isinstance(data, dict) else None
        raise RuntimeError(message or "Could not fetch live practice context.")

    raw_text = _extract_response_text(data)
    if not raw_text:
        raise RuntimeError("The live practice search returned no usable text.")

    payload = _parse_live_context(raw_text)
    topics = []
    for topic in payload.get("topics", [])[:3]:
        title = str(topic.get("title_fr", "")).strip()
        summary = str(topic.get("summary_fr", "")).strip()
        if title and summary:
            topics.append({"title_fr": title, "summary_fr": summary})
    if len(topics) != 3:
        raise RuntimeError("The news search did not return exactly three usable topics.")

    weather_summary = str(payload.get("weather_fr", "")).strip() if include_weather else ""
    if include_weather and not weather_summary:
        raise RuntimeError("The weather search did not return a usable weather summary.")

    return {
        "topics": topics,
        "weather_summary": weather_summary,
    }


def _build_news_context(topics: list[dict[str, str]]) -> str:
    lines = [
        "Contexte d'actualite recente pour commencer la conversation.",
        "Utilise uniquement ces sujets comme base pour l'ouverture si l'utilisateur veut parler d'actualite.",
    ]
    for index, topic in enumerate(topics, start=1):
        lines.append(f"{index}. {topic['title_fr']} - {topic['summary_fr']}")
    return "\n".join(lines)


def _build_weather_context(focus_place: str, weather_summary: str) -> str:
    return (
        "Contexte meteo actuel pour la conversation.\n"
        f"Lieu: {focus_place.strip() or 'Paris, France'}.\n"
        f"Meteo: {weather_summary}"
    )


def _build_greeting(topics: list[dict[str, str]]) -> str:
    if len(topics) != 3:
        return (
            "Salue l'utilisateur tres naturellement en francais, puis demande-lui simplement "
            "de quoi il aimerait parler aujourd'hui."
        )

    topic_lines = "\n".join(
        f"{index}. {topic['title_fr']} - {topic['summary_fr']}"
        for index, topic in enumerate(topics, start=1)
    )
    return (
        "Salue l'utilisateur tres naturellement en francais, puis propose exactement ces trois "
        "sujets d'actualite en une formulation simple et orale. Ne rajoute pas d'autres sujets. "
        "Termine en demandant lequel il prefere.\n"
        f"{topic_lines}"
    )


def _mint_realtime_client_secret(
    api_key: str,
    *,
    voice: str,
    instructions: str,
) -> dict[str, Any]:
    payload = {
        "session": {
            "type": "realtime",
            "model": "gpt-realtime",
            "instructions": instructions,
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "transcription": {
                        "model": "gpt-4o-transcribe",
                        "language": "fr",
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "create_response": True,
                        "interrupt_response": True,
                        "prefix_padding_ms": 400,
                        "silence_duration_ms": 3000,
                    }
                },
                "output": {
                    "voice": voice,
                },
            },
        }
    }

    response = requests.post(
        "https://api.openai.com/v1/realtime/client_secrets",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )

    try:
        data = response.json()
    except ValueError:
        data = {"raw_text": response.text}

    if response.status_code >= 400:
        message = data.get("error", {}).get("message") if isinstance(data, dict) else None
        raise RuntimeError(message or response.text or "Unknown OpenAI error while minting client secret.")

    if not isinstance(data, dict):
        raise RuntimeError("Unexpected response while minting client secret.")

    return data


def _build_realtime_component(
    *,
    client_secret: str,
    voice: str,
    instructions: str,
    greeting: str,
) -> str:
    config_json = json.dumps(
        {
            "clientSecret": client_secret,
            "voice": voice,
            "instructions": instructions,
            "model": "gpt-realtime",
            "greeting": greeting,
        }
    )

    return f"""
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
      :root {{
        --bg: #f5efe4;
        --panel: rgba(255, 251, 245, 0.86);
        --panel-strong: #fffaf2;
        --ink: #1f1b16;
        --muted: #6e6256;
        --line: rgba(64, 51, 35, 0.12);
        --accent: #0d8a72;
        --accent-2: #ff7a59;
        --accent-3: #165dff;
        --danger: #b5332f;
        --shadow: 0 18px 50px rgba(80, 56, 24, 0.12);
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        font-family: "Avenir Next", "Segoe UI", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(255, 177, 120, 0.35), transparent 32%),
          radial-gradient(circle at top right, rgba(22, 93, 255, 0.12), transparent 26%),
          linear-gradient(180deg, #f9f3e7 0%, #f4ede2 100%);
        overflow: hidden;
      }}

      .shell {{
        max-width: 1120px;
        margin: 0 auto;
        padding: 24px 20px 28px;
        height: 100vh;
        overflow: hidden;
      }}

      .hero {{
        display: grid;
        grid-template-columns: minmax(320px, 520px) minmax(320px, 1fr);
        gap: 18px;
        align-items: stretch;
        height: 100%;
      }}

      .card {{
        background: var(--panel);
        backdrop-filter: blur(12px);
        border: 1px solid var(--line);
        border-radius: 28px;
        box-shadow: var(--shadow);
      }}

      .stage {{
        padding: 28px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 100%;
        min-height: 0;
        overflow: hidden;
      }}

      .eyebrow {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-radius: 999px;
        background: rgba(13, 138, 114, 0.1);
        color: var(--accent);
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-weight: 700;
      }}

      h1 {{
        margin: 16px 0 10px;
        font-size: clamp(32px, 5vw, 54px);
        line-height: 0.95;
        letter-spacing: -0.04em;
      }}

      .lede {{
        margin: 0 0 22px;
        color: var(--muted);
        font-size: 15px;
        line-height: 1.6;
        max-width: 40ch;
      }}

      .orb-wrap {{
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 10px 0 26px;
      }}

      .orb-ring {{
        width: 240px;
        height: 240px;
        border-radius: 50%;
        display: grid;
        place-items: center;
        background:
          radial-gradient(circle at 30% 30%, rgba(255,255,255,0.72), transparent 36%),
          conic-gradient(from 210deg, #ff9966, #ffd166, #0d8a72, #165dff, #ff9966);
        box-shadow:
          inset 0 2px 18px rgba(255,255,255,0.4),
          0 18px 44px rgba(22, 93, 255, 0.18);
        position: relative;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
      }}

      .orb-ring::after {{
        content: "";
        position: absolute;
        inset: 16px;
        border-radius: 50%;
        background:
          radial-gradient(circle at 35% 30%, rgba(255,255,255,0.88), rgba(255,255,255,0.08) 38%, rgba(9,20,31,0.12) 100%),
          linear-gradient(180deg, rgba(255,255,255,0.84), rgba(255,255,255,0.36));
      }}

      .orb-core {{
        position: relative;
        z-index: 1;
        width: 132px;
        height: 132px;
        border: none;
        border-radius: 50%;
        background:
          radial-gradient(circle at 30% 30%, #ffffff, #ffd9cf 34%, #ff8d6d 68%, #d74c2f 100%);
        color: #471b14;
        box-shadow:
          inset 0 10px 16px rgba(255,255,255,0.55),
          0 12px 24px rgba(183, 61, 36, 0.26);
        font-size: 44px;
        cursor: pointer;
        transition: transform 0.18s ease, filter 0.18s ease;
      }}

      .orb-core:hover {{
        transform: scale(1.03);
        filter: saturate(1.06);
      }}

      .orb-core:disabled {{
        cursor: wait;
        opacity: 0.76;
      }}

      .stage.listening .orb-ring {{
        animation: breathing 1.8s ease-in-out infinite;
        box-shadow:
          inset 0 2px 18px rgba(255,255,255,0.4),
          0 22px 54px rgba(13, 138, 114, 0.24);
      }}

      .stage.speaking .orb-ring {{
        animation: speaking 0.9s ease-in-out infinite;
        box-shadow:
          inset 0 2px 18px rgba(255,255,255,0.44),
          0 24px 62px rgba(22, 93, 255, 0.24);
      }}

      .stage.connecting .orb-ring {{
        animation: spinpulse 1.4s linear infinite;
      }}

      @keyframes breathing {{
        0%, 100% {{ transform: scale(1); }}
        50% {{ transform: scale(1.05); }}
      }}

      @keyframes speaking {{
        0%, 100% {{ transform: scale(1); }}
        25% {{ transform: scale(1.06); }}
        75% {{ transform: scale(1.1); }}
      }}

      @keyframes spinpulse {{
        0% {{ transform: rotate(0deg) scale(1); }}
        50% {{ transform: rotate(180deg) scale(1.04); }}
        100% {{ transform: rotate(360deg) scale(1); }}
      }}

      .status-row {{
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-bottom: 12px;
      }}

      .chip {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 14px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 700;
        background: var(--panel-strong);
        border: 1px solid var(--line);
        color: var(--ink);
      }}

      .chip.live {{
        color: var(--accent);
      }}

      .status-copy {{
        min-height: 52px;
      }}

      .status-title {{
        margin: 0 0 6px;
        font-size: 22px;
        letter-spacing: -0.03em;
      }}

      .status-text {{
        margin: 0;
        color: var(--muted);
        line-height: 1.55;
        font-size: 14px;
      }}

      .controls {{
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-top: 20px;
      }}

      .action {{
        border: none;
        border-radius: 16px;
        padding: 14px 18px;
        font-size: 14px;
        font-weight: 700;
        cursor: pointer;
        transition: transform 0.15s ease, opacity 0.15s ease;
      }}

      .action:hover {{
        transform: translateY(-1px);
      }}

      .action.primary {{
        background: var(--ink);
        color: white;
      }}

      .action.secondary {{
        background: white;
        color: var(--ink);
        border: 1px solid var(--line);
      }}

      .action.ghost {{
        background: transparent;
        color: var(--muted);
        border: 1px dashed rgba(64, 51, 35, 0.22);
      }}

      .action:disabled {{
        opacity: 0.48;
        cursor: default;
        transform: none;
      }}

      .feed {{
        padding: 20px;
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
        overflow: hidden;
      }}

      .feed-top {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: flex-start;
        margin-bottom: 16px;
      }}

      .feed h2 {{
        margin: 0;
        font-size: 24px;
        letter-spacing: -0.03em;
      }}

      .feed-sub {{
        margin: 6px 0 0;
        color: var(--muted);
        font-size: 14px;
        line-height: 1.5;
      }}

      .event-log {{
        font-size: 12px;
        color: var(--muted);
        background: rgba(22, 27, 31, 0.05);
        padding: 10px 12px;
        border-radius: 14px;
        min-width: 170px;
        border: 1px solid rgba(64, 51, 35, 0.08);
      }}

      .timeline {{
        display: flex;
        flex-direction: column;
        gap: 12px;
        overflow-y: auto;
        padding-right: 6px;
        min-height: 0;
        flex: 1;
        overscroll-behavior: contain;
      }}

      .bubble {{
        padding: 14px 16px;
        border-radius: 20px;
        border: 1px solid var(--line);
        line-height: 1.6;
        font-size: 14px;
        background: white;
        box-shadow: 0 8px 22px rgba(46, 33, 15, 0.05);
      }}

      .bubble.user {{
        align-self: flex-end;
        background: rgba(22, 93, 255, 0.08);
        max-width: 82%;
      }}

      .bubble.assistant {{
        align-self: flex-start;
        background: rgba(13, 138, 114, 0.08);
        max-width: 82%;
      }}

      .bubble.system {{
        align-self: stretch;
        background: rgba(255, 122, 89, 0.08);
      }}

      .bubble-label {{
        display: block;
        margin-bottom: 6px;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
      }}

      .placeholder {{
        border: 1px dashed rgba(64, 51, 35, 0.18);
        border-radius: 22px;
        padding: 18px;
        color: var(--muted);
        background: rgba(255,255,255,0.42);
        font-size: 14px;
        line-height: 1.6;
        margin-top: 12px;
      }}

      .footer-note {{
        margin-top: 16px;
        color: var(--muted);
        font-size: 12px;
        line-height: 1.5;
      }}

      @media (max-width: 900px) {{
        body {{
          overflow: auto;
        }}

        .hero {{
          grid-template-columns: 1fr;
          height: auto;
        }}

        .stage,
        .feed {{
          min-height: auto;
          height: auto;
          overflow: visible;
        }}

        .feed-top {{
          flex-direction: column;
        }}

        .shell {{
          height: auto;
          overflow: visible;
        }}

        .timeline {{
          max-height: 420px;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="shell">
      <div class="hero">
        <section id="stage" class="card stage idle">
          <div>
            <div class="eyebrow">French speaking practice</div>
            <h1>Talk naturally. Interrupt naturally. Learn naturally.</h1>
            <p class="lede">
              Practice speaking French in a more natural rhythm, pause to think, jump back in,
              and build confidence through real conversation instead of one-shot recordings.
            </p>
          </div>

          <div class="orb-wrap">
            <div class="orb-ring">
              <button id="micBtn" class="orb-core" title="Start speaking">🎙️</button>
            </div>
          </div>

          <div>
            <div class="status-row">
              <div class="chip live" id="modeChip">Ready</div>
              <div class="chip" id="voiceChip">Voice: {voice}</div>
            </div>

            <div class="status-copy">
              <h3 class="status-title" id="statusTitle">Ready for a live conversation</h3>
              <p class="status-text" id="statusText">
                Click the orb, allow microphone access, and start speaking French. You can pause,
                think, and jump back in naturally.
              </p>
            </div>

            <div class="controls">
              <button id="connectBtn" class="action primary">Start Speaking</button>
              <button id="hangupBtn" class="action secondary" disabled>Pause Practice</button>
              <button id="clearBtn" class="action ghost">Clear Conversation</button>
            </div>

            <p class="footer-note">
              Stay on this page while you practise. If starting the conversation fails, refresh the
              page or create a fresh connection above and try again.
            </p>
          </div>
        </section>

        <section class="card feed">
          <div class="feed-top">
            <div>
              <h2>Conversation</h2>
              <p class="feed-sub">
                Your words appear as you speak, and Lucie's replies show up as they come in.
              </p>
            </div>
            <div id="eventLog" class="event-log">Ready when you are.</div>
          </div>

          <div id="timeline" class="timeline"></div>

          <div id="placeholder" class="placeholder">
            Use this space to follow the flow of the conversation. The older voice page is still in
            the sidebar if you want to compare both approaches.
          </div>
        </section>
      </div>
    </div>

    <script>
      const CONFIG = {config_json};
      const REALTIME_URL = "https://api.openai.com/v1/realtime/calls";

      let pc = null;
      let dc = null;
      let localStream = null;
      let remoteAudio = null;
      let sessionActive = false;
      let assistantSpeaking = false;
      let lastAssistantItemId = null;
      let currentAssistantBubble = null;
      let currentUserBubble = null;
      let currentAssistantText = "";
      let currentUserText = "";
      let currentAssistantFinalized = false;

      const stage = document.getElementById("stage");
      const micBtn = document.getElementById("micBtn");
      const connectBtn = document.getElementById("connectBtn");
      const hangupBtn = document.getElementById("hangupBtn");
      const clearBtn = document.getElementById("clearBtn");
      const modeChip = document.getElementById("modeChip");
      const voiceChip = document.getElementById("voiceChip");
      const statusTitle = document.getElementById("statusTitle");
      const statusText = document.getElementById("statusText");
      const timeline = document.getElementById("timeline");
      const placeholder = document.getElementById("placeholder");
      const eventLog = document.getElementById("eventLog");

      function setUIState(mode, title, text) {{
        stage.className = `card stage ${{mode}}`;
        modeChip.textContent = title;
        statusTitle.textContent = title;
        statusText.textContent = text;
      }}

      function setControls() {{
        connectBtn.disabled = sessionActive;
        hangupBtn.disabled = !sessionActive;
        micBtn.disabled = false;
        micBtn.textContent = sessionActive ? "⏹" : "🎙️";
        micBtn.title = sessionActive ? "Pause practice" : "Start speaking";
        voiceChip.textContent = `Voice: ${{CONFIG.voice}}`;
      }}

      function stampEvent(text) {{
        const now = new Date();
        const hh = now.toLocaleTimeString([], {{ hour: "2-digit", minute: "2-digit", second: "2-digit" }});
        eventLog.textContent = `${{hh}} • ${{text}}`;
      }}

      function escapeHtml(text) {{
        return text
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;");
      }}

      function ensureBubble(role, initialText = "") {{
        placeholder.style.display = "none";

        const bubble = document.createElement("div");
        bubble.className = `bubble ${{role}}`;

        const label = document.createElement("span");
        label.className = "bubble-label";
        label.textContent =
          role === "assistant" ? "Lucie" :
          role === "user" ? "You" :
          "System";

        const body = document.createElement("div");
        body.className = "bubble-body";
        body.innerHTML = escapeHtml(initialText);

        bubble.appendChild(label);
        bubble.appendChild(body);
        timeline.appendChild(bubble);
        timeline.scrollTop = timeline.scrollHeight;
        return bubble;
      }}

      function updateBubble(bubble, text) {{
        if (!bubble) return;
        const body = bubble.querySelector(".bubble-body");
        body.innerHTML = escapeHtml(text || "...");
        timeline.scrollTop = timeline.scrollHeight;
      }}

      function addSystemBubble(text) {{
        ensureBubble("system", text);
      }}

      function sendEvent(payload) {{
        if (dc && dc.readyState === "open") {{
          dc.send(JSON.stringify(payload));
        }}
      }}

      function interruptAssistantPlayback() {{
        if (!assistantSpeaking || !remoteAudio) {{
          return;
        }}

        const playedMs = Math.max(0, Math.floor((remoteAudio.currentTime || 0) * 1000));

        try {{
          remoteAudio.pause();
        }} catch (err) {{
          console.warn("pause failed", err);
        }}

        if (lastAssistantItemId) {{
          sendEvent({{
            type: "conversation.item.truncate",
            item_id: lastAssistantItemId,
            content_index: 0,
            audio_end_ms: playedMs,
          }});
        }}

        sendEvent({{ type: "response.cancel" }});
        assistantSpeaking = false;
        stampEvent("Lucie paused");
      }}

      async function startSession() {{
        if (sessionActive) {{
          return;
        }}

        setUIState(
          "connecting",
          "Connecting",
          "Getting your microphone ready so you can start speaking."
        );
        stampEvent("Requesting microphone");

        try {{
          localStream = await navigator.mediaDevices.getUserMedia({{
            audio: {{
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
            }},
          }});
        }} catch (err) {{
          console.error(err);
          setUIState(
            "error",
            "Microphone blocked",
            "The browser denied microphone access. Allow the microphone and try again."
          );
          addSystemBubble("Microphone access was denied, so speaking practice could not start.");
          stampEvent("Microphone denied");
          return;
        }}

        try {{
          pc = new RTCPeerConnection();
          remoteAudio = document.createElement("audio");
          remoteAudio.autoplay = true;
          remoteAudio.playsInline = true;
          remoteAudio.style.display = "none";
          document.body.appendChild(remoteAudio);

          pc.ontrack = (event) => {{
            remoteAudio.srcObject = event.streams[0];
          }};

          pc.onconnectionstatechange = () => {{
            stampEvent(`Peer ${{pc.connectionState}}`);
            if (pc.connectionState === "failed" || pc.connectionState === "disconnected") {{
              setUIState(
                "error",
                "Connection lost",
                "The conversation dropped. Refresh the page or create a fresh connection and try again."
              );
            }}
          }};

          localStream.getTracks().forEach((track) => pc.addTrack(track, localStream));

          dc = pc.createDataChannel("oai-events");
          dc.addEventListener("open", onDataChannelOpen);
          dc.addEventListener("message", onServerEvent);
          dc.addEventListener("close", () => stampEvent("Data channel closed"));

          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);

          const response = await fetch(REALTIME_URL, {{
            method: "POST",
            headers: {{
              Authorization: `Bearer ${{CONFIG.clientSecret}}`,
              "Content-Type": "application/sdp",
            }},
            body: offer.sdp,
          }});

          if (!response.ok) {{
            const errorText = await response.text();
            throw new Error(errorText || `HTTP ${{response.status}}`);
          }}

          const answer = {{
            type: "answer",
            sdp: await response.text(),
          }};
          await pc.setRemoteDescription(answer);

          sessionActive = true;
          assistantSpeaking = false;
          setControls();
          setUIState(
            "listening",
            "Ready to speak",
            "Speak naturally in French. If Lucie is still talking, you can simply start speaking."
          );
          stampEvent("Practice started");
          addSystemBubble("French speaking practice is ready.");
        }} catch (err) {{
          console.error(err);
          stopSession({{
            preserveTimeline: true,
            systemMessage: `Connection failed: ${{String(err).slice(0, 260)}}`,
          }});
          setUIState(
            "error",
            "Could not start",
            "The conversation could not start. The page may need a fresh connection."
          );
          stampEvent("Could not start");
        }}
      }}

      function onDataChannelOpen() {{
        stampEvent("Data channel open");

        sendEvent({{
          type: "session.update",
          session: {{
            type: "realtime",
            model: CONFIG.model,
            output_modalities: ["audio"],
            audio: {{
              input: {{
                transcription: {{
                  model: "gpt-4o-transcribe",
                  language: "fr",
                }},
                turn_detection: {{
                  type: "server_vad",
                  create_response: true,
                  interrupt_response: true,
                  prefix_padding_ms: 400,
                  silence_duration_ms: 3000,
                }},
              }},
              output: {{
                voice: CONFIG.voice,
              }},
            }},
          }},
        }});

        sendEvent({{
          type: "response.create",
          response: {{
            output_modalities: ["audio"],
            instructions: CONFIG.greeting,
          }},
        }});
      }}

      function finalizeCurrentUser(text) {{
        if (!text || !text.trim()) {{
          currentUserText = "";
          currentUserBubble = null;
          return;
        }}
        if (!currentUserBubble) {{
          currentUserBubble = ensureBubble("user", text);
        }}
        updateBubble(currentUserBubble, text.trim());
        currentUserText = "";
        currentUserBubble = null;
      }}

      function finalizeCurrentAssistant(text) {{
        if (!text || !text.trim()) {{
          currentAssistantText = "";
          currentAssistantBubble = null;
          currentAssistantFinalized = false;
          return;
        }}
        if (!currentAssistantBubble) {{
          currentAssistantBubble = ensureBubble("assistant", text);
        }}
        updateBubble(currentAssistantBubble, text.trim());
        currentAssistantText = "";
        currentAssistantFinalized = true;
      }}

      function extractAssistantText(response) {{
        if (!response || !Array.isArray(response.output)) {{
          return "";
        }}

        const chunks = [];
        for (const item of response.output) {{
          if (!Array.isArray(item.content)) continue;
          for (const content of item.content) {{
            if (typeof content.transcript === "string" && content.transcript.trim()) {{
              chunks.push(content.transcript.trim());
              continue;
            }}
            if (typeof content.text === "string" && content.text.trim()) {{
              chunks.push(content.text.trim());
            }}
          }}
        }}
        return chunks.join("\\n").trim();
      }}

      function onServerEvent(messageEvent) {{
        let event;
        try {{
          event = JSON.parse(messageEvent.data);
        }} catch (err) {{
          console.warn("Bad event payload", err);
          return;
        }}

        switch (event.type) {{
          case "session.created":
            stampEvent("Session created");
            break;

          case "session.updated":
            stampEvent("Session updated");
            break;

          case "input_audio_buffer.speech_started":
            interruptAssistantPlayback();
            currentUserText = "";
            if (!currentUserBubble) {{
              currentUserBubble = ensureBubble("user", "...");
            }}
            setUIState(
              "listening",
              "Listening",
              "You are speaking. Keep going naturally."
            );
            stampEvent("User started speaking");
            break;

          case "input_audio_buffer.speech_stopped":
            setUIState(
              "connecting",
              "Processing",
              "You stopped speaking. Lucie is preparing a reply."
            );
            stampEvent("User stopped speaking");
            break;

          case "conversation.item.input_audio_transcription.delta":
            if (!currentUserBubble) {{
              currentUserBubble = ensureBubble("user", event.delta || "...");
            }}
            currentUserText += event.delta || "";
            updateBubble(currentUserBubble, currentUserText || "...");
            break;

          case "conversation.item.input_audio_transcription.completed":
            finalizeCurrentUser(event.transcript || "");
            stampEvent("Your words were captured");
            break;

          case "response.output_item.added":
            if (event.item && event.item.role === "assistant") {{
              lastAssistantItemId = event.item.id || lastAssistantItemId;
              currentAssistantText = "";
              currentAssistantFinalized = false;
              if (!currentAssistantBubble) {{
                currentAssistantBubble = ensureBubble("assistant", "...");
              }}
            }}
            break;

          case "response.output_audio.delta":
            assistantSpeaking = true;
            setUIState(
              "speaking",
              "Lucie is speaking",
              "Listen to the reply, or jump in whenever you want to continue."
            );
            break;

          case "response.output_audio.done":
            assistantSpeaking = false;
            setUIState(
              "listening",
              "Listening",
              "Your turn again. Keep the conversation moving."
            );
            stampEvent("Lucie finished speaking");
            break;

          case "response.output_audio_transcript.delta":
          case "response.output_text.delta":
            if (!currentAssistantBubble) {{
              currentAssistantBubble = ensureBubble("assistant", event.delta || "...");
            }}
            currentAssistantText += event.delta || "";
            updateBubble(currentAssistantBubble, currentAssistantText || "...");
            break;

          case "response.output_audio_transcript.done":
          case "response.output_text.done":
            finalizeCurrentAssistant(event.transcript || event.text || "");
            break;

          case "response.done": {{
            assistantSpeaking = false;
            const finalText = extractAssistantText(event.response);
            if (finalText && !currentAssistantFinalized) {{
              finalizeCurrentAssistant(finalText);
            }}
            currentAssistantBubble = null;
            currentAssistantText = "";
            currentAssistantFinalized = false;
            setUIState(
              "listening",
              "Listening",
              "Lucie finished. Speak again whenever you are ready."
            );
            stampEvent("Reply complete");
            break;
          }}

          case "response.cancelled":
            assistantSpeaking = false;
            setUIState(
              "listening",
              "Listening",
              "Lucie stopped so you can continue speaking."
            );
            stampEvent("Reply paused");
            break;

          case "error": {{
            const errorMessage = event.error && event.error.message
              ? event.error.message
              : "Unknown realtime error";
            addSystemBubble(`Something went wrong: ${{errorMessage}}`);
            setUIState("error", "Something went wrong", errorMessage);
            stampEvent("Something went wrong");
            break;
          }}

          default:
            break;
        }}
      }}

      function clearTranscript() {{
        timeline.innerHTML = "";
        placeholder.style.display = "block";
        currentAssistantBubble = null;
        currentUserBubble = null;
        currentAssistantText = "";
        currentUserText = "";
        currentAssistantFinalized = false;
        lastAssistantItemId = null;
        stampEvent("Transcript cleared");
      }}

      function stopSession(options = {{}}) {{
        const preserveTimeline = Boolean(options.preserveTimeline);
        const systemMessage = options.systemMessage || "";

        sessionActive = false;
        assistantSpeaking = false;

        if (dc) {{
          try {{
            dc.close();
          }} catch (err) {{
            console.warn(err);
          }}
          dc = null;
        }}

        if (pc) {{
          try {{
            pc.close();
          }} catch (err) {{
            console.warn(err);
          }}
          pc = null;
        }}

        if (localStream) {{
          localStream.getTracks().forEach((track) => track.stop());
          localStream = null;
        }}

        if (remoteAudio) {{
          try {{
            remoteAudio.pause();
          }} catch (err) {{
            console.warn(err);
          }}
          remoteAudio.srcObject = null;
          remoteAudio.remove();
          remoteAudio = null;
        }}

        currentAssistantBubble = null;
        currentUserBubble = null;
        currentAssistantText = "";
        currentUserText = "";
        currentAssistantFinalized = false;
        setControls();
        setUIState(
          "idle",
          "Practice paused",
          "Start again whenever you want to continue speaking."
        );
        stampEvent("Practice paused");

        if (systemMessage) {{
          addSystemBubble(systemMessage);
        }}

        if (!preserveTimeline && !timeline.children.length) {{
          placeholder.style.display = "block";
        }}
      }}

      micBtn.addEventListener("click", () => {{
        if (sessionActive) {{
          stopSession();
        }} else {{
          startSession();
        }}
      }});

      connectBtn.addEventListener("click", startSession);
      hangupBtn.addEventListener("click", () => stopSession());
      clearBtn.addEventListener("click", clearTranscript);

      setControls();
    </script>
  </body>
</html>
"""


st.title("🎙️ Speak In French")
st.caption("A more natural space to practise speaking, listening, and thinking out loud in French.")

api_key = os.getenv("OPENAI_API_KEY", "")

with st.expander("Settings", expanded=not bool(api_key)):
    api_key_input = st.text_input(
        "OpenAI API key",
        value=api_key,
        type="password",
        help="Used only to open the live speaking experience.",
    )
    if api_key_input:
        api_key = api_key_input

    selected_voice = st.selectbox(
        "Assistant voice",
        VOICE_OPTIONS,
        index=VOICE_OPTIONS.index("sage") if "sage" in VOICE_OPTIONS else 0,
        help="Choose the voice you want to practise with.",
    )

    system_prompt = st.text_area(
        "Conversation instructions",
        value=DEFAULT_PROMPT,
        height=240,
        help="Use this to shape Lucie's teaching style and tone.",
    )

    st.markdown("##### Current topics")
    topic_focus = st.multiselect(
        "Topic areas",
        TOPIC_OPTIONS,
        # default=["Politics", "Arts and culture", "Sports"],
        help="Guide what kind of current topics Lucie should retrieve before the conversation starts.",
    )

    focus_place = st.text_input(
        "Place to focus on",
        value="Paris, France",
        help="Examples: `Paris, France`, `Marseille, France`, `Belgium`, `Berlin, Germany`.",
    )

    include_weather = st.checkbox(
        "Let Lucie know the current weather for this place",
        value=True,
        help="When enabled, the prep step also fetches a short current weather note for the selected place.",
    )

    days_back = st.slider(
        "How recent should the topics be (in days)?",
        min_value=1,
        max_value=14,
        value=7,
        help="Lucie will look for topics from within this recent window.",
    )

col_a, col_b = st.columns([1, 1])
with col_a:
    refresh_requested = st.button(
        "Prepare Voice Practice",
        type="primary",
        use_container_width=True,
        help="Click this before starting if the live conversation needs a fresh connection.",
    )
with col_b:
    st.markdown(
        """
        <div style="padding:0.6rem 0;color:#6b7280;font-size:0.95rem;">
        Recommended flow: prepare the connection, then start speaking in the panel below.
        </div>
        """,
        unsafe_allow_html=True,
    )

if not api_key:
    st.warning("Enter an OpenAI API key above to start the live French speaking page.")
    st.stop()

if refresh_requested:
    st.session_state["voice_realtime_nonce"] = st.session_state.get("voice_realtime_nonce", 0) + 1

news_topics: list[dict[str, str]] = []
weather_summary = ""
effective_prompt = system_prompt
greeting_prompt = (
    "Salue l'utilisateur tres naturellement en francais, puis demande-lui simplement "
    "de quoi il aimerait parler aujourd'hui."
)
news_fetch_warning: str | None = None
weather_fetch_warning: str | None = None

try:
    with st.spinner("Preparing your live speaking connection..."):
        try:
            live_context = _fetch_live_context(
                api_key,
                focus_place=focus_place,
                topic_labels=topic_focus,
                days_back=days_back,
                include_weather=include_weather,
            )
            news_topics = live_context["topics"]
            weather_summary = live_context["weather_summary"]
            effective_prompt = f"{system_prompt}\n\n{_build_news_context(news_topics)}"
            greeting_prompt = _build_greeting(news_topics)
            if weather_summary:
                effective_prompt = f"{effective_prompt}\n\n{_build_weather_context(focus_place, weather_summary)}"
        except Exception as exc:
            warning_text = str(exc)
            news_fetch_warning = (
                "Current prep could not be refreshed, so Lucie will start without live topics"
                + (" or weather" if include_weather else "")
                + f": {warning_text}"
            )
            if include_weather:
                weather_fetch_warning = (
                    "Current weather could not be refreshed, so Lucie will start without a live weather note: "
                    f"{warning_text}"
                )
        token_payload = _mint_realtime_client_secret(
            api_key,
            voice=selected_voice,
            instructions=effective_prompt,
        )
except Exception as exc:
    st.error(f"Could not prepare the live speaking connection: {exc}")
    st.markdown(
        """
        This usually means one of these:
        - the API key is invalid
        - the account does not have live voice access
        - the request format changed and needs a quick adjustment
        """
    )
    st.stop()

client_secret = token_payload.get("value") or token_payload.get("client_secret", {}).get("value")
expires_at = token_payload.get("expires_at")

if not client_secret:
    st.error(f"OpenAI returned an unexpected token payload: {token_payload}")
    st.stop()

meta_cols = st.columns(3)
meta_cols[0].metric("Model", "gpt-realtime")
meta_cols[1].metric("Voice", selected_voice)
meta_cols[2].metric("Connection", "ready" if client_secret else "missing")

if expires_at:
    st.caption(f"If starting fails, prepare the connection again and retry. Token expiry: `{expires_at}`.")

if news_fetch_warning:
    st.warning(news_fetch_warning)

if weather_fetch_warning:
    st.warning(weather_fetch_warning)

if news_topics:
    with st.expander("Current topics Lucie can use", expanded=False):
        st.caption(
            f"Focus: `{focus_place}` | Topics: `{', '.join(topic_focus) if topic_focus else 'general current affairs'}` | Window: last `{days_back}` days"
        )
        for index, topic in enumerate(news_topics, start=1):
            st.markdown(f"**{index}. {topic['title_fr']}**  \n{topic['summary_fr']}")

if weather_summary:
    st.caption(f"Current weather for `{focus_place}`: {weather_summary}")

components.html(
    _build_realtime_component(
        client_secret=client_secret,
        voice=selected_voice,
        instructions=effective_prompt,
        greeting=greeting_prompt,
    ),
    height=760,
    scrolling=False,
)
