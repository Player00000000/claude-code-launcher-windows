/* ── STATE ── */
let lastProjectsJson = '';
let showArchived = false;
let allProjects  = [];
let currentUsage = {};
let sortBy       = 'name';
let viewMode     = 'grid';
let onTop        = false;

/* ── HTML ESCAPE ── */
function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
    .replace(/\n/g, '&#10;').replace(/\r/g, '');
}

/* ── SORT (Feature 2) ── */
function setSortBy(val) {
  sortBy = val;
  applyFilter(document.getElementById('search-bar').value);
}

function sortProjects(projects) {
  const pinned   = projects.filter(p => p.pinned);
  const unpinned = projects.filter(p => !p.pinned);
  unpinned.sort((a, b) => {
    switch (sortBy) {
      case 'launched': return (b.last_launched_ts || 0) - (a.last_launched_ts || 0);
      case 'modified': return (b.last_modified_ts || 0) - (a.last_modified_ts || 0);
      case 'status':   return a.status.localeCompare(b.status);
      default:         return a.name.localeCompare(b.name);
    }
  });
  return [...pinned, ...unpinned];
}

/* ── RENDER ── */
function renderProjects(projects) {
  allProjects = projects;
  applyFilter(document.getElementById('search-bar').value);
}

function applyFilter(query) {
  const grid  = document.getElementById('project-grid');
  const count = document.getElementById('project-count');
  const q = query.trim().toLowerCase();

  let visible = allProjects;
  if (q) {
    visible = allProjects.filter(p =>
      p.name.toLowerCase().includes(q) ||
      p.description.toLowerCase().includes(q) ||
      (p.tech || []).some(t => t.toLowerCase().includes(q))
    );
  }

  visible = sortProjects(visible);
  count.textContent = visible.length + ' PROJECTS';

  if (!visible.length) {
    grid.innerHTML = q
      ? `<div class="loading-msg">NO MATCH FOR "${esc(q.toUpperCase())}"</div>`
      : '<div class="loading-msg">NO PROJECTS FOUND</div>';
    return;
  }

  grid.innerHTML = visible.map((p, i) => {
    const kbdHint = (i < 9)
      ? `<span class="kbd-hint" title="Press ${i+1} to launch">${i+1}</span>` : '';

    const pinBtn = `<button class="btn-pin${p.pinned ? ' pinned' : ''}"
      onclick="togglePin('${esc(p.name)}')" title="${p.pinned ? 'Unpin' : 'Pin to top'}">
      ${p.pinned ? '★' : '☆'}</button>`;

    let gitBadge = '';
    if (p.git) {
      const dot = p.git.dirty > 0 ? `<span class="git-dirty">•${p.git.dirty}</span>` : '';
      gitBadge = `<span class="git-badge" title="${p.git.dirty} uncommitted file(s)">⑂ ${esc(p.git.branch)}${dot}</span>`;
    }

    const launchedHtml = p.last_launched
      ? `<div class="card-launched">▶ launched ${esc(p.last_launched)}</div>` : '';

    const notesHtml = p.notes
      ? `<div class="card-notes collapsed">${esc(p.notes)}</div>
         <button class="btn-notes-toggle" onclick="toggleNotes(this)">▼ NOTES</button>` : '';

    const archiveClass = p.archived ? ' card-archived' : '';
    const archiveBadge = p.archived ? '<div class="archive-badge">ARCHIVED</div>' : '';

    const portBtn = p.port
      ? `<button class="btn-quick" onclick="openBrowser('${esc(p.name)}','${esc(p.port)}')" title="Open localhost:${esc(p.port)}">🌐</button>` : '';

    return `
    <div class="card${archiveClass}"
         data-name="${esc(p.name)}"
         data-wsl-path="${esc(p.wsl_path)}"
         data-color="${esc(p.color)}"
         data-status="${esc(p.status)}"
         data-launch-cmd="${esc(p.launch_cmd)}"
         data-port="${esc(p.port)}"
         style="--card-color:${p.color}">
      ${kbdHint}${archiveBadge}
      <div class="card-header">
        <div class="card-dot" style="background:${p.color}"></div>
        <span class="card-name">${esc(p.name)}</span>
        ${pinBtn}
        <button class="btn-edit" onclick="openEditModal('${esc(p.name)}',event)" title="Edit">✎</button>
      </div>
      <div class="card-meta">
        <span class="status-badge" style="--status-color:${p.status_color}">${esc(p.status)}</span>
        ${gitBadge}
        <span class="last-modified">⏱ ${esc(p.last_modified)}</span>
        <span class="disk-size">💾 ${esc(p.disk_size)}</span>
      </div>
      ${launchedHtml}
      <div class="card-desc">${esc(p.description)}</div>
      ${notesHtml}
      <div class="card-tech">
        ${(p.tech || []).map(t => `<span class="tag">${esc(t)}</span>`).join('')}
      </div>
      <div class="card-footer">
        <div class="quick-actions">
          <button class="btn-quick" onclick="openExplorer('${esc(p.name)}')" title="Open in Explorer">📁</button>
          <button class="btn-quick" onclick="openVSCode('${esc(p.name)}')" title="Open in VS Code">💻</button>
          ${portBtn}
        </div>
        <button class="btn-pixel btn-launch"
                onclick="launchProject('${esc(p.name)}','${esc(p.wsl_path)}',this)">
          <span class="btn-label">▶ LAUNCH</span>
        </button>
      </div>
    </div>`;
  }).join('');
}

