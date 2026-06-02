import re
import json

# ── Field-specific skill keywords ─────────────────────────────
# Include both multi-word AND single-word variants so matching is robust
FIELD_SKILLS = {
    "electrical": [
        "autocad", "matlab", "plc", "scada", "etap", "proteus", "hmi",
        "pspice", "ltspice", "multisim", "pvsyst", "dialux",
        "transformer", "switchgear", "substation", "inverter", "rectifier",
        "vfd", "ups", "relay", "earthing", "commissioning",
        "circuit design", "power systems", "power distribution",
        "motor control", "panel design", "cable sizing", "lighting design",
        "protection relay", "relay protection", "load flow",
        "electrical drawings", "high voltage", "low voltage",
        "iec standards", "ieee standards", "iec 61850", "iec 60909", "nec",
    ],
    "mechanical": [
        "solidworks", "catia", "ansys", "creo", "inventor",
        "fea", "cfd", "cnc", "cam", "metrology",
        "thermodynamics", "hvac", "welding", "kaizen",
        "fluid mechanics", "manufacturing", "lean manufacturing",
        "six sigma", "iso 9001", "3d printing", "injection molding",
        "gd&t", "autocad",
    ],
    "civil": [
        "revit", "etabs", "staad", "safe", "sap2000", "primavera",
        "surveying", "gis",
        "structural design", "concrete design", "steel design",
        "foundation design", "road design", "drainage",
        "civil 3d", "ms project", "quantity surveying", "bill of quantities",
        "aci code", "eurocode", "autocad",
    ],
    "software": [
        "python", "java", "javascript", "typescript", "ruby", "go",
        "rust", "php", "swift", "kotlin", "react", "vue", "angular",
        "flask", "django", "nodejs", "express", "fastapi", "graphql",
        "docker", "kubernetes", "aws", "azure", "gcp", "jenkins",
        "mysql", "postgresql", "mongodb", "redis", "git", "github",
        "rest api", "ci/cd", "agile", "scrum", "c++", "c#",
    ],
    "data": [
        "pandas", "numpy", "tensorflow", "pytorch", "spark", "hadoop",
        "tableau", "airflow", "sklearn",
        "machine learning", "deep learning", "nlp", "computer vision",
        "data visualization", "a/b testing", "etl", "power bi",
        "scikit-learn", "sql", "statistics",
    ],
    "medical": [
        "emr", "ehr", "hipaa", "cpr", "acls", "bls", "ecg", "ultrasound",
        "pharmacology", "anatomy", "physiology", "surgery", "radiology",
        "pathology", "nursing",
        "clinical diagnosis", "patient care", "icd-10",
        "medical research", "clinical trials", "medical coding", "gcp",
    ],
    "finance": [
        "bloomberg", "cfa", "cpa", "gaap", "ifrs", "quickbooks",
        "accounting", "audit", "taxation", "investment", "portfolio",
        "valuation", "derivatives", "treasury",
        "financial modeling", "dcf", "risk management",
        "equity research", "investment banking", "corporate finance",
        "financial analysis", "portfolio analysis", "sap",
    ],
    "marketing": [
        "seo", "sem", "hubspot", "salesforce", "canva", "mailchimp",
        "advertising", "branding", "copywriting",
        "google analytics", "google ads", "facebook ads",
        "campaign management", "brand strategy", "crm", "a/b testing",
        "content marketing", "social media", "email marketing",
        "market research", "adobe creative", "conversion rate optimization",
    ],
    "education": [
        "pedagogy", "lms", "moodle",
        "curriculum development", "lesson planning", "student assessment",
        "classroom management", "differentiated instruction",
        "e-learning", "google classroom", "bloom taxonomy",
        "special education", "ib curriculum", "cambridge curriculum",
    ],
    "hr": [
        "recruitment", "onboarding", "payroll", "hris", "workday", "shrm",
        "talent acquisition", "performance management",
        "employee relations", "labor law", "training development",
        "succession planning", "organizational development",
        "compensation", "benefits", "linkedin recruiter", "sap hr",
    ],
}

