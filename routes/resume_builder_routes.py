from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session, jsonify, send_file, make_response)
from flask_login import login_required, current_user
from models.db import query
from services.ats_scorer import calculate_ats_score
from services.ai_analyzer import analyze_resume
from models.resume import Resume
import json, io, os, re
from datetime import datetime

builder_bp = Blueprint('builder', __name__)

# ── Template catalogue ─────────────────────────────────────
TEMPLATES_LIST = [
    {'id': 'professional',    'label': 'Professional',      'file': 'resume_professional.html',    'preview_color': '#7c3aed', 'description': 'Clean corporate style'},
    {'id': 'executive',       'label': 'Executive',         'file': 'resume_executive.html',       'preview_color': '#0f4c3a', 'description': 'Bold executive presence'},
    {'id': 'modern_minimal',  'label': 'Modern Minimal',    'file': 'resume_modern_minimal.html',  'preview_color': '#2563eb', 'description': 'Sleek and contemporary'},
    {'id': 'simple_classic',  'label': 'Simple Classic',    'file': 'resume_simple_classic.html',  'preview_color': '#374151', 'description': 'Timeless classic layout'},
    {'id': 'elegant',         'label': 'Elegant',           'file': 'resume_elegant.html',         'preview_color': '#9f7aea', 'description': 'Refined elegant design'},
    {'id': 'tech_developer',  'label': 'Tech Developer',    'file': 'resume_tech_developer.html',  'preview_color': '#0ea5e9', 'description': 'Perfect for engineers'},
    {'id': 'creative_bold',   'label': 'Creative Bold',     'file': 'resume_creative_bold.html',   'preview_color': '#e11d48', 'description': 'Stand-out creative flair'},
    {'id': 'academic',        'label': 'Academic',          'file': 'resume_academic.html',        'preview_color': '#1d4ed8', 'description': 'Ideal for researchers'},
    {'id': 'ats_friendly',    'label': 'ATS Friendly',      'file': 'resume_ats_friendly.html',    'preview_color': '#15803d', 'description': 'Optimised for ATS systems'},
    {'id': 'two_column_pro',  'label': 'Two Column Pro',    'file': 'resume_two_column_pro.html',  'preview_color': '#0f766e', 'description': 'Space-efficient two columns'},
    {'id': 'fresh_graduate',  'label': 'Fresh Graduate',    'file': 'resume_fresh_graduate.html',  'preview_color': '#d97706', 'description': 'Great for new graduates'},
    {'id': 'corporate_blue',  'label': 'Corporate Blue',    'file': 'resume_corporate_blue.html',  'preview_color': '#1e40af', 'description': 'Traditional corporate blue'},
    {'id': 'dark_mode',       'label': 'Dark Mode',         'file': 'resume_dark_mode.html',       'preview_color': '#1f2937', 'description': 'Striking dark theme'},
    {'id': 'compact_one_page','label': 'Compact One Page',  'file': 'resume_compact_one_page.html','preview_color': '#6d28d9', 'description': 'Fits everything on one page'},
    {'id': 'infographic',     'label': 'Infographic',       'file': 'resume_infographic.html',     'preview_color': '#db2777', 'description': 'Visual infographic style'},
    {'id': 'minimalist_pro',  'label': 'Minimalist Pro',    'file': 'resume_minimalist_pro.html',  'preview_color': '#475569', 'description': 'Clean minimalist layout'},
    {'id': 'slate_gold',      'label': 'Slate & Gold',      'file': 'resume_slate_gold.html',      'preview_color': '#b45309', 'description': 'Sophisticated slate & gold'},
]

_TEMPLATES_BY_ID = {t['id']: t for t in TEMPLATES_LIST}


# ── Template -> render-style config ─────────────────────────
# layout: 'plain'    -> ATS-safe, single column, no color/boxes
#         'centered' -> centered header + accent line, two-column body
#         'banner'   -> full-width colored header band, single column body
#         'sidebar'  -> colored left column + main content column
# accent: matches each template's preview_color above
# font:   'Helvetica' or 'Times' (fpdf2 core fonts)
# 'variant' (only meaningful for layout='plain') carries small
# typographic-only knobs so the 5 ATS-safe/no-color templates stay
# distinguishable from one another without breaking ATS-safety:
#   align:   'left' or 'center' name/header alignment
#   divider: 'none' | 'single' | 'double' rule style under headings
#   spacing: extra character-spacing (tracking) on section headings
#   compact: tighter line-height / smaller body font when True
TEMPLATE_STYLES = {
    'professional':     {'layout': 'centered', 'accent': '#7c3aed', 'font': 'Helvetica'},
    'executive':        {'layout': 'banner',   'accent': '#0f4c3a', 'font': 'Times'},
    'modern_minimal':   {'layout': 'centered', 'accent': '#2563eb', 'font': 'Helvetica'},
    'simple_classic':   {'layout': 'plain',    'accent': '#374151', 'font': 'Times',
                          'variant': {'align': 'center', 'divider': 'double', 'spacing': 0, 'compact': False}},
    'elegant':          {'layout': 'centered', 'accent': '#9f7aea', 'font': 'Times'},
    'tech_developer':   {'layout': 'sidebar',  'accent': '#0ea5e9', 'font': 'Helvetica'},
    'creative_bold':    {'layout': 'sidebar',  'accent': '#e11d48', 'font': 'Helvetica'},
    'academic':         {'layout': 'plain',    'accent': '#1d4ed8', 'font': 'Times',
                          'variant': {'align': 'left', 'divider': 'single', 'spacing': 0, 'compact': False}},
    'ats_friendly':     {'layout': 'plain',    'accent': '#15803d', 'font': 'Helvetica',
                          'variant': {'align': 'left', 'divider': 'none', 'spacing': 0, 'compact': False}},
    'two_column_pro':   {'layout': 'sidebar',  'accent': '#0f766e', 'font': 'Helvetica'},
    'fresh_graduate':   {'layout': 'centered', 'accent': '#d97706', 'font': 'Helvetica'},
    'corporate_blue':   {'layout': 'banner',   'accent': '#1e40af', 'font': 'Times'},
    'dark_mode':        {'layout': 'banner',   'accent': '#1f2937', 'font': 'Helvetica'},
    'compact_one_page': {'layout': 'plain',    'accent': '#6d28d9', 'font': 'Helvetica',
                          'variant': {'align': 'left', 'divider': 'single', 'spacing': 0, 'compact': True}},
    'infographic':      {'layout': 'sidebar',  'accent': '#db2777', 'font': 'Helvetica'},
    'minimalist_pro':   {'layout': 'plain',    'accent': '#475569', 'font': 'Helvetica',
                          'variant': {'align': 'center', 'divider': 'none', 'spacing': 1, 'compact': False}},
    'slate_gold':       {'layout': 'banner',   'accent': '#b45309', 'font': 'Times'},
}