/* ── LOAD PROJECTS ── */
async function loadProjects(force = false) {
  const modalsOpen =
    !document.getElementById('add-modal').classList.contains('hidden') ||
    !document.getElementById('edit-modal').classList.contains('hidden');
  if (modalsOpen && !force) return;

  try {
    const projects = await window.pywebview.api.get_projects(showArchived);
    const json = JSON.stringify(projects);
    if (json !== lastProjectsJson || force) {
      lastProjectsJson = json;
      renderProjects(projects);
    }
  } catch (e) {
    document.getElementById('project-grid').innerHTML =
      '<div class="loading-msg">ERROR LOADING PROJECTS</div>';
  }
}

window.addEventListener('pywebviewready', () => {
  loadProjects(true);
  loadUsage();
  setInterval(() => loadProjects(), 5000);
});

/* ── SEARCH ── */
function filterProjects(query) { applyFilter(query); }

/* ── VIEW TOGGLE (Feature 3) ── */
function toggleView() {
  viewMode = viewMode === 'grid' ? 'list' : 'grid';
  const grid = document.getElementById('project-grid');
  grid.classList.toggle('list-view', viewMode === 'list');
  const btn = document.getElementById('view-toggle');
  btn.textContent = viewMode === 'list' ? '⊞' : '☰';
  btn.title = viewMode === 'list' ? 'Switch to grid view' : 'Switch to list view';
}

/* ── ARCHIVE TOGGLE ── */
function toggleArchivedView() {
  showArchived = !showArchived;
  const btn = document.getElementById('archive-toggle');
  btn.classList.toggle('active', showArchived);
  btn.title = showArchived ? 'Hide archived' : 'Show archived';
  loadProjects(true);
}

/* ── PIN (Feature 1) ── */
async function togglePin(name) {
  const r = await window.pywebview.api.toggle_pin(name);
  if (r.ok) loadProjects(true);
}

/* ── ALWAYS ON TOP (Feature 7) ── */
async function toggleAlwaysOnTop() {
  const r = await window.pywebview.api.toggle_always_on_top();
  if (r.ok) {
    onTop = r.on_top;
    const btn = document.getElementById('ontop-btn');
    btn.classList.toggle('active', onTop);
    btn.title = onTop ? 'Disable always on top' : 'Always on top';
    showToast(onTop ? 'ALWAYS ON TOP: ON' : 'ALWAYS ON TOP: OFF', 'success');
  } else {
    showToast('ERROR: ' + (r.error || 'Unknown'), 'error');
  }
}

/* ── NOTES TOGGLE ── */
function toggleNotes(btn) {
  const notes = btn.previousElementSibling;
  if (!notes) return;
  const collapsed = notes.classList.toggle('collapsed');
  btn.textContent = collapsed ? '▼ NOTES' : '▲ NOTES';
}

/* ── QUICK ACTIONS ── */
async function openExplorer(name) {
  const r = await window.pywebview.api.open_explorer(name);
  if (!r.ok) showToast('ERROR: ' + r.error, 'error');
}
async function openVSCode(name) {
  const r = await window.pywebview.api.open_vscode(name);
  if (!r.ok) showToast('ERROR: ' + r.error, 'error');
}
async function openBrowser(name, port) {
  if (!port) { showToast('SET PORT IN EDIT FIRST', 'error'); return; }
  const r = await window.pywebview.api.open_browser(name, port);
  if (!r.ok) showToast('ERROR: ' + (r.error || 'Unknown'), 'error');
}

