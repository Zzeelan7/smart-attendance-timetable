"""
generator/data.py
Static data definitions for 4th Semester ECE.
All subject, schedule, and room data lives here — easy to extend for other semesters.
"""

# ── Schedule constants ────────────────────────────────────────────
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
# Period indices 0-5 map to P1-P6. P7 is display-only (always blocked).
PERIODS = list(range(6))   # 0..5
PERIOD_TIMES = {
    '0': '9:00–10:00',
    '1': '10:00–11:00',
    '2': '11:15–12:15',
    '3': '12:15–1:15',
    '4': '2:00–3:00',
    '5': '3:00–4:00',
    'p7': '4:00–5:00',
}

# Consecutive period pairs usable for 2-period lab blocks
LAB_PAIRS = [(0, 1), (2, 3), (4, 5)]

# ── Hardcoded rooms (Phase 1) ─────────────────────────────────────
CLASSROOMS = {'A': '308', 'B': '309'}
LAB_ROOMS   = ['214', '215', '216', '207', '302', '303']

# ── 4th Semester subjects ─────────────────────────────────────────
SUBJECTS_4SEM = [
    {
        'code': '22MAT41B', 'abbr': 'MAT', 'color': '#7c5cf6',
        'name': 'Probability Theory & Linear Algebra',
        'theory_periods': 3, 'excl': False, 'has_lab': False,
    },
    {
        'code': '22EC42', 'abbr': 'MCESD', 'color': '#4f8ef7',
        'name': 'Microcontrollers & Embedded System Design',
        'theory_periods': 3, 'excl': False, 'has_lab': True, 'lab_abbr': 'MCESD LAB',
    },
    {
        'code': '22EC43', 'abbr': 'DSP', 'color': '#22d3a0',
        'name': 'Digital Signal Processing',
        'theory_periods': 3, 'excl': True, 'has_lab': True, 'lab_abbr': 'IDSP',
    },
    {
        'code': '22EC44', 'abbr': 'PCT', 'color': '#f78c54',
        'name': 'Principles of Communication Theory',
        'theory_periods': 3, 'excl': True, 'has_lab': True, 'lab_abbr': 'IPCT',
    },
    {
        'code': '22EC461', 'abbr': 'ELEC', 'color': '#f75492',
        'name': 'Industrial Electronics / RTOS (Elective)',
        'theory_periods': 3, 'excl': False, 'has_lab': False,
    },
    {
        'code': '22UH48', 'abbr': 'UHV', 'color': '#f7c154',
        'name': 'Universal Human Values',
        'theory_periods': 1, 'excl': False, 'has_lab': False,
    },
]

# Independent labs (not tied to a theory subject)
INDEPENDENT_LABS = [
    {'abbr': 'DCDF', 'name': 'Digital Circuit Design with FPGA', 'color': '#06b6d4'},
]

# NCMC sub-courses (one lecture per week, Period 7 — display only)
NCMC_COURSES = ['YOGA', 'NSS', 'SPORTS', 'CULTURAL']

# Fixed weekly blocks (positions chosen by algorithm to match real pattern)
FIXED_BLOCKS = {
    'MINI_PROJECT': {'display': 'MINI PROJECT', 'color': '#475569'},
    'NCMC':         {'display': 'NCMC',          'color': '#334155'},
    'DIP_MATHS':    {'display': 'DIP MATHS',     'color': '#1e293b'},
    'PROCTORING':   {'display': 'PROCTORING',    'color': '#374151'},
}

# Saturday fixed layout (shared by all sections)
SATURDAY_LAYOUT = [
    {'periods': [0, 1], 'type': 'MINI_PROJECT'},
    {'periods': [2, 3], 'type': 'PROCTORING'},
    {'periods': [4, 5], 'type': 'EXCL'},  # Elective extra
]

# Colors for subjects lookup
SUBJECT_COLORS = {s['abbr']: s['color'] for s in SUBJECTS_4SEM}
SUBJECT_COLORS.update({'MCESD LAB': '#3b82f6', 'IDSP': '#10b981',
                        'IPCT': '#f97316', 'DCDF': '#06b6d4',
                        'MINI PROJECT': '#475569', 'UHV': '#f7c154',
                        'ELEC': '#f75492', 'LAB': '#0d9488'})
