from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


MEMORY_PATH = Path("data/private/voice_realtime_memory.json")
TOPIC_CACHE_PATH = Path("data/private/voice_realtime_topics_cache.json")
MAX_PROMPT_FACTS = 5
MAX_FACTS_PER_SAVE = 5

PROFILE_FIELDS = {
    "display_name": "Jonny",
    "location": "Hambourg (ville d'origine), a vécu à Paris, Berlin, Shanghai, Singapour, Bangkok, Saint-Gall et Madrid",
    "background": "Consultant en data science",
    "interests": "la course à pied, le football, les expositions d'art moderne, la nutrition, la politique allemande, française et internationale",
    "lifestyle": "A récemment déménagé à Munich et a emménagé avec sa copine",
    "french_goals": "Atteindre un meilleur niveau B2 et éventuellement se préparer à des entretiens",
    "extra_context": "",
}


def _default_store() -> dict[str, Any]:
    return {
        "profile": dict(PROFILE_FIELDS),
        "learned_facts": [],
    }


def _normalize_profile(profile: dict[str, Any] | None) -> dict[str, str]:
    normalized = dict(PROFILE_FIELDS)
    if not profile:
        return normalized

    for key in normalized:
        normalized[key] = str(profile.get(key, "") or "").strip()
    return normalized


