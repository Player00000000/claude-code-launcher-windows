/* ── STATE ── */
let lastProjectsJson = '';
let showArchived     = false;
let allProjects      = [];
let currentUsage     = {};
let currentSettings  = {};
let sortBy           = 'name';
let viewMode         = 'grid';
let pollTimer        = null;

/* ── FORMATTERS ── */
function fmtTok(n) {
  if (!n) return '0';
  if (n < 1000)       return n + '';
  if (n < 1_000_000)  return (n / 1000).toFixed(0) + 'K';
  return (n / 1_000_000).toFixed(1) + 'M';
}

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
      data-action="pin" title="${p.pinned ? 'Unpin' : 'Pin to top'}">
      ${p.pinned ? '★' : '☆'}</button>`;

    let gitBadge = '';
    if (p.git) {
      const dot    = p.git.dirty > 0 ? `<span class="git-dirty">•${p.git.dirty}</span>` : '';
      const ahead  = p.git.ahead  > 0 ? `<span class="git-ahead">↑${p.git.ahead}</span>`  : '';
      const behind = p.git.behind > 0 ? `<span class="git-behind">↓${p.git.behind}</span>` : '';
      gitBadge = `<span class="git-badge" title="${p.git.dirty} uncommitted file(s)">⑂ ${esc(p.git.branch)}${dot}${ahead}${behind}</span>`;
    }

    const liveDot = p.live
      ? `<span class="live-dot" title="Active Claude session"></span>` : '';

    const launchedHtml = p.last_launched
      ? `<div class="card-launched">▶ launched ${esc(p.last_launched)}</div>` : '';

    const usageHtml = p.tok_sum > 0
      ? `<div class="card-usage">Σ ${fmtTok(p.tok_sum)} · ~$${p.est_cost.toFixed(2)} EST</div>` : '';

    const resumeBtn = p.has_sessions
      ? `<button class="btn-quick" data-action="resume" title="Resume last session">⟲</button>` : '';
    const historyBtn = p.has_sessions
      ? `<button class="btn-quick" data-action="history" title="Session history">≡</button>` : '';

    const notesHtml = p.notes
      ? `<div class="card-notes collapsed">${esc(p.notes)}</div>
         <button class="btn-notes-toggle" data-action="notes">▼ NOTES</button>` : '';

    const archiveClass = p.archived ? ' card-archived' : '';
    const archiveBadge = p.archived ? '<div class="archive-badge">ARCHIVED</div>' : '';

    const portBtn = p.port
      ? `<button class="btn-quick" data-action="browser" title="Open localhost:${esc(p.port)}">🌐</button>` : '';

    const repoBtn = p.remote_url
      ? `<button class="btn-quick" data-action="repo" title="Open GitHub repo">↗</button>` : '';
    const pullBtn = (p.git && p.git.behind > 0)
      ? `<button class="btn-quick" data-action="pull" title="Pull ${p.git.behind} commit(s)">⇣</button>` : '';
    const commitBtn = (p.git && (p.git.dirty > 0 || p.git.ahead > 0))
      ? `<button class="btn-commit" data-action="commitpush" title="Commit &amp; push">⇧</button>` : '';

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
        <span class="card-name">${esc(p.name)}</span>${liveDot}
        ${pinBtn}
        <button class="btn-edit" data-action="edit" title="Edit">✎</button>
      </div>
      <div class="card-meta">
        <span class="status-badge" style="--status-color:${p.status_color}">${esc(p.status)}</span>
        ${gitBadge}
        <span class="last-modified">⏱ ${esc(p.last_modified)}</span>
        <span class="disk-size">💾 ${esc(p.disk_size)}</span>
      </div>
      ${launchedHtml}
      ${usageHtml}
      <div class="card-desc">${esc(p.description)}</div>
      ${notesHtml}
      <div class="card-tech">
        ${(p.tech || []).map(t => `<span class="tag">${esc(t)}</span>`).join('')}
      </div>
      <div class="card-footer">
        <div class="quick-actions">
          <button class="btn-quick" data-action="explorer" title="Open in Explorer">📁</button>
          <button class="btn-quick" data-action="vscode" title="Open in VS Code">💻</button>
          ${portBtn}
          ${resumeBtn}
          ${historyBtn}
          ${repoBtn}
          ${pullBtn}
        </div>
        <div style="display:flex;gap:6px;align-items:center">
          ${commitBtn}
          <button class="btn-pixel btn-launch" data-action="launch" style="flex:1">
            <span class="btn-label">▶ LAUNCH</span>
          </button>
        </div>
      </div>
    </div>`;
  }).join('');
}

