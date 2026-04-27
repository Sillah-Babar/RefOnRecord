'use strict';

/* =============================================================
   RefOnRecord Web Client
   API: http://74.241.132.64:8080
   Author: RefOnRecord team — PWP 2026

   Architecture: single-page application with hash-based routing.
   All views are rendered into static <div> elements; JS toggles
   their visibility and populates them with data fetched from the
   REST API described in openapi.yaml.
============================================================= */

// ── Configuration ────────────────────────────────────────────
// Value comes from config.js (loaded before this script in index.html).
// To switch environments edit config.js — do not hardcode here.
const API_BASE = window.APP_CONFIG?.API_BASE || 'http://74.241.132.64:8080';

// ── Application State ────────────────────────────────────────
/**
 * Central mutable state shared across all view functions.
 * token / userId are also persisted in localStorage so the
 * session survives a page refresh.
 */
const state = {
  token:            null,
  userId:           null,
  user:             null,
  currentProjectId: null,
  currentProject:   null,
  /** polling timer id for pending-verification auto-refresh */
  pollTimer:        null,
};

// ── Persistence ───────────────────────────────────────────────
/** Restore auth from localStorage on startup. */
function loadAuth() {
  state.token  = localStorage.getItem('ror_token');
  const uid    = localStorage.getItem('ror_userId');
  state.userId = uid ? parseInt(uid, 10) : null;
}

/**
 * Persist a successful login to localStorage.
 * @param {string} token - JWT bearer token
 * @param {number} userId - numeric user id
 */
function saveAuth(token, userId) {
  state.token  = token;
  state.userId = userId;
  localStorage.setItem('ror_token',  token);
  localStorage.setItem('ror_userId', String(userId));
}

/** Remove all stored credentials and reset state. */
function clearAuth() {
  state.token  = null;
  state.userId = null;
  state.user   = null;
  localStorage.removeItem('ror_token');
  localStorage.removeItem('ror_userId');
  stopPoll();
}

// ── API Client ────────────────────────────────────────────────
/**
 * Make an authenticated request to the RefOnRecord API.
 * @param {string} path - API path, e.g. '/api/users/1/'
 * @param {object} opts - fetch options + optional `body` object
 * @returns {Promise<object|null>} parsed JSON body or null for 204
 * @throws {object} {status, message, data} on non-2xx responses
 */
async function apiFetch(path, opts = {}) {
  const headers = {};
  if (opts.body)   headers['Content-Type'] = 'application/json';
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method:  opts.method || 'GET',
    headers,
    body:    opts.body ? JSON.stringify(opts.body) : undefined,
  });

  if (res.status === 204) return null;

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    // 401 outside the auth page → session expired
    if (res.status === 401 && window.location.hash !== '#login') {
      clearAuth();
      renderAuth();
      toast('Session expired. Please sign in again.', 'error');
    }
    const err  = new Error(data.message || data.error || `HTTP ${res.status}`);
    err.status = res.status;
    err.data   = data;
    throw err;
  }

  return data;
}

// Convenience API namespaces ---------------------------------

const AuthAPI = {
  login:    (email, pw)  => apiFetch('/api/auth/login/',  { method: 'POST', body: { email, password: pw } }),
  logout:   ()           => apiFetch('/api/auth/logout/', { method: 'DELETE' }),
  register: (data)       => apiFetch('/api/users/',       { method: 'POST', body: data }),
};

const UsersAPI = {
  get:    (uid)        => apiFetch(`/api/users/${uid}/`),
  update: (uid, data)  => apiFetch(`/api/users/${uid}/`, { method: 'PUT', body: data }),
  del:    (uid)        => apiFetch(`/api/users/${uid}/`, { method: 'DELETE' }),
};

const ProjectsAPI = {
  list:   (uid)              => apiFetch(`/api/users/${uid}/projects/`),
  create: (uid, data)        => apiFetch(`/api/users/${uid}/projects/`,   { method: 'POST', body: data }),
  get:    (uid, pid)         => apiFetch(`/api/users/${uid}/projects/${pid}/`),
  update: (uid, pid, data)   => apiFetch(`/api/users/${uid}/projects/${pid}/`, { method: 'PUT',  body: data }),
  del:    (uid, pid)         => apiFetch(`/api/users/${uid}/projects/${pid}/`, { method: 'DELETE' }),
};

const ExpsAPI = {
  list:   (uid, pid)           => apiFetch(`/api/users/${uid}/projects/${pid}/experiences/`),
  create: (uid, pid, data)     => apiFetch(`/api/users/${uid}/projects/${pid}/experiences/`, { method: 'POST', body: data }),
  get:    (uid, pid, eid)      => apiFetch(`/api/users/${uid}/projects/${pid}/experiences/${eid}/`),
  update: (uid, pid, eid, d)   => apiFetch(`/api/users/${uid}/projects/${pid}/experiences/${eid}/`, { method: 'PUT', body: d }),
  del:    (uid, pid, eid)      => apiFetch(`/api/users/${uid}/projects/${pid}/experiences/${eid}/`, { method: 'DELETE' }),
};

const VRsAPI = {
  list:   (uid, pid, eid)      => apiFetch(`/api/users/${uid}/projects/${pid}/experiences/${eid}/verification-requests/`),
  create: (uid, pid, eid, d)   => apiFetch(`/api/users/${uid}/projects/${pid}/experiences/${eid}/verification-requests/`, { method: 'POST', body: d }),
};