def _get_template(template_id):
    """Return template dict, falling back to 'professional'."""
    return _TEMPLATES_BY_ID.get(template_id) or _TEMPLATES_BY_ID['professional']


def _get_draft(draft_id):
    return query(
        "SELECT * FROM resume_builder_drafts WHERE id=? AND user_id=?",
        (draft_id, current_user.id), fetchone=True
    )


# ── List / landing ────────────────────────────────────────────
@builder_bp.route('/resume-builder')
@login_required
def builder_home():
    drafts = query(
        "SELECT * FROM resume_builder_drafts WHERE user_id=? ORDER BY updated_at DESC",
        (current_user.id,), fetchall=True
    )
    return render_template('resume_builder_list.html', drafts=drafts)


# ── New draft ─────────────────────────────────────────────────
@builder_bp.route('/resume-builder/new', methods=['POST'])
@login_required
def builder_new():
    name = request.form.get('name', 'My Resume').strip() or 'My Resume'
    draft_id = query(
        "INSERT INTO resume_builder_drafts (user_id, name, data, template) VALUES (?,?,?,?)",
        (current_user.id, name, '{}', 'professional'), commit=True
    )
    return redirect(url_for('builder.builder_edit', draft_id=draft_id))


# ── Edit draft ────────────────────────────────────────────────
@builder_bp.route('/resume-builder/<int:draft_id>/edit')
@login_required
def builder_edit(draft_id):
    draft = _get_draft(draft_id)
    if not draft:
        flash('Resume draft not found.', 'error')
        return redirect(url_for('builder.builder_home'))
    try:
        data = json.loads(draft['data'] or '{}')
    except Exception:
        data = {}
    return render_template('resume_builder.html', draft=draft, data=data,
                           templates=TEMPLATES_LIST)


# ── HTML Preview (renders selected Jinja2 template) ───────────
@builder_bp.route('/resume-builder/<int:draft_id>/preview')
@login_required
def builder_preview(draft_id):
    draft = _get_draft(draft_id)
    if not draft:
        flash('Draft not found.', 'error')
        return redirect(url_for('builder.builder_home'))

    try:
        data = json.loads(draft['data'] or '{}')
    except Exception:
        data = {}

    template_id = request.args.get('template_id') or draft.get('template') or 'professional'
    tpl = _get_template(template_id)

    personal       = data.get('personal', {})
    summary        = data.get('summary', '')
    experience     = data.get('experience', [])
    education      = data.get('education', [])
    skills         = data.get('skills', [])
    certifications = data.get('certifications', [])
    languages      = data.get('languages', [])
    projects       = data.get('projects', [])

    return render_template(
        tpl["file"],
        personal=personal, summary=summary, experience=experience,
        education=education, skills=skills, certifications=certifications,
        languages=languages, projects=projects
    )


# ── AJAX save ─────────────────────────────────────────────────
@builder_bp.route('/resume-builder/<int:draft_id>/save', methods=['POST'])
@login_required
def builder_save(draft_id):
    draft = _get_draft(draft_id)
    if not draft:
        return jsonify({'ok': False, 'error': 'Not found'}), 404

    payload = request.get_json(silent=True) or {}
    data     = json.dumps(payload.get('data', {}))
    template = payload.get('template', 'professional')
    name     = payload.get('name', draft['name'])[:80]

    query(
        "UPDATE resume_builder_drafts SET data=?, template=?, name=?, updated_at=datetime('now') WHERE id=?",
        (data, template, name, draft_id), commit=True
    )
    return jsonify({'ok': True})


# ── Delete draft ──────────────────────────────────────────────
@builder_bp.route('/resume-builder/<int:draft_id>/delete', methods=['POST'])
@login_required
def builder_delete(draft_id):
    draft = _get_draft(draft_id)
    if draft:
        query("DELETE FROM resume_builder_drafts WHERE id=?", (draft_id,), commit=True)
        flash('Resume deleted.', 'success')
    return redirect(url_for('builder.builder_home'))


