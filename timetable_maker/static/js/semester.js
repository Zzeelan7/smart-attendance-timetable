/* semester.js — Handles the 3-step form on the semester configuration page */

'use strict';

// ── State ────────────────────────────────────────────────────────
const state = {
  students: { A: [], B: [] },
  currentStep: 1,
};

// ── Step navigation ──────────────────────────────────────────────
function goStep(n) {
  document.getElementById('step-' + state.currentStep).classList.remove('active');
  document.getElementById('step-dot-' + state.currentStep).classList.remove('active');
  document.getElementById('step-dot-' + state.currentStep).classList.add('done');

  state.currentStep = n;
  document.getElementById('step-' + n).classList.add('active');
  document.getElementById('step-dot-' + n).classList.add('active');

  if (n === 3) buildReviewPanel();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Single file upload ────────────────────────────────────────────
const fileInput = document.getElementById('file-all');
const dropZone  = document.getElementById('dz-all');

if (fileInput) {
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) uploadStudents(fileInput.files[0]);
  });
}

if (dropZone) {
  dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) uploadStudents(file);
  });
}

async function uploadStudents(file) {
  const countEl = document.getElementById('count-all');
  countEl.textContent = 'Uploading…';

  const form = new FormData();
  form.append('file', file);

  try {
    const r = await fetch('/api/upload_students', { method: 'POST', body: form });
    const d = await r.json();

    if (!d.success) {
      countEl.textContent = 'Upload failed';
      alert('Upload error: ' + d.error);
      return;
    }

    // Store in state
    state.students.A = d.section_A;
    state.students.B = d.section_B;

    // Update counts
    countEl.textContent = `${d.total} students uploaded`;
    document.getElementById('count-a').textContent = `${d.count_A} students`;
    document.getElementById('count-b').textContent = `${d.count_B} students`;

    // Show previews for each section
    showSectionPreview('a', d.section_A);
    showSectionPreview('b', d.section_B);

    // Reveal the division preview panel
    document.getElementById('division-preview').classList.remove('hidden');

    // Update drop zone to show success
    dropZone.innerHTML = `
      <div class="dz-icon">✅</div>
      <p style="color:var(--green)">${file.name} uploaded successfully</p>
      <span class="dz-hint">${d.total} students · Click to replace</span>`;
    dropZone.appendChild(fileInput);

  } catch (e) {
    countEl.textContent = 'Error';
    alert('Network error: ' + e.message);
  }
}

function showSectionPreview(sec, students) {
  const el = document.getElementById('preview-' + sec);
  if (!el) return;
  const show = students.slice(0, 6);
  const more = students.length > 6 ? `<em style="color:var(--text3)">… and ${students.length - 6} more</em>` : '';
  el.innerHTML = show.map((s, i) =>
    `<span style="color:var(--text3)">${i + 1}.</span> ${s.name}` +
    (s.usn ? ` <span style="color:var(--text3);font-family:var(--mono)">${s.usn}</span>` : '')
  ).join('<br>') + (more ? '<br>' + more : '');
}