const SharesAPI = {
  list:   (uid, pid)      => apiFetch(`/api/users/${uid}/projects/${pid}/shares/`),
  create: (uid, pid, d)   => apiFetch(`/api/users/${uid}/projects/${pid}/shares/`, { method: 'POST', body: d }),
  getPublic: (token)      => apiFetch(`/api/shares/${token}/`),
  del:    (uid, pid, sid) => apiFetch(`/api/users/${uid}/projects/${pid}/shares/${sid}/`, { method: 'DELETE' }),
};

// ── UI Helpers ────────────────────────────────────────────────
/**
 * Show a toast notification.
 * @param {string} message - text to display
 * @param {'info'|'success'|'error'} type
 * @param {number} duration - ms before auto-dismiss
 */
function toast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  const el        = document.createElement('div');
  el.className    = `toast toast-${type}`;
  el.innerHTML    = `<span>${esc(message)}</span>
                     <button class="toast-close" aria-label="Close">×</button>`;
  el.querySelector('.toast-close').onclick = () => el.remove();
  container.appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 350); }, duration);
}

/**
 * Toggle the full-page loading cursor overlay.
 * @param {boolean} on
 */
function setLoading(on) {
  document.body.classList.toggle('loading', on);
}

/**
 * Show one view, hide all others.
 * @param {string} id - element id of the view to show
 */
function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
  const el = document.getElementById(id);
  if (el) el.classList.remove('hidden');
}

// Modal state -------------------------------------------------
let _closeModal = null;

/**
 * Render HTML into the modal overlay and show it.
 * Buttons with [data-dismiss] and overlay clicks will close it.
 * @param {string} html - modal card HTML
 * @returns {Function} close function
 */
function openModal(html) {
  const overlay = document.getElementById('modal-overlay');
  const content = document.getElementById('modal-content');
  content.innerHTML = html;
  overlay.classList.remove('hidden');

  _closeModal = () => {
    overlay.classList.add('hidden');
    content.innerHTML = '';
    _closeModal = null;
  };

  overlay.onclick = (e) => { if (e.target === overlay) _closeModal?.(); };
  content.querySelectorAll('[data-dismiss]').forEach(b => { b.onclick = () => _closeModal?.(); });
  return () => _closeModal?.();
}

function closeModal() { _closeModal?.(); }

/**
 * Show a confirmation dialog and return a promise that resolves
 * to true (confirmed) or false (cancelled).
 * @param {string} message
 * @returns {Promise<boolean>}
 */
function confirmDialog(message) {
  return new Promise((resolve) => {
    const close = openModal(`
      <div class="modal-card">
        <h3>Confirm</h3>
        <p style="font-size:.875rem;color:#374151">${esc(message)}</p>
        <div class="modal-actions">
          <button data-dismiss class="btn-outline">Cancel</button>
          <button id="confirm-ok" class="btn-danger">Confirm</button>
        </div>
      </div>`);
    document.getElementById('confirm-ok').onclick = () => { close(); resolve(true); };
    document.getElementById('modal-overlay').onclick = (e) => {
      if (e.target === document.getElementById('modal-overlay')) { close(); resolve(false); }
    };
  });
}

/**
 * Copy text to the system clipboard and show a toast.
 * @param {string} text
 */
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast('Copied to clipboard!', 'success', 2000);
  } catch {
    toast('Copy failed — please copy manually.', 'error');
  }
}

// ── Formatting helpers ────────────────────────────────────────
/**
 * Escape a string for safe HTML insertion.
 * @param {string} str
 * @returns {string}
 */
function esc(str) {
  const d = document.createElement('div');
  d.textContent = String(str ?? '');
  return d.innerHTML;
}

/**
 * Format an ISO date string as "Jan 2023".
 * @param {string|null} s
 * @returns {string}
 */
function fmtDate(s) {
  if (!s) return 'Present';
  return new Date(s).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}

/**
 * Format an ISO datetime string as "Apr 27, 2026".
 * @param {string|null} s
 * @returns {string}
 */