# ── Field detection: single strong words per field ────────────
# These are words that almost certainly appear in that field's resume
# Using single words / short phrases that even a brief mention will match
FIELD_WORD_SCORES = {
    "electrical": [
        # Very specific EE-only words (high value)
        ("electrical", 3), ("electricity", 3), ("electr", 2),
        ("voltage", 3), ("wiring", 3), ("transformer", 3),
        ("substation", 3), ("switchgear", 3), ("plc", 3),
        ("scada", 3), ("etap", 3), ("proteus", 3), ("hmi", 2),
        ("relay", 2), ("earthing", 3), ("inverter", 3),
        ("rectifier", 3), ("vfd", 3), ("ampere", 3), ("kilowatt", 3),
        ("kva", 2), ("mva", 2), ("ohm", 2), ("circuit", 2),
        ("panel", 2), ("capacitor", 3), ("inductor", 3),
        ("power grid", 3), ("power plant", 3), ("power system", 3),
        ("high voltage", 3), ("low voltage", 3), ("medium voltage", 3),
        ("electrical engineering", 5), ("b.e electrical", 5),
        ("b.sc electrical", 5), ("b.tech electrical", 5),
        ("m.sc electrical", 5), ("m.tech electrical", 5),
        ("dept. of electrical", 5), ("department of electrical", 5),
        ("faculty of electrical", 5),
    ],
    "mechanical": [
        ("mechanical", 3), ("solidworks", 3), ("catia", 3),
        ("thermodynamics", 3), ("hvac", 2), ("cnc", 3),
        ("hydraulic", 3), ("pneumatic", 3), ("gearbox", 3),
        ("mechanical engineering", 5),
    ],
    "civil": [
        ("civil", 3), ("structural", 3), ("concrete", 2),
        ("rebar", 3), ("foundation", 2), ("surveying", 3),
        ("revit", 3), ("etabs", 3), ("staad", 3),
        ("civil engineering", 5),
    ],
    "software": [
        ("software engineer", 4), ("software developer", 4),
        ("web developer", 4), ("backend", 3), ("frontend", 3),
        ("full stack", 3), ("fullstack", 3), ("devops", 3),
        ("programming", 2), ("algorithm", 2), ("deployment", 2),
        ("computer science", 4), ("information technology", 3),
    ],
    "data": [
        ("data scientist", 5), ("data analyst", 5),
        ("machine learning", 4), ("deep learning", 4),
        ("neural network", 4), ("dataset", 3), ("model training", 3),
        ("data engineering", 4), ("business intelligence", 4),
    ],
    "medical": [
        ("patient", 2), ("clinical", 2), ("hospital", 2),
        ("diagnosis", 3), ("treatment", 2), ("surgery", 3),
        ("medical", 2), ("pharmacy", 3), ("nursing", 3),
        ("physician", 4), ("doctor", 3), ("mbbs", 5), ("md ", 3),
    ],
    "finance": [
        ("accounting", 2), ("audit", 2), ("taxation", 3),
        ("financial", 2), ("investment", 2), ("banking", 2),
        ("portfolio", 3), ("treasury", 3), ("cfa", 3), ("cpa", 3),
        ("finance manager", 4), ("financial analyst", 4),
    ],
    "marketing": [
        ("marketing", 2), ("advertising", 2), ("campaign", 2),
        ("brand", 2), ("seo", 3), ("social media", 2),
        ("content strategy", 3), ("digital marketing", 4),
    ],
    "education": [
        ("teaching", 2), ("classroom", 3), ("curriculum", 3),
        ("pedagogy", 4), ("students", 2), ("faculty", 2),
        ("academic", 2), ("tutor", 3), ("lecturer", 3),
        ("professor", 3), ("teacher", 3),
    ],
    "hr": [
        ("recruitment", 3), ("payroll", 3), ("onboarding", 3),
        ("talent acquisition", 4), ("human resources", 4),
        ("hr manager", 4), ("hrbp", 4),
    ],
}

# ── Soft skills (universal fallback) ──────────────────────────
SOFT_SKILLS = [
    "communication", "leadership", "teamwork", "problem solving", "analytical",
    "management", "collaboration", "critical thinking", "time management",
    "adaptability", "creativity", "attention to detail",
]

# ── Section headings ATS expects ──────────────────────────────
SECTION_HEADINGS = [
    "experience", "education", "skills", "summary", "objective",
    "projects", "certifications", "achievements", "languages", "references"
]


