/* ── Tab navigation ─────────────────────────────────────── */
let _enrollSnapshotInterval = null;

function startEnrollPreview() {
  if (_enrollSnapshotInterval) return;
  const img = document.getElementById('enroll-snapshot');
  if (!img) return;
  _enrollSnapshotInterval = setInterval(async () => {
    try {
      const r = await fetch('/api/snapshot');
      if (!r.ok) return;
      const blob = await r.blob();
      const old = img.src;
      img.src = URL.createObjectURL(blob);
      if (old && old.startsWith('blob:')) URL.revokeObjectURL(old);
    } catch {}
  }, 800);
}

function stopEnrollPreview() {
  if (_enrollSnapshotInterval) {
    clearInterval(_enrollSnapshotInterval);
    _enrollSnapshotInterval = null;
  }
}

document.querySelectorAll('.nav-item[data-tab]').forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault();
    const tab = item.dataset.tab;
    if (!tab) return;
    const tabPanel = document.getElementById('tab-' + tab);
    if (!tabPanel) return;
    document.querySelectorAll('.nav-item[data-tab]').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    item.classList.add('active');
    tabPanel.classList.add('active');
    if (tab === 'enroll')   startEnrollPreview();
    else                    stopEnrollPreview();
    if (tab === 'people')   loadPeople();
    if (tab === 'logs')     loadLogs();
    if (tab === 'settings') loadSettingsStatus();
  });
});

/* ── Toast ──────────────────────────────────────────────── */
let toastTimer;
function showToast(msg, type = 'info') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast ${type}`;
  t.classList.remove('hidden');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add('hidden'), 3500);
}

/* ── Status polling ─────────────────────────────────────── */
async function pollStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();

    // Sidebar camera status
    const dot   = document.getElementById('cam-status-dot');
    const label = document.getElementById('cam-status-label');
    const sub   = document.getElementById('cam-source-label');
    if (d.camera_ok) {
      dot.className = 'status-indicator online';
      label.textContent = 'Camera Online';
    } else {
      dot.className = 'status-indicator offline';
      label.textContent = 'Camera Offline';
    }
    sub.textContent = d.camera_type || '—';

    // Video badge
    document.getElementById('cam-type-badge').textContent = d.camera_type || 'CAM';

    // Detection panel
    const list = document.getElementById('detection-list');
    if (d.current_faces && d.current_faces.length > 0) {
      list.innerHTML = d.current_faces.map(f => `
        <div class="face-chip ${f.is_known ? 'known' : 'unknown'}">
          <div class="face-avatar ${f.is_known ? 'known' : 'unknown'}">
            ${f.is_known ? f.name[0].toUpperCase() : '?'}
          </div>
          <div class="face-info">
            <div class="face-name">${f.name}</div>
            <div class="face-conf">${f.confidence}% confidence</div>
          </div>
        </div>`).join('');
    } else {
      list.innerHTML = '<div class="no-detection">No faces in frame</div>';
    }

    // Stats
    document.getElementById('stat-enrolled').textContent = d.enrolled || 0;
  } catch {}
}

async function pollStats() {
  try {
    const r = await fetch('/api/stats');
    const s = await r.json();
    document.getElementById('stat-today').textContent   = s.today_events   || 0;
    document.getElementById('stat-total').textContent   = s.total_events   || 0;
    document.getElementById('stat-unknown').textContent = s.unknown_count  || 0;
  } catch {}
}

setInterval(pollStatus, 1200);
setInterval(pollStats, 5000);
pollStatus();
pollStats();

/* ── Snapshot ───────────────────────────────────────────── */
function takeSnapshot() {
  const link = document.createElement('a');
  link.href = '/api/snapshot';
  link.click();
  showToast('📸 Snapshot downloaded!', 'success');
}

/* ── Enroll from camera ─────────────────────────────────── */
async function enrollFromCamera() {
  const name = document.getElementById('enroll-name-live').value.trim();
  const msg  = document.getElementById('enroll-live-msg');
  const btn  = document.getElementById('btn-enroll-live');
  if (!name) { showMsg(msg, 'error', '⚠ Please enter a name.'); return; }

  // Check system status first
  try {
    const statusResp = await fetch('/api/status');
    const status = await statusResp.json();
    if (!status.face_recognition_available) {
      showMsg(msg, 'error', '✗ face_recognition not available - use image enrollment instead');
      showToast('Try uploading an image instead', 'info');
      return;
    }
    if (!status.camera_ok) {
      showMsg(msg, 'error', '✗ Camera not connected - enable your camera or use image enrollment');
      showToast('Camera not available - use image upload', 'info');
      return;
    }
  } catch {}

  btn.disabled = true;
  btn.textContent = 'Capturing…';
  try {
    const r = await fetch('/api/enroll', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ name })
    });
    const d = await r.json();
    if (d.success) {
      showMsg(msg, 'success', `✓ ${d.message}`);
      showToast(`✓ ${name} enrolled!`, 'success');
      document.getElementById('enroll-name-live').value = '';
      loadPeople();
    } else {
      showMsg(msg, 'error', `✗ ${d.error || 'Enrollment failed'}`);
      if (d.error && d.error.includes('Camera')) {
        showToast('💡 Try the image upload method instead', 'info');
      }
    }
  } catch (e) {
    showMsg(msg, 'error', '✗ Network error - check camera and try again');
  }
  btn.disabled = false;
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px"><path d="M12 5v14M5 12l7-7 7 7"/></svg> Capture & Enroll`;
}