function fmtDateTime(s) {
  if (!s) return '—';
  return new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/**
 * Build a coloured status badge span.
 * @param {string} status - one of not_requested|pending|verified|rejected|expired
 * @returns {string} HTML string
 */
function statusBadge(status) {
  const map = {
    not_requested: ['status-neutral',  'Not Requested'],
    pending:       ['status-pending',  '⏳ Pending'],
    verified:      ['status-verified', '✓ Verified'],
    rejected:      ['status-rejected', '✗ Rejected'],
    expired:       ['status-expired',  'Expired'],
  };
  const [cls, label] = map[status] || ['status-neutral', status];
  return `<span class="status-badge ${cls}">${label}</span>`;
}

// ── Polling helpers ───────────────────────────────────────────
/** Start auto-refreshing the experiences list every 30 s. */
function startPoll() {
  stopPoll();
  state.pollTimer = setInterval(() => {
    const expTab = document.getElementById('tab-experiences');
    if (expTab && !expTab.classList.contains('hidden')) loadExperiences(true);
  }, 30000);
}

/** Cancel any running auto-refresh. */
function stopPoll() {
  if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
}

// ── AUTH VIEW ─────────────────────────────────────────────────
/** Render the authentication view and attach form handlers. */
function renderAuth() {
  showView('view-auth');

  // Tab switching
  document.querySelectorAll('.auth-tabs .tab-btn').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('.auth-tabs .tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      document.getElementById('form-login').classList.toggle('hidden',    tab !== 'login');
      document.getElementById('form-register').classList.toggle('hidden', tab !== 'register');
    };
  });

  // Login submit
  document.getElementById('form-login').onsubmit = async (e) => {
    e.preventDefault();
    const email = e.target.email.value.trim();
    const pw    = e.target.password.value;
    try {
      setLoading(true);
      const data = await AuthAPI.login(email, pw);
      saveAuth(data.token, data.user_id);
      state.user = await UsersAPI.get(data.user_id);
      renderDashboard();
    } catch (err) {
      toast(err.status === 401 ? 'Invalid email or password.' : (err.message || 'Login failed.'), 'error');
    } finally {
      setLoading(false);
    }
  };

  // Register submit
  document.getElementById('form-register').onsubmit = async (e) => {
    e.preventDefault();
    const payload = {
      email:    e.target.email.value.trim(),
      username: e.target.username.value.trim(),
      password: e.target.password.value,
    };
    const phone = e.target.phone.value.trim();
    if (phone) payload.phone_number = phone;
    try {
      setLoading(true);
      await AuthAPI.register(payload);
      toast('Account created! Please sign in.', 'success');
      document.querySelector('.auth-tabs [data-tab="login"]').click();
      e.target.reset();
    } catch (err) {
      if (err.status === 409) toast('Email or username is already taken.', 'error');
      else toast(err.message || 'Registration failed.', 'error');
    } finally {
      setLoading(false);
    }
  };
}

// ── DASHBOARD VIEW ────────────────────────────────────────────
/** Render the dashboard and load the project list. */
async function renderDashboard() {
  stopPoll();
  state.currentProjectId = null;
  state.currentProject   = null;

  showView('view-dashboard');

  if (!state.user) {
    state.user = await UsersAPI.get(state.userId).catch(() => null);
  }

  document.getElementById('header-username').textContent = state.user?.username || '';

  document.getElementById('btn-logout').onclick = async () => {
    try { await AuthAPI.logout(); } catch { /* ignore */ }
    clearAuth();
    renderAuth();
    toast('Signed out.', 'info', 2000);
  };

  document.getElementById('btn-new-project').onclick = openNewProjectModal;

  await loadProjects();
}

/**
 * Fetch and render the user's project grid.
 * Shows empty-state when no projects exist.
 */
