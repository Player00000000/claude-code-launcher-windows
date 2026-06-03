/* ── RENDER ── */
function renderProjects(projects) {
  const grid  = document.getElementById('project-grid');
  const count = document.getElementById('project-count');
  count.textContent = projects.length + ' PROJECTS';

  if (!projects.length) {
    grid.innerHTML = '<div class="loading-msg">NO PROJECTS FOUND</div>';
    return;
  }

  grid.innerHTML = projects.map(p => `
    <div class="card"
         data-name="${esc(p.name)}"
         data-wsl-path="${esc(p.wsl_path)}"
         data-color="${esc(p.color)}"
         data-status="${esc(p.status)}"
         style="--card-color:${p.color}">
      <div class="card-header">
        <div class="card-dot" style="background:${p.color}"></div>
        <span class="card-name">${esc(p.name)}</span>
        <button class="btn-edit" onclick="openEditModal('${esc(p.name)}',event)" title="Edit">✎</button>
      </div>
      <div class="card-meta">
        <span class="status-badge" style="--status-color:${p.status_color}">${esc(p.status)}</span>
        <span class="last-modified">⏱ ${esc(p.last_modified)}</span>
      </div>
      <div class="card-desc">${esc(p.description)}</div>
      <div class="card-tech">
        ${p.tech.map(t => `<span class="tag">${esc(t)}</span>`).join('')}
      </div>
      <div class="card-footer">
        <button class="btn-pixel btn-launch"
                onclick="launchProject('${esc(p.name)}','${esc(p.wsl_path)}',this)">
          <span class="btn-label">▶ LAUNCH</span>
        </button>
      </div>
    </div>
  `).join('');
}

function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

/* ── INIT ── */
async function loadProjects() {
  try {
    const projects = await window.pywebview.api.get_projects();
    renderProjects(projects);
  } catch (e) {
    document.getElementById('project-grid').innerHTML =
      '<div class="loading-msg">ERROR LOADING PROJECTS</div>';
  }
}

window.addEventListener('pywebviewready', loadProjects);

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
  try {
    const data = await window.pywebview.api.launch_project(name, wslPath);
    if (data.ok) {
      showToast('LAUNCHING ' + name.toUpperCase(), 'success');
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
  const tech   = document.getElementById('add-tech').value.trim()
                   .split(',').map(t => t.trim()).filter(Boolean);
  const color  = document.getElementById('add-color').value;
  const status = document.getElementById('add-status').value;
  if (!name) { showToast('NAME REQUIRED', 'error'); return; }

  const data = await window.pywebview.api.add_project(name, desc, color, tech, status);
  if (data.ok) {
    closeModal('add-modal');
    showToast('CREATED ' + name.toUpperCase(), 'success');
    setTimeout(loadProjects, 400);
  } else {
    showToast('ERROR: ' + (data.error || 'Unknown'), 'error');
  }
}

/* ── EDIT ── */
function openEditModal(name, event) {
  event.stopPropagation();
  const card   = document.querySelector(`.card[data-name="${CSS.escape(name)}"]`);
  const status = card.dataset.status || 'ACTIVE';
  document.getElementById('edit-name').value   = name;
  document.getElementById('edit-desc').value   = card.querySelector('.card-desc').textContent;
  document.getElementById('edit-tech').value   = Array.from(card.querySelectorAll('.tag')).map(t=>t.textContent).join(', ');
  document.getElementById('edit-color').value  = card.dataset.color || '#888899';
  document.getElementById('edit-status').value = status;
  document.getElementById('edit-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('edit-desc').focus(), 50);
}

async function saveEdit() {
  const name   = document.getElementById('edit-name').value;
  const desc   = document.getElementById('edit-desc').value.trim();
  const tech   = document.getElementById('edit-tech').value.trim()
                   .split(',').map(t => t.trim()).filter(Boolean);
  const color  = document.getElementById('edit-color').value;
  const status = document.getElementById('edit-status').value;

  const data = await window.pywebview.api.update_project(name, desc, color, tech, status);
  if (data.ok) {
    closeModal('edit-modal');
    showToast('SAVED', 'success');
    setTimeout(loadProjects, 400);
  } else {
    showToast('SAVE FAILED', 'error');
  }
}

/* ── KEYBOARD ── */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeModal('add-modal'); closeModal('edit-modal'); }
});
