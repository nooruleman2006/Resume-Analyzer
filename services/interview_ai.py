"""
Interview AI service — uses Groq_Key_2 as primary, GEMINI_API_KEY_2 as fallback.
Completely isolated from the ATS Gemini key and main Groq key.
"""
import requests
import json
import time
import logging
import os
from config import Config

logger = logging.getLogger(__name__)

# ── Groq config ────────────────────────────────────────────────────────────
_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
]
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ── Gemini config (fallback) ───────────────────────────────────────────────
_GEMINI_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
]


def _get_groq_key():
    return os.environ.get('Groq_Key_2', '') or getattr(Config, 'Groq_Key_2', '') or ''


def _get_gemini_key():
    return os.environ.get('GEMINI_API_KEY_2', '') or getattr(Config, 'GEMINI_API_KEY_2', '') or ''


def is_configured():
    return bool(_get_groq_key() or _get_gemini_key())


# ── Groq caller ────────────────────────────────────────────────────────────

def _call_groq(system_prompt, messages, timeout=40):
    """
    messages: list of {"role": "user"|"assistant", "content": "..."}
    Returns assistant reply text.
    """
    key = _get_groq_key()
    if not key:
        raise RuntimeError("Groq_Key_2 not configured.")

    payload_messages = [{"role": "system", "content": system_prompt}] + messages

    last_err = None
    for model in _GROQ_MODELS:
        try:
            resp = requests.post(
                _GROQ_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": payload_messages,
                    "temperature": 0.85,
                    "max_tokens": 1024,
                },
                timeout=timeout
            )
            if resp.status_code == 429:
                logger.warning(f"[InterviewAI] Groq 429 on {model}")
                time.sleep(1)
                continue
            if not resp.ok:
                logger.warning(f"[InterviewAI] Groq {resp.status_code} on {model}: {resp.text[:300]}")
                last_err = Exception(f"Groq {resp.status_code}")
                continue
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"[InterviewAI] Groq error on {model}: {e}")
            last_err = e
            continue

    raise last_err or RuntimeError("All Groq models failed")


# ── Gemini caller (fallback) ───────────────────────────────────────────────