async function loadProjects() {
  const grid = document.getElementById('projects-grid');
  grid.innerHTML = '<div class="loading-text">Loading resumes</div>';
  try {
    const projects = await ProjectsAPI.list(state.userId);
    if (!projects.length) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1">
          <div class="empty-icon">📄</div>
          <h3>No resumes yet</h3>
          <p>Create your first resume project to get started.</p>
          <button class="btn-primary" onclick="openNewProjectModal()">+ Create Resume</button>
        </div>`;
      return;
    }
    grid.innerHTML = projects.map(projectCardHTML).join('');
    grid.querySelectorAll('[data-action="open"]').forEach(btn => {
      btn.onclick = () => renderProject(parseInt(btn.dataset.id, 10));
    });
    grid.querySelectorAll('[data-action="del"]').forEach(btn => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        if (await confirmDialog(`Delete "${btn.dataset.name}"? This removes all experiences and shares.`)) {
          try {
            await ProjectsAPI.del(state.userId, parseInt(btn.dataset.id, 10));
            toast('Resume deleted.', 'success');
            loadProjects();
          } catch (err) { toast(err.message, 'error'); }
        }
      };
    });
  } catch (err) {
    grid.innerHTML = `<div class="error-state" style="grid-column:1/-1">
      <div class="error-icon">⚠️</div><h2>Load Failed</h2><p>${esc(err.message)}</p></div>`;
  }
}

/**
 * Build the HTML for one project card.
 * @param {object} p - project object from API
 * @returns {string}
 */
function projectCardHTML(p) {
  const tmpl = { classic: '📋 Classic', modern: '✨ Modern', minimal: '◼ Minimal' }[p.template_style] || p.template_style;
  return `
    <div class="project-card">
      <div class="project-card-header">
        <h3 class="project-card-name">${esc(p.project_name)}</h3>
        <span class="badge">${tmpl}</span>
      </div>
      <div class="project-card-meta">
        ${p.current_company ? `<span>🏢 ${esc(p.current_company)}</span>` : ''}
        <span class="${p.is_employed ? 'text-green' : 'text-muted'}">
          ${p.is_employed ? '● Employed' : '● Seeking'}
        </span>
      </div>
      <div class="project-card-footer">
        <span class="text-muted" style="font-size:.775rem">${fmtDateTime(p.updated_at)}</span>
        <div class="card-actions">
          <button class="btn-sm btn-primary" data-action="open" data-id="${p.project_id}">Open →</button>
          <button class="btn-sm btn-sm-danger" data-action="del"
            data-id="${p.project_id}" data-name="${esc(p.project_name)}" title="Delete">🗑</button>
        </div>
      </div>
    </div>`;
}

/** Open the "new project" modal and handle submission. */
function openNewProjectModal() {
  const close = openModal(`
    <div class="modal-card">
      <h3>New Resume Project</h3>
      <form id="form-new-project" style="display:flex;flex-direction:column;gap:.85rem">
        <div class="form-group">
          <label>Resume Name *</label>
          <input name="project_name" type="text" required maxlength="200"
                 placeholder="e.g. Software Engineer Resume 2026" />
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Template Style</label>
            <select name="template_style">
              <option value="classic">Classic</option>
              <option value="modern">Modern</option>
              <option value="minimal">Minimal</option>
            </select>
          </div>
          <div class="form-group">
            <label>Employment Status</label>
            <select name="is_employed">
              <option value="false">Unemployed / Seeking</option>
              <option value="true">Currently Employed</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label>Current Company</label>
          <input name="current_company" type="text" maxlength="200" placeholder="e.g. TechCorp" />
        </div>
        <div class="modal-actions">
          <button type="button" data-dismiss class="btn-outline">Cancel</button>
          <button type="submit" class="btn-primary">Create Resume</button>
        </div>
      </form>
    </div>`);

  document.getElementById('form-new-project').onsubmit = async (e) => {
    e.preventDefault();
    const data = {
      project_name:   e.target.project_name.value.trim(),
      template_style: e.target.template_style.value,
      is_employed:    e.target.is_employed.value === 'true',
    };
    const co = e.target.current_company.value.trim();
    if (co) data.current_company = co;
    try {
      setLoading(true);
      const p = await ProjectsAPI.create(state.userId, data);
      close();
      toast('Resume created!', 'success');
      renderProject(p.project_id);
    } catch (err) {
      toast(err.message || 'Failed to create resume.', 'error');
    } finally { setLoading(false); }
  };
}

// ── PROJECT VIEW ──────────────────────────────────────────────
/**
 * Load a project and render the project detail view.
 * @param {number} projectId
 */
async function renderProject(projectId) {
  state.currentProjectId = projectId;
  showView('view-project');

  // Header buttons
  document.getElementById('btn-back-dashboard').onclick = () => renderDashboard();
  document.getElementById('btn-logout-project').onclick = async () => {
    try { await AuthAPI.logout(); } catch { /* ignore */ }
    clearAuth();
    renderAuth();
  };

  // Tab switching
  document.querySelectorAll('.project-tabs .tab-btn').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('.project-tabs .tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('#view-project .tab-content').forEach(c => c.classList.add('hidden'));
      document.getElementById(`tab-${btn.dataset.tab}`).classList.remove('hidden');
      if (btn.dataset.tab === 'experiences') { loadExperiences(); startPoll(); }
      else                                   { stopPoll(); }
      if (btn.dataset.tab === 'shares') loadShares();
    };
  });

  // Add / Create buttons in sub-tabs
  document.getElementById('btn-add-experience').onclick = openAddExpModal;
  document.getElementById('btn-create-share').onclick   = openCreateShareModal;

  await loadProjectData(projectId);
}

/**
 * Fetch project data from API and populate the overview form and header.
 * @param {number} projectId
 */
async function loadProjectData(projectId) {
  try {
    setLoading(true);
    const p = await ProjectsAPI.get(state.userId, projectId);
    state.currentProject = p;
    document.getElementById('project-title-display').textContent    = p.project_name;
    document.getElementById('project-breadcrumb-name').textContent  = p.project_name;
    document.title = `${p.project_name} — RefOnRecord`;

    // Render badges
    const badges = document.getElementById('project-badges');
    badges.innerHTML = `
      <span class="badge">${esc(p.template_style)}</span>
      <span class="badge ${p.is_employed ? 'badge-green' : ''}">${p.is_employed ? '● Employed' : '● Seeking'}</span>`;

    fillProjectForm(p);
  } catch (err) {
    toast(`Failed to load project: ${err.message}`, 'error');
    renderDashboard();
  } finally { setLoading(false); }
}

/**
 * Fill the overview edit form with the project's current values
 * and attach the submit handler.
 * @param {object} p - project object from API
 */
function fillProjectForm(p) {
  const form = document.getElementById('form-edit-project');
  form.project_name.value      = p.project_name    || '';
  form.template_style.value    = p.template_style  || 'classic';
  form.is_employed.value       = p.is_employed ? 'true' : 'false';
  form.current_company.value   = p.current_company  || '';
  form.phone_number.value      = p.phone_number     || '';
  form.linkedin_url.value      = p.linkedin_url     || '';
  form.github_url.value        = p.github_url       || '';
  form.personal_website.value  = p.personal_website || '';
  form.education_details.value = p.education_details || '';

  form.onsubmit = async (e) => {
    e.preventDefault();
    const data = {
      project_name:      form.project_name.value.trim(),
      template_style:    form.template_style.value,
      is_employed:       form.is_employed.value === 'true',
      education_details: form.education_details.value.trim(),
    };
    ['current_company','phone_number','linkedin_url','github_url','personal_website'].forEach(k => {
      const v = form[k].value.trim();
      // Send null for blank optional fields so the API clears previously-set values
      data[k] = v || null;
    });
    try {
      setLoading(true);
      const updated = await ProjectsAPI.update(state.userId, state.currentProjectId, data);
      state.currentProject = updated;
      document.getElementById('project-title-display').textContent   = updated.project_name;
      document.getElementById('project-breadcrumb-name').textContent = updated.project_name;
      document.title = `${updated.project_name} — RefOnRecord`;
      const badges = document.getElementById('project-badges');
      badges.innerHTML = `
        <span class="badge">${esc(updated.template_style)}</span>
        <span class="badge ${updated.is_employed ? 'badge-green' : ''}">${updated.is_employed ? '● Employed' : '● Seeking'}</span>`;
      toast('Resume saved!', 'success');
    } catch (err) {
      toast(err.message || 'Failed to save.', 'error');
    } finally { setLoading(false); }
  };
}

// ── EXPERIENCES ───────────────────────────────────────────────
/**
 * Fetch and render the experiences list for the current project.
 * @param {boolean} silent - if true, suppress the loading spinner (used by auto-poll)
 */
async function loadExperiences(silent = false) {
  const list = document.getElementById('experiences-list');
  if (!silent) list.innerHTML = '<div class="loading-text">Loading experiences</div>';
  try {
    const exps = await ExpsAPI.list(state.userId, state.currentProjectId);
    if (!exps.length) {
      list.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">💼</div>
          <h3>No experiences yet</h3>
          <p>Add your first work experience to start building your verified resume.</p>
        </div>`;
      return;
    }
    list.innerHTML = exps.map(expCardHTML).join('');

    list.querySelectorAll('[data-action="view-vrs"]').forEach(btn => {
      btn.onclick = () => openVerificationsModal(parseInt(btn.dataset.id, 10));
    });
    list.querySelectorAll('[data-action="edit-exp"]').forEach(btn => {
      btn.onclick = () => openEditExpModal(parseInt(btn.dataset.id, 10));
    });
    list.querySelectorAll('[data-action="del-exp"]').forEach(btn => {
      btn.onclick = async () => {
        if (await confirmDialog(`Delete the experience at "${btn.dataset.name}"?`)) {
          try {
            await ExpsAPI.del(state.userId, state.currentProjectId, parseInt(btn.dataset.id, 10));
            toast('Experience deleted.', 'success');
            loadExperiences();
          } catch (err) { toast(err.message, 'error'); }
        }
      };
    });
  } catch (err) {
    list.innerHTML = `<div class="error-state"><div class="error-icon">⚠️</div>
      <h2>Load Failed</h2><p>${esc(err.message)}</p></div>`;
  }
}

