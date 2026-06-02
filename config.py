import os
from dotenv import load_dotenv

load_dotenv(override=False)  # Replit Secrets (env vars) take precedence over .env file

class Config:
    # ── Flask ──────────────────────────────────────────
    SECRET_KEY = os.getenv('SECRET_KEY') or 'dev-secret-key-change-in-production'
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024   # 5 MB upload limit

    # ── CSRF (Flask-WTF) ───────────────────────────────
    WTF_CSRF_ENABLED      = True
    WTF_CSRF_TIME_LIMIT   = 3600  # 1 hour token expiry

    # ── Database (SQLite) ──────────────────────────────
    DB_PATH = os.path.join(os.path.dirname(__file__), 'resume_analyzer.db')

    # ── Gemini AI (ATS scoring) ────────────────────────
    # Support both GEMINI_API_KEY and GOOGLE_API_KEY (Replit default name)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY', '')

    # ── Gemini AI (Interview feature — isolated key) ───
    GEMINI_API_KEY_2 = os.getenv('GEMINI_API_KEY_2', '')

    # ── Groq AI ────────────────────────────────────────
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

    # ── Job APIs ───────────────────────────────────────
    ADZUNA_APP_ID  = os.getenv('ADZUNA_APP_ID',  '')
    ADZUNA_APP_KEY = os.getenv('ADZUNA_APP_KEY', '')
    RAPIDAPI_KEY   = os.getenv('RAPIDAPI_KEY',   '')

    # ── File Upload ────────────────────────────────────
    UPLOAD_FOLDER      = os.path.join(os.path.dirname(__file__), 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}