/* ── LOAD PROJECTS ── */
function isAnyModalOpen() {
  return ['add-modal','edit-modal','billing-modal','help-modal',
          'settings-modal','sessions-modal','commit-modal','delete-modal','rename-modal','clone-modal']
    .some(id => !document.getElementById(id).classList.contains('hidden'));
}

async function loadProjects(force = false) {
  if (isAnyModalOpen() && !force) return;

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

/* ── DELEGATED CARD CLICK HANDLER ── */
document.getElementById('project-grid').addEventListener('click', e => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  const card = btn.closest('.card');
  const d = card ? card.dataset : {};
  switch (btn.dataset.action) {
    case 'pin':        togglePin(d.name); break;
    case 'edit':       e.stopPropagation(); openEditModal(d.name); break;
    case 'explorer':   openExplorer(d.name); break;
    case 'vscode':     openVSCode(d.name); break;
    case 'browser':    openBrowser(d.name, d.port); break;
    case 'launch':     launchProject(d.name, d.wslPath, btn); break;
    case 'notes':      toggleNotes(btn); break;
    // stubs — filled in later phases:
    case 'resume':     resumeProject(d.name, d.wslPath); break;
    case 'history':    openHistoryModal(d.name); break;
    case 'commitpush': openCommitModal(d.name); break;
    case 'pull':       pullProject(d.name); break;
    case 'repo':       openRepo(d.name); break;
  }
});

window.addEventListener('pywebviewready', async () => {
  try {
    currentSettings = await window.pywebview.api.get_settings();
    applyTheme(currentSettings.theme || 'neon');
    if (currentSettings.summer) initSummer();
  } catch(e) {}
  loadProjects(true);
  loadUsage();
  startPollTimer();
});

function startPollTimer() {
  if (pollTimer) clearInterval(pollTimer);
  const ms = Math.max(2, (currentSettings.poll_interval_sec || 5)) * 1000;
  pollTimer = setInterval(() => loadProjects(), ms);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme || 'neon');
}

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
      if (window.summer) window.summer.excite();
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
  document.getElementById('add-name').value        = '';
  document.getElementById('add-desc').value        = '';
  document.getElementById('add-tech').value        = '';
  document.getElementById('add-color').value       = '#888899';
  document.getElementById('add-status').value      = 'ACTIVE';
  document.getElementById('add-create-repo').checked = false;
  document.getElementById('add-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('add-name').focus(), 50);
}

async function addProject() {
  const name        = document.getElementById('add-name').value.trim();
  const desc        = document.getElementById('add-desc').value.trim() || 'New project.';
  const tech        = document.getElementById('add-tech').value.trim().split(',').map(t=>t.trim()).filter(Boolean);
  const color       = document.getElementById('add-color').value;
  const status      = document.getElementById('add-status').value;
  const create_repo = document.getElementById('add-create-repo').checked;
  if (!name) { showToast('NAME REQUIRED', 'error'); return; }
  const data = await window.pywebview.api.add_project(name, desc, color, tech, status, create_repo);
  if (data.ok) {
    closeModal('add-modal');
    const msg = create_repo ? 'CREATING REPO...' : 'CREATED';
    showToast(msg + ' ' + name.toUpperCase(), 'success');
    setTimeout(() => loadProjects(true), 400);
  } else {
    showToast('ERROR: ' + (data.error || 'Unknown'), 'error');
  }
}