/**
 * Build the HTML for one experience card.
 * @param {object} exp - experience object from API
 * @returns {string}
 */
function expCardHTML(exp) {
  const desc = exp.description.length > 200
    ? `${esc(exp.description.substring(0, 200))}…`
    : esc(exp.description);
  return `
    <div class="experience-card">
      <div class="exp-header">
        <div>
          <div class="exp-title">${esc(exp.position_title)}</div>
          <div class="exp-company">${esc(exp.company_name)}</div>
          <div class="exp-dates">${fmtDate(exp.start_date)} — ${fmtDate(exp.end_date)}</div>
        </div>
        <div>${statusBadge(exp.verification_status)}</div>
      </div>
      <p class="exp-desc">${desc}</p>
      <div class="exp-actions">
        <button class="btn-sm btn-outline" data-action="view-vrs" data-id="${exp.experience_id}">
          🔒 Verifications
        </button>
        <button class="btn-sm btn-outline" data-action="edit-exp" data-id="${exp.experience_id}">
          ✏ Edit
        </button>
        <button class="btn-sm btn-sm-danger" data-action="del-exp"
          data-id="${exp.experience_id}" data-name="${esc(exp.company_name)}">
          Delete
        </button>
      </div>
    </div>`;
}

/** Open the "add experience" modal and handle form submission. */
function openAddExpModal() {
  const close = openModal(`
    <div class="modal-card modal-large">
      <h3>Add Work Experience</h3>
      <form id="form-add-exp" style="display:flex;flex-direction:column;gap:.85rem">
        <div class="form-row">
          <div class="form-group">
            <label>Company Name *</label>
            <input name="company_name" type="text" required maxlength="200" placeholder="e.g. TechCorp" />
          </div>
          <div class="form-group">
            <label>Position Title *</label>
            <input name="position_title" type="text" required maxlength="200" placeholder="e.g. Senior Engineer" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Start Date *</label>
            <input name="start_date" type="date" required />
          </div>
          <div class="form-group">
            <label>End Date <span class="hint">(blank = current)</span></label>
            <input name="end_date" type="date" />
          </div>
        </div>
        <div class="form-group">
          <label>Description *</label>
          <textarea name="description" required rows="4"
            placeholder="Describe your responsibilities and key achievements…"></textarea>
        </div>
        <div class="modal-actions">
          <button type="button" data-dismiss class="btn-outline">Cancel</button>
          <button type="submit" class="btn-primary">Add Experience</button>
        </div>
      </form>
    </div>`);

  document.getElementById('form-add-exp').onsubmit = async (e) => {
    e.preventDefault();
    const data = {
      company_name:   e.target.company_name.value.trim(),
      position_title: e.target.position_title.value.trim(),
      start_date:     e.target.start_date.value,
      description:    e.target.description.value.trim(),
    };
    const end = e.target.end_date.value;
    if (end) data.end_date = end;
    try {
      setLoading(true);
      await ExpsAPI.create(state.userId, state.currentProjectId, data);
      close();
      toast('Experience added!', 'success');
      loadExperiences();
    } catch (err) {
      toast(err.message || 'Failed to add experience.', 'error');
    } finally { setLoading(false); }
  };
}