def detect_field(text_lower):
    """
    Detect the professional field by scoring single-word / short-phrase
    indicators. Each indicator has a weight; the field with the highest
    total score wins. No multi-word phrase dependency — even one strong
    word (e.g. 'voltage', 'scada') is enough to tip towards electrical.
    """
    scores = {field: 0 for field in FIELD_WORD_SCORES}

    for field, weighted_words in FIELD_WORD_SCORES.items():
        for word, weight in weighted_words:
            if word in text_lower:
                scores[field] += weight

    best_field = max(scores, key=scores.get)
    if scores[best_field] == 0:
        return "software"  # last-resort default
    return best_field


def calculate_ats_score(resume_text, job_description=''):
    """
    Returns a dict with:
      ats_score, readability_score, keyword_score,
      present_skills, missing_skills, score_breakdown, detected_field
    """
    text_lower = resume_text.lower()

    # 0 ── Detect professional field ──────────────────
    detected_field = detect_field(text_lower)
    field_skills = FIELD_SKILLS.get(detected_field, FIELD_SKILLS["software"])

    # 1 ── Skills detection (field-specific) ──────────
    present_skills = []
    for skill in field_skills:
        # Use word boundaries; re.escape handles special chars like c++
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text_lower):
            present_skills.append(skill)

    # If no technical skills found, fall back to soft skills only
    if not present_skills:
        present_skills = [s for s in SOFT_SKILLS if s in text_lower]

    missing_skills = [s for s in field_skills if s not in present_skills][:10]

    skills_score = min(int((len(present_skills) / max(len(field_skills) * 0.3, 1)) * 100), 100)

    # 2 ── Section headings ────────────────────────────
    sections_found = sum(1 for h in SECTION_HEADINGS if h in text_lower)
    section_score = int((sections_found / len(SECTION_HEADINGS)) * 100)

    # 3 ── Keyword match with job description ──────────
    if job_description:
        jd_lower = job_description.lower()
        jd_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', jd_lower))
        res_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', text_lower))
        overlap = jd_words & res_words
        keyword_score = min(int((len(overlap) / max(len(jd_words), 1)) * 100), 100)
    else:
        # Score against field-specific skills when no JD provided
        keyword_score = min(int((len(present_skills) / max(len(field_skills) * 0.4, 1)) * 100), 100)

    # 4 ── Formatting signals ──────────────────────────
    bullet_count = resume_text.count('•') + resume_text.count('-') + resume_text.count('*')
    has_email = bool(re.search(r'[\w.]+@[\w.]+\.\w+', resume_text))
    has_phone = bool(re.search(r'[\+\d][\d\s\-]{8,}', resume_text))
    word_count = len(resume_text.split())
    format_score = 50
    format_score += 15 if has_email else 0
    format_score += 10 if has_phone else 0
    format_score += 10 if bullet_count > 5 else 0
    format_score += 15 if 300 < word_count < 1200 else 0
    format_score = min(format_score, 100)

    # 5 ── Work experience signals ─────────────────────
    exp_keywords = ['experience', 'worked', 'developed', 'managed', 'built', 'designed', 'implemented', 'led']
    exp_score = min(sum(10 for w in exp_keywords if w in text_lower), 100)

    # 6 ── Readability ─────────────────────────────────
    sentences = re.split(r'[.!?]', resume_text)
    avg_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
    readability = 100 if avg_len < 20 else max(100 - int((avg_len - 20) * 3), 40)

    # 7 ── Overall ATS score (weighted) ────────────────
    ats_score = int(
        skills_score * 0.30 +
        section_score * 0.20 +
        keyword_score * 0.20 +
        format_score * 0.15 +
        exp_score * 0.15
    )

    score_breakdown = {
        "Skills Match": skills_score,
        "Work Experience": exp_score,
        "Section Structure": section_score,
        "Formatting": format_score,
        "Keywords": keyword_score,
    }

    return {
        "ats_score": ats_score,
        "readability_score": readability,
        "keyword_score": keyword_score,
        "present_skills": present_skills,
        "missing_skills": missing_skills,
        "score_breakdown": score_breakdown,
        "detected_field": detected_field,
    }