/* ── Image preview & upload ─────────────────────────────── */
function previewImage(input) {
  const preview = document.getElementById('img-preview');
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = e => {
      preview.src = e.target.result;
      preview.classList.remove('hidden');
    };
    reader.readAsDataURL(input.files[0]);
  }
}

async function enrollFromImage() {
  const name  = document.getElementById('enroll-name-img').value.trim();
  const file  = document.getElementById('img-upload').files[0];
  const msg   = document.getElementById('enroll-img-msg');
  const btn   = document.getElementById('btn-enroll-img');
  if (!name) { showMsg(msg, 'error', '⚠ Please enter a name.'); return; }
  if (!file) { showMsg(msg, 'error', '⚠ Please select an image.'); return; }

  // Check face_recognition availability
  try {
    const statusResp = await fetch('/api/status');
    const status = await statusResp.json();
    if (!status.face_recognition_available) {
      showMsg(msg, 'error', '✗ Enrollment system not available (face_recognition not installed)');
      return;
    }
  } catch {}

  btn.disabled = true;
  btn.textContent = 'Enrolling…';
  const form = new FormData();
  form.append('name', name);
  form.append('image', file);
  try {
    const r = await fetch('/api/enroll_image', { method: 'POST', body: form });
    const d = await r.json();
    if (d.success) {
      showMsg(msg, 'success', `✓ ${d.message}`);
      showToast(`✓ ${name} enrolled from image!`, 'success');
      document.getElementById('enroll-name-img').value = '';
      document.getElementById('img-upload').value = '';
      document.getElementById('img-preview').classList.add('hidden');
      loadPeople();  // Refresh people list
    } else {
      showMsg(msg, 'error', `✗ ${d.error || 'Enrollment failed'}`);
    }
  } catch (e) {
    showMsg(msg, 'error', '✗ Network or processing error');
  }
  btn.disabled = false;
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px"><path d="M12 5v14M5 12l7-7 7 7"/></svg> Enroll from Image`;
}

async function rebuildEncodings() {
  const msg = document.getElementById('rebuild-msg');
  const btn = document.getElementById('btn-rebuild');
  btn.disabled = true; btn.textContent = 'Rebuilding…';
  try {
    const r = await fetch('/api/rebuild', { method: 'POST' });
    const d = await r.json();
    showMsg(msg, 'success', `✓ ${d.message}`);
    showToast('✓ Encodings rebuilt!', 'success');
  } catch {
    showMsg(msg, 'error', '✗ Failed to rebuild');
  }
  btn.disabled = false; btn.textContent = 'Rebuild Encodings';
}

