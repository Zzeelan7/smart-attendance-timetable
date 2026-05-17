"""
generator/scheduler.py — Constrained greedy scheduler.

Hard constraints:
  C1: Each teacher may have at most 2 Period-1 (P1) classes per week.
  C2: Each theory teacher (MAT/DSP/PCT/MCESD/ELEC) must have ≥1 P3 class.
      Enforced by giving strong P3 preference ONLY during major theory placement
      so UHV/ELEC don't consume all P3 slots first.
  C3: Spread teacher classes across different days (day-load scoring).
"""

from .data import (DAYS, PERIODS, LAB_PAIRS, CLASSROOMS, LAB_ROOMS,
                   SUBJECTS_4SEM, SUBJECT_COLORS)

# ── Slot builders ─────────────────────────────────────────────────

def _theory_slot(abbr, teacher, room, color, name=''):
    return {'subject': abbr, 'display': abbr, 'type': 'theory',
            'teacher': teacher, 'room': room, 'color': color, 'name': name}

def _excl_slot(abbr, teacher, room, color, name=''):
    return {'subject': abbr, 'display': f'{abbr} EXCL', 'type': 'excl',
            'teacher': teacher, 'room': room, 'color': color, 'name': name}

def _lab_slot(batches_info):
    display = ' | '.join(b['lab'] for b in batches_info)
    return {'subject': 'LAB', 'display': display, 'type': 'lab',
            'color': '#0d9488', 'batches': batches_info, 'teacher': None, 'room': None}

def _fixed_slot(key, display, color):
    return {'subject': key, 'display': display, 'type': 'fixed',
            'color': color, 'teacher': None, 'room': None}


# ── Main generator ────────────────────────────────────────────────

