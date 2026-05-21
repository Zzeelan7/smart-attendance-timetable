"""
app.py — Flask web server for the Smart Timetable Generator.
"""

import os, sys, json, io
from datetime import datetime
from flask import (Flask, render_template, request, jsonify,
                   send_file, session)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from generator import generate
from generator.exporter import export_excel, export_pdf
from generator.data import SUBJECTS_4SEM, DAYS, PERIOD_TIMES, SUBJECT_COLORS

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'timetable-gen-secret-2025'

# Persistent result cache — survives server restarts
_CACHE_FILE = os.path.join(BASE_DIR, 'last_result.json')
_last_result = {}

def _save_result(result: dict):
    """Persist the scheduler result to disk."""
    try:
        with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(result, f)
    except Exception as e:
        app.logger.warning(f'Could not save result cache: {e}')

def _load_result() -> dict:
    """Load the last scheduler result from disk."""
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

# Load from disk on startup
_last_result = _load_result()

# ── Routes ────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/semester/<int:sem>')
def semester_form(sem):
    if sem != 4:
        return render_template('coming_soon.html', sem=sem)
    return render_template('semester.html',
                           subjects=SUBJECTS_4SEM,
                           sem=sem)


@app.route('/api/generate', methods=['POST'])
def api_generate():
    """Accept form data, run scheduler, return JSON result."""
    global _last_result
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data received'}), 400

    try:
        result = generate(data)
        _last_result = result
        _save_result(result)          # persist to disk for export
        return jsonify({
            'success': True,
            'errors': result.get('errors', []),
            'grid_A': result['A'],
            'grid_B': result['B'],
            'teacher_schedules': {
                name: grid
                for name, grid in result.get('teacher_schedules', {}).items()
            },
            'days': DAYS,
            'period_times': PERIOD_TIMES,
            'colors': SUBJECT_COLORS,
        })
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e),
                        'traceback': traceback.format_exc()}), 500


@app.route('/result')
def result_page():
    result = _last_result or _load_result()
    return render_template('result.html',
                           days=DAYS,
                           period_times=PERIOD_TIMES,
                           result_json=json.dumps(result))