/**
 * Fetch an experience by id, open a pre-filled edit modal.
 * @param {number} expId
 */
async function openEditExpModal(expId) {
  let exp;
  try {
    setLoading(true);
    exp = await ExpsAPI.get(state.userId, state.currentProjectId, expId);
  } catch (err) { toast(err.message, 'error'); return; }
  finally { setLoading(false); }

  const close = openModal(`
    <div class="modal-card modal-large">
      <h3>Edit Experience</h3>
      <form id="form-edit-exp" style="display:flex;flex-direction:column;gap:.85rem">
        <div class="form-row">
          <div class="form-group">
            <label>Company Name *</label>
            <input name="company_name" type="text" required maxlength="200"
                   value="${esc(exp.company_name)}" />
          </div>
          <div class="form-group">
            <label>Position Title *</label>
            <input name="position_title" type="text" required maxlength="200"
                   value="${esc(exp.position_title)}" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Start Date *</label>
            <input name="start_date" type="date" required value="${exp.start_date}" />
          </div>
          <div class="form-group">
            <label>End Date <span class="hint">(blank = current)</span></label>
            <input name="end_date" type="date" value="${exp.end_date || ''}" />
          </div>
        </div>
        <div class="form-group">
          <label>Description *</label>
          <textarea name="description" required rows="4">${esc(exp.description)}</textarea>
        </div>
        <div class="modal-actions">
          <button type="button" data-dismiss class="btn-outline">Cancel</button>
          <button type="submit" class="btn-primary">Save Changes</button>
        </div>
      </form>
    </div>`);

  document.getElementById('form-edit-exp').onsubmit = async (e) => {
    e.preventDefault();
    const data = {
      company_name:   e.target.company_name.value.trim(),
      position_title: e.target.position_title.value.trim(),
      start_date:     e.target.start_date.value,
      description:    e.target.description.value.trim(),
    };
    const end = e.target.end_date.value;
    if (end) data.end_date = end;
    try {
      setLoading(true);
      await ExpsAPI.update(state.userId, state.currentProjectId, expId, data);
      close();
      toast('Experience updated!', 'success');
      loadExperiences();
    } catch (err) {
      toast(err.message || 'Failed to update.', 'error');
    } finally { setLoading(false); }
  };
}

/**
 * Load verification requests for an experience and show them in a modal
 * that also contains a "Request Verification" form.
 * @param {number} expId
 */
async function openVerificationsModal(expId) {
  let exp, vrs;
  try {
    setLoading(true);
    [exp, vrs] = await Promise.all([
      ExpsAPI.get(state.userId, state.currentProjectId, expId),
      VRsAPI.list(state.userId, state.currentProjectId, expId),
    ]);
  } catch (err) { toast(err.message, 'error'); return; }
  finally { setLoading(false); }

  const vrItems = vrs.length
    ? vrs.map(vr => `
        <div class="ver-item">
          <div class="ver-header">
            <strong>${esc(vr.verifier_name)}</strong>
            ${statusBadge(vr.status)}
          </div>
          <div class="ver-details">
            <span>${esc(vr.verifier_position)}</span>
            <span>${esc(vr.verifier_email)}</span>
            <span>Sent: ${fmtDateTime(vr.requested_at)}</span>
            ${vr.responded_at ? `<span>Responded: ${fmtDateTime(vr.responded_at)}</span>` : ''}
            ${vr.status === 'pending' ? `<span>Expires: ${fmtDateTime(vr.expires_at)}</span>` : ''}
          </div>
          ${vr.verifier_comment ? `<div class="ver-comment">"${esc(vr.verifier_comment)}"</div>` : ''}
        </div>`).join('')
    : '<p class="text-muted" style="font-size:.875rem">No verification requests yet.</p>';

  const close = openModal(`
    <div class="modal-card modal-large">
      <h3>Verification Requests</h3>
      <p class="ver-modal-sub">
        <strong>${esc(exp.position_title)}</strong> at ${esc(exp.company_name)}
        &nbsp;${statusBadge(exp.verification_status)}
      </p>
      <div class="ver-list">${vrItems}</div>
      <hr class="modal-divider" />
      <h4>Request New Verification</h4>
      <form id="form-req-ver" style="display:flex;flex-direction:column;gap:.85rem;margin-top:.75rem">
        <div class="form-row">
          <div class="form-group">
            <label>Verifier Name *</label>
            <input name="verifier_name" type="text" required maxlength="200"
                   placeholder="e.g. Jane Smith" />
          </div>
          <div class="form-group">
            <label>Verifier Position *</label>
            <input name="verifier_position" type="text" required maxlength="200"
                   placeholder="e.g. Engineering Manager" />
          </div>
        </div>
        <div class="form-group">
          <label>Verifier Email *</label>
          <input name="verifier_email" type="email" required
                 placeholder="jane@company.com" />
        </div>
        <div class="modal-actions">
          <button type="button" data-dismiss class="btn-outline">Close</button>
          <button type="submit" class="btn-primary">Send Request</button>
        </div>
      </form>
    </div>`);

  document.getElementById('form-req-ver').onsubmit = async (e) => {
    e.preventDefault();
    const data = {
      verifier_name:     e.target.verifier_name.value.trim(),
      verifier_position: e.target.verifier_position.value.trim(),
      verifier_email:    e.target.verifier_email.value.trim(),
    };
    try {
      setLoading(true);
      await VRsAPI.create(state.userId, state.currentProjectId, expId, data);
      close();
      toast('Verification request sent!', 'success');
      loadExperiences();
    } catch (err) {
      toast(err.message || 'Failed to send request.', 'error');
    } finally { setLoading(false); }
  };
}