def generate(form_data: dict) -> dict:
    tA = form_data.get('teachers_A', {})
    tB = form_data.get('teachers_B', {})
    lA = form_data.get('lab_teachers_A', {})
    lB = form_data.get('lab_teachers_B', {})

    grids  = {'A': [[None]*6 for _ in range(5)],
               'B': [[None]*6 for _ in range(5)]}
    busy   = {}   # teacher -> set of (day, period)
    errors = []

    # ── Core helpers ──────────────────────────────────────────────

    def is_free(sec, day, p):
        return grids[sec][day][p] is None

    def teacher_free(t, day, p):
        return (day, p) not in busy.get(t, set())

    def book(t, day, p):
        busy.setdefault(t, set()).add((day, p))

    def day_has(sec, day, abbr):
        return any(c and c.get('subject') == abbr for c in grids[sec][day])

    # ── Constraint trackers ───────────────────────────────────────

    def p1_count(t):
        return sum(1 for (d, p) in busy.get(t, set()) if p == 0)

    def day_count(t, day):
        return sum(1 for (d, p) in busy.get(t, set()) if d == day)

    def has_p3(t):
        return any(p == 2 for (d, p) in busy.get(t, set()))

    # ── Scoring ───────────────────────────────────────────────────

    def score(t, day, p, want_p3=False):
        """
        Soft constraint scoring (lower = better).
        C3: Penalise days already busy for this teacher (spread workload).
        C1 soft: Heavy penalty for P1 when teacher already at 2+ P1 slots.
        C2 soft: Strong P3 pull only when want_p3=True and teacher has no P3.
        """
        s = 0
        if t:
            s += day_count(t, day) * 25          # C3: prefer emptier days
            p1c = p1_count(t)
            if p == 0:
                if p1c >= 2:
                    s += 80                       # C1: heavy P1 penalty
                elif p1c == 1:
                    s += 30                       # mild discourage 2nd P1
                else:
                    s += 10                       # slight preference away from P1
            if want_p3 and p == 2 and not has_p3(t):
                s -= 50                           # C2: strong P3 pull
        return s

    def candidates(sec, teacher=None, abbr=None, want_p3=False):
        """All valid (score, day, period) candidates, sorted best-first."""
        t = teacher or ''
        result = []
        for day in range(5):
            if abbr and day_has(sec, day, abbr):
                continue
            for p in range(6):
                if not is_free(sec, day, p):
                    continue
                if t and not teacher_free(t, day, p):
                    continue
                # No hard block — use score penalty instead (soft constraint)
                result.append((score(t, day, p, want_p3), day, p))
        result.sort()
        return result

    # ── Placement helpers ─────────────────────────────────────────

    def place(sec, day, p, slot, t=None):
        grids[sec][day][p] = slot
        if t:
            book(t, day, p)

    def place_lab(sec, day, p1, p2, binfo):
        slot = _lab_slot(binfo)
        grids[sec][day][p1] = slot
        grids[sec][day][p2] = {**slot, 'display': '(cont.)'}
        for b in binfo:
            if b.get('teacher'):
                book(b['teacher'], day, p1)
                book(b['teacher'], day, p2)

    def place_theory(sec, teachers, abbr, color, name, count, want_p3=True):
        """Place `count` theory slots, re-querying candidates each time.
        P3 preference only applied until teacher already has a P3 slot.
        """
        t = teachers.get(abbr, '')
        room = CLASSROOMS[sec]
        placed = 0
        while placed < count:
            # Only pull toward P3 if teacher doesn't have one yet (prevent hoarding)
            need_p3 = want_p3 and (not has_p3(t) if t else False)
            cands = candidates(sec, teacher=t or None, abbr=abbr, want_p3=need_p3)
            if not cands:
                break
            _, day, p = cands[0]
            place(sec, day, p,
                  _theory_slot(abbr, t, room, color, name), t or None)
            placed += 1
        return placed

    # ── STEP 1: Fixed blocks ──────────────────────────────────────
    for day, sec in [(2, 'A'), (3, 'B')]:
        for p in [4, 5]:
            place(sec, day, p, _fixed_slot('MINI_PROJECT', 'MINI PROJECT', '#475569'))

    # ── STEP 2: UHV (1 period) ── want_p3=True so UHV competes for P3 fairly ──
    for sec, teachers in [('A', tA), ('B', tB)]:
        t    = teachers.get('UHV', '')
        room = CLASSROOMS[sec]
        # Only want P3 if teacher doesn't already have it
        need_p3 = not has_p3(t) if t else False
        cands = candidates(sec, teacher=t or None, abbr='UHV', want_p3=need_p3)
        if cands:
            _, day, p = cands[0]
            place(sec, day, p,
                  _theory_slot('UHV', t, room, '#f7c154', 'Universal Human Values'),
                  t or None)
        else:
            errors.append(f'Section {sec}: could not place UHV')

    # ── STEP 3: ELEC (3 periods) ── want_p3 only until teacher has P3 ───
    for sec, teachers in [('A', tA), ('B', tB)]:
        placed = place_theory(sec, teachers, 'ELEC', '#f75492',
                              'Industrial Electronics/RTOS', 3, want_p3=True)
        if placed < 3:
            errors.append(f'Section {sec}: only {placed}/3 ELEC periods placed')

    # ── STEP 4: Lab slots ─────────────────────────────────────────────
    # Only 1 P3-P4 lab per section to preserve P3 slots for theory teachers.
    # Section A: Mon P3-P4 + 3×P5-P6
    # Section B: Tue P3-P4 + 3×P5-P6
    preferred_labs = {
        'A': [(0, 2, 3), (1, 4, 5), (3, 4, 5), (4, 4, 5)],
        'B': [(0, 2, 3), (1, 4, 5), (2, 4, 5), (4, 4, 5)],
    }
    LAB_PAIR_ORDER = [(2, 3), (4, 5), (0, 1)]   # prefer non-P1 in fallback
    labs_list = ['MCESD LAB', 'IDSP', 'IPCT', 'DCDF']
    batches   = {'A': ['4A1', '4A2', '4A3'], 'B': ['4B1', '4B2', '4B3']}

    for sec in ['A', 'B']:
        lab_teachers = lA if sec == 'A' else lB
        placed_count = 0
        used_positions = []

        for slot_idx, (pref_day, pref_p1, pref_p2) in enumerate(preferred_labs[sec]):
            day, p1, p2 = pref_day, pref_p1, pref_p2
            if not (is_free(sec, day, p1) and is_free(sec, day, p2)):
                found = False
                # Search order: try P3-P4 on ALL days first, then P5-P6,
                # then P1-P2 (as last resort). Within each pair type, try
                # other days before the same preferred day.
                other_days = [d for d in range(5) if d != pref_day]
                search_days = other_days + [pref_day]
                for alt_p1, alt_p2 in LAB_PAIR_ORDER:
                    for alt_day in search_days:
                        if (alt_day, alt_p1, alt_p2) in used_positions:
                            continue
                        if not (is_free(sec, alt_day, alt_p1) and
                                is_free(sec, alt_day, alt_p2)):
                            continue
                        if alt_p1 == 0:
                            over = any(
                                p1_count(lab_teachers.get(lb, '')) >= 2
                                for lb in labs_list
                                if lab_teachers.get(lb, '')
                            )
                            if over:
                                continue
                        day, p1, p2 = alt_day, alt_p1, alt_p2
                        found = True
                        break
                    if found:
                        break
                if not found:
                    errors.append(
                        f'Section {sec}: could not place lab slot {slot_idx+1}')
                    continue

            binfo = []
            for b_idx, batch in enumerate(batches[sec]):
                lab     = labs_list[(slot_idx + b_idx) % 4]
                teacher = lab_teachers.get(lab, '')
                room    = LAB_ROOMS[b_idx % len(LAB_ROOMS)]
                binfo.append({'batch': batch, 'lab': lab,
                              'teacher': teacher, 'room': room})

            place_lab(sec, day, p1, p2, binfo)
            used_positions.append((day, p1, p2))
            placed_count += 1

        if placed_count < 4:
            errors.append(f'Section {sec}: only {placed_count}/4 lab slots placed')

    # ── STEP 5: DSP + PCT (3 theory + 1 EXCL) ── want_p3=True ─────────
    for abbr, color, name in [
        ('DSP', '#22d3a0', 'Digital Signal Processing'),
        ('PCT', '#f78c54', 'Principles of Communication Theory'),
    ]:
        for sec, teachers in [('A', tA), ('B', tB)]:
            t    = teachers.get(abbr, '')
            room = CLASSROOMS[sec]
            placed = place_theory(sec, teachers, abbr, color, name, 3, want_p3=True)
            if placed < 3:
                errors.append(
                    f'Section {sec}: only {placed}/3 {abbr} theory placed')
            # EXCL: re-query fresh after theory placed
            excl_placed = False
            cands = candidates(sec, teacher=t or None, abbr=abbr, want_p3=False)
            if cands:
                _, day, p = cands[0]
                place(sec, day, p,
                      _excl_slot(abbr, t, room, color, name), t or None)
                excl_placed = True
            if not excl_placed:
                errors.append(f'Section {sec}: {abbr} EXCL could not be placed')

    # ── STEP 6: MCESD (3 theory) — want_p3=True ──────────────────
    for sec, teachers in [('A', tA), ('B', tB)]:
        placed = place_theory(sec, teachers, 'MCESD', '#4f8ef7',
                              'Microcontrollers & Embedded System Design',
                              3, want_p3=True)
        if placed < 3:
            errors.append(f'Section {sec}: only {placed}/3 MCESD placed')

    # ── STEP 7: MAT (3 theory) — want_p3=True ────────────────────
    for sec, teachers in [('A', tA), ('B', tB)]:
        placed = place_theory(sec, teachers, 'MAT', '#7c5cf6',
                              'Probability Theory & Linear Algebra',
                              3, want_p3=True)
        if placed < 3:
            errors.append(f'Section {sec}: only {placed}/3 MAT placed')

    # ── STEP 8: C1/C2 validation ──────────────────────────────────
    theory_teachers = set()
    for teachers in [tA, tB]:
        for abbr in ['DSP', 'PCT', 'MCESD', 'MAT', 'ELEC', 'UHV']:
            t = teachers.get(abbr, '')
            if t:
                theory_teachers.add(t)

    for t in theory_teachers:
        cnt = p1_count(t)
        if cnt > 2:
            errors.append(
                f'[WARNING] Teacher "{t}" has {cnt} first-period (P1) classes '
                f'this week (target: max 2)')
        if not has_p3(t):
            errors.append(
                f'[WARNING] Teacher "{t}" has no third-period (P3) class '
                f'this week (target: at least 1)')

    # ── STEP 9: Build teacher timetables ─────────────────────────
    teacher_schedules = {}
    for sec in ['A', 'B']:
        for day in range(5):
            for p in range(6):
                cell = grids[sec][day][p]
                if not cell or cell['type'] == 'fixed':
                    continue
                t = cell.get('teacher')
                if t:
                    teacher_schedules.setdefault(t, [[None]*6 for _ in range(5)])
                    teacher_schedules[t][day][p] = {
                        'section': sec, 'subject': cell['subject'],
                        'display': cell['display'], 'color': cell['color'],
                        'room': cell.get('room', ''),
                    }
                if cell.get('type') == 'lab' and cell.get('batches'):
                    for b in cell['batches']:
                        bt = b.get('teacher')
                        if bt:
                            teacher_schedules.setdefault(
                                bt, [[None]*6 for _ in range(5)])
                            teacher_schedules[bt][day][p] = {
                                'section': sec, 'subject': b['lab'],
                                'display': b['lab'],
                                'color': SUBJECT_COLORS.get(b['lab'], '#475569'),
                                'room': b.get('room', ''),
                                'batch': b['batch'],
                            }

    return {
        'A': grids['A'],
        'B': grids['B'],
        'teacher_schedules': teacher_schedules,
        'errors': errors,
    }