/* ── EDIT ── */
async function openEditModal(name) {
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
let _claudeUsage = null;

async function loadUsage() {
  try {
    currentUsage = await window.pywebview.api.get_usage();
    try { _claudeUsage = await window.pywebview.api.get_claude_usage(); } catch(e) {}
    renderCredit(currentUsage);
  } catch(e) {}
}

function renderCredit(u) {
  const el = document.getElementById('credit-widget');
  if (!el) return;
  const launches = u.launches_this_month || 0;
  const resetHtml = (u.reset_in_days !== null && u.reset_in_days !== undefined)
    ? `<span class="credit-pill credit-reset" onclick="openBillingModal()" title="Resets in ${u.reset_in_days}d">⚡ ${u.reset_in_days}D</span>`
    : `<span class="credit-pill credit-set" onclick="openBillingModal()" title="Set billing date">⚡ SET</span>`;

  let tokHtml = '';
  if (_claudeUsage) {
    const p = _claudeUsage.period || _claudeUsage.total || {};
    const tok = p.tok_sum || 0;
    const cost = p.est_cost || 0;
    if (tok > 0) {
      tokHtml = `<span class="credit-pill credit-launches" title="Tokens this billing period · est cost">
        ${fmtTok(tok)} TOK · ~$${cost.toFixed(2)}</span>`;
    }
  }
  if (!tokHtml) {
    tokHtml = `<span class="credit-pill credit-launches" title="Launches this month">▶ ${launches}</span>`;
  }

  el.innerHTML = `${resetHtml}${tokHtml}
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

/* ── DELETE / RENAME / PRUNE ── */
function openDeleteFromEdit() {
  const name = document.getElementById('edit-name').value;
  document.getElementById('delete-project-name').value  = name;
  document.getElementById('delete-confirm-input').value = '';
  closeModal('edit-modal');
  document.getElementById('delete-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('delete-confirm-input').focus(), 50);
}

async function doDeleteProject() {
  const name    = document.getElementById('delete-project-name').value;
  const confirm = document.getElementById('delete-confirm-input').value.trim();
  if (confirm !== name) { showToast('NAME MISMATCH', 'error'); return; }
  const r = await window.pywebview.api.delete_project(name, confirm);
  if (r.ok) {
    closeModal('delete-modal');
    showToast('DELETED ' + name.toUpperCase(), 'success');
    setTimeout(() => loadProjects(true), 400);
  } else {
    showToast('ERROR: ' + (r.error || 'Unknown'), 'error');
  }
}

function openRenameFromEdit() {
  const name = document.getElementById('edit-name').value;
  document.getElementById('rename-project-old').value = name;
  document.getElementById('rename-project-new').value = name;
  closeModal('edit-modal');
  document.getElementById('rename-modal').classList.remove('hidden');
  setTimeout(() => {
    const el = document.getElementById('rename-project-new');
    el.focus(); el.select();
  }, 50);
}

async function doRenameProject() {
  const old_name = document.getElementById('rename-project-old').value;
  const new_name = document.getElementById('rename-project-new').value.trim();
  if (!new_name || new_name === old_name) { showToast('ENTER NEW NAME', 'error'); return; }
  const r = await window.pywebview.api.rename_project(old_name, new_name);
  if (r.ok) {
    closeModal('rename-modal');
    showToast('RENAMED TO ' + new_name.toUpperCase(), 'success');
    setTimeout(() => loadProjects(true), 400);
  } else {
    showToast('ERROR: ' + (r.error || 'Unknown'), 'error');
  }
}

/* ── SETTINGS ── */
async function openSettingsModal() {
  const s = currentSettings;
  document.getElementById('settings-win-base').value    = s.win_base    || '';
  document.getElementById('settings-wsl-distro').value  = s.wsl_distro  || 'Ubuntu';
  document.getElementById('settings-poll').value        = s.poll_interval_sec || 5;
  document.getElementById('settings-scan').value        = s.scan_interval_sec || 60;
  document.getElementById('settings-summer').checked    = !!s.summer;
  const theme = s.theme || 'neon';
  document.querySelectorAll('input[name="theme"]').forEach(r => { r.checked = r.value === theme; });
  document.getElementById('settings-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('settings-win-base').focus(), 50);
  // Load orphan count async
  try {
    const r = await window.pywebview.api.get_orphan_count();
    const n = (r && r.count) || 0;
    const lbl = document.getElementById('orphan-count-label');
    if (lbl) lbl.textContent = n === 0 ? 'No orphan meta entries' : `${n} orphan meta entr${n === 1 ? 'y' : 'ies'}`;
    const btn = document.getElementById('prune-btn');
    if (btn) btn.disabled = n === 0;
  } catch(e) {}
}

async function doPruneMeta() {
  const r = await window.pywebview.api.prune_meta();
  if (r.ok) {
    const n = (r.pruned || []).length;
    const lbl = document.getElementById('orphan-count-label');
    if (lbl) lbl.textContent = `Pruned ${n} entr${n === 1 ? 'y' : 'ies'}`;
    const btn = document.getElementById('prune-btn');
    if (btn) btn.disabled = true;
    showToast(`PRUNED ${n} ORPHAN(S)`, 'success');
    setTimeout(() => loadProjects(true), 400);
  } else {
    showToast('ERROR: ' + (r.error || 'Unknown'), 'error');
  }
}

async function saveSettingsModal() {
  const win_base          = document.getElementById('settings-win-base').value.trim();
  const wsl_distro        = document.getElementById('settings-wsl-distro').value.trim() || 'Ubuntu';
  const poll_interval_sec = parseInt(document.getElementById('settings-poll').value) || 5;
  const scan_interval_sec = parseInt(document.getElementById('settings-scan').value) || 60;
  const summer            = document.getElementById('settings-summer').checked;
  const theme             = document.querySelector('input[name="theme"]:checked')?.value || 'neon';

  const data = await window.pywebview.api.api_save_settings({
    win_base, wsl_distro, poll_interval_sec, scan_interval_sec, summer, theme,
  });
  if (data.ok) {
    currentSettings = { ...currentSettings, win_base, wsl_distro, poll_interval_sec, scan_interval_sec, summer, theme };
    applyTheme(theme);
    startPollTimer();
    if (summer) initSummer(); else hideSummer();
    closeModal('settings-modal');
    showToast('SETTINGS SAVED', 'success');
    setTimeout(() => loadProjects(true), 400);
  } else {
    showToast('ERROR: ' + (data.error || 'Unknown'), 'error');
  }
}

/* ── PHASE STUBS (filled in later phases) ── */
function initSummer()  { if (window.summer) window.summer.init(); }
function hideSummer()  { if (window.summer) window.summer.hide(); }

async function resumeProject(name, wslPath) {
  const r = await window.pywebview.api.resume_project(name, wslPath, '');
  if (r.ok) {
    showToast('RESUMING ' + name.toUpperCase(), 'success');
    if (window.summer) window.summer.excite();
    setTimeout(() => loadProjects(true), 1500);
  } else {
    showToast('ERROR: ' + (r.error || 'Unknown'), 'error');
  }
}

async function openHistoryModal(name) {
  const card     = document.querySelector(`.card[data-name="${CSS.escape(name)}"]`);
  const wslPath  = card ? card.dataset.wslPath : '';
  const sessions = await window.pywebview.api.get_sessions(name, wslPath);
  const title    = document.getElementById('sessions-modal-title');
  const list     = document.getElementById('sessions-list');
  title.textContent = 'SESSION HISTORY: ' + name.toUpperCase();
  if (!sessions || !sessions.length) {
    list.innerHTML = '<div class="loading-msg" style="padding:20px">NO SESSIONS FOUND</div>';
  } else {
    list.innerHTML = sessions.map(s => `
      <div class="session-row" data-action="resume-session"
           data-session-id="${esc(s.id)}" data-name="${esc(name)}" data-wsl-path="${esc(wslPath)}">
        <div class="session-row-header">
          <span class="session-ago">${esc(s.start_ago || 'unknown')}</span>
          <span class="session-meta">${s.msg_count} msg</span>
        </div>
        <div class="session-prompt">${esc(s.first_prompt || '(no text prompt)')}</div>
      </div>`).join('');

    list.onclick = async e => {
      const row = e.target.closest('[data-action="resume-session"]');
      if (!row) return;
      const r = await window.pywebview.api.resume_project(
        row.dataset.name, row.dataset.wslPath, row.dataset.sessionId);
      if (r.ok) {
        closeModal('sessions-modal');
        showToast('RESUMING SESSION', 'success');
        if (window.summer) window.summer.excite();
      } else {
        showToast('ERROR: ' + (r.error || 'Unknown'), 'error');
      }
    };
  }
  document.getElementById('sessions-modal').classList.remove('hidden');
}
async function openCommitModal(name) {
  const r = await window.pywebview.api.get_commit_preview(name);
  if (!r.ok) { showToast('ERROR: ' + r.error, 'error'); return; }
  if (!r.count) { showToast('NOTHING TO COMMIT', ''); return; }
  document.getElementById('commit-project-name').value = name;
  document.getElementById('commit-file-list').value    = r.files;
  document.getElementById('commit-message').value      = r.default_msg;
  document.getElementById('commit-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('commit-message').focus(), 50);
}

async function doCommitPush() {
  const name = document.getElementById('commit-project-name').value;
  const msg  = document.getElementById('commit-message').value.trim();
  if (!msg) { showToast('ENTER COMMIT MESSAGE', 'error'); return; }
  const btn = document.querySelector('#commit-modal .btn-confirm');
  btn.textContent = 'WORKING...'; btn.disabled = true;
  try {
    const r = await window.pywebview.api.commit_push(name, msg);
    if (r.ok) {
      closeModal('commit-modal');
      showToast(r.msg || 'DONE', 'success');
      setTimeout(() => loadProjects(true), 600);
    } else {
      showToast('ERROR: ' + (r.error || 'Unknown'), 'error');
    }
  } finally {
    btn.textContent = 'COMMIT & PUSH'; btn.disabled = false;
  }
}

async function pullProject(name) {
  showToast('PULLING ' + name.toUpperCase() + '...', '');
  const r = await window.pywebview.api.git_pull(name);
  if (r.ok) {
    showToast((r.msg || 'PULLED').toUpperCase(), 'success');
    setTimeout(() => loadProjects(true), 600);
  } else {
    showToast('ERROR: ' + (r.error || 'Unknown'), 'error');
  }
}

async function openRepo(name) {
  const r = await window.pywebview.api.open_repo(name);
  if (!r.ok) showToast('ERROR: ' + (r.error || 'No remote'), 'error');
}

/* ── KEYBOARD ── */
document.addEventListener('keydown', e => {
  const active  = document.activeElement;
  const inInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(active.tagName);
  const modalOpen = isAnyModalOpen();

  if (e.key === 'Escape') {
    if (inInput && active.id === 'search-bar') {
      active.value = ''; filterProjects(''); active.blur();
    }
    ['add-modal','edit-modal','billing-modal','help-modal',
     'settings-modal','sessions-modal','commit-modal','delete-modal','rename-modal','clone-modal']
      .forEach(id => closeModal(id));
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
    const cards = document.querySelectorAll('#project-grid .card');
    if (cards[idx]) cards[idx].querySelector('[data-action="launch"]')?.click();
  }
});

/* ── CLONE FROM GITHUB ── */
function openCloneModal() {
  document.getElementById('clone-url').value  = '';
  document.getElementById('clone-name').value = '';
  document.getElementById('clone-status').textContent = '';
  document.getElementById('clone-status').style.color = '';
  document.getElementById('clone-btn').textContent = '⬇ CLONE';
  document.getElementById('clone-btn').disabled = false;
  document.getElementById('clone-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('clone-url').focus(), 50);
}

function _deriveRepoName(url) {
  url = url.trim().replace(/\/$/, '');
  let name = url.split('/').pop().split(':').pop();
  if (name.endsWith('.git')) name = name.slice(0, -4);
  return name;
}

function onCloneUrlInput(val) {
  const name = _deriveRepoName(val);
  if (name) document.getElementById('clone-name').value = name;
  onCloneNameInput(name);
}

function onCloneNameInput(name) {
  const status = document.getElementById('clone-status');
  const btn    = document.getElementById('clone-btn');
  const exists = allProjects.some(p => p.name.toLowerCase() === name.toLowerCase());
  if (!name) {
    status.textContent = ''; status.style.color = '';
    btn.textContent = '⬇ CLONE';
  } else if (exists) {
    status.textContent = `"${name}" already exists — will PULL instead`;
    status.style.color = '#ffe66d';
    btn.textContent = '⇣ PULL';
  } else {
    status.textContent = `Will clone as: ${name}`;
    status.style.color = 'var(--accent)';
    btn.textContent = '⬇ CLONE';
  }
}

async function doClone() {
  const url  = document.getElementById('clone-url').value.trim();
  const name = document.getElementById('clone-name').value.trim();
  if (!url) { showToast('ENTER URL', 'error'); return; }

  const exists = allProjects.some(p => p.name.toLowerCase() === name.toLowerCase());
  if (exists) {
    closeModal('clone-modal');
    showToast('PULLING ' + name.toUpperCase() + '...', '');
    const r = await window.pywebview.api.git_pull(name);
    if (r.ok) showToast((r.msg || 'PULLED').toUpperCase(), 'success');
    else       showToast('ERROR: ' + (r.error || 'Unknown'), 'error');
    setTimeout(() => loadProjects(true), 600);
    return;
  }

  const btn = document.getElementById('clone-btn');
  btn.textContent = 'CLONING...'; btn.disabled = true;
  try {
    const r = await window.pywebview.api.clone_project(url, name);
    if (r.ok) {
      closeModal('clone-modal');
      showToast('CLONED ' + r.name.toUpperCase(), 'success');
      setTimeout(() => loadProjects(true), 600);
    } else if (r.error === 'exists') {
      onCloneNameInput(r.name);
    } else {
      showToast('ERROR: ' + (r.error || 'Unknown'), 'error');
    }
  } finally {
    btn.textContent = '⬇ CLONE'; btn.disabled = false;
  }
}