// ── Review panel ─────────────────────────────────────────────────
function buildReviewPanel() {
  const subjects = [
    { abbr: 'MAT',   label: 'Probability Theory & Linear Algebra' },
    { abbr: 'MCESD', label: 'Microcontrollers & Embedded System Design' },
    { abbr: 'DSP',   label: 'Digital Signal Processing' },
    { abbr: 'PCT',   label: 'Principles of Communication Theory' },
    { abbr: 'ELEC',  label: 'Industrial Electronics / RTOS (Elective)' },
    { abbr: 'UHV',   label: 'Universal Human Values' },
  ];
  const labs = [
    { id: 'MCESD_LAB', label: 'MCESD Lab (22ECL45)' },
    { id: 'IDSP',      label: 'IDSP Lab (DSP Lab)' },
    { id: 'IPCT',      label: 'IPCT Lab (PCT Lab)' },
    { id: 'DCDF',      label: 'DCDF Lab (22ECL471)' },
  ];

  let html = '<div class="review-section"><h4>👨‍🏫 Theory Teachers</h4>';
  subjects.forEach(s => {
    const tA = document.getElementById(`t_A_${s.abbr}`)?.value.trim() || '';
    const tB = document.getElementById(`t_B_${s.abbr}`)?.value.trim() || '';
    html += `<div class="review-row">
      <span class="review-key">${s.label}</span>
      <span class="review-val">A: ${tA || '<span class="review-empty">Not entered</span>'}</span>
      <span class="review-val">B: ${tB || '<span class="review-empty">Not entered</span>'}</span>
    </div>`;
  });
  html += '</div>';

  html += '<div class="review-section"><h4>🔬 Lab Teachers</h4>';
  labs.forEach(l => {
    const tA = document.getElementById(`l_A_${l.id}`)?.value.trim() || '';
    const tB = document.getElementById(`l_B_${l.id}`)?.value.trim() || '';
    html += `<div class="review-row">
      <span class="review-key">${l.label}</span>
      <span class="review-val">A: ${tA || '<span class="review-empty">Not entered</span>'}</span>
      <span class="review-val">B: ${tB || '<span class="review-empty">Not entered</span>'}</span>
    </div>`;
  });
  html += '</div>';

  const totalStudents = state.students.A.length + state.students.B.length;
  html += `<div class="review-section"><h4>👥 Students</h4>
    <div class="review-row">
      <span class="review-key">Total uploaded</span>
      <span class="review-val">${totalStudents} students</span>
    </div>
    <div class="review-row">
      <span class="review-key">Section A</span>
      <span class="review-val">${state.students.A.length} students</span>
    </div>
    <div class="review-row">
      <span class="review-key">Section B</span>
      <span class="review-val">${state.students.B.length} students</span>
    </div>
  </div>`;

  document.getElementById('review-panel').innerHTML = html;
}

// ── Generate ─────────────────────────────────────────────────────
async function runGenerate() {
  const errDiv = document.getElementById('generate-errors');
  errDiv.classList.add('hidden');
  errDiv.innerHTML = '';

  const subjects = ['MAT', 'MCESD', 'DSP', 'PCT', 'ELEC', 'UHV'];
  const labKeys  = ['MCESD_LAB', 'IDSP', 'IPCT', 'DCDF'];

  const teachers_A = {}, teachers_B = {};
  subjects.forEach(abbr => {
    teachers_A[abbr] = document.getElementById(`t_A_${abbr}`)?.value.trim() || '';
    teachers_B[abbr] = document.getElementById(`t_B_${abbr}`)?.value.trim() || '';
  });

  const lab_teachers_A = {}, lab_teachers_B = {};
  labKeys.forEach(k => {
    const key = k.replace('_', ' ');
    lab_teachers_A[key] = document.getElementById(`l_A_${k}`)?.value.trim() || '';
    lab_teachers_B[key] = document.getElementById(`l_B_${k}`)?.value.trim() || '';
  });

  const payload = {
    teachers_A,
    teachers_B,
    lab_teachers_A,
    lab_teachers_B,
    students_A: state.students.A,
    students_B: state.students.B,
  };

  const loading = document.getElementById('gen-loading');
  const btn     = document.getElementById('btn-generate');
  loading.classList.remove('hidden');
  btn.disabled = true;

  try {
    const r = await fetch('/api/generate', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    const d = await r.json();

    loading.classList.add('hidden');
    btn.disabled = false;

    if (!d.success) {
      errDiv.innerHTML = `<strong>Error:</strong> ${d.error}
        <pre style="font-size:0.7rem;margin-top:8px;opacity:0.6">${d.traceback || ''}</pre>`;
      errDiv.classList.remove('hidden');
      return;
    }

    if (d.errors && d.errors.length) {
      errDiv.innerHTML = `<strong>⚠ Scheduling Warnings (timetable still generated):</strong><ul>` +
        d.errors.map(e => `<li>${e}</li>`).join('') + '</ul>';
      errDiv.classList.remove('hidden');
    }

    // Store students alongside result
    d.students_A = state.students.A;
    d.students_B = state.students.B;

    sessionStorage.setItem('tt_result', JSON.stringify(d));
    window.location.href = '/result';

  } catch (e) {
    loading.classList.add('hidden');
    btn.disabled = false;
    errDiv.innerHTML = `<strong>Network error:</strong> ${e.message}`;
    errDiv.classList.remove('hidden');
  }
}