# ── Analyze built resume ───────────────────────────────────────
@builder_bp.route('/resume-builder/<int:draft_id>/analyze', methods=['POST'])
@login_required
def builder_analyze(draft_id):
    draft = _get_draft(draft_id)
    if not draft:
        flash('Draft not found.', 'error')
        return redirect(url_for('builder.builder_home'))

    try:
        data = json.loads(draft['data'] or '{}')
    except Exception:
        data = {}

    resume_text = _data_to_text(data)
    if len(resume_text.strip()) < 30:
        flash('Please fill in your resume before analyzing.', 'error')
        return redirect(url_for('builder.builder_edit', draft_id=draft_id))

    ats_data = calculate_ats_score(resume_text)
    ai_data  = analyze_resume(resume_text,
                              present_skills=ats_data['present_skills'],
                              missing_skills=ats_data['missing_skills'])

    name = data.get('personal', {}).get('name', 'Built Resume') or 'Built Resume'
    filename = f"{name.replace(' ', '_')}_Builder.txt"

    resume_id = Resume.create(
        user_id         = current_user.id,
        filename        = filename,
        stored_path     = f'builder_{draft_id}',
        raw_text        = resume_text,
        skills          = ats_data['present_skills'],
        job_title       = '',
        industry        = '',
        job_description = '',
    )
    query(
        """INSERT INTO analysis_results
           (resume_id, ats_score, readability_score, keyword_score,
            ai_summary, ai_suggestions, ai_strengths, ai_weaknesses,
            ai_suitable_roles, present_skills, missing_skills, score_breakdown)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            resume_id,
            ats_data['ats_score'], ats_data['readability_score'], ats_data['keyword_score'],
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
    flash('Resume analyzed! View your full ATS report below.', 'success')
    return redirect(url_for('resume.analysis'))


# ── Export PDF ────────────────────────────────────────────────
@builder_bp.route('/resume-builder/<int:draft_id>/export/pdf')
@login_required
def builder_export_pdf(draft_id):
    draft = _get_draft(draft_id)
    if not draft:
        flash('Draft not found.', 'error')
        return redirect(url_for('builder.builder_home'))

    try:
        data = json.loads(draft['data'] or '{}')
    except Exception:
        data = {}

    template_id = request.args.get('template_id') or draft.get('template') or 'professional'
    tpl = _get_template(template_id)

    # Render the SAME html template the preview uses
    html = render_template(
        tpl['file'],
        personal=data.get('personal', {}),
        summary=data.get('summary', ''),
        experience=data.get('experience', []),
        education=data.get('education', []),
        skills=data.get('skills', []),
        certifications=data.get('certifications', []),
        languages=data.get('languages', []),
        projects=data.get('projects', []),
    )

    # Print it to PDF with headless Chromium
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until='networkidle')
        pdf_bytes = page.pdf(
            format='A4',
            print_background=True,
            margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},
        )
        browser.close()

    name = data.get('personal', {}).get('name', 'Resume').replace(' ', '_')
    filename = f"{name}_Resume.pdf"

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

# ── Export DOCX ───────────────────────────────────────────────
@builder_bp.route('/resume-builder/<int:draft_id>/export/docx')
@login_required
def builder_export_docx(draft_id):
    draft = _get_draft(draft_id)
    if not draft:
        flash('Draft not found.', 'error')
        return redirect(url_for('builder.builder_home'))

    try:
        data = json.loads(draft['data'] or '{}')
    except Exception:
        data = {}

    template = draft.get('template') or data.get('template') or 'professional'
    # sanitize: only allow known template ids
    if template not in _TEMPLATES_BY_ID:
        template = 'professional'

    docx_bytes = _generate_docx(data, template)
    name       = data.get('personal', {}).get('name', 'Resume').replace(' ', '_')
    filename   = f"{name}_Resume.docx"

    return send_file(
        io.BytesIO(docx_bytes),
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=filename
    )


# ── Helpers ───────────────────────────────────────────────────

def _data_to_text(data):
    """Convert builder data dict to plain resume text for ATS scoring."""
    lines = []
    p = data.get('personal', {})
    if p.get('name'):    lines.append(p['name'])
    if p.get('email'):   lines.append(p['email'])
    if p.get('phone'):   lines.append(p['phone'])
    if p.get('location'):lines.append(p['location'])
    if p.get('linkedin'):lines.append(p['linkedin'])

    if data.get('summary'):
        lines += ['', 'SUMMARY', data['summary']]

    if data.get('experience'):
        lines.append('')
        lines.append('EXPERIENCE')
        for e in data['experience']:
            lines.append(f"{e.get('role','')} at {e.get('company','')}")
            lines.append(f"{e.get('start','')} – {e.get('end','Present')}")
            if e.get('description'):
                lines.append(e['description'])

    if data.get('education'):
        lines.append('')
        lines.append('EDUCATION')
        for e in data['education']:
            lines.append(f"{e.get('degree','')} in {e.get('field','')} – {e.get('institution','')}")
            if e.get('year'): lines.append(str(e['year']))

    if data.get('skills'):
        lines += ['', 'SKILLS', ', '.join(data['skills'])]

    if data.get('projects'):
        lines.append('')
        lines.append('PROJECTS')
        for p in data['projects']:
            lines.append(p.get('name', ''))
            if p.get('description'): lines.append(p['description'])
            if p.get('technologies'): lines.append(f"Technologies: {p['technologies']}")

    if data.get('certifications'):
        lines.append('')
        lines.append('CERTIFICATIONS')
        for c in data['certifications']:
            lines.append(f"{c.get('name','')} — {c.get('org','')} {c.get('year','')}")

    if data.get('languages'):
        lines.append('')
        lines.append('LANGUAGES')
        for l in data['languages']:
            lines.append(f"{l.get('language','')} ({l.get('level','')})")

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════
# PDF GENERATION — 4 shared layout paths driven by TEMPLATE_STYLES
# ═══════════════════════════════════════════════════════════════

def _generate_pdf(data, template='professional'):
    """Generate a styled PDF using fpdf2. Layout/color/font come from
    TEMPLATE_STYLES so every template id in TEMPLATES_LIST renders
    with its own distinct look, not just the 3 that used to have a
    bespoke branch."""
    from fpdf import FPDF
    import io

    style = TEMPLATE_STYLES.get(template) or TEMPLATE_STYLES['professional']
    LAYOUT = style['layout']
    ACCENT = style['accent']
    FONT   = style['font']

    def h2r(hex_color):
        h = hex_color.lstrip('#')
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    PW, M = 210, 15          # page width, margin
    CW = PW - 2 * M          # content width = 180
    LEFT_W, GAP, RIGHT_W = 62, 8, 110
    LEFT_X, RIGHT_X = M, M + LEFT_W + GAP

    p = data.get('personal', {})
    name = p.get('name', '') or 'Your Name'
    contacts = [c for c in [p.get('email'), p.get('phone'), p.get('location'),
                            p.get('linkedin'), p.get('portfolio')] if c]

    # ── shared drawing helpers (parametrized by FONT / a supplied color) ──
    def sec_title(text, color, y, w, size=10, line=True, x=None):
        x = M if x is None else x
        pdf.set_xy(x, y)
        pdf.set_font(FONT, 'B', size)
        pdf.set_text_color(*h2r(color))
        pdf.cell(w, 6, text, ln=1)
        if line:
            pdf.set_draw_color(*h2r(color))
            pdf.set_line_width(0.35)
            pdf.line(x, y + 6, x + w, y + 6)
        return y + 9
    
    def entry_block(title, subtitle, desc, y, w, x=None, title_size=9.5,
                    title_color='#1f2937', sub_color='#6b7280', body_color='#374151'):
        x = M if x is None else x
        pdf.set_xy(x, y)
        pdf.set_font(FONT, 'B', title_size)
        pdf.set_text_color(*h2r(title_color))
        pdf.cell(w, 5, title, ln=1)
        if subtitle:
            pdf.set_xy(x, pdf.get_y())
            pdf.set_font(FONT, 'I', 8)
            pdf.set_text_color(*h2r(sub_color))
            pdf.cell(w, 4, subtitle, ln=1)
        if desc:
            pdf.set_font(FONT, '', 8.5)
            pdf.set_text_color(*h2r(body_color))
            for line in desc.split('\n'):
                line = line.strip().lstrip('*').lstrip('-').strip()
                if line:
                    pdf.set_x(x)
                    pdf.multi_cell(w, 4, f"- {line}")
        return pdf.get_y() + 2

    def skill_chip_row(skills, w, y, x, bg, fg, border=None):
        pdf.set_xy(x, y)
        pdf.set_font(FONT, '', 8)
        cx = x
        for s in skills:
            tw = pdf.get_string_width(s) + 8
            if cx + tw > x + w:
                cx = x
                y = pdf.get_y() + 6
            pdf.set_xy(cx, y)
            pdf.set_fill_color(*h2r(bg))
            pdf.set_text_color(*h2r(fg))
            if border:
                pdf.set_draw_color(*h2r(border))
                pdf.cell(tw, 5.5, f'  {s}  ', ln=0, fill=True, border=1)
            else:
                pdf.cell(tw, 5.5, f'  {s}  ', ln=0, fill=True)
            cx += tw + 2
        return pdf.get_y() + 8

    # ══════════════════════════════════════════════════
    # LAYOUT: PLAIN — ATS-safe, single column, no color/boxes
    # ══════════════════════════════════════════════════
    def render_plain():
        variant = style.get('variant') or {}
        v_align = variant.get('align', 'left')
        v_divider = variant.get('divider', 'single')
        v_spacing = variant.get('spacing', 0)
        v_compact = variant.get('compact', False)
        align = 'C' if v_align == 'center' else 'L'
        body_size = 8.5 if v_compact else 9.5
        line_gap = 4 if v_compact else 4.5
        head_gap = 2 if v_compact else 3

        y = 16
        pdf.set_xy(M, y)
        pdf.set_font(FONT, 'B', 15 if v_compact else 16)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(CW, 7, name, ln=1, align=align)
        y += 7
        if contacts:
            pdf.set_xy(M, y)
            pdf.set_font(FONT, '', 9)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(CW, 5, '  |  '.join(contacts), ln=1, align=align)
            y += 5 if v_compact else 6
        if v_divider != 'none':
            pdf.set_draw_color(120, 120, 120)
            pdf.set_line_width(0.3)
            pdf.line(M, y, PW - M, y)
            if v_divider == 'double':
                pdf.line(M, y + 1, PW - M, y + 1)
        y += head_gap + 3

        def heading(text, y):
            pdf.set_xy(M, y)
            pdf.set_font(FONT, 'B', 10.5)
            pdf.set_text_color(0, 0, 0)
            if v_spacing:
                pdf.set_char_spacing(v_spacing)
            pdf.cell(CW, 6, text.upper(), ln=1, align=align)
            if v_spacing:
                pdf.set_char_spacing(0)
            if v_divider != 'none':
                pdf.set_draw_color(150, 150, 150)
                pdf.set_line_width(0.2)
                pdf.line(M, y + 6, PW - M, y + 6)
                if v_divider == 'double':
                    pdf.line(M, y + 6.8, PW - M, y + 6.8)
            return y + 9 - (1 if v_compact else 0)

        if data.get('summary'):
            y = heading('Summary', y)
            pdf.set_xy(M, y)
            pdf.set_font(FONT, '', body_size)
            pdf.set_text_color(20, 20, 20)
            pdf.multi_cell(CW, line_gap, data['summary'])
            y = pdf.get_y() + head_gap

        if data.get('experience'):
            y = heading('Experience', y)
            for e in data['experience']:
                title = e.get('role', '')
                if e.get('company'):
                    title = f"{title} - {e['company']}" if title else e['company']
                y = entry_block(title, f"{e.get('start','')} - {e.get('end','Present')}",
                                e.get('description', ''), y, CW,
                                title_color='#000000', sub_color='#444444', body_color='#111111')

        if data.get('education'):
            y = heading('Education', y)
            for e in data['education']:
                deg = f"{e.get('degree','')} in {e.get('field','')}" if e.get('field') else e.get('degree', '')
                yr = f' {e["year"]}' if e.get('year') else ''
                y = entry_block(deg, f"{e.get('institution','')}{yr}", '', y, CW,
                                title_color='#000000', sub_color='#444444')

        if data.get('skills'):
            y = heading('Skills', y)
            pdf.set_xy(M, y)
            pdf.set_font(FONT, '', body_size)
            pdf.set_text_color(20, 20, 20)
            pdf.multi_cell(CW, line_gap, ', '.join(data['skills']))
            y = pdf.get_y() + head_gap

        if data.get('projects'):
            y = heading('Projects', y)
            for pr in data['projects']:
                sub = f"Technologies: {pr['technologies']}" if pr.get('technologies') else ''
                y = entry_block(pr.get('name', ''), sub, pr.get('description', ''), y, CW,
                                title_color='#000000', sub_color='#444444')

        if data.get('certifications'):
            y = heading('Certifications', y)
            for c in data['certifications']:
                org = f' - {c["org"]}' if c.get('org') else ''
                yr = f' ({c["year"]})' if c.get('year') else ''
                pdf.set_xy(M, y)
                pdf.set_font(FONT, '', 9)
                pdf.set_text_color(20, 20, 20)
                pdf.cell(CW, 5, f"{c.get('name','')}{org}{yr}", ln=1)
                y += 5
            y += head_gap

        if data.get('languages'):
            y = heading('Languages', y)
            langs = [f"{l.get('language','')} ({l.get('level','')})" for l in data['languages']]
            pdf.set_xy(M, y)
            pdf.set_font(FONT, '', 9)
            pdf.set_text_color(20, 20, 20)
            pdf.multi_cell(CW, 5, '   |   '.join(langs))

    # ══════════════════════════════════════════════════
    # LAYOUT: CENTERED — centered header + accent line, two-column body
    # ══════════════════════════════════════════════════
    def render_centered():
        pdf.set_xy(M, 15)
        pdf.set_font(FONT, 'B', 18)
        pdf.set_text_color(*h2r(ACCENT))
        pdf.cell(CW, 8, name, ln=1, align='C')
        if contacts:
            pdf.set_font(FONT, '', 8.5)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(CW, 5, '  |  '.join(contacts), ln=1, align='C')
        pdf.set_draw_color(*h2r(ACCENT))
        pdf.set_line_width(0.8)
        pdf.line(M, 32, PW - M, 32)
        y = 38

        if data.get('summary'):
            y = sec_title('PROFESSIONAL SUMMARY', ACCENT, y, CW, size=10)
            pdf.set_xy(M, y)
            pdf.set_font(FONT, '', 9)
            pdf.set_text_color(*h2r('#374151'))
            pdf.multi_cell(CW, 4.5, data['summary'])
            y = pdf.get_y() + 4

        if data.get('experience'):
            y = sec_title('WORK EXPERIENCE', ACCENT, y, CW, size=10)
            for e in data['experience']:
                title = e.get('role', '')
                if e.get('company'):
                    title = f"{title} - {e['company']}" if title else e['company']
                y = entry_block(title, f"{e.get('start','')} - {e.get('end','Present')}",
                                e.get('description', ''), y, CW)
            y += 2

        mid = y
        if data.get('education') or data.get('projects'):
            y = sec_title('EDUCATION', ACCENT, y, CW / 2 - 4, size=10)
            for e in data['education']:
                deg = f"{e.get('degree','')} in {e.get('field','')}" if e.get('field') else e.get('degree', '')
                yr = f' {e["year"]}' if e.get('year') else ''
                y = entry_block(deg, f"{e.get('institution','')}{yr}", '', y, CW / 2 - 4)
            if data.get('projects'):
                y = sec_title('PROJECTS', ACCENT, y, CW / 2 - 4, size=10)
                for pr in data['projects']:
                    sub = f"Tech: {pr['technologies']}" if pr.get('technologies') else ''
                    y = entry_block(pr.get('name', ''), sub, pr.get('description', ''), y, CW / 2 - 4)
            y += 2

        ry = mid
        if data.get('skills'):
            ry = sec_title('SKILLS', ACCENT, ry, CW / 2 - 4, size=10)
            ry = skill_chip_row(data['skills'], CW / 2 - 4, ry, M + CW / 2 + 4,
                                bg='#f5f3ff', fg='#374151', border='#e5e7eb') - 4

        if data.get('certifications'):
            ry = sec_title('CERTIFICATIONS', ACCENT, ry, CW / 2 - 4, size=10)
            for c in data['certifications']:
                pdf.set_xy(M + CW / 2 + 4, ry)
                pdf.set_font(FONT, '', 8.5)
                pdf.set_text_color(*h2r('#374151'))
                org = f' - {c["org"]}' if c.get('org') else ''
                yr = f' ({c["year"]})' if c.get('year') else ''
                pdf.cell(CW / 2 - 4, 4, f"{c.get('name','')}{org}{yr}", ln=1)
                ry += 5
            ry += 2

        if data.get('languages'):
            ry = sec_title('LANGUAGES', ACCENT, ry, CW / 2 - 4, size=10)
            pdf.set_xy(M + CW / 2 + 4, ry)
            pdf.set_font(FONT, '', 8.5)
            pdf.set_text_color(*h2r('#374151'))
            langs = [f"{l.get('language','')} ({l.get('level','')})" for l in data['languages']]
            pdf.multi_cell(CW / 2 - 4, 5, '   |   '.join(langs))

    # ══════════════════════════════════════════════════
    # LAYOUT: BANNER — full-width colored header band, single column
    # ══════════════════════════════════════════════════
    def render_banner():
        pdf.set_fill_color(*h2r(ACCENT))
        pdf.rect(0, 0, PW, 30, style='F')
        pdf.set_xy(M, 9)
        pdf.set_font(FONT, 'B', 19)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(CW, 8, name, ln=1)
        if contacts:
            pdf.set_xy(M, 19)
            pdf.set_font(FONT, '', 9)
            pdf.set_text_color(235, 235, 235)
            pdf.cell(CW, 5, '   |   '.join(contacts), ln=1)

        y = 38

        def heading(text, y):
            pdf.set_xy(M, y)
            pdf.set_font(FONT, 'B', 10.5)
            pdf.set_text_color(*h2r(ACCENT))
            pdf.cell(CW, 6, text.upper(), ln=1)
            pdf.set_draw_color(*h2r('#e5e7eb'))
            pdf.set_line_width(0.3)
            pdf.line(M, y + 6, PW - M, y + 6)
            return y + 9

        if data.get('summary'):
            y = heading('Professional Summary', y)
            pdf.set_xy(M, y)
            pdf.set_font(FONT, '', 9.5)
            pdf.set_text_color(*h2r('#374151'))
            pdf.multi_cell(CW, 4.5, data['summary'])
            y = pdf.get_y() + 4

        if data.get('experience'):
            y = heading('Professional Experience', y)
            for e in data['experience']:
                title = e.get('role', '')
                if e.get('company'):
                    title = f"{title} - {e['company']}" if title else e['company']
                y = entry_block(title, f"{e.get('start','')} - {e.get('end','Present')}",
                                e.get('description', ''), y, CW,
                                title_color='#1f2937', sub_color=ACCENT)

        if data.get('education'):
            y = heading('Education', y)
            for e in data['education']:
                deg = f"{e.get('degree','')} in {e.get('field','')}" if e.get('field') else e.get('degree', '')
                yr = f' {e["year"]}' if e.get('year') else ''
                y = entry_block(deg, f"{e.get('institution','')}{yr}", '', y, CW,
                                title_color='#1f2937', sub_color=ACCENT)

        if data.get('skills'):
            y = heading('Core Skills', y)
            y = skill_chip_row(data['skills'], CW, y, M, bg='#f3f4f6', fg='#1f2937')

        if data.get('projects'):
            y = heading('Projects', y)
            for pr in data['projects']:
                sub = f"Technologies: {pr['technologies']}" if pr.get('technologies') else ''
                y = entry_block(pr.get('name', ''), sub, pr.get('description', ''), y, CW,
                                title_color='#1f2937', sub_color=ACCENT)

        if data.get('certifications'):
            y = heading('Certifications', y)
            for c in data['certifications']:
                org = f' - {c["org"]}' if c.get('org') else ''
                yr = f' ({c["year"]})' if c.get('year') else ''
                pdf.set_xy(M, y)
                pdf.set_font(FONT, '', 9)
                pdf.set_text_color(*h2r('#374151'))
                pdf.cell(CW, 5, f"{c.get('name','')}{org}{yr}", ln=1)
                y += 5
            y += 3

        if data.get('languages'):
            y = heading('Languages', y)
            langs = [f"{l.get('language','')} ({l.get('level','')})" for l in data['languages']]
            pdf.set_xy(M, y)
            pdf.set_font(FONT, '', 9.5)
            pdf.set_text_color(*h2r('#374151'))
            pdf.multi_cell(CW, 5, '   |   '.join(langs))

    # ══════════════════════════════════════════════════
    # LAYOUT: SIDEBAR — colored left column + main content column
    # ══════════════════════════════════════════════════
    def render_sidebar():
        pdf.set_fill_color(*h2r(ACCENT))
        pdf.rect(0, 0, LEFT_W + M, 297, style='F')
        ly = 16

        initials = ''.join([w[0] for w in name.split() if w])[:2].upper() if name else '?'
        pdf.set_xy(LEFT_X + 3, ly)
        pdf.set_font(FONT, 'B', 15)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(LEFT_W - 6, 8, initials, ln=1, align='C')
        ly += 11

        pdf.set_xy(LEFT_X + 3, ly)
        pdf.set_font(FONT, 'B', 11)
        pdf.set_text_color(255, 255, 255)
        pdf.multi_cell(LEFT_W - 6, 5, name, align='C')
        ly = pdf.get_y() + 4

        def side_heading(text, y):
            pdf.set_xy(LEFT_X + 3, y)
            pdf.set_font(FONT, 'B', 7.5)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(LEFT_W - 6, 5, text.upper(), ln=1)
            pdf.set_draw_color(255, 255, 255)
            pdf.set_line_width(0.2)
            pdf.line(LEFT_X + 3, y + 5, LEFT_X + LEFT_W - 3, y + 5)
            return y + 8

        if contacts:
            ly = side_heading('Contact', ly)
            pdf.set_font(FONT, '', 7.5)
            pdf.set_text_color(240, 240, 245)
            for c in contacts:
                pdf.set_xy(LEFT_X + 3, ly)
                pdf.multi_cell(LEFT_W - 6, 4, c)
                ly = pdf.get_y()
            ly += 3

        if data.get('skills'):
            ly = side_heading('Skills', ly)
            pdf.set_font(FONT, '', 7.5)
            pdf.set_text_color(255, 255, 255)
            for s in data['skills']:
                pdf.set_xy(LEFT_X + 3, ly)
                pdf.cell(LEFT_W - 6, 4.5, f"- {s}", ln=1)
                ly += 4.5
            ly += 3

        if data.get('education'):
            ly = side_heading('Education', ly)
            for e in data['education']:
                deg = f"{e.get('degree','')} in {e.get('field','')}" if e.get('field') else e.get('degree', '')
                pdf.set_xy(LEFT_X + 3, ly)
                pdf.set_font(FONT, 'B', 7.5)
                pdf.set_text_color(255, 255, 255)
                pdf.multi_cell(LEFT_W - 6, 4, e.get('institution', ''))
                ly = pdf.get_y()
                pdf.set_xy(LEFT_X + 3, ly)
                pdf.set_font(FONT, '', 7)
                pdf.set_text_color(230, 230, 235)
                yr = f' {e["year"]}' if e.get('year') else ''
                pdf.multi_cell(LEFT_W - 6, 4, f"{deg}{yr}")
                ly = pdf.get_y() + 2
            ly += 2

        if data.get('languages'):
            ly = side_heading('Languages', ly)
            pdf.set_font(FONT, '', 7.5)
            pdf.set_text_color(255, 255, 255)
            for l in data['languages']:
                pdf.set_xy(LEFT_X + 3, ly)
                pdf.cell(LEFT_W - 6, 4.5, f"{l.get('language','')} - {l.get('level','')}", ln=1)
                ly += 4.5

        # ── main column ──
        ry = 16
        if data.get('summary'):
            ry = sec_title('SUMMARY', ACCENT, ry, RIGHT_W, size=9.5)
            pdf.set_xy(RIGHT_X, ry)
            pdf.set_font(FONT, '', 8.5)
            pdf.set_text_color(*h2r('#374151'))
            pdf.multi_cell(RIGHT_W, 4, data['summary'])
            ry = pdf.get_y() + 4

        if data.get('experience'):
            ry = sec_title('EXPERIENCE', ACCENT, ry, RIGHT_W, size=9.5)
            for e in data['experience']:
                title = e.get('role', '')
                if e.get('company'):
                    title = f"{title} - {e['company']}" if title else e['company']
                ry = entry_block(title, f"{e.get('start','')} - {e.get('end','Present')}",
                                 e.get('description', ''), ry, RIGHT_W, x=RIGHT_X,
                                 title_color='#1f2937', sub_color=ACCENT)

        if data.get('projects'):
            ry = sec_title('PROJECTS', ACCENT, ry, RIGHT_W, size=9.5)
            for pr in data['projects']:
                sub = f"Technologies: {pr['technologies']}" if pr.get('technologies') else ''
                ry = entry_block(pr.get('name', ''), sub, pr.get('description', ''), ry, RIGHT_W,
                                 x=RIGHT_X, title_color='#1f2937', sub_color=ACCENT)

        if data.get('certifications'):
            ry = sec_title('CERTIFICATIONS', ACCENT, ry, RIGHT_W, size=9.5)
            for c in data['certifications']:
                pdf.set_xy(RIGHT_X, ry)
                pdf.set_font(FONT, '', 8.5)
                pdf.set_text_color(*h2r('#374151'))
                org = f' - {c["org"]}' if c.get('org') else ''
                yr = f' ({c["year"]})' if c.get('year') else ''
                pdf.cell(RIGHT_W, 4.5, f"{c.get('name','')}{org}{yr}", ln=1)
                ry += 5

    layout_fn = {
        'plain': render_plain,
        'centered': render_centered,
        'banner': render_banner,
        'sidebar': render_sidebar,
    }.get(LAYOUT, render_centered)
    layout_fn()

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
# DOCX GENERATION — same TEMPLATE_STYLES config drives accent /
# font / heading style. Sidebar & banner layouts get a colored
# name banner since python-docx can't render a true side column.
# ═══════════════════════════════════════════════════════════════

def _generate_docx(data, template='professional'):
    """Generate a styled DOCX using python-docx, matching the
    template's accent color, font, and layout family."""
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    style = TEMPLATE_STYLES.get(template) or TEMPLATE_STYLES['professional']
    LAYOUT = style['layout']
    ACCENT_HEX = style['accent'].lstrip('#')
    accent = RGBColor.from_string(ACCENT_HEX.upper())
    font_name = 'Times New Roman' if style['font'] == 'Times' else 'Arial'
    dark = RGBColor(0x1f, 0x29, 0x37)
    gray = RGBColor(0x6b, 0x72, 0x80)
    black = RGBColor(0x11, 0x11, 0x11)
    use_color = LAYOUT != 'plain'          # 'plain' stays ATS-safe / colorless
    heading_color = accent if use_color else black
    text_color = dark if use_color else black

    doc = Document()
    doc.styles['Normal'].font.name = font_name
    doc.styles['Normal'].font.size = Pt(10)

    for section in doc.sections:
        section.top_margin    = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin   = Inches(0.85)
        section.right_margin  = Inches(0.85)

    def set_cell_background(cell, hex_color):
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), hex_color)
        cell._tc.get_or_add_tcPr().append(shd)

    p = data.get('personal', {})
    name = p.get('name', '') or 'Your Name'
    contacts = [x for x in [p.get('email'), p.get('phone'), p.get('location'),
                            p.get('linkedin'), p.get('portfolio')] if x]

    if LAYOUT in ('banner', 'sidebar') and use_color:
        # colored name banner (stand-in for a colored header/sidebar)
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.rows[0].cells[0]
        set_cell_background(cell, ACCENT_HEX)
        cell.width = Inches(6.8)
        cp = cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = cp.add_run(name)
        run.bold = True
        run.font.size = Pt(20)
        run.font.name = font_name
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        cp.paragraph_format.space_before = Pt(6)
        if contacts:
            cp2 = cell.add_paragraph()
            cp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run2 = cp2.add_run(' | '.join(contacts))
            run2.font.size = Pt(9)
            run2.font.name = font_name
            run2.font.color.rgb = RGBColor(0xF0, 0xF0, 0xF0)
            cp2.paragraph_format.space_after = Pt(6)
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
    else:
        align = WD_ALIGN_PARAGRAPH.CENTER if LAYOUT != 'plain' else WD_ALIGN_PARAGRAPH.LEFT
        np = doc.add_paragraph()
        np.alignment = align
        run = np.add_run(name)
        run.bold = True
        run.font.size = Pt(18 if LAYOUT != 'plain' else 16)
        run.font.name = font_name
        run.font.color.rgb = heading_color
        np.paragraph_format.space_after = Pt(4)
        if contacts:
            cpar = doc.add_paragraph()
            cpar.alignment = align
            crun = cpar.add_run(' | '.join(contacts))
            crun.font.size = Pt(9.5)
            crun.font.name = font_name
            crun.font.color.rgb = gray
            cpar.paragraph_format.space_after = Pt(6)

    def add_section_heading(text):
        hp = doc.add_paragraph()
        run = hp.add_run(text.upper())
        run.bold = True
        run.font.size = Pt(11)
        run.font.name = font_name
        run.font.color.rgb = heading_color
        hp.paragraph_format.space_before = Pt(10)
        hp.paragraph_format.space_after = Pt(2)
        pPr = hp._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '4')
        bottom.set(qn('w:space'), '1')
        bottom.set(qn('w:color'), ACCENT_HEX if use_color else '999999')
        pBdr.append(bottom)
        pPr.append(pBdr)

    def add_body(text, bold=False, italic=False, size=9.5, color=None):
        bp = doc.add_paragraph()
        run = bp.add_run(text)
        run.bold = bold
        run.italic = italic
        run.font.size = Pt(size)
        run.font.name = font_name
        run.font.color.rgb = color or text_color
        bp.paragraph_format.space_after = Pt(2)
        return bp

    if data.get('summary'):
        add_section_heading('Professional Summary')
        add_body(data['summary'])

    if data.get('experience'):
        add_section_heading('Work Experience')
        for e in data['experience']:
            if e.get('role') or e.get('company'):
                title = e.get('role', '')
                if e.get('company'):
                    title = f"{title} — {e['company']}" if title else e['company']
                add_body(title, bold=True)
                add_body(f"{e.get('start','')} – {e.get('end','Present')}", italic=True, color=gray)
                if e.get('description'):
                    for line in e['description'].split('\n'):
                        line = line.strip().lstrip('•-').strip()
                        if line:
                            add_body(f'• {line}')

    if data.get('education'):
        add_section_heading('Education')
        for e in data['education']:
            if e.get('institution') or e.get('degree'):
                deg = f"{e.get('degree','')} in {e.get('field','')}" if e.get('field') else e.get('degree', '')
                add_body(deg, bold=True)
                add_body(f"{e.get('institution','')} {('· ' + str(e['year'])) if e.get('year') else ''}", color=gray)

    if data.get('skills'):
        add_section_heading('Skills')
        add_body(', '.join(data['skills']))

    if data.get('projects'):
        add_section_heading('Projects')
        for pr in data['projects']:
            if pr.get('name'):
                add_body(pr['name'], bold=True)
                if pr.get('technologies'):
                    add_body(f"Technologies: {pr['technologies']}", italic=True, color=gray)
                if pr.get('description'):
                    add_body(pr['description'])

    if data.get('certifications'):
        add_section_heading('Certifications')
        for c in data['certifications']:
            if c.get('name'):
                add_body(f"{c['name']} — {c.get('org','')} {c.get('year','')}")

    if data.get('languages'):
        add_section_heading('Languages')
        langs = [f"{l.get('language','')} ({l.get('level','')})" for l in data['languages'] if l.get('language')]
        add_body(', '.join(langs))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()