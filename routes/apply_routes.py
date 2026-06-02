from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from services.auto_applier import auto_apply
from services.job_fetcher import fetch_all_jobs, get_sample_jobs
from services.job_matcher import rank_jobs, _detect_resume_field
from services.ats_scorer import detect_field
from models.resume import Resume
from models.application import Application
from models.db import query
import json

# Map detected field → a human-readable job search keyword
FIELD_SEARCH_KEYWORDS = {
    "electrical":  "Electrical Engineer",
    "mechanical":  "Mechanical Engineer",
    "civil":       "Civil Engineer",
    "software":    "Software Developer",
    "data":        "Data Analyst",
    "medical":     "Medical Doctor",
    "finance":     "Financial Analyst",
    "marketing":   "Marketing Manager",
    "education":   "Teacher",
    "hr":          "HR Manager",
}

apply_bp = Blueprint('apply', __name__)


@apply_bp.route('/auto-apply', methods=['GET', 'POST'])
@login_required
def auto_apply_page():
    latest_resume = Resume.get_latest(current_user.id)

    # BUG 5 FIX: Block access entirely if no resume uploaded
    if not latest_resume:
        flash('Please upload a resume before using Auto Apply.', 'error')
        return redirect(url_for('resume.upload'))

    # Build matched job list (shown on both GET and after POST)
    present_skills = []
    resume_text = ''
    if latest_resume:
        try:
            present_skills = json.loads(latest_resume.get('skills_extracted') or '[]')
        except Exception:
            present_skills = []
        resume_text = latest_resume.get('raw_text', '') or ''

    # Build field-aware search keywords so job fetching targets the right profession
    if resume_text:
        detected_field = detect_field(resume_text.lower())
        field_keyword = FIELD_SEARCH_KEYWORDS.get(detected_field, '')
    else:
        field_keyword = ''
    skill_keywords = ', '.join(present_skills[:3]) if present_skills else ''
    keywords = field_keyword or skill_keywords or 'engineer'

    all_jobs = fetch_all_jobs(keywords)
    if not all_jobs:
        all_jobs = get_sample_jobs()
    all_jobs = rank_jobs(all_jobs, present_skills, resume_text)

    # Mark already-applied
    applied_urls = set()
    for app in Application.get_by_user(current_user.id):
        if app.get('job_url'):
            applied_urls.add(app['job_url'])
    for job in all_jobs:
        job['already_applied'] = job.get('url', '') in applied_urls

    if request.method == 'GET':
        min_match = 70
        eligible = [j for j in all_jobs if j['match'] >= min_match and not j['already_applied']]
        return render_template('auto_apply.html',
            resume=latest_resume,
            all_jobs=all_jobs,
            eligible=eligible,
            min_match=min_match,
            results=None,
        )

    # ── POST: bulk apply ──────────────────────────────────────
    min_match = int(request.form.get('min_match', 70))
    eligible = [j for j in all_jobs if j['match'] >= min_match and not j['already_applied']]

    if not latest_resume:
        flash('Please upload a resume first.', 'error')
        return redirect(url_for('resume.upload'))

    if not eligible:
        flash('No new jobs meet your match threshold. Lower the threshold or browse more jobs.', 'info')
        return redirect(url_for('apply.auto_apply_page'))

    user_info = {
        'first_name': current_user.first_name,
        'last_name':  current_user.last_name,
    }

    results = []
    for job in eligible[:15]:
        success, message = auto_apply(job, {}, user_info)

        if not Application.already_applied(current_user.id, job.get('url', '')):
            Application.create(
                user_id=current_user.id,
                job_title=job.get('title', ''),
                company=job.get('company', ''),
                job_url=job.get('url', ''),
                location=job.get('location', ''),
                salary=job.get('salary', ''),
                match_score=job.get('match', 0),
                source=job.get('source', 'auto'),
                resume_id=latest_resume['id'],
            )
            # Mark status
            app_row = query(
                "SELECT id FROM applications WHERE user_id=%s AND job_url=%s "
                "ORDER BY applied_at DESC LIMIT 1",
                (current_user.id, job.get('url', '')), fetchone=True
            )
            if app_row:
                Application.update_status(app_row['id'], 'applied' if success else 'failed')

        results.append({
            'job':     job,
            'success': success,
            'message': message,
        })

    applied_count = sum(1 for r in results if r['success'])
    flash(f'Auto-apply complete: {applied_count} of {len(results)} applications submitted.', 'success')

    return render_template('auto_apply.html',
        resume=latest_resume,
        all_jobs=all_jobs,
        eligible=eligible,
        min_match=min_match,
        results=results,
        applied_count=applied_count,
    )
