import requests
import json
import re
import time
import logging
from config import Config

logger = logging.getLogger(__name__)


# ── API Key Helpers ────────────────────────────────────────────

def _get_gemini_key():
    """Return the Gemini API key from environment variables."""
    key = Config.GEMINI_API_KEY or ''
    if not key:
        logger.error("[Gemini] GEMINI_API_KEY is not set in environment variables.")
    return key


def _get_groq_key():
    """Return the Groq API key from environment variables."""
    key = getattr(Config, 'GROQ_API_KEY', '') or ''
    if not key:
        logger.error("[Groq] GROQ_API_KEY is not set in environment variables.")
    return key


def is_gemini_configured():
    return bool(_get_gemini_key())


def is_groq_configured():
    return bool(_get_groq_key())


class RateLimitError(Exception):
    """Raised when an API returns 429 Too Many Requests."""
    pass


# ── Gemini: Resume Analysis ────────────────────────────────────

_GEMINI_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
]


def _call_gemini(prompt, api_key, timeout=30):
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    hit_rate_limit = False
    retry_after = 60
    last_err = None

    for model in _GEMINI_MODELS:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        try:
            response = requests.post(url, json=payload, timeout=timeout)

            if response.status_code == 429:
                hit_rate_limit = True
                try:
                    details = response.json().get("error", {}).get("details", [])
                    for d in details:
                        if d.get("@type", "").endswith("RetryInfo"):
                            raw_delay = d.get("retryDelay", "60s")
                            retry_after = int(raw_delay.rstrip("s")) + 5
                except Exception:
                    pass
                logger.warning(f"[Gemini] 429 on {model}, retry_after={retry_after}s")
                time.sleep(1)
                continue

            response.raise_for_status()
            data = response.json()
            raw = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            logger.info(f"[Gemini] Success with model {model}")
            return raw

        except RateLimitError:
            raise
        except requests.exceptions.HTTPError as e:
            logger.warning(f"[Gemini] HTTP error on {model}: {e}")
            last_err = e
            continue
        except Exception as e:
            logger.warning(f"[Gemini] Error on {model}: {e}")
            last_err = e
            continue

    if hit_rate_limit:
        err = RateLimitError(str(retry_after))
        err.retry_after = retry_after
        raise err

    raise last_err or Exception("All Gemini models failed")


# ── Groq: Interview Questions & Evaluation ────────────────────

_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]


def _call_groq(prompt, api_key, timeout=30):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_err = None
    hit_rate_limit = False
    retry_after = 60

    for model in _GROQ_MODELS:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1024,
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)

            if response.status_code == 429:
                hit_rate_limit = True
                try:
                    retry_after = int(response.headers.get("Retry-After", 60)) + 5
                except Exception:
                    pass
                logger.warning(f"[Groq] 429 on {model}, retry_after={retry_after}s")
                time.sleep(1)
                continue

            response.raise_for_status()
            data = response.json()
            raw = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            logger.info(f"[Groq] Success with model {model}")
            return raw

        except RateLimitError:
            raise
        except requests.exceptions.HTTPError as e:
            logger.warning(f"[Groq] HTTP error on {model}: {e}")
            last_err = e
            continue
        except Exception as e:
            logger.warning(f"[Groq] Error on {model}: {e}")
            last_err = e
            continue

    if hit_rate_limit:
        err = RateLimitError(str(retry_after))
        err.retry_after = retry_after
        raise err

    raise last_err or Exception("All Groq models failed")


# ── Public Functions ───────────────────────────────────────────

