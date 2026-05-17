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
    return render_template('result.html',
                           days=DAYS,
                           period_times=PERIOD_TIMES)


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


if __name__ == '__main__':
    print('=' * 50)
    print(' Smart Timetable Generator')
    print(' Open: http://localhost:5001')
    print('=' * 50)
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