/* ── TOAST ── */
let toastTimer;
function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast' + (type ? ' ' + type : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = 'toast hidden'; }, 3000);
}

/* ── LAUNCH ── */
async function launchProject(name, wslPath, btn) {
  if (btn.classList.contains('loading')) return;
  btn.classList.add('loading');
  btn.querySelector('.btn-label').textContent = '... LAUNCHING';
  const card = btn.closest('.card');
  const launchCmd = card ? (card.dataset.launchCmd || '') : '';
  try {
    const data = await window.pywebview.api.launch_project(name, wslPath, launchCmd);
    if (data.ok) {
      showToast('LAUNCHING ' + name.toUpperCase(), 'success');
      setTimeout(() => { loadProjects(true); loadUsage(); }, 1500);
    } else {
      showToast('ERROR: ' + (data.error || 'Unknown'), 'error');
    }
  } catch (e) {
    showToast('ERROR: ' + e.message, 'error');
  } finally {
    setTimeout(() => {
      btn.classList.remove('loading');
      btn.querySelector('.btn-label').textContent = '▶ LAUNCH';
    }, 2000);
  }
}

/* ── MODALS ── */
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }
function closeOnBackdrop(e, id) { if (e.target.id === id) closeModal(id); }
function setSwatch(color, inputId) { document.getElementById(inputId).value = color; }
function openHelp() { document.getElementById('help-modal').classList.remove('hidden'); }