/* ── People tab ─────────────────────────────────────────── */
async function loadPeople() {
  const grid = document.getElementById('people-grid');
  grid.innerHTML = '<div class="loading-msg">Loading…</div>';
  try {
    const r = await fetch('/api/people');
    const d = await r.json();
    if (!d.people.length) {
      grid.innerHTML = '<div class="loading-msg">No enrolled people yet.</div>';
      return;
    }
    grid.innerHTML = d.people.map(p => `
      <div class="person-card" id="pcard-${p.name}">
        <div class="person-avatar-large">${p.name[0].toUpperCase()}</div>
        <div class="person-name">${p.name}</div>
        <div class="person-meta">${p.encodings} encoding(s) · ${p.images} image(s)</div>
        <button class="btn btn-danger" style="width:100%;justify-content:center"
          onclick="deletePerson('${p.name}')">🗑 Remove</button>
      </div>`).join('');
  } catch {
    grid.innerHTML = '<div class="loading-msg">Error loading people.</div>';
  }
}

async function deletePerson(name) {
  if (!confirm(`Remove "${name}" from the system?`)) return;
  try {
    const r = await fetch('/api/delete_person', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ name })
    });
    const d = await r.json();
    showToast(d.success ? `✓ ${name} removed` : `✗ ${d.message}`, d.success ? 'success' : 'error');
    loadPeople();
  } catch {
    showToast('✗ Network error', 'error');
  }
}

/* ── Logs tab ───────────────────────────────────────────── */
async function loadLogs() {
  const tbody = document.getElementById('log-body');
  tbody.innerHTML = '<tr><td colspan="5" class="loading-msg">Loading…</td></tr>';
  try {
    const r = await fetch('/api/log?n=100');
    const d = await r.json();
    const events = [...d.events].reverse();
    if (!events.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="loading-msg">No events yet.</td></tr>';
      return;
    }
    tbody.innerHTML = events.map(e => {
      const time = new Date(e.timestamp).toLocaleTimeString();
      const date = new Date(e.timestamp).toLocaleDateString();
      return `<tr>
        <td><span style="color:var(--text2)">${date}</span> ${time}</td>
        <td><strong>${e.name}</strong></td>
        <td style="font-family:var(--mono)">${e.confidence}%</td>
        <td><span class="badge ${e.is_known ? 'badge-green' : 'badge-red'}">
          ${e.is_known ? '✓ Known' : '? Unknown'}</span></td>
        <td style="font-family:var(--mono);font-size:0.75rem;color:var(--text3)">${e.camera || '—'}</td>
      </tr>`;
    }).join('');
  } catch {
    tbody.innerHTML = '<tr><td colspan="5" class="loading-msg">Error loading logs.</td></tr>';
  }
}

/* ── Settings / camera switch ───────────────────────────── */
async function switchCamera(type) {
  const msg = document.getElementById('cam-switch-msg');
  let source;
  if (type === 'pc') {
    source = parseInt(document.getElementById('pc-index').value) || 0;
  } else {
    source = document.getElementById('esp32-url').value.trim();
    if (!source) { showMsg(msg, 'error', '⚠ Enter the ESP32-CAM stream URL'); return; }
  }
  showMsg(msg, 'info', '⏳ Switching camera…');
  try {
    const r = await fetch('/api/set_camera', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ source })
    });
    const d = await r.json();
    if (d.success) {
      showMsg(msg, 'success', `✓ Camera switched to: ${source}`);
      showToast('✓ Camera switched!', 'success');
    } else {
      showMsg(msg, 'error', `✗ Failed to connect to: ${source}`);
    }
  } catch {
    showMsg(msg, 'error', '✗ Network error');
  }
  loadSettingsStatus();
}

async function loadSettingsStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    document.getElementById('settings-status').innerHTML = `
Camera OK:    ${d.camera_ok ? '✅ Yes' : '❌ No'}
Source:       ${d.camera_source}
Type:         ${d.camera_type}
Enrolled:     ${d.enrolled} face(s)
Known people: ${(d.known_people || []).join(', ') || 'None'}
Timestamp:    ${d.timestamp}`;
  } catch {}
}

/* ── Drag & Drop on upload zone ─────────────────────────── */
const zone = document.getElementById('upload-zone');
if (zone) {
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length) {
      document.getElementById('img-upload').files = files;
      previewImage(document.getElementById('img-upload'));
    }
  });
}

/* ── Util ───────────────────────────────────────────────── */
function showMsg(el, type, text) {
  el.className = `msg-box ${type}`;
  el.textContent = text;
  el.classList.remove('hidden');
}