def _normalize_learned_fact(fact: dict[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(fact, dict):
        return None

    timestamp = str(fact.get("timestamp", "") or "").strip()
    label = str(fact.get("label", "") or "").strip()
    summary = str(fact.get("summary", "") or "").strip()
    source = str(fact.get("source", "") or "from_conversation").strip()

    if not summary:
        return None

    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat()
    if not label:
        label = "Personal detail"

    return {
        "timestamp": timestamp,
        "label": label[:80],
        "summary": summary[:280],
        "source": source[:40] or "from_conversation",
    }


def _sort_learned_facts(facts: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for fact in facts:
        clean_fact = _normalize_learned_fact(fact)
        if clean_fact:
            normalized.append(clean_fact)

    return sorted(
        normalized,
        key=lambda item: item.get("timestamp", ""),
        reverse=True,
    )


def load_memory_store(memory_path: Path = MEMORY_PATH) -> dict[str, Any]:
    if not memory_path.exists():
        return _default_store()

    try:
        payload = json.loads(memory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_store()

    if not isinstance(payload, dict):
        return _default_store()

    return {
        "profile": _normalize_profile(payload.get("profile")),
        "learned_facts": _sort_learned_facts(payload.get("learned_facts", [])),
    }


def save_memory_store(store: dict[str, Any], memory_path: Path = MEMORY_PATH) -> dict[str, Any]:
    normalized_store = {
        "profile": _normalize_profile(store.get("profile")),
        "learned_facts": _sort_learned_facts(store.get("learned_facts", [])),
    }
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(
        json.dumps(normalized_store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return normalized_store


def _normalize_live_context_params(
    *,
    focus_place: str,
    topic_labels: list[str],
    days_back: int,
    include_weather: bool,
) -> dict[str, Any]:
    normalized_topic_labels = sorted(
        [str(label).strip() for label in topic_labels if str(label).strip()],
        key=str.casefold,
    )
    return {
        "focus_place": focus_place.strip(),
        "topic_labels": normalized_topic_labels,
        "days_back": int(days_back),
        "include_weather": bool(include_weather),
    }


def _normalize_cached_topics(topics: Any) -> list[dict[str, str]]:
    if not isinstance(topics, list):
        return []

    normalized: list[dict[str, str]] = []
    for topic in topics[:3]:
        if not isinstance(topic, dict):
            continue
        title = str(topic.get("title_fr", "") or "").strip()
        summary = str(topic.get("summary_fr", "") or "").strip()
        if title and summary:
            normalized.append({"title_fr": title[:120], "summary_fr": summary[:280]})
    return normalized


def load_live_context_cache(cache_path: Path = TOPIC_CACHE_PATH) -> dict[str, Any] | None:
    if not cache_path.exists():
        return None

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    params = payload.get("params", {})
    topics = _normalize_cached_topics(payload.get("topics"))
    weather_summary = str(payload.get("weather_summary", "") or "").strip()
    cached_at = str(payload.get("cached_at", "") or "").strip()

    if not isinstance(params, dict) or len(topics) != 3:
        return None

    try:
        normalized_params = _normalize_live_context_params(
            focus_place=str(params.get("focus_place", "") or ""),
            topic_labels=[
                str(label).strip()
                for label in params.get("topic_labels", [])
                if str(label).strip()
            ],
            days_back=int(params.get("days_back", 0) or 0),
            include_weather=bool(params.get("include_weather", False)),
        )
    except (TypeError, ValueError):
        return None

    return {
        "cached_at": cached_at,
        "params": normalized_params,
        "topics": topics,
        "weather_summary": weather_summary if weather_summary else "",
    }


def save_live_context_cache(
    live_context: dict[str, Any],
    *,
    focus_place: str,
    topic_labels: list[str],
    days_back: int,
    include_weather: bool,
    cache_path: Path = TOPIC_CACHE_PATH,
) -> dict[str, Any]:
    topics = _normalize_cached_topics(live_context.get("topics"))
    if len(topics) != 3:
        raise ValueError("Live context cache requires exactly three usable topics.")

    normalized_cache = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "params": _normalize_live_context_params(
            focus_place=focus_place,
            topic_labels=topic_labels,
            days_back=days_back,
            include_weather=include_weather,
        ),
        "topics": topics,
        "weather_summary": str(live_context.get("weather_summary", "") or "").strip(),
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(normalized_cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return normalized_cache


def update_profile(profile: dict[str, Any], memory_path: Path = MEMORY_PATH) -> dict[str, Any]:
    store = load_memory_store(memory_path)
    normalized_profile = _normalize_profile(profile)
    if store["profile"] == normalized_profile:
        return store

    store["profile"] = normalized_profile
    return save_memory_store(store, memory_path)


def append_learned_facts(
    facts: list[dict[str, Any]],
    *,
    memory_path: Path = MEMORY_PATH,
) -> dict[str, Any]:
    store = load_memory_store(memory_path)
    existing_summaries = {fact["summary"].casefold() for fact in store["learned_facts"]}

    for fact in facts:
        normalized_fact = _normalize_learned_fact(fact)
        if not normalized_fact:
            continue
        summary_key = normalized_fact["summary"].casefold()
        if summary_key in existing_summaries:
            continue
        store["learned_facts"].append(normalized_fact)
        existing_summaries.add(summary_key)

    return save_memory_store(store, memory_path)


def build_user_context_block(
    profile: dict[str, Any],
    learned_facts: list[dict[str, Any]],
    *,
    max_facts: int = MAX_PROMPT_FACTS,
) -> str:
    normalized_profile = _normalize_profile(profile)
    lines = ["Informations durables sur l'utilisateur."]

    profile_labels = {
        "display_name": "Nom ou prenom",
        "location": "Lieu ou pays importants",
        "background": "Travail, etudes ou parcours",
        "interests": "Centres d'interet",
        "lifestyle": "Vie personnelle ou habitudes importantes",
        "french_goals": "Objectifs actuels en francais",
        "extra_context": "Autre contexte personnel utile",
    }
    for key, label in profile_labels.items():
        value = normalized_profile.get(key, "")
        if value:
            lines.append(f"- {label}: {value}")

    recent_facts = _sort_learned_facts(learned_facts)[:max_facts]
    if recent_facts:
        lines.append("- Souvenirs personnels issus de conversations precedentes:")
        for fact in recent_facts:
            lines.append(f"  - {fact['summary']}")

    if len(lines) == 1:
        return ""

    return "\n".join(lines)


def summarize_transcript_to_facts(
    api_key: str,
    transcript: str,
    *,
    profile: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    transcript_text = transcript.strip()
    if not transcript_text:
        return []

    normalized_profile = _normalize_profile(profile)
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4.1-mini",
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Extract only durable personal facts about the user from the "
                                "conversation transcript. Focus on identity, life context, work, "
                                "studies, hobbies, family context, places, plans, and recurring "
                                "interests that Lucie should remember later.\n\n"
                                "Rules:\n"
                                "- Return facts only if they are explicitly stated or strongly self-described by the user.\n"
                                "- Never infer personality traits or broad psychological claims.\n"
                                "- Never include teaching preferences, correction style, or instructions for Lucie.\n"
                                "- Never include raw transcript excerpts longer than needed.\n"
                                "- Ignore fleeting small talk unless it reflects a durable personal detail.\n"
                                "- If there are no durable personal facts worth saving, return an empty facts array."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Existing profile context:\n"
                                f"{json.dumps(normalized_profile, ensure_ascii=False)}\n\n"
                                "Transcript:\n"
                                f"{transcript_text}"
                            ),
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "voice_realtime_memory_facts",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "facts": {
                                "type": "array",
                                "maxItems": MAX_FACTS_PER_SAVE,
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "label": {"type": "string"},
                                        "summary": {"type": "string"},
                                    },
                                    "required": ["label", "summary"],
                                },
                            }
                        },
                        "required": ["facts"],
                    },
                }
            },
        },
        timeout=35,
    )

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("Could not decode the personal-memory summary response.") from exc

    if response.status_code >= 400:
        message = data.get("error", {}).get("message") if isinstance(data, dict) else None
        raise RuntimeError(message or "Could not summarize the saved conversation.")

    raw_text = _extract_response_text(data)
    if not raw_text:
        return []

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Could not parse the personal-memory summary.") from exc

    facts: list[dict[str, str]] = []
    for fact in payload.get("facts", []):
        label = str(fact.get("label", "") or "").strip()
        summary = str(fact.get("summary", "") or "").strip()
        if not summary:
            continue
        facts.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "label": label[:80] or "Personal detail",
                "summary": summary[:280],
                "source": "from_conversation",
            }
        )

    return facts


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
