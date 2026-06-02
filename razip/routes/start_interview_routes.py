from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from models.resume import Resume
from models.db import query
import services.interview_ai as interview_ai
import json

start_interview_bp = Blueprint('start_interview', __name__)


def _get_resume_text():
    """Return raw resume text for the current user's latest resume."""
    resume_id = session.get('last_resume_id')
    resume = None
    if resume_id:
        r = Resume.get_by_id(resume_id)
        if r and r['user_id'] == current_user.id:
            resume = r
    if not resume:
        resume = Resume.get_latest(current_user.id)
    if not resume:
        return '', ''
    raw = resume.get('raw_text', '') or ''
    job_title = resume.get('job_title', '') or ''
    return raw[:6000], job_title


@start_interview_bp.route('/start-interview')
@login_required
def start_interview_page():
    _, job_title = _get_resume_text()
    configured = interview_ai.is_configured()
    return render_template('start_interview.html',
                           job_title=job_title,
                           interview_configured=configured)


@start_interview_bp.route('/start-interview/chat', methods=['POST'])
@login_required
def interview_chat():
    data = request.get_json(silent=True) or {}
    role         = (data.get('role')         or '').strip()[:200]
    company_type = (data.get('company_type') or 'Corporate').strip()
    tone         = (data.get('tone')         or 'Neutral').strip()
    history      = data.get('history', [])

    if not role:
        return jsonify({'ok': False, 'error': 'Please provide the interview role.'}), 400

    resume_text, _ = _get_resume_text()

    system_prompt = interview_ai.build_system_prompt(role, company_type, tone, resume_text)

    try:
        reply = interview_ai.chat(system_prompt, history)
    except RuntimeError as e:
        return jsonify({'ok': False, 'error': str(e)}), 503
    except Exception as e:
        return jsonify({'ok': False, 'error': 'AI service error. Please try again.'}), 503

    return jsonify({'ok': True, 'reply': reply})


@start_interview_bp.route('/start-interview/report', methods=['POST'])
@login_required
def interview_report():
    data = request.get_json(silent=True) or {}
    role         = (data.get('role')         or '').strip()[:200]
    company_type = (data.get('company_type') or 'Corporate').strip()
    tone         = (data.get('tone')         or 'Neutral').strip()
    history      = data.get('history', [])

    resume_text, _ = _get_resume_text()
    system_prompt = interview_ai.build_system_prompt(role, company_type, tone, resume_text)

    try:
        raw = interview_ai.generate_report(system_prompt, history)
        report = json.loads(raw)
    except json.JSONDecodeError:
        return jsonify({'ok': False, 'error': 'Could not parse report. Please try again.'}), 503
    except RuntimeError as e:
        return jsonify({'ok': False, 'error': str(e)}), 503
    except Exception as e:
        return jsonify({'ok': False, 'error': 'Report generation failed. Please try again.'}), 503

    return jsonify({'ok': True, 'report': report})


@start_interview_bp.route('/start-interview/video-report', methods=['POST'])
@login_required
def interview_video_report():
    data = request.get_json(silent=True) or {}
    role         = (data.get('role')         or '').strip()[:200]
    company_type = (data.get('company_type') or 'Corporate').strip()
    tone         = (data.get('tone')         or 'Neutral').strip()
    history      = data.get('history', [])
    video_analytics = data.get('video_analytics', {})

    resume_text, _ = _get_resume_text()
    system_prompt = interview_ai.build_system_prompt(role, company_type, tone, resume_text)

    try:
        raw = interview_ai.generate_video_report(system_prompt, history, video_analytics)
        report = json.loads(raw)
        print("DEBUG REPORT:", json.dumps(report, indent=2))
    except json.JSONDecodeError:
        return jsonify({'ok': False, 'error': 'Could not parse report. Please try again.'}), 503
    except RuntimeError as e:
        return jsonify({'ok': False, 'error': str(e)}), 503
    except Exception as e:
        return jsonify({'ok': False, 'error': 'Report generation failed. Please try again.'}), 503

    return jsonify({'ok': True, 'report': report})