def analyze_resume(resume_text, job_title='', job_description='', present_skills=None, missing_skills=None):
    """Gemini-powered resume analysis."""
    context = ""
    if job_title:
        context += f"\nTarget Job Title: {job_title}"
    if job_description:
        context += f"\nJob Description:\n{job_description[:1000]}"
    if present_skills:
        context += f"\nDetected Skills: {', '.join(present_skills[:15])}"

    prompt = f"""
You are an expert resume reviewer and career coach with deep knowledge across ALL industries —
engineering, medicine, law, finance, education, arts, and more.

Carefully read the resume below and identify the candidate's ACTUAL profession and industry
(do NOT assume software/tech unless the resume clearly shows that field).

{context}

Resume Text:
\"\"\"
{resume_text[:3500]}
\"\"\"

IMPORTANT INSTRUCTIONS:
1. First determine the candidate's real field (e.g. Electrical Engineering, Medicine, Marketing, Finance, Teaching, etc.)
2. "suitable_roles" MUST be real roles within THAT specific field
3. "missing_keywords" MUST be industry-specific keywords/tools/certifications for THAT field
4. The summary must reference the candidate's actual profession and experience level
5. NEVER suggest programming languages unless the resume is clearly for a software/IT role

Return ONLY a valid JSON object — no markdown, no explanation outside JSON.

Return this exact JSON structure:
{{
  "detected_field": "The actual profession/industry you identified",
  "summary": "2-3 sentence overall assessment referencing their actual field and experience",
  "suggestions": [
    {{
      "icon": "✏️",
      "type": "improve",
      "heading": "Short heading",
      "text": "Detailed actionable advice specific to their field"
    }}
  ],
  "suitable_roles": ["Role 1", "Role 2", "Role 3"],
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "missing_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}

Rules:
- suggestions: 4-6 items, field-relevant; type in [improve, add, remove]; icons ✏️/➕/❌
- suitable_roles: 3-5 items within candidate's real profession
- missing_keywords: field-specific tools/skills/certs only
"""

    api_key = _get_gemini_key()
    if not api_key:
        return _fallback_analysis()

    last_error = None
    for attempt in range(1, 3):
        try:
            raw = _call_gemini(prompt, api_key)
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
            result = json.loads(raw)

            required = ['suitable_roles', 'strengths', 'weaknesses', 'suggestions', 'missing_keywords', 'summary']
            for field in required:
                if not result.get(field):
                    raise ValueError(f"Missing or empty field: {field}")

            logger.info(f"[Gemini] analyze_resume success attempt {attempt}. Field: {result.get('detected_field')}")
            return result

        except json.JSONDecodeError as e:
            last_error = f"JSON parse error attempt {attempt}: {e}"
            logger.error(f"[Gemini] {last_error}")
        except ValueError as e:
            last_error = f"Validation error attempt {attempt}: {e}"
            logger.error(f"[Gemini] {last_error}")
        except Exception as e:
            last_error = f"Error attempt {attempt}: {type(e).__name__}: {e}"
            logger.error(f"[Gemini] {last_error}")

    logger.error(f"[Gemini] analyze_resume all attempts failed: {last_error}")
    return _fallback_analysis()


def generate_interview_questions(resume_text, job_title='', job_description=''):
    """
    Groq-powered interview question generation (falls back to Gemini).
    Returns a list of question strings, or [] on failure.
    """
    target = job_title or job_description or 'the role shown in the resume'
    prompt = f"""You are an expert interview coach with deep knowledge across all industries.

Based on the following resume and target job, generate exactly 8-10 likely interview questions the candidate should prepare for.
Mix of: behavioral (Tell me about a time...), technical (based on skills in resume), and role-specific (based on job).

Return ONLY a valid JSON array of question strings — no markdown, no explanation, no extra text.
Example format: ["Question 1?", "Question 2?", ...]

Resume:
\"\"\"
{resume_text[:3000]}
\"\"\"

Target Job / Role: {target[:500]}"""

    # Try Groq first
    groq_key = _get_groq_key()
    if groq_key:
        try:
            raw = _call_groq(prompt, groq_key, timeout=30)
            raw = re.sub(r'^```(?:json)?\s*', '', raw.strip())
            raw = re.sub(r'\s*```$', '', raw)
            questions = json.loads(raw)
            if isinstance(questions, list) and len(questions) >= 4:
                logger.info(f"[Groq] generate_interview_questions: {len(questions)} questions")
                return [str(q).strip() for q in questions if str(q).strip()]
            logger.error(f"[Groq] Too few questions: {questions}")
        except RateLimitError:
            raise
        except Exception as e:
            logger.warning(f"[Groq] generate_interview_questions failed: {e} — falling back to Gemini")

    # Fallback to Gemini
    logger.info("[Gemini] generate_interview_questions fallback")
    gemini_key = _get_gemini_key()
    if not gemini_key:
        return []

    try:
        raw = _call_gemini(prompt, gemini_key, timeout=30)
        raw = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        raw = re.sub(r'\s*```$', '', raw)
        questions = json.loads(raw)
        if isinstance(questions, list) and len(questions) >= 4:
            logger.info(f"[Gemini] generate_interview_questions fallback: {len(questions)} questions")
            return [str(q).strip() for q in questions if str(q).strip()]
    except RateLimitError:
        raise
    except Exception as e:
        logger.error(f"[Gemini] generate_interview_questions fallback failed: {e}")

    return []


