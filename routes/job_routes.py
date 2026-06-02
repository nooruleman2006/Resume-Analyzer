from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from services.job_fetcher import fetch_all_jobs, get_sample_jobs
from config import Config
from services.job_matcher import rank_jobs
from models.resume import Resume
from models.application import Application
from models.db import query
from datetime import datetime
import json

job_bp = Blueprint('jobs', __name__)


def _fmt_date(val, fmt='%b %d, %Y'):
    if not val:
        return '—'
    if isinstance(val, str):
        try:
            val = datetime.strptime(val[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return val
    return val.strftime(fmt)


@job_bp.route('/jobs')
@login_required
def browse_jobs():
    search_query = request.args.get('q', '').strip()
    location = request.args.get('location', 'Pakistan').strip() or 'Pakistan'
    job_type = request.args.get('type', '').strip()

    latest_resume = Resume.get_latest(current_user.id)
    present_skills = []
    resume_text = ''

    if latest_resume:
        try:
            present_skills = json.loads(latest_resume.get('skills_extracted') or '[]')
        except Exception:
            present_skills = []
        resume_text = latest_resume.get('raw_text', '') or ''

    keywords = search_query or (', '.join(present_skills[:5]) if present_skills else 'software developer')
    jobs = fetch_all_jobs(keywords, location=location)
    if not jobs:
        jobs = get_sample_jobs()

    jobs = rank_jobs(jobs, present_skills, resume_text)

    if job_type and job_type != 'Any Type':
        jobs = [j for j in jobs if job_type.lower() in (j.get('type', '').lower())]

    applied_urls = set()
    user_apps = Application.get_by_user(current_user.id)
    for app in user_apps:
        if app.get('job_url'):
            applied_urls.add(app['job_url'])

    for job in jobs:
        job['applied'] = job.get('url', '') in applied_urls

    return render_template('jobs.html',
        jobs=jobs,
        job_count=len(jobs),
        query=search_query,
        location=location,
        job_type=job_type,
        has_jsearch=bool(Config.RAPIDAPI_KEY),
    )


@job_bp.route('/apply/<job_id>', methods=['POST'])
@login_required
def apply_job(job_id):
    job_title = request.form.get('job_title', '')
    company = request.form.get('company', '')
    job_url = request.form.get('job_url', '')
    location = request.form.get('location', '')
    salary = request.form.get('salary', '')
    match_score = int(request.form.get('match_score', 0))
    source = request.form.get('source', 'manual')

    latest_resume = Resume.get_latest(current_user.id)
    resume_id = latest_resume['id'] if latest_resume else None

    if not Application.already_applied(current_user.id, job_url):
        Application.create(
            user_id=current_user.id,
            job_title=job_title,
            company=company,
            job_url=job_url,
            location=location,
            salary=salary,
            match_score=match_score,
            source=source,
            resume_id=resume_id,
        )
        app_row = query(
            "SELECT id FROM applications WHERE user_id=%s AND job_url=%s ORDER BY applied_at DESC LIMIT 1",
            (current_user.id, job_url), fetchone=True
        )
        if app_row:
            Application.update_status(app_row['id'], 'applied')
        flash(f'Applied to {job_title} at {company}!', 'success')
    else:
        flash('You have already applied to this job.', 'error')

    return redirect(url_for('jobs.browse_jobs'))


@job_bp.route('/applied')
@login_required
def applications():
    apps = Application.get_by_user(current_user.id)
    stats = Application.get_stats(current_user.id)

    status_cls = {
        'pending': 'status-sent',
        'applied': 'status-sent',
        'viewed': 'status-viewed',
        'interview': 'status-interview',
        'rejected': 'status-rejected',
        'failed': 'status-rejected',
    }
    for a in apps:
        a['cls'] = status_cls.get(a['status'], 'status-sent')
        a['applied_fmt'] = _fmt_date(a.get('applied_at'), '%b %d')

    return render_template('applied.html', applications=apps, stats=stats)
