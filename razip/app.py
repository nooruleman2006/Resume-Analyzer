from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, current_user, login_required
from flask_wtf.csrf import CSRFProtect, CSRFError
from config import Config
from models.db import create_tables, migrate_tables
from models.user import User
from models.resume import Resume
from models.application import Application
from models.db import query
from datetime import datetime
import json, os

# ── App Init ──────────────────────────────────────────────────
app = Flask(__name__)
app.config.from_object(Config)
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

print("GROQ configured:", bool(Config.GROQ_API_KEY))
print("GEMINI configured:", bool(Config.GEMINI_API_KEY))

# ── Database Init ─────────────────────────────────────────────
create_tables()
migrate_tables()

# ── CSRF Protection ───────────────────────────────────────────
csrf = CSRFProtect(app)

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template('error.html',
        error_code=400,
        error_title='Invalid or Expired Form',
        error_message='Your form session has expired or was tampered with. Please go back and try again.'
    ), 400

# ── Flask-Login ───────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view     = 'auth.login'
login_manager.login_message  = 'Please log in to access this page.'
login_manager.login_message_category = 'error'

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(int(user_id))

# ── Blueprints ────────────────────────────────────────────────
from routes.auth_routes               import auth_bp
from routes.resume_routes             import resume_bp
from routes.job_routes                import job_bp
from routes.apply_routes              import apply_bp
from routes.settings_routes           import settings_bp
from routes.resume_builder_routes     import builder_bp
from routes.interview_routes          import interview_bp
from routes.start_interview_routes    import start_interview_bp

app.register_blueprint(auth_bp)
app.register_blueprint(resume_bp)
app.register_blueprint(job_bp)
app.register_blueprint(apply_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(builder_bp)
app.register_blueprint(interview_bp)
app.register_blueprint(start_interview_bp)

# ── Main / Dashboard routes ───────────────────────────────────
from flask import Blueprint
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


def _parse_date(val, fmt='%b %d, %Y'):
    """Parse a SQLite datetime string or a datetime object into a display string."""
    if not val:
        return '—'
    if isinstance(val, str):
        try:
            val = datetime.strptime(val[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return val
    return val.strftime(fmt)


@main_bp.route('/dashboard')
@login_required
def dashboard():
    latest_resume  = Resume.get_latest(current_user.id)
    recent_resumes = Resume.get_by_user(current_user.id, limit=3)
    stats          = Application.get_stats(current_user.id)
    recent_apps    = Application.get_by_user(current_user.id, limit=5)

    # ATS score from latest analysis
    ats_score      = 0
    present_skills = []
    missing_skills = []

    if latest_resume:
        result = query(
            "SELECT * FROM analysis_results WHERE resume_id=? ORDER BY analyzed_at DESC LIMIT 1",
            (latest_resume['id'],), fetchone=True
        )
        if result:
            ats_score      = result['ats_score']
            present_skills = json.loads(result['present_skills'] or '[]')
            missing_skills = json.loads(result['missing_skills'] or '[]')

    # Status CSS class mapping
    status_cls = {
        'pending':   'status-sent',
        'applied':   'status-sent',
        'viewed':    'status-viewed',
        'interview': 'status-interview',
        'rejected':  'status-rejected',
        'failed':    'status-rejected',
    }
    for app_item in recent_apps:
        app_item['cls']        = status_cls.get(app_item['status'], 'status-sent')
        app_item['applied_fmt'] = _parse_date(app_item.get('applied_at'), '%b %d')

    # Score level and formatted date for each resume
    def score_level(s):
        if s >= 75: return 'high'
        if s >= 55: return 'mid'
        return 'low'

    for r in recent_resumes:
        res = query(
            "SELECT ats_score FROM analysis_results WHERE resume_id=? LIMIT 1",
            (r['id'],), fetchone=True
        )
        r['score'] = res['ats_score'] if res else 0
        r['level'] = score_level(r['score'])
        r['date']  = _parse_date(r.get('upload_date'))

    return render_template('dashboard.html',
        ats_score          = ats_score,
        apps_sent          = stats.get('applied', 0) or 0,
        interviews         = stats.get('interviews', 0) or 0,
        resumes            = recent_resumes,
        applications       = recent_apps,
        present_skills     = present_skills,
        missing_skills     = missing_skills,
    )

app.register_blueprint(main_bp)


# ── Sidebar context processor ─────────────────────────────────
@app.context_processor
def sidebar_context():
    """Inject live sidebar data into every template."""
    from flask_login import current_user

    ctx = {
        'is_logged_in':       current_user.is_authenticated,
        'gemini_configured':  True,
        'sb_ats_score':       0,
        'sb_resume_count':    0,
        'sb_app_count':       0,
    }

    if current_user.is_authenticated:
        try:
            resumes = Resume.get_by_user(current_user.id, limit=100)
            ctx['sb_resume_count'] = len(resumes)

            latest = Resume.get_latest(current_user.id)
            if latest:
                ar = query(
                    "SELECT ats_score FROM analysis_results WHERE resume_id=? "
                    "ORDER BY analyzed_at DESC LIMIT 1",
                    (latest['id'],), fetchone=True
                )
                if ar:
                    ctx['sb_ats_score'] = ar['ats_score']

            stats = Application.get_stats(current_user.id)
            ctx['sb_app_count'] = int(stats.get('total') or 0)
        except Exception:
            pass
    ctx['gemini_configured'] = True

    return ctx


# ── Run ───────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