def evaluate_interview_answer(question, user_answer, resume_context=''):
    """
    Groq-powered answer evaluation (falls back to Gemini).
    Returns dict with: score, strengths, improvements, suggestedAnswer
    """
    prompt = f"""You are an expert interview coach. Evaluate the following interview answer honestly and constructively.

Return ONLY a valid JSON object with exactly these keys: score, strengths, improvements, suggestedAnswer.
- score: one of "Excellent", "Good", or "Needs Improvement"
- strengths: 1-2 sentences on what was done well
- improvements: 1-2 sentences on what could be better
- suggestedAnswer: a concise model answer (3-5 sentences) the candidate could use

No markdown, no extra text outside the JSON object.

Interview Question: {question}

Candidate's Answer: {user_answer[:1500] if user_answer else '(No answer provided)'}

Resume Context: {resume_context[:600] if resume_context else 'Not provided'}"""

    # Try Groq first
    groq_key = _get_groq_key()
    if groq_key:
        try:
            raw = _call_groq(prompt, groq_key, timeout=30)
            raw = re.sub(r'^```(?:json)?\s*', '', raw.strip())
            raw = re.sub(r'\s*```$', '', raw)
            result = json.loads(raw)
            for key in ('score', 'strengths', 'improvements', 'suggestedAnswer'):
                if key not in result:
                    raise ValueError(f"Missing key: {key}")
            logger.info("[Groq] evaluate_interview_answer success")
            return result
        except RateLimitError:
            raise
        except Exception as e:
            logger.warning(f"[Groq] evaluate_interview_answer failed: {e} — falling back to Gemini")

    # Fallback to Gemini
    logger.info("[Gemini] evaluate_interview_answer fallback")
    gemini_key = _get_gemini_key()
    if not gemini_key:
        return _fallback_feedback()

    try:
        raw = _call_gemini(prompt, gemini_key, timeout=30)
        raw = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        raw = re.sub(r'\s*```$', '', raw)
        result = json.loads(raw)
        for key in ('score', 'strengths', 'improvements', 'suggestedAnswer'):
            if key not in result:
                raise ValueError(f"Missing key: {key}")
        logger.info("[Gemini] evaluate_interview_answer fallback success")
        return result
    except RateLimitError:
        raise
    except Exception as e:
        logger.error(f"[Gemini] evaluate_interview_answer fallback failed: {e}")

    return _fallback_feedback()


# ── Fallbacks ──────────────────────────────────────────────────

def _fallback_feedback():
    return {
        'score': 'Good',
        'strengths': 'Your answer addressed the question directly.',
        'improvements': 'AI feedback is temporarily unavailable. Add specific examples and measurable outcomes.',
        'suggestedAnswer': 'AI feedback is temporarily unavailable. Please try again shortly.',
    }


def _fallback_analysis():
    return {
        "detected_field": "General",
        "summary": (
            "Your resume has been parsed and scored successfully. "
            "AI-powered feedback is temporarily unavailable — "
            "your ATS score and skill analysis are still shown below."
        ),
        "suggestions": [
            {"icon": "✏️", "type": "improve", "heading": "Strengthen your summary",
             "text": "Add a concise professional summary at the top with your years of experience and key skills."},
            {"icon": "➕", "type": "add", "heading": "Add industry-specific keywords",
             "text": "Include field-relevant keywords and tools to improve ATS match for your target roles."},
            {"icon": "📊", "type": "improve", "heading": "Quantify achievements",
             "text": "Replace vague statements with numbers — e.g. 'reduced downtime by 30%'."},
            {"icon": "🗂️", "type": "add", "heading": "Add a Projects or Certifications section",
             "text": "List 2-3 relevant projects or certifications with their impact and tools used."},
        ],
        "suitable_roles": ["Professional in your field", "Senior Specialist", "Department Lead"],
        "strengths": ["Resume successfully parsed", "Skills detected and scored"],
        "weaknesses": ["AI feedback temporarily unavailable", "Re-upload to get field-specific suggestions"],
        "missing_keywords": [],
    }