def _call_gemini(system_prompt, conversation, timeout=40):
    """
    conversation: list of {"role": "user"|"model", "parts": [{"text": "..."}]}
    Returns assistant reply text.
    """
    key = _get_gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY_2 not configured.")

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": conversation,
        "generationConfig": {"temperature": 0.85, "maxOutputTokens": 1024}
    }

    last_err = None
    for model in _GEMINI_MODELS:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={key}"
        )
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.status_code == 429:
                logger.warning(f"[InterviewAI] Gemini 429 on {model}")
                time.sleep(1)
                continue
            if not resp.ok:
                logger.warning(f"[InterviewAI] Gemini {resp.status_code} on {model}: {resp.text[:300]}")
                last_err = Exception(f"Gemini {resp.status_code}")
                continue
            data = resp.json()
            return (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
        except Exception as e:
            logger.warning(f"[InterviewAI] Gemini error on {model}: {e}")
            last_err = e
            continue

    raise last_err or RuntimeError("All Gemini models failed")


# ── Unified caller ─────────────────────────────────────────────────────────

def _call_ai(system_prompt, groq_messages, gemini_conversation, timeout=40):
    """Try Groq first, fall back to Gemini."""
    if _get_groq_key():
        try:
            return _call_groq(system_prompt, groq_messages, timeout)
        except Exception as e:
            logger.warning(f"[InterviewAI] Groq failed, trying Gemini fallback: {e}")

    if _get_gemini_key():
        return _call_gemini(system_prompt, gemini_conversation, timeout)

    raise RuntimeError("No AI provider configured. Add Groq_Key_2 or GEMINI_API_KEY_2 to your .env file.")


# ── Public API ─────────────────────────────────────────────────────────────

def build_system_prompt(role, company_type, tone, resume_text):
    return (
        f"You are a professional {tone} interviewer from a {company_type} company, "
        f"interviewing a candidate for the role of {role}.\n\n"
        f"Here is the candidate's resume:\n{resume_text}\n\n"
        "Conduct a realistic interview. Ask ONE question at a time. "
        "After the candidate answers, ask a relevant follow-up before moving to the next question. "
        "Stay in character throughout. Never reveal you are an AI. "
        "Use STAR method awareness in follow-up probing.\n\n"
        "If company type is FAANG: ask harder, more technical and deep-dive questions.\n"
        "If company type is Startup: ask versatile, problem-solving and adaptability focused questions.\n"
        "If company type is Corporate: ask structured, process-oriented and behavioral questions.\n\n"
        "Start by greeting the candidate warmly, introducing yourself with a first name and title, "
        "then ask them to tell you about themselves."
    )


def chat(system_prompt, history):
    """
    history: list of {"role": "user"|"model", "text": "..."} dicts
    Returns next AI message string.
    """
    # Groq format (uses "assistant" instead of "model")
    groq_messages = [
        {"role": "assistant" if m["role"] == "model" else "user", "content": m["text"]}
        for m in history
    ]
    if not groq_messages:
        groq_messages = [{"role": "user", "content": "Please begin the interview now."}]

    # Gemini format
    gemini_conv = [
        {"role": m["role"], "parts": [{"text": m["text"]}]}
        for m in history
    ]
    if not gemini_conv:
        gemini_conv = [{"role": "user", "parts": [{"text": "Please begin the interview now."}]}]

    return _call_ai(system_prompt, groq_messages, gemini_conv)


def _build_report_prompt(transcript, analytics_text=""):
    return (
        "The interview has now ended. Based on the full transcript below, "
        "generate a detailed evaluation report as a valid JSON object with exactly these keys:\n"
        "{\n"
        '  "overall_score": <integer 0-100>,\n'
        '  "confidence_level": <"Low"|"Medium"|"High">,\n'
        '  "star_usage": <"Poor"|"Fair"|"Good"|"Excellent">,\n'
        '  "strengths": [<3 short strings>],\n'
        '  "improvements": [<3 short strings>],\n'
        '  "question_ratings": [\n'
        '    {"question": "...", "rating": <1-5>, "feedback": "..."}\n'
        "  ],\n"
        '  "sample_answers": [\n'
        '    {"question": "...", "strong_answer": "..."}\n'
        "  ],\n"
        '  "tips": [<3-5 short actionable tip strings>]\n'
        "}\n\n"
        + (
            "Also consider the candidate's speech analytics (WPM, filler words, answer length). "
            "Faster than 120 WPM suggests rushing; slower than 80 WPM suggests hesitancy. "
            "Many filler words suggest nervousness. Incorporate these into feedback and tips.\n\n"
            if analytics_text else ""
        )
        + "Return ONLY the JSON object, no markdown, no extra text.\n\n"
        f"TRANSCRIPT:\n{transcript}\n{analytics_text}"
    )


def _clean_json(raw):
    """Strip markdown fences if present."""
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def generate_report(system_prompt, history):
    transcript = "\n\n".join(
        f"{'INTERVIEWER' if m['role'] == 'model' else 'CANDIDATE'}: {m['text']}"
        for m in history
    )
    prompt = _build_report_prompt(transcript)

    groq_messages = [{"role": "user", "content": prompt}]
    gemini_conv   = [{"role": "user", "parts": [{"text": prompt}]}]

    raw = _call_ai(system_prompt, groq_messages, gemini_conv, timeout=60)
    return _clean_json(raw)


def generate_video_report(system_prompt, history, video_analytics):
    transcript = "\n\n".join(
        f"{'INTERVIEWER' if m['role'] == 'model' else 'CANDIDATE'}: {m['text']}"
        for m in history
    )

    analytics_text = ""
    per_q = video_analytics.get('per_question', [])
    if per_q:
        analytics_text += "\n\nPER-QUESTION ANALYTICS:\n"
        for i, q in enumerate(per_q, 1):
            analytics_text += (
                f"Q{i}: duration={q.get('durationSec','?')}s, "
                f"words={q.get('wordCount','?')}, "
                f"WPM={q.get('wpm','?')}, "
                f"fillers={q.get('fillerCount',0)}\n"
            )
        analytics_text += (
            f"\nOVERALL: total_duration={video_analytics.get('total_duration_sec','?')}s, "
            f"questions_answered={video_analytics.get('questions_answered','?')}, "
            f"avg_wpm={video_analytics.get('avg_wpm','?')}, "
            f"total_fillers={video_analytics.get('total_filler_words',0)}\n"
        )

    prompt = _build_report_prompt(transcript, analytics_text)

    groq_messages = [{"role": "user", "content": prompt}]
    gemini_conv   = [{"role": "user", "parts": [{"text": prompt}]}]

    raw = _call_ai(system_prompt, groq_messages, gemini_conv, timeout=60)
    return _clean_json(raw)