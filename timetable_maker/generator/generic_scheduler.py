"""
generic_scheduler.py — Multi-semester constraint-based timetable generator.
Works with any subjects, credits, and teacher assignments from wizard_state.json.
"""

import random
import colorsys

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
PERIODS = 6   # P1..P6  (index 0-5)
MAX_STUDENTS_PER_SEC = 75

# Auto-generate distinct colors for subjects
_PALETTE = [
    '#4f8ef7','#22d3a0','#f78c54','#a855f7','#f43f5e',
    '#06b6d4','#84cc16','#f59e0b','#ec4899','#14b8a6',
    '#8b5cf6','#ef4444','#10b981','#f97316','#6366f1',
]

def _color_for(idx: int) -> str:
    return _PALETTE[idx % len(_PALETTE)]


def generate_generic(state: dict) -> dict:
    """
    state keys:
      semesters  : [1, 4, 6, ...]
      subjects   : { "4": [{name,code,credits,hours,type,elective}, ...], ... }
      teachers   : { "4": { "0": {A:"Dr.X", B:"Dr.Y", labA:"Prof.Z", labB:"..."}, ...} }
      students   : { "4": {A:[{name,usn},...], B:[...]} }
      constraints: { hard:[{id,value},...], soft:[{id,value},...] }
    """
    semesters   = state.get('semesters', [])
    subjects_db = state.get('subjects', {})
    teachers_db = state.get('teachers', {})
    students_db = state.get('students', {})
    constraints = state.get('constraints', {'hard': [], 'soft': []})

    # Parse constraint flags
    hard_ids = {c['id']: c.get('value', True) for c in constraints.get('hard', [])}
    soft_ids = {c['id']: c.get('value', True) for c in constraints.get('soft', [])}
    max_p1_per_week = int(hard_ids.get('max_p1', soft_ids.get('max_p1', 99)))
    max_per_day     = int(hard_ids.get('max_per_day', soft_ids.get('max_per_day', 6)))
    no_backtoback   = 'no_backtoback' in hard_ids or 'no_backtoback' in soft_ids
    want_spread     = 'spread' in soft_ids
    want_min_p3     = 'min_p3' in soft_ids

    # Global teacher busy map: teacher_name -> set of (day, period) tuples
    # Shared across ALL semesters to detect cross-semester conflicts
    teacher_busy: dict[str, set] = {}

    results = {}   # sem -> {A: grid, B: grid, teacher_schedules: {}, errors: []}
    all_errors = []

    # ── Build lookup structures from AI-parsed custom rules ──────────
    parsed_rules    = state.get('parsed_constraints', [])
    teacher_blocked = {}   # teacher -> set of (day_idx, period_idx)
    section_blocked = {}   # (sem_str, section) -> set of (day_idx, period_idx)
    teacher_max_override = {}   # teacher -> max_per_day override
    no_consec_teachers   = set()   # per-teacher no-consecutive

    DAYS_MAP = {d.lower(): i for i, d in enumerate(DAYS)}
    # also accept 3-letter abbreviations: mon, tue, etc.
    DAYS_MAP.update({d[:3].lower(): i for i, d in enumerate(DAYS)})

    all_sems_str = [str(s) for s in semesters]

    for rule in parsed_rules:
        action = rule.get('action', 'unknown')

        if action == 'block_teacher_day':
            teacher  = rule.get('teacher', '')
            day_name = rule.get('day', '')
            periods  = rule.get('periods', 'all')
            if periods == 'all':
                periods = list(range(PERIODS))
            day_idx = DAYS_MAP.get(day_name.lower(), -1)
            if teacher and day_idx >= 0:
                teacher_blocked.setdefault(teacher, set())
                for p in periods:
                    if 0 <= int(p) < PERIODS:
                        teacher_blocked[teacher].add((day_idx, int(p)))

        elif action == 'block_teacher_period':
            teacher = rule.get('teacher', '')
            period  = int(rule.get('period', -1))
            if teacher and 0 <= period < PERIODS:
                teacher_blocked.setdefault(teacher, set())
                for d in range(len(DAYS)):
                    teacher_blocked[teacher].add((d, period))

        elif action == 'only_available_days':
            teacher        = rule.get('teacher', '')
            available_days = {d.lower() for d in rule.get('days', [])}
            # also accept 3-letter abbreviations
            available_days |= {d[:3].lower() for d in rule.get('days', [])}
            if teacher:
                teacher_blocked.setdefault(teacher, set())
                for d_idx, d_name in enumerate(DAYS):
                    if d_name.lower() not in available_days and d_name[:3].lower() not in available_days:
                        for p in range(PERIODS):
                            teacher_blocked[teacher].add((d_idx, p))

        elif action == 'max_classes_per_day':
            teacher = rule.get('teacher', '')
            limit   = int(rule.get('limit', max_per_day))
            if teacher:
                teacher_max_override[teacher] = limit

        elif action == 'no_consecutive':
            teacher = rule.get('teacher', '')
            if teacher:
                no_consec_teachers.add(teacher)

        elif action == 'block_section_day':
            sem_target     = str(rule.get('semester', 'all'))
            section_target = rule.get('section', 'all')
            day_name       = rule.get('day', '')
            periods        = rule.get('periods', 'all')
            if periods == 'all':
                periods = list(range(PERIODS))
            day_idx = DAYS_MAP.get(day_name.lower(), -1)
            if day_idx >= 0:
                target_sems = all_sems_str if sem_target == 'all' else [sem_target]
                target_secs = ['A', 'B'] if section_target.lower() == 'all' else [section_target.upper()]
                for ts in target_sems:
                    for sec in target_secs:
                        key = (ts, sec)
                        section_blocked.setdefault(key, set())
                        for p in periods:
                            if 0 <= int(p) < PERIODS:
                                section_blocked[key].add((day_idx, int(p)))


    for sem in semesters:
        sem_key = str(sem)
        subj_list = subjects_db.get(sem_key, [])
        t_map = teachers_db.get(sem_key, {})   # idx -> {A, B, labA, labB}
        st_map = students_db.get(sem_key, {'A': [], 'B': []})
        errors = []

        # Build grids: grid[section][day][period] = slot_dict | None
        grid = {
            'A': [[None]*PERIODS for _ in range(len(DAYS))],
            'B': [[None]*PERIODS for _ in range(len(DAYS))],
        }
        teacher_sched = {}  # teacher -> {A: grid, B: grid} for this sem

        def busy(teacher: str, day: int, period: int) -> bool:
            """True if teacher is already placed at (day, period) in ANY semester."""
            return (day, period) in teacher_busy.get(teacher, set())

        def mark_busy(teacher: str, day: int, period: int):
            teacher_busy.setdefault(teacher, set()).add((day, period))

        def p1_count(teacher: str) -> int:
            return sum(1 for (d, p) in teacher_busy.get(teacher, set()) if p == 0)

        def day_count(teacher: str, day: int) -> int:
            return sum(1 for (d, p) in teacher_busy.get(teacher, set()) if d == day)

        def score_slot(teacher: str, day: int, period: int) -> float:
            """Lower score = better candidate slot."""
            s = 0.0
            # Spread across days
            if want_spread:
                s += day_count(teacher, day) * 2.0
            # P1 penalty
            if period == 0 and max_p1_per_week < 99:
                s += p1_count(teacher) * 3.0
            # Prefer P3 (index 2)
            if want_min_p3 and period == 2:
                s -= 2.0
            # Global back-to-back penalty
            if no_backtoback:
                neighbors = [(day, period-1), (day, period+1)]
                for nb in neighbors:
                    if nb in teacher_busy.get(teacher, set()):
                        s += 5.0
            # AI: per-teacher no_consecutive penalty
            if teacher in no_consec_teachers:
                for nb in [(day, period-1), (day, period+1)]:
                    if nb in teacher_busy.get(teacher, set()):
                        s += 8.0   # stronger than global penalty
            return s

        def place_slot(section: str, day: int, period: int, slot: dict, teacher: str):
            grid[section][day][period] = slot
            if teacher:
                mark_busy(teacher, day, period)
                teacher_sched.setdefault(teacher, {
                    'A': [[None]*PERIODS for _ in range(len(DAYS))],
                    'B': [[None]*PERIODS for _ in range(len(DAYS))],
                })
                teacher_sched[teacher][section][day][period] = slot

        def find_slots(teacher: str, section: str, count: int,
                       prefer_p3: bool = False, is_lab: bool = False) -> list:
            """Return up to `count` best (score, day, period) candidates."""
            candidates = []
            # Per-teacher max_per_day: use override if set, else global
            t_max = teacher_max_override.get(teacher, max_per_day)
            for d in range(len(DAYS)):
                if day_count(teacher, d) >= t_max:
                    continue
                periods_range = range(PERIODS - 1) if is_lab else range(PERIODS)
                for p in periods_range:
                    # Free in this sem's section grid
                    if grid[section][d][p] is not None:
                        continue
                    # Free globally for this teacher
                    if teacher and busy(teacher, d, p):
                        continue
                    # AI: teacher-blocked slots (day off, period off, only-available-days)
                    if teacher and (d, p) in teacher_blocked.get(teacher, set()):
                        continue
                    # AI: section-blocked slots
                    if (sem_key, section) in section_blocked and \
                            (d, p) in section_blocked[(sem_key, section)]:
                        continue
                    # Lab: second consecutive slot must also be free
                    if is_lab and grid[section][d][p+1] is not None:
                        continue
                    if is_lab and teacher and busy(teacher, d, p+1):
                        continue
                    if is_lab and teacher and (d, p+1) in teacher_blocked.get(teacher, set()):
                        continue
                    # Hard: P1 limit
                    if p == 0 and p1_count(teacher) >= max_p1_per_week:
                        continue
                    sc = score_slot(teacher, d, p)
                    candidates.append((sc, d, p))
            candidates.sort(key=lambda x: x[0])
            return candidates[:count]

        # ── Place each subject ───────────────────────────────────────
        for idx, subj in enumerate(subj_list):
            name    = subj.get('name', f'Subject {idx}')
            code    = subj.get('code', '')
            hours   = int(subj.get('hours', subj.get('credits', 3)))
            stype   = subj.get('type', 'theory')
            elective = subj.get('elective', False)
            color   = _color_for(idx)
            t_entry = t_map.get(str(idx), {})

            label = f'{code}' if code else name[:6].upper()

            for section in ('A', 'B'):
                sec_key = 'B' if section == 'B' else 'A'
                t_key   = 'B' if section == 'B' else 'A'

                # Theory teacher
                theory_teacher = t_entry.get(f'teacher_{t_key}', t_entry.get(t_key, '')) or ''
                lab_teacher    = t_entry.get(f'lab_{t_key}', '') or theory_teacher

                if stype in ('theory', 'theory+lab'):
                    # Place theory hours
                    slots_needed = hours if stype == 'theory' else max(hours - 2, 1)
                    cands = find_slots(theory_teacher, section, slots_needed,
                                       prefer_p3=want_min_p3)
                    placed = 0
                    for _, d, p in cands:
                        slot = {
                            'display': label, 'full_name': name,
                            'teacher': theory_teacher, 'color': color,
                            'type': 'theory', 'elective': elective,
                        }
                        place_slot(section, d, p, slot, theory_teacher)
                        placed += 1
                    if placed < slots_needed:
                        errors.append(f'[WARNING] Sem {sem} Sec {section}: {name} — only {placed}/{slots_needed} theory slots placed')

                if stype in ('lab', 'theory+lab'):
                    # Place one 2-period lab block
                    cands = find_slots(lab_teacher, section, 1, is_lab=True)
                    if cands:
                        _, d, p = cands[0]
                        lab_slot = {
                            'display': label + ' LAB', 'full_name': name + ' Lab',
                            'teacher': lab_teacher, 'color': color,
                            'type': 'lab',
                        }
                        place_slot(section, d, p,   lab_slot, lab_teacher)
                        place_slot(section, d, p+1, {**lab_slot, 'cont': True}, lab_teacher)
                    else:
                        errors.append(f'[WARNING] Sem {sem} Sec {section}: {name} lab could not be placed')

        # ── Validate hard constraints ─────────────────────────────────
        violated_hard = []
        if max_p1_per_week < 99:
            for t, busy_set in teacher_busy.items():
                p1 = sum(1 for (d, p) in busy_set if p == 0)
                if p1 > max_p1_per_week:
                    violated_hard.append(f'Teacher "{t}" has {p1} P1 classes (limit {max_p1_per_week})')

        for v in violated_hard:
            errors.append(f'[HARD VIOLATED] {v} — please amend or remove this constraint')

        results[sem_key] = {
            'grid_A': grid['A'],
            'grid_B': grid['B'],
            'teacher_schedules': teacher_sched,
            'students_A': st_map.get('A', []),
            'students_B': st_map.get('B', []),
            'errors': errors,
        }
        all_errors.extend(errors)

    return {
        'semesters': semesters,
        'results': results,
        'all_errors': all_errors,
        'parsed_constraints': parsed_rules,   # carry through for result page
        'days': DAYS,
        'period_times': [
            '9:00-10:00','10:00-11:00','11:15-12:15',
            '12:15-1:15','2:00-3:00','3:00-4:00'
        ],
        # Legacy keys for existing result.html compatibility (sem 4 only)
        'A': results.get('4', {}).get('grid_A', []),
        'B': results.get('4', {}).get('grid_B', []),
        'teacher_schedules': results.get('4', {}).get('teacher_schedules', {}),
        'errors': all_errors,
    }