// ── SHARE LINKS ───────────────────────────────────────────────
/** Fetch and render the share links list for the current project. */
async function loadShares() {
  const list = document.getElementById('shares-list');
  list.innerHTML = '<div class="loading-text">Loading share links</div>';
  try {
    const shares = await SharesAPI.list(state.userId, state.currentProjectId);
    if (!shares.length) {
      list.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🔗</div>
          <h3>No share links yet</h3>
          <p>Create a share link to let recruiters view your verified resume.</p>
        </div>`;
      return;
    }
    list.innerHTML = shares.map(shareCardHTML).join('');

    list.querySelectorAll('[data-action="copy"]').forEach(btn => {
      btn.onclick = () => copyToClipboard(buildShareUrl(btn.dataset.token));
    });
    list.querySelectorAll('[data-action="view"]').forEach(btn => {
      btn.onclick = () => { window.location.hash = `#share/${btn.dataset.token}`; };
    });
    list.querySelectorAll('[data-action="del-share"]').forEach(btn => {
      btn.onclick = async () => {
        if (await confirmDialog('Delete this share link? Anyone using it will lose access.')) {
          try {
            await SharesAPI.del(state.userId, state.currentProjectId, parseInt(btn.dataset.id, 10));
            toast('Share link deleted.', 'success');
            loadShares();
          } catch (err) { toast(err.message, 'error'); }
        }
      };
    });
  } catch (err) {
    list.innerHTML = `<div class="error-state"><div class="error-icon">⚠️</div>
      <h2>Load Failed</h2><p>${esc(err.message)}</p></div>`;
  }
}

/**
 * Build the full shareable URL for a given token.
 * @param {string} token
 * @returns {string}
 */
function buildShareUrl(token) {
  return `${window.location.origin}${window.location.pathname}#share/${token}`;
}

/**
 * Build the HTML for one share link card.
 * @param {object} share - share object from API
 * @returns {string}
 */
function shareCardHTML(share) {
  const url     = buildShareUrl(share.share_token);
  const expired = share.expires_at && new Date(share.expires_at) < new Date();
  return `
    <div class="share-card ${expired ? 'share-expired' : ''}">
      <div class="share-header">
        <div class="share-header-left">
          ${share.recipient_email
            ? `<strong>${esc(share.recipient_email)}</strong>`
            : '<span class="text-muted">Public link</span>'}
          <span class="badge">${share.access_type}</span>
          ${expired ? '<span class="badge badge-red">Expired</span>' : ''}
        </div>
        <span class="text-muted" style="font-size:.775rem">👁 ${share.view_count} views</span>
      </div>
      <div class="share-url-row">
        <input class="share-url-input" value="${esc(url)}" readonly />
        <button class="btn-sm btn-outline" data-action="copy" data-token="${share.share_token}">Copy</button>
        <button class="btn-sm btn-outline" data-action="view" data-token="${share.share_token}">View</button>
      </div>
      <div class="share-footer">
        <div class="share-footer-left">
          <span>Created: ${fmtDateTime(share.created_at)}</span>
          ${share.expires_at ? `<span>Expires: ${fmtDateTime(share.expires_at)}</span>` : ''}
        </div>
        <button class="btn-sm btn-sm-danger" data-action="del-share" data-id="${share.share_id}">Delete</button>
      </div>
    </div>`;
}

/** Open the "create share link" modal and handle submission. */
function openCreateShareModal() {
  const close = openModal(`
    <div class="modal-card">
      <h3>Create Share Link</h3>
      <form id="form-create-share" style="display:flex;flex-direction:column;gap:.85rem">
        <div class="form-group">
          <label>Recipient Email <span class="hint">(optional)</span></label>
          <input name="recipient_email" type="email" placeholder="recruiter@company.com" />
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Access Type</label>
            <select name="access_type">
              <option value="view">View Only</option>
              <option value="edit">Edit (Premium)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Expiration Date <span class="hint">(optional)</span></label>
            <input name="expires_at" type="datetime-local" />
          </div>
        </div>
        <div class="form-group">
          <label>Email Subject <span class="hint">(optional)</span></label>
          <input name="email_subject" type="text" maxlength="500"
                 placeholder="Check out my resume" />
        </div>
        <div class="form-group">
          <label>Email Message <span class="hint">(optional)</span></label>
          <textarea name="email_message" rows="3"
            placeholder="Hi, please take a look at my verified resume…"></textarea>
        </div>
        <div class="modal-actions">
          <button type="button" data-dismiss class="btn-outline">Cancel</button>
          <button type="submit" class="btn-primary">Create Link</button>
        </div>
      </form>
    </div>`);

  document.getElementById('form-create-share').onsubmit = async (e) => {
    e.preventDefault();
    const data = { access_type: e.target.access_type.value };
    const email   = e.target.recipient_email.value.trim();
    const subject = e.target.email_subject.value.trim();
    const message = e.target.email_message.value.trim();
    const expires = e.target.expires_at.value;
    if (email)   data.recipient_email = email;
    if (subject) data.email_subject   = subject;
    if (message) data.email_message   = message;
    if (expires) data.expires_at      = new Date(expires).toISOString();
    try {
      setLoading(true);
      const share = await SharesAPI.create(state.userId, state.currentProjectId, data);
      close();
      toast('Share link created!', 'success');
      // Offer to copy immediately
      await copyToClipboard(buildShareUrl(share.share_token));
      loadShares();
    } catch (err) {
      toast(err.message || 'Failed to create share link.', 'error');
    } finally { setLoading(false); }
  };
}

