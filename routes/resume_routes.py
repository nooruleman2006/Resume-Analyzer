from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from utils.validators import allowed_file, allowed_mimetype
from utils.helpers import save_uploaded_file
from services.pdf_parser import parse_resume
from services.ats_scorer import calculate_ats_score
from services.ai_analyzer import analyze_resume
from models.resume import Resume
from models.db import query
from datetime import datetime
import json, os

resume_bp = Blueprint('resume', __name__)


def _fmt_date(val, fmt='%b %d, %Y'):
    """Parse a SQLite datetime string or datetime object into a display string."""
    if not val:
        return '—'
    if isinstance(val, str):
        try:
            val = datetime.strptime(val[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return val
    return val.strftime(fmt)


@resume_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'GET':
        return render_template('upload.html')

    # ── Validate file ─────────────────────────────────
    file = request.files.get('resume')
    if not file or file.filename == '':
        flash('Please select a resume file.', 'error')
        return redirect(url_for('resume.upload'))

    if not allowed_file(file.filename) or not allowed_mimetype(file):
        flash('Only PDF, DOC, and DOCX files are allowed.', 'error')
        return redirect(url_for('resume.upload'))

    # ── Save file ─────────────────────────────────────
    stored_path, original_name = save_uploaded_file(file, current_user.id)

    # ── Extract text ──────────────────────────────────
    try:
        raw_text = parse_resume(stored_path)
    except Exception as e:
        flash(f'Could not read your file: {str(e)}', 'error')
        return redirect(url_for('resume.upload'))

    if len(raw_text.strip()) < 50:
        flash('Resume appears to be empty or unreadable. Please try a different file.', 'error')
        return redirect(url_for('resume.upload'))

    # ── ATS Scoring ───────────────────────────────────
    job_title       = request.form.get('job_title', '').strip()
    industry        = request.form.get('industry',  '').strip()
    job_description = request.form.get('job_desc',  '').strip()

    ats_data = calculate_ats_score(raw_text, job_description)

    # ── AI Analysis ───────────────────────────────────
    ai_data = analyze_resume(
        raw_text,
        job_title       = job_title,
        job_description = job_description,
        present_skills  = ats_data['present_skills'],
        missing_skills  = ats_data['missing_skills'],
    )

    # ── Save to DB ────────────────────────────────────
    resume_id = Resume.create(
        user_id         = current_user.id,
        filename        = original_name,
        stored_path     = stored_path,
        raw_text        = raw_text,
        skills          = ats_data['present_skills'],
        job_title       = job_title,
        industry        = industry,
        job_description = job_description,
    )

    query(
        """INSERT INTO analysis_results
           (resume_id, ats_score, readability_score, keyword_score,
            ai_summary, ai_suggestions, ai_strengths, ai_weaknesses,
            ai_suitable_roles, present_skills, missing_skills, score_breakdown)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            resume_id,
            ats_data['ats_score'],
            ats_data['readability_score'],
            ats_data['keyword_score'],
            ai_data.get('summary', ''),
            json.dumps(ai_data.get('suggestions', [])),
            json.dumps(ai_data.get('strengths', [])),
            json.dumps(ai_data.get('weaknesses', [])),
            json.dumps(ai_data.get('suitable_roles', [])),
            json.dumps(ats_data['present_skills']),
            json.dumps(ats_data['missing_skills']),
            json.dumps(ats_data['score_breakdown']),
        ),
        commit=True
    )

    session['last_resume_id'] = resume_id
    return redirect(url_for('resume.analysis'))


@resume_bp.route('/resumes')
@login_required
def resumes():
    rows = Resume.get_by_user(current_user.id, limit=100)
    items = []
    for r in rows:
        ar = query(
            "SELECT ats_score, readability_score, keyword_score, analyzed_at "
            "FROM analysis_results WHERE resume_id=? ORDER BY analyzed_at DESC LIMIT 1",
            (r['id'],), fetchone=True
        )
        score = ar['ats_score'] if ar else None
        level = 'high' if score and score >= 75 else ('mid' if score and score >= 50 else 'low')
        items.append({
            'id':         r['id'],
            'filename':   r['filename'],
            'job_title':  r['job_title'] or '—',
            'industry':   r['industry'] or '—',
            'date':       _fmt_date(r.get('upload_date')),
            'score':      score,
            'level':      level,
            'readability': ar['readability_score'] if ar else None,
            'keyword':    ar['keyword_score'] if ar else None,
            'analyzed':   bool(ar),
        })
    return render_template('resumes.html', resumes=items)


@resume_bp.route('/resumes/<int:resume_id>/delete', methods=['POST'])
@login_required
def delete_resume(resume_id):
    r = Resume.get_by_id(resume_id)
    if not r or r['user_id'] != current_user.id:
        flash('Resume not found.', 'error')
        return redirect(url_for('resume.resumes'))

    # Delete analysis results first (FK cascade would handle it but be explicit)
    query("DELETE FROM analysis_results WHERE resume_id=?", (resume_id,), commit=True)
    query("DELETE FROM resumes WHERE id=?", (resume_id,), commit=True)

    # Remove stored file if it exists
    try:
        if r.get('stored_path') and os.path.exists(r['stored_path']):
            os.remove(r['stored_path'])
    except Exception:
        pass

    flash('Resume deleted successfully.', 'success')
    return redirect(url_for('resume.resumes'))


@resume_bp.route('/resumes/<int:resume_id>/view')
@login_required
def view_resume(resume_id):
    r = Resume.get_by_id(resume_id)
    if not r or r['user_id'] != current_user.id:
        flash('Resume not found.', 'error')
        return redirect(url_for('resume.resumes'))
    session['last_resume_id'] = resume_id
    return redirect(url_for('resume.analysis'))


@resume_bp.route('/analysis')
@login_required
def analysis():
    resume_id = session.get('last_resume_id')
    if not resume_id:
        flash('No analysis found. Please upload a resume first.', 'error')
        return redirect(url_for('resume.upload'))

    resume = Resume.get_by_id(resume_id)
    if not resume or resume['user_id'] != current_user.id:
        flash('Resume not found.', 'error')
        return redirect(url_for('resume.upload'))

    result = query(
        "SELECT * FROM analysis_results WHERE resume_id = ? ORDER BY analyzed_at DESC LIMIT 1",
        (resume_id,), fetchone=True
    )

    if not result:
        flash('Analysis not found.', 'error')
        return redirect(url_for('resume.upload'))

    suggestions     = json.loads(result['ai_suggestions']    or '[]')
    strengths       = json.loads(result.get('ai_strengths',  '[]') or '[]')
    weaknesses      = json.loads(result.get('ai_weaknesses', '[]') or '[]')
    suitable_roles  = json.loads(result.get('ai_suitable_roles', '[]') or '[]')
    present_skills  = json.loads(result['present_skills']    or '[]')
    missing_skills  = json.loads(result['missing_skills']    or '[]')
    score_breakdown = json.loads(result['score_breakdown']   or '{}')

    return render_template('results.html',
        resume          = resume,
        upload_date     = _fmt_date(resume.get('upload_date')),
        score           = result['ats_score'],
        readability     = result['readability_score'],
        keyword_score   = result['keyword_score'],
        summary         = result['ai_summary'] or '',
        suggestions     = suggestions,
        strengths       = strengths,
        weaknesses      = weaknesses,
        suitable_roles  = suitable_roles,
        present_skills  = present_skills,
        missing_skills  = missing_skills,
        breakdown       = list(score_breakdown.items()),
    )
