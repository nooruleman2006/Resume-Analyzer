import re


# ── Field-specific job title keywords for bonus scoring ──────
FIELD_TITLE_KEYWORDS = {
    "electrical": [
        "electrical", "electronics", "power", "circuit", "automation",
        "instrumentation", "plc", "scada", "hvac", "control", "energy",
        "substation", "protection", "relay", "engineer",
    ],
    "mechanical": [
        "mechanical", "manufacturing", "production", "hvac", "automotive",
        "maintenance", "design", "engineer", "cad", "cnc",
    ],
    "civil": [
        "civil", "structural", "construction", "site", "infrastructure",
        "highway", "bridge", "geotechnical", "quantity", "surveyor",
    ],
    "software": [
        "software", "developer", "engineer", "backend", "frontend",
        "fullstack", "devops", "cloud", "python", "java", "react",
    ],
    "data": [
        "data", "analyst", "scientist", "machine learning", "ai",
        "intelligence", "analytics", "bi", "statistics",
    ],
    "medical": [
        "doctor", "physician", "nurse", "clinical", "medical",
        "health", "healthcare", "dental", "pharmacy", "therapist",
    ],
    "finance": [
        "finance", "accounting", "audit", "tax", "investment",
        "banking", "financial", "analyst", "treasury", "cfa",
    ],
    "marketing": [
        "marketing", "digital", "seo", "brand", "content",
        "social", "campaign", "growth", "advertising",
    ],
}


def _detect_resume_field(present_skills, resume_text):
    """Guess field from skills + resume text for better matching."""
    text = resume_text.lower()
    skills_str = ' '.join(s.lower() for s in present_skills)

    field_signals = {
        "electrical": ["electrical", "voltage", "plc", "scada", "transformer", "circuit", "substation"],
        "mechanical": ["mechanical", "solidworks", "catia", "thermodynamics", "cnc", "hvac"],
        "civil":      ["civil", "structural", "concrete", "foundation", "surveying", "etabs"],
        "software":   ["python", "java", "javascript", "react", "django", "flask", "nodejs"],
        "data":       ["machine learning", "deep learning", "pandas", "tensorflow", "dataset"],
        "medical":    ["patient", "clinical", "hospital", "diagnosis", "nursing", "medical"],
        "finance":    ["accounting", "audit", "financial", "investment", "portfolio"],
        "marketing":  ["seo", "campaign", "brand", "advertising", "social media"],
    }

    best_field, best_score = "software", 0
    combined = text + " " + skills_str
    for field, signals in field_signals.items():
        score = sum(1 for s in signals if s in combined)
        if score > best_score:
            best_score, best_field = score, field
    return best_field


def score_job_match(job, present_skills, resume_text=''):
    """
    Score how well a job matches the user's resume.
    Returns match percentage (0-100).
    Field-aware: uses resume field to determine relevant bonus keywords.
    """
    score = 0
    title_lower = job.get('title', '').lower()
    desc_lower  = (job.get('description', '') or '').lower()
    text_lower  = resume_text.lower()
    skill_set   = set(s.lower() for s in present_skills)

    # ── 1. Job title words vs resume text (most reliable) ──────
    title_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', title_lower))
    matched_in_resume = sum(1 for w in title_words if w in text_lower)
    score += min(matched_in_resume * 10, 40)

    # ── 2. Skills vs job title words ───────────────────────────
    skill_title_overlap = title_words & skill_set
    score += min(len(skill_title_overlap) * 12, 30)

    # ── 3. Skills vs job description (if available) ────────────
    if desc_lower:
        desc_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', desc_lower))
        skill_desc_overlap = desc_words & skill_set
        score += min(len(skill_desc_overlap) * 5, 20)

    # ── 4. Field-specific title keyword bonus ──────────────────
    detected_field = _detect_resume_field(present_skills, resume_text)
    field_kws = FIELD_TITLE_KEYWORDS.get(detected_field, [])
    field_hits = sum(1 for kw in field_kws if kw in title_lower)
    score += min(field_hits * 8, 24)

    # ── 5. Generic seniority/role-level bonuses ─────────────────
    seniority_words = {"senior", "lead", "manager", "head", "principal", "director"}
    resume_seniority = seniority_words & set(re.findall(r'\b\w+\b', text_lower))
    title_seniority  = seniority_words & title_words
    if resume_seniority & title_seniority:
        score += 6

    # Ensure a base score of at least 10 if any title word appears in resume
    if score == 0 and matched_in_resume > 0:
        score = 15

    return min(score, 99)  # 99 cap — perfect match reserved for exact JD


def rank_jobs(jobs, present_skills, resume_text=''):
    """
    Score all jobs and sort by match percentage descending.
    Returns the same list with 'match' field populated.
    """
    for job in jobs:
        job['match'] = score_job_match(job, present_skills, resume_text)

    jobs.sort(key=lambda j: j['match'], reverse=True)

    # Mark top 2 as featured
    for i, job in enumerate(jobs):
        job['featured'] = (i < 2 and job['match'] >= 60)

    return jobs
