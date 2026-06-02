from flask import (Blueprint, render_template, request, jsonify, session,
                   redirect, url_for, flash)
from flask_login import login_required, current_user
from models.resume import Resume
from models.db import query
from services.ai_analyzer import generate_interview_questions, evaluate_interview_answer, RateLimitError
import json

interview_bp = Blueprint('interview', __name__)


def _get_resume_context():
    """Return (resume_row, raw_text, brief_context) for the session's active resume."""
    resume_id = session.get('last_resume_id')
    if not resume_id:
        return None, '', ''
    resume = Resume.get_by_id(resume_id)
    if not resume or resume['user_id'] != current_user.id:
        return None, '', ''
    raw_text = resume.get('raw_text', '') or ''
    brief    = raw_text[:600]
    return resume, raw_text, brief


# ── Page ──────────────────────────────────────────────────────
@interview_bp.route('/interview-prep')
@login_required
def interview_prep():
    resume, raw_text, _ = _get_resume_context()
    job_title = (resume or {}).get('job_title', '') or ''
    return render_template('interview_prep.html',
        has_resume = bool(resume),
        job_title  = job_title,
        resume_filename = (resume or {}).get('filename', ''),
    )


# ── AJAX: Generate questions ──────────────────────────────────
@interview_bp.route('/interview-prep/generate', methods=['POST'])
@login_required
def generate_questions():
    data        = request.get_json(silent=True) or {}
    job_title   = (data.get('jobTitle') or '').strip()[:200]
    job_desc    = (data.get('jobDesc')  or '').strip()[:1500]

    _, raw_text, _ = _get_resume_context()

    if not raw_text:
        return jsonify({'ok': False, 'error': 'No resume found. Please upload and analyze a resume first.'}), 400

    try:
        questions = generate_interview_questions(raw_text, job_title, job_desc)
    except RateLimitError as e:
        return jsonify({'ok': False, 'error': 'rate_limit', 'retry_after': getattr(e, 'retry_after', 60)}), 429

    if not questions:
        return jsonify({'ok': False, 'error': 'Could not generate questions. Please try again in a moment.'}), 503

    return jsonify({'ok': True, 'questions': questions})


# ── AJAX: Evaluate answer ─────────────────────────────────────
@interview_bp.route('/interview-prep/evaluate', methods=['POST'])
@login_required
def evaluate_answer():
    data        = request.get_json(silent=True) or {}
    question    = (data.get('question')   or '').strip()
    user_answer = (data.get('answer')     or '').strip()

    if not question:
        return jsonify({'ok': False, 'error': 'No question provided.'}), 400

    _, _, brief_context = _get_resume_context()

    try:
        feedback = evaluate_interview_answer(question, user_answer, brief_context)
    except RateLimitError as e:
        return jsonify({'ok': False, 'error': 'rate_limit', 'retry_after': getattr(e, 'retry_after', 60)}), 429

    return jsonify({'ok': True, 'feedback': feedback})