/* ── ADD ── */
function openAddModal() {
  document.getElementById('add-name').value   = '';
  document.getElementById('add-desc').value   = '';
  document.getElementById('add-tech').value   = '';
  document.getElementById('add-color').value  = '#888899';
  document.getElementById('add-status').value = 'ACTIVE';
  document.getElementById('add-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('add-name').focus(), 50);
}

async function addProject() {
  const name   = document.getElementById('add-name').value.trim();
  const desc   = document.getElementById('add-desc').value.trim() || 'New project.';
  const tech   = document.getElementById('add-tech').value.trim().split(',').map(t=>t.trim()).filter(Boolean);
  const color  = document.getElementById('add-color').value;
  const status = document.getElementById('add-status').value;
  if (!name) { showToast('NAME REQUIRED', 'error'); return; }
  const data = await window.pywebview.api.add_project(name, desc, color, tech, status);
  if (data.ok) {
    closeModal('add-modal');
    showToast('CREATED ' + name.toUpperCase(), 'success');
    setTimeout(() => loadProjects(true), 400);
  } else {
    showToast('ERROR: ' + (data.error || 'Unknown'), 'error');
  }
}

/* ── EDIT ── */
async function openEditModal(name, event) {
  event.stopPropagation();
  const card = document.querySelector(`.card[data-name="${CSS.escape(name)}"]`);
  const archived = card.classList.contains('card-archived');
  let meta = {};
  try { meta = await window.pywebview.api.get_project_meta(name); } catch(e) {}

  document.getElementById('edit-name').value       = name;
  document.getElementById('edit-desc').value       = meta.description || '';
  document.getElementById('edit-notes').value      = meta.notes || '';
  document.getElementById('edit-tech').value       = (meta.tech || []).join(', ');
  document.getElementById('edit-color').value      = meta.color || card.dataset.color || '#888899';
  document.getElementById('edit-status').value     = meta.status || card.dataset.status || 'ACTIVE';
  document.getElementById('edit-launch-cmd').value = meta.launch_cmd || '';
  document.getElementById('edit-port').value       = meta.port || '';

  const archBtn = document.getElementById('edit-archive-btn');
  if (archived) {
    archBtn.textContent = '✓ UNARCHIVE';
    archBtn.classList.add('btn-unarchive'); archBtn.classList.remove('btn-archive');
  } else {
    archBtn.textContent = '⊘ ARCHIVE';
    archBtn.classList.add('btn-archive'); archBtn.classList.remove('btn-unarchive');
  }
  document.getElementById('edit-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('edit-desc').focus(), 50);
}

async function saveEdit() {
  const name      = document.getElementById('edit-name').value;
  const desc      = document.getElementById('edit-desc').value.trim();
  const notes     = document.getElementById('edit-notes').value.trim();
  const tech      = document.getElementById('edit-tech').value.trim().split(',').map(t=>t.trim()).filter(Boolean);
  const color     = document.getElementById('edit-color').value;
  const status    = document.getElementById('edit-status').value;
  const launchCmd = document.getElementById('edit-launch-cmd').value.trim();
  const port      = document.getElementById('edit-port').value.trim();

  const data = await window.pywebview.api.update_project(name, desc, color, tech, status, launchCmd, notes, port);
  if (data.ok) {
    closeModal('edit-modal');
    showToast('SAVED', 'success');
    setTimeout(() => loadProjects(true), 400);
  } else {
    showToast('SAVE FAILED', 'error');
  }
}

async function archiveFromEdit() {
  const name = document.getElementById('edit-name').value;
  const data = await window.pywebview.api.toggle_archive(name);
  if (data.ok) {
    closeModal('edit-modal');
    showToast(data.archived ? 'ARCHIVED' : 'UNARCHIVED', data.archived ? '' : 'success');
    setTimeout(() => loadProjects(true), 400);
  } else {
    showToast('FAILED', 'error');
  }
}

/* ── CREDIT WIDGET ── */
async function loadUsage() {
  try { currentUsage = await window.pywebview.api.get_usage(); renderCredit(currentUsage); } catch(e) {}
}

function renderCredit(u) {
  const el = document.getElementById('credit-widget');
  if (!el) return;
  const launches = u.launches_this_month || 0;
  const resetHtml = (u.reset_in_days !== null && u.reset_in_days !== undefined)
    ? `<span class="credit-pill credit-reset" onclick="openBillingModal()" title="Resets in ${u.reset_in_days}d">⚡ ${u.reset_in_days}D</span>`
    : `<span class="credit-pill credit-set" onclick="openBillingModal()" title="Set billing date">⚡ SET</span>`;
  el.innerHTML = `${resetHtml}
    <span class="credit-pill credit-launches" title="Launches this month">▶ ${launches}</span>
    <span class="credit-pill credit-console" onclick="openConsole()" title="Anthropic Console">CONSOLE ↗</span>`;
}

function openBillingModal() {
  document.getElementById('billing-day-input').value = currentUsage.billing_start_day || '';
  document.getElementById('billing-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('billing-day-input').focus(), 50);
}

async function openConsole() {
  try { await window.pywebview.api.open_console(); } catch(e) {}
}

async function saveBillingDay() {
  const day = parseInt(document.getElementById('billing-day-input').value);
  if (!day || day < 1 || day > 28) { showToast('ENTER DAY 1-28', 'error'); return; }
  const data = await window.pywebview.api.set_billing_day(day);
  if (data.ok) {
    closeModal('billing-modal');
    showToast('BILLING DATE: DAY ' + day, 'success');
    loadUsage();
  } else {
    showToast('ERROR: ' + (data.error || 'Unknown'), 'error');
  }
}

/* ── KEYBOARD ── */
document.addEventListener('keydown', e => {
  const active  = document.activeElement;
  const inInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(active.tagName);
  const modalOpen =
    !document.getElementById('add-modal').classList.contains('hidden') ||
    !document.getElementById('edit-modal').classList.contains('hidden') ||
    !document.getElementById('billing-modal').classList.contains('hidden') ||
    !document.getElementById('help-modal').classList.contains('hidden');

  if (e.key === 'Escape') {
    if (inInput && active.id === 'search-bar') {
      active.value = ''; filterProjects(''); active.blur();
    }
    closeModal('add-modal'); closeModal('edit-modal');
    closeModal('billing-modal'); closeModal('help-modal');
    return;
  }
  if (!modalOpen && !inInput && e.key === '/') {
    e.preventDefault();
    document.getElementById('search-bar').focus();
    return;
  }
  if (!modalOpen && !inInput && e.key === '?') {
    openHelp(); return;
  }
  if (!modalOpen && !inInput && e.key >= '1' && e.key <= '9') {
    const idx = parseInt(e.key) - 1;
    const cards = document.querySelectorAll('.card:not(.card-archived)');
    if (cards[idx]) cards[idx].querySelector('.btn-launch')?.click();
  }
});