@app.route('/api/upload_students', methods=['POST'])
def upload_students():
    """
    Parse a single Excel file with all students.
    Sort alphabetically by name, then divide into 2 equal sections (max 75 each).
    Returns both sections with their student lists.
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    file = request.files['file']
    try:
        import openpyxl, math
        wb = openpyxl.load_workbook(io.BytesIO(file.read()))
        ws = wb.active
        students = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            name = str(row[0]).strip() if row[0] else ''
            usn  = str(row[1]).strip() if len(row) > 1 and row[1] else ''
            if name and name.lower() != 'none':
                students.append({'name': name, 'usn': usn})

        # Sort alphabetically by name
        students.sort(key=lambda s: s['name'].upper())

        total = len(students)
        # Divide equally — if odd, A gets one extra
        split  = math.ceil(total / 2)
        # Enforce max 75 per section
        split  = min(split, 75)
        sec_a  = students[:split]
        sec_b  = students[split:split + 75]

        return jsonify({
            'success': True,
            'total': total,
            'section_A': sec_a,
            'section_B': sec_b,
            'count_A': len(sec_a),
            'count_B': len(sec_b),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/export/excel')
def export_excel_route():
    global _last_result
    # Reload from disk if in-memory result was lost (e.g. server restart)
    result = _last_result or _load_result()
    if not result or 'A' not in result:
        return render_template('coming_soon.html', sem='?'), 404
    try:
        data = export_excel(result)
        buf = io.BytesIO(data)
        buf.seek(0)
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'timetable_4sem_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        return f'Excel export failed: {e}', 500


@app.route('/export/pdf')
def export_pdf_route():
    global _last_result
    result = _last_result or _load_result()
    if not result or 'A' not in result:
        return render_template('coming_soon.html', sem='?'), 404
    try:
        data = export_pdf(result)
        buf = io.BytesIO(data)
        buf.seek(0)
        return send_file(
            buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'timetable_4sem_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        return f'PDF export failed: {e}', 500


@app.route('/api/subjects/4')
def api_subjects():
    return jsonify({'subjects': SUBJECTS_4SEM})


# ── Wizard State (stored in a file, not cookie) ───────────────────
_WIZARD_FILE = os.path.join(BASE_DIR, 'wizard_state.json')

def _save_wizard(state: dict):
    with open(_WIZARD_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f)

def _load_wizard() -> dict:
    if os.path.exists(_WIZARD_FILE):
        try:
            with open(_WIZARD_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ── Step 0: Receive semester selection from home page ─────────────
@app.route('/wizard/students', methods=['GET', 'POST'])
def wizard_students():
    if request.method == 'POST':
        sems_raw = request.form.get('sems', '')
        sems = [int(s) for s in sems_raw.split(',') if s.strip().isdigit()]
        # Process uploaded CSVs
        import csv, math
        students = {}
        for sem in sems:
            f = request.files.get(f'csv_{sem}')
            if f and f.filename:
                text = f.read().decode('utf-8', errors='ignore')
                rows = list(csv.reader(text.splitlines()))
                # skip header row if first cell looks like 'name'
                if rows and rows[0] and rows[0][0].strip().lower() in ('name','student name','sl no','sno'):
                    rows = rows[1:]
                parsed = []
                for r in rows:
                    name = r[0].strip() if len(r) > 0 else ''
                    usn  = r[1].strip() if len(r) > 1 else ''
                    if name:
                        parsed.append({'name': name, 'usn': usn})
                parsed.sort(key=lambda x: x['name'].upper())
                total = len(parsed)
                split = min(math.ceil(total / 2), 75)
                students[str(sem)] = {
                    'A': parsed[:split],
                    'B': parsed[split:split+75],
                }
            else:
                students[str(sem)] = {'A': [], 'B': []}
        state = _load_wizard()
        state.update({'semesters': sems, 'students': students, 'sems_csv': sems_raw})
        _save_wizard(state)
        return render_template('wizard_subjects.html',
                               semesters=sems,
                               sems_csv=sems_raw)
    else:
        # GET — from home page form
        sems_raw = request.args.get('sems', '') or request.form.get('sems', '')
        sems = [int(s) for s in sems_raw.split(',') if s.strip().isdigit()]
        state = {'semesters': sems, 'sems_csv': sems_raw}
        _save_wizard(state)
        return render_template('wizard_students.html',
                               semesters=sems,
                               sems_csv=sems_raw)


# ── Redirect from home POST ───────────────────────────────────────
@app.route('/wizard/start', methods=['POST'])
def wizard_start():
    from flask import redirect, url_for
    sems_raw = request.form.get('sems', '')
    return redirect(url_for('wizard_students') + f'?sems={sems_raw}')


# ── Step 2: Subjects ──────────────────────────────────────────────
@app.route('/wizard/subjects', methods=['GET', 'POST'])
def wizard_subjects():
    state = _load_wizard()
    sems = state.get('semesters', [])
    sems_csv = state.get('sems_csv', ','.join(str(s) for s in sems))
    if request.method == 'POST':
        subjects_json = request.form.get('subjects_json', '{}')
        try:
            subjects = json.loads(subjects_json)
        except Exception:
            subjects = {}
        state['subjects'] = subjects
        _save_wizard(state)
        return render_template('wizard_teachers.html',
                               semesters=sems,
                               sems_csv=sems_csv,
                               subjects=subjects)
    return render_template('wizard_subjects.html',
                           semesters=sems,
                           sems_csv=sems_csv)


# ── Step 3: Teachers ──────────────────────────────────────────────
@app.route('/wizard/teachers', methods=['GET', 'POST'])
def wizard_teachers():
    state = _load_wizard()
    sems = state.get('semesters', [])
    sems_csv = state.get('sems_csv', '')
    subjects = state.get('subjects', {})
    if request.method == 'POST':
        # Parse teacher fields: t_{sem}_{subj_idx}_{role}
        teachers = {}
        for key, val in request.form.items():
            if key.startswith('t_') and val.strip():
                parts = key.split('_', 3)
                if len(parts) == 4:
                    _, sem, idx, role = parts
                    teachers.setdefault(sem, {}).setdefault(idx, {})[role] = val.strip()
        state['teachers'] = teachers
        _save_wizard(state)
        return render_template('wizard_constraints.html',
                               semesters=sems,
                               sems_csv=sems_csv)
    return render_template('wizard_teachers.html',
                           semesters=sems,
                           sems_csv=sems_csv,
                           subjects=subjects)


# ── Step 4: Constraints ───────────────────────────────────────────
@app.route('/wizard/constraints', methods=['GET', 'POST'])
def wizard_constraints():
    state = _load_wizard()
    sems = state.get('semesters', [])
    sems_csv = state.get('sems_csv', '')
    if request.method == 'POST':
        c_json = request.form.get('constraints_json', '{}')
        try:
            constraints = json.loads(c_json)
        except Exception:
            constraints = {'hard': [], 'soft': []}
        state['constraints'] = constraints
        _save_wizard(state)
        subjects = state.get('subjects', {})
        return render_template('wizard_review.html',
                               semesters=sems,
                               sems_csv=sems_csv,
                               subjects=subjects,
                               constraints=constraints)
    return render_template('wizard_constraints.html',
                           semesters=sems,
                           sems_csv=sems_csv)


# ── Step 5: Review page (GET) ─────────────────────────────────────
@app.route('/wizard/review', methods=['GET', 'POST'])
def wizard_review():
    state = _load_wizard()
    sems = state.get('semesters', [])
    sems_csv = state.get('sems_csv', '')
    subjects = state.get('subjects', {})
    constraints = state.get('constraints', {'hard': [], 'soft': []})
    return render_template('wizard_review.html',
                           semesters=sems,
                           sems_csv=sems_csv,
                           subjects=subjects,
                           constraints=constraints)


# ── Step 5: Generate ─────────────────────────────────────────────
@app.route('/wizard/generate', methods=['POST'])
def wizard_generate():
    global _last_result
    from generator.generic_scheduler import generate_generic
    from flask import redirect, url_for
    state = _load_wizard()

    # ── AI: parse custom constraints before scheduling ────────────
    constraints = state.get('constraints', {'hard': [], 'soft': []})
    custom_items = [
        {'text': c['text'], 'type': 'hard'}
        for c in constraints.get('hard', [])
        if c.get('id') == 'custom' and c.get('text')
    ] + [
        {'text': c['text'], 'type': 'soft'}
        for c in constraints.get('soft', [])
        if c.get('id') == 'custom' and c.get('text')
    ]
    if custom_items:
        try:
            from generator.constraint_parser import parse_all_constraints
            parsed = parse_all_constraints(custom_items)
            state['parsed_constraints'] = parsed
            _save_wizard(state)
        except Exception as e:
            app.logger.warning(f'AI constraint parsing skipped: {e}')

    try:
        result = generate_generic(state)
        _last_result = result
        _save_result(result)
    except Exception as e:
        import traceback
        app.logger.error(traceback.format_exc())
        _last_result = {'error': str(e), 'semesters': state.get('semesters', [])}
        _save_result(_last_result)
    return redirect(url_for('result_page'))


# ── AI key management ─────────────────────────────────────────────
@app.route('/api/ai-key', methods=['GET', 'POST'])
def ai_key():
    from generator.constraint_parser import load_api_key, save_api_key
    if request.method == 'POST':
        data = request.get_json(force=True)
        key = (data or {}).get('key', '').strip()
        if key:
            save_api_key(key)
            return jsonify({'status': 'saved'})
        return jsonify({'status': 'error', 'reason': 'empty key'}), 400
    # GET — return masked key
    key = load_api_key()
    masked = (key[:8] + '...' + key[-4:]) if len(key) > 12 else ('configured' if key else '')
    return jsonify({'configured': bool(key), 'masked': masked})


if __name__ == '__main__':
    print('=' * 50)
    print(' Smart Timetable Generator')
    print(' Open: http://localhost:5001')
    print('=' * 50)
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)