// ── PUBLIC RESUME VIEW ────────────────────────────────────────
/**
 * Render the public (unauthenticated) resume view for a given share token.
 * @param {string} token - share token from URL hash
 */
async function renderPublicView(token) {
  stopPoll();
  showView('view-public');
  document.title = 'Resume — RefOnRecord';

  const container = document.getElementById('public-resume-content');
  container.innerHTML = '<div class="loading-text">Loading resume</div>';

  try {
    const { project, experiences } = await SharesAPI.getPublic(token);
    const verifiedCount = experiences.filter(e => e.verification_status === 'verified').length;
    document.title = `${project.project_name} — RefOnRecord`;

    container.innerHTML = `
      <div class="public-resume">

        <div class="pub-header">
          <div class="pub-identity">
            <h1 class="pub-title">${esc(project.project_name)}</h1>
            <div class="pub-links">
              ${project.phone_number    ? `<span>📞 ${esc(project.phone_number)}</span>` : ''}
              ${project.linkedin_url    ? `<a href="${esc(project.linkedin_url)}" target="_blank" rel="noopener">LinkedIn</a>` : ''}
              ${project.github_url      ? `<a href="${esc(project.github_url)}"  target="_blank" rel="noopener">GitHub</a>`   : ''}
              ${project.personal_website? `<a href="${esc(project.personal_website)}" target="_blank" rel="noopener">Website</a>` : ''}
            </div>
            ${project.current_company ? `<div style="margin-top:.4rem;font-size:.85rem;opacity:.8">🏢 ${esc(project.current_company)}</div>` : ''}
          </div>
          <div class="pub-stats">
            <div class="stat-box">
              <div class="stat-num">${experiences.length}</div>
              <div class="stat-label">Experiences</div>
            </div>
            <div class="stat-box verified-stat">
              <div class="stat-num">${verifiedCount}</div>
              <div class="stat-label">Verified</div>
            </div>
          </div>
        </div>

        ${project.education_details ? `
          <div class="pub-section">
            <h2 class="pub-section-title">Education</h2>
            <p style="font-size:.875rem;color:#374151">${esc(project.education_details)}</p>
          </div>` : ''}

        <div class="pub-section">
          <h2 class="pub-section-title">Work Experience</h2>
          ${!experiences.length
            ? '<p class="text-muted" style="font-size:.875rem">No experiences listed.</p>'
            : experiences.map(exp => `
                <div class="pub-exp">
                  <div class="pub-exp-header">
                    <div>
                      <h3>${esc(exp.position_title)}</h3>
                      <div class="pub-exp-company">${esc(exp.company_name)}</div>
                      <div class="pub-exp-dates">${fmtDate(exp.start_date)} — ${fmtDate(exp.end_date)}</div>
                    </div>
                    ${exp.verification_status === 'verified'
                      ? '<div class="verified-badge">✓ Verified</div>'
                      : ''}
                  </div>
                  <p class="pub-exp-desc">${esc(exp.description)}</p>
                </div>`).join('')}
        </div>

        <div class="pub-footer">
          <span>Powered by <strong>RefOnRecord</strong> · Verified Professional Resumes</span>
          <button class="btn-ghost no-print" onclick="window.print()" style="font-size:.775rem">🖨 Print</button>
        </div>
      </div>`;

  } catch {
    container.innerHTML = `
      <div class="error-state">
        <div class="error-icon">🔗</div>
        <h2>Resume Not Found</h2>
        <p>This share link may have expired or been deleted.</p>
        <button class="btn-primary" onclick="navigateToHome()">Go to App</button>
      </div>`;
  }
}

// ── ROUTING ───────────────────────────────────────────────────
/** Navigate back to the home route and re-run the router. */
function navigateToHome() {
  window.location.hash = '';
  route();
}

/**
 * Hash-based router. Called on DOMContentLoaded and hashchange.
 * Routes:
 *   #share/<token>  → public resume view
 *   (anything else) → auth if logged out, dashboard if logged in
 */
function route() {
  const hash = window.location.hash;
  if (hash.startsWith('#share/')) {
    const token = hash.slice(7);
    if (token) { renderPublicView(token); return; }
  }
  if (state.token) {
    renderDashboard();
  } else {
    renderAuth();
  }
}

// ── INIT ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadAuth();
  route();
  window.addEventListener('hashchange', route);

  // Expose functions used by inline onclick attributes in HTML/templates
  window.openNewProjectModal  = openNewProjectModal;
  window.openAddExpModal      = openAddExpModal;
  window.openCreateShareModal = openCreateShareModal;
  window.navigateToHome       = navigateToHome;
});
