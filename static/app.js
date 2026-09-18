// Executive Productivity Agent - Reactive Frontend Engine

let currentDashboardData = null;
let currentActionsList = [];
let currentFilter = 'all';

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}

async function initApp() {
  await fetchDashboard();
  setupEventListeners();
}

function setupEventListeners() {
  // Poll or refresh listener if needed
}

// ---------------- Navigation ----------------
function switchView(viewName) {
  const views = ['dashboard', 'inputs', 'actions', 'evidence', 'qa'];
  views.forEach(v => {
    const el = document.getElementById(`view-${v}`);
    const navBtn = document.getElementById(`nav-${v}`);
    if (el) {
      if (v === viewName) {
        el.classList.remove('hidden');
      } else {
        el.classList.add('hidden');
      }
    }
    if (navBtn) {
      if (v === viewName) {
        navBtn.className = "nav-btn w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-sm font-medium text-white bg-indigo-600/20 border border-indigo-500/30 transition";
        const icon = navBtn.querySelector('i');
        if (icon) icon.className = icon.className.replace('text-slate-400', 'text-indigo-400');
      } else {
        navBtn.className = "nav-btn w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition";
      }
    }
  });

  if (viewName === 'evidence') {
    renderEvidenceAudit();
  }
}

// ---------------- Data Fetching & Dashboard ----------------
async function fetchDashboard() {
  try {
    const res = await fetch('/api/dashboard');
    const data = await res.json();
    currentDashboardData = data;
    currentActionsList = [
      ...(data.commitments || []),
      ...(data.follow_ups || []),
      ...(data.unclear_items || [])
    ];
    renderDashboard(data);
    renderInputsView(data.sources || []);
    renderActionCards(currentActionsList);
    populateModalDropdown(data.sources || []);
  } catch (err) {
    console.error("Failed to load dashboard data:", err);
  }
}

async function refreshData() {
  try {
    const res = await fetch('/api/process', { method: 'POST' });
    await fetchDashboard();
  } catch (err) {
    console.error("Refresh failed:", err);
  }
}

function renderDashboard(data) {
  // 1. Data Pack Status Badge
  const statusBadge = document.getElementById('data-status-badge');
  const statusText = document.getElementById('data-status-text');
  const dp = data.data_pack_status;

  if (dp.is_empty) {
    statusBadge.className = "flex items-center space-x-2 px-3 py-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-xs text-amber-300";
    statusText.innerText = "Source data not loaded";
  } else if (dp.all_loaded) {
    statusBadge.className = "flex items-center space-x-2 px-3 py-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-xs text-emerald-300";
    statusText.innerText = `Data Pack Active (${dp.loaded_count}/${dp.total_count} Loaded)`;
  } else {
    statusBadge.className = "flex items-center space-x-2 px-3 py-1.5 rounded-lg border border-indigo-500/30 bg-indigo-500/10 text-xs text-indigo-300";
    statusText.innerText = `Partially Loaded (${dp.loaded_count}/${dp.total_count})`;
  }

  // 2. Metrics
  document.getElementById('metric-priorities').innerText = data.metrics.priorities_today;
  document.getElementById('metric-commitments').innerText = data.metrics.my_commitments;
  document.getElementById('metric-waiting').innerText = data.metrics.waiting_on_others;
  document.getElementById('metric-conflicts').innerText = data.metrics.calendar_conflicts;
  document.getElementById('metric-unclear').innerText = data.metrics.unclear_ownership;
  document.getElementById('metric-sources').innerText = `${dp.loaded_count} / ${dp.total_count}`;
  document.getElementById('brief-ref-date').innerText = `Ref Date: ${data.reference_date}`;

  // 3. Executive Summary
  const summaryEl = document.getElementById('brief-summary-text');
  if (dp.is_empty) {
    summaryEl.innerHTML = `<span class="text-amber-300 font-medium">Source data not loaded:</span> The AIONOS assignment data pack has not been loaded into <code>data/raw/</code>. 
    Click <strong>"Load / Edit Assignment Data"</strong> above to paste or verify transcripts, calendars, and emails. No synthetic facts will be invented.`;
  } else {
    summaryEl.innerText = `Arjun, you have ${data.metrics.my_commitments} active commitments, ${data.metrics.priorities_today} priority items requiring action, and ${data.metrics.waiting_on_others} deliverables pending from others. ${data.metrics.unclear_ownership} action items need ownership triage.`;
  }

  // 4. Priorities List
  const prioritiesContainer = document.getElementById('dash-priorities-list');
  if (!data.priorities || data.priorities.length === 0) {
    prioritiesContainer.innerHTML = `<div class="p-6 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
      ${dp.is_empty ? 'Source data not loaded. No priorities extracted.' : 'No urgent or overdue priorities today.'}
    </div>`;
  } else {
    prioritiesContainer.innerHTML = data.priorities.map(p => `
      <div class="p-3.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition flex items-start justify-between">
        <div class="space-y-1 pr-2">
          <div class="flex items-center space-x-2">
            <span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">${p.urgency_status}</span>
            <span class="text-xs font-semibold text-slate-200">${escapeHtml(p.task)}</span>
          </div>
          <p class="text-[11px] text-slate-400">Owner: <strong class="text-slate-300">${p.owner || 'Unassigned'}</strong> &bull; Due: ${p.raw_deadline || 'Today'}</p>
        </div>
        <button onclick="openEvidenceDrawer('${p.id}')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-indigo-300 hover:text-indigo-200 text-[11px] font-medium transition shrink-0">
          Source
        </button>
      </div>
    `).join('');
  }

  // 5. Conflicts List
  const conflictsContainer = document.getElementById('dash-conflicts-list');
  if (!data.calendar_conflicts || data.calendar_conflicts.length === 0) {
    conflictsContainer.innerHTML = `<div class="p-6 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
      ${dp.is_empty ? 'Source data not loaded. No calendar events detected.' : 'Zero calendar conflicts detected.'}
    </div>`;
  } else {
    conflictsContainer.innerHTML = data.calendar_conflicts.map(c => `
      <div class="p-3.5 rounded-xl bg-slate-900 border border-orange-500/20 bg-orange-500/5 transition space-y-1">
        <div class="flex items-center justify-between">
          <span class="text-xs font-semibold text-orange-300">${escapeHtml(c.event_title)}</span>
          <span class="text-[10px] text-orange-400 font-mono">${c.start_time} - ${c.end_time}</span>
        </div>
        <p class="text-[11px] text-slate-400">${escapeHtml(c.description)}</p>
      </div>
    `).join('');
  }

  // 6. Commitments List
  const commitmentsContainer = document.getElementById('dash-commitments-list');
  document.getElementById('dash-my-count').innerText = `${(data.commitments || []).length} items`;
  if (!data.commitments || data.commitments.length === 0) {
    commitmentsContainer.innerHTML = `<div class="p-6 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
      ${dp.is_empty ? 'Source data not loaded. No commitments found.' : 'No commitments made by Arjun Malhotra in loaded sources.'}
    </div>`;
  } else {
    commitmentsContainer.innerHTML = data.commitments.slice(0, 4).map(renderCompactAction).join('');
  }

  // 7. Waiting on Others List
  const waitingContainer = document.getElementById('dash-waiting-list');
  document.getElementById('dash-waiting-count').innerText = `${(data.follow_ups || []).length} items`;
  if (!data.follow_ups || data.follow_ups.length === 0) {
    waitingContainer.innerHTML = `<div class="p-6 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
      ${dp.is_empty ? 'Source data not loaded. No pending follow-ups.' : 'No items currently waiting on colleagues.'}
    </div>`;
  } else {
    waitingContainer.innerHTML = data.follow_ups.slice(0, 4).map(renderCompactAction).join('');
  }
}

function renderCompactAction(item) {
  const isUnclear = item.ownership_category === "Unclear Ownership";
  return `
    <div class="p-3 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition flex items-center justify-between">
      <div class="space-y-0.5 pr-2">
        <div class="text-xs font-medium text-slate-200 line-clamp-1">${escapeHtml(item.task)}</div>
        <div class="text-[11px] text-slate-400">
          ${isUnclear ? '<span class="badge-unclear px-1.5 py-0.2 rounded text-[10px]">Unclear Owner</span>' : `Owner: <span class="text-slate-300">${item.owner}</span>`}
          ${item.raw_deadline ? `&bull; <span class="text-amber-400">${item.raw_deadline}</span>` : ''}
        </div>
      </div>
      <button onclick="openEvidenceDrawer('${item.id}')" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-indigo-300 text-[11px] transition shrink-0">
        View
      </button>
    </div>
  `;
}

// ---------------- Input Intelligence View ----------------
function renderInputsView(sources) {
  const container = document.getElementById('sources-grid');
  if (!container) return;

  container.innerHTML = sources.map(s => {
    const isLoaded = s.is_loaded;
    return `
      <div class="glass-panel p-4 rounded-xl border ${isLoaded ? 'border-indigo-500/30' : 'border-slate-800'} flex flex-col justify-between space-y-3">
        <div>
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">${s.channel}</span>
            <span class="text-[10px] px-2 py-0.5 rounded-full font-medium ${isLoaded ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 text-slate-500 border border-slate-700'}">
              ${isLoaded ? `${s.char_count} chars` : 'Source data not loaded'}
            </span>
          </div>
          <h4 class="text-xs font-bold text-white mt-1.5">${escapeHtml(s.title)}</h4>
          <p class="text-[11px] text-slate-400 font-mono mt-1">${s.rel_path}</p>
          <div class="mt-3 p-2.5 rounded-lg bg-slate-950/80 border border-slate-800/80 text-[11px] font-mono text-slate-400 line-clamp-3">
            ${escapeHtml(s.preview)}
          </div>
        </div>
        <div class="pt-2 border-t border-slate-800/80 flex items-center justify-between">
          <span class="text-[10px] text-slate-400">${isLoaded ? 'Extraction ready' : 'Awaiting input'}</span>
          <button onclick="openModalForSource('${s.id}')" class="text-xs font-medium text-indigo-400 hover:text-indigo-300">
            ${isLoaded ? 'View / Edit' : '+ Load Data'}
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// ---------------- Action Cards View ----------------
function filterActions(category) {
  currentFilter = category;
  document.querySelectorAll('.action-filter-btn').forEach(btn => {
    btn.className = "action-filter-btn px-3 py-1.5 rounded-lg font-medium text-slate-400 hover:text-white";
  });
  const activeBtnId = category === 'all' ? 'filter-all' : 
                      category === 'My Action' ? 'filter-my' : 
                      category === 'Waiting on Others' ? 'filter-waiting' : 'filter-unclear';
  const activeBtn = document.getElementById(activeBtnId);
  if (activeBtn) activeBtn.className = "action-filter-btn px-3 py-1.5 rounded-lg font-medium bg-indigo-600 text-white";

  let filtered = currentActionsList;
  if (category !== 'all') {
    filtered = currentActionsList.filter(a => a.ownership_category === category);
  }
  renderActionCards(filtered);
}

function renderActionCards(actions) {
  const container = document.getElementById('action-cards-container');
  if (!container) return;

  if (!actions || actions.length === 0) {
    container.innerHTML = `
      <div class="col-span-2 p-12 text-center border border-dashed border-slate-800 rounded-2xl glass-panel space-y-2">
        <i class="fa-solid fa-list-check text-slate-600 text-2xl"></i>
        <h4 class="text-sm font-semibold text-slate-300">No Action Items in This Category</h4>
        <p class="text-xs text-slate-400">
          Load or paste raw assignment data pack content to extract verified action cards.
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = actions.map(act => {
    const isUnclear = act.ownership_category === "Unclear Ownership";
    const isOverdue = act.urgency_status === "Overdue";
    const isDueToday = act.urgency_status === "Due Today";

    const urgencyClass = isOverdue ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' :
                         isDueToday ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                         'bg-slate-800 text-slate-400 border-slate-700';

    return `
      <div class="glass-panel p-5 rounded-2xl border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between space-y-4">
        <div class="space-y-2.5">
          <div class="flex items-start justify-between">
            <span class="text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${urgencyClass}">
              ${act.urgency_status}
            </span>
            <span class="text-xs text-slate-400">
              <i class="fa-solid fa-link text-[10px] mr-1"></i> ${(act.sources || []).length} source(s)
            </span>
          </div>

          <h3 class="text-sm font-semibold text-white leading-snug">${escapeHtml(act.task)}</h3>

          <div class="grid grid-cols-2 gap-2 text-xs pt-1">
            <div class="p-2 rounded-lg bg-slate-950 border border-slate-800/80">
              <span class="text-[10px] text-slate-400 block">Owner</span>
              <span class="font-medium ${isUnclear ? 'text-rose-400' : 'text-slate-200'}">
                ${isUnclear ? '⚠️ Flagged: Unclear' : escapeHtml(act.owner || 'None')}
              </span>
            </div>
            <div class="p-2 rounded-lg bg-slate-950 border border-slate-800/80">
              <span class="text-[10px] text-slate-400 block">Deadline</span>
              <span class="font-medium text-slate-200">${escapeHtml(act.raw_deadline || 'None specified')}</span>
            </div>
          </div>

          ${act.conflict_notes ? `
            <div class="p-2.5 rounded-lg bg-orange-500/10 border border-orange-500/20 text-[11px] text-orange-300">
              <i class="fa-solid fa-triangle-exclamation mr-1"></i> ${escapeHtml(act.conflict_notes)}
            </div>
          ` : ''}
        </div>

        <div class="pt-3 border-t border-slate-800 flex items-center justify-between">
          <span class="text-xs text-slate-400">
            Counterparty: <strong class="text-slate-300">${escapeHtml(act.counterparty || 'None')}</strong>
          </span>
          <button onclick="openEvidenceDrawer('${act.id}')" class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition shadow flex items-center space-x-1.5">
            <i class="fa-solid fa-file-lines text-[10px]"></i>
            <span>View Source Evidence</span>
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// ---------------- Evidence Audit View ----------------
function renderEvidenceAudit() {
  const container = document.getElementById('evidence-audit-list');
  if (!container) return;

  if (!currentActionsList || currentActionsList.length === 0) {
    container.innerHTML = `
      <div class="p-12 text-center border border-dashed border-slate-800 rounded-2xl glass-panel text-slate-400 text-xs">
        Source data not loaded. No evidence entries to inspect.
      </div>
    `;
    return;
  }

  container.innerHTML = currentActionsList.map(act => {
    return `
      <div class="glass-panel p-5 rounded-2xl border border-slate-800 space-y-3">
        <div class="flex items-start justify-between">
          <div>
            <span class="text-[10px] uppercase font-bold text-indigo-400 tracking-wider">Action Intent</span>
            <h4 class="text-sm font-semibold text-white mt-0.5">${escapeHtml(act.task)}</h4>
            <p class="text-xs text-slate-400 mt-0.5">Owner: <strong class="text-slate-300">${act.owner || 'Unclear'}</strong> &bull; Status: ${act.urgency_status}</p>
          </div>
          <button onclick="openEvidenceDrawer('${act.id}')" class="text-xs text-indigo-400 hover:underline">
            Open Drawer &rarr;
          </button>
        </div>

        <div class="space-y-2">
          ${(act.sources || []).map(s => `
            <div class="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs space-y-1">
              <div class="flex items-center justify-between text-[10px] text-slate-400">
                <span class="font-bold text-indigo-300">[${escapeHtml(s.channel)}] ${escapeHtml(s.source_id)}</span>
                <span>${escapeHtml(s.timestamp_or_date)} &bull; ${escapeHtml(s.author_or_speaker || 'Speaker')}</span>
              </div>
              <blockquote class="border-l-2 border-indigo-500 pl-3 py-0.5 font-mono text-[11px] text-slate-300 italic">
                "${escapeHtml(s.verbatim_quote || '')}"
              </blockquote>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }).join('');
}

// ---------------- Slide-Over Evidence Drawer ----------------
function openEvidenceDrawer(actionId) {
  const item = currentActionsList.find(a => a.id === actionId);
  if (!item) return;

  document.getElementById('drawer-task-title').innerText = item.task;
  const listContainer = document.getElementById('drawer-citations-list');

  if (!item.sources || item.sources.length === 0) {
    listContainer.innerHTML = `
      <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-500">
        No supporting quotes attached to this item.
      </div>
    `;
  } else {
    listContainer.innerHTML = item.sources.map((s, idx) => `
      <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
        <div class="flex items-center justify-between text-[11px]">
          <span class="font-semibold text-indigo-400">[${escapeHtml(s.channel)}]</span>
          <span class="text-slate-400">${escapeHtml(s.timestamp_or_date)}</span>
        </div>
        <div class="text-[11px] text-slate-300">
          Source: <strong class="text-white">${escapeHtml(s.source_id)}</strong> 
          &bull; Speaker: <strong class="text-white">${escapeHtml(s.author_or_speaker || 'Unknown')}</strong>
        </div>
        <div class="p-3 rounded-lg bg-slate-900 border border-slate-800 font-mono text-xs text-emerald-300/90 leading-relaxed">
          "${escapeHtml(s.verbatim_quote)}"
        </div>
        <div class="text-[10px] text-slate-500">
          Context: ${escapeHtml(s.context || 'Raw document excerpt')}
        </div>
      </div>
    `).join('');
  }

  const drawer = document.getElementById('evidence-drawer');
  if (drawer) drawer.classList.remove('hidden');
}

function closeEvidenceDrawer() {
  const drawer = document.getElementById('evidence-drawer');
  if (drawer) drawer.classList.add('hidden');
}

// ---------------- Grounded Q&A Assistant ----------------
async function askPreset(questionText) {
  const inputEl = document.getElementById('qa-custom-input');
  inputEl.value = questionText;
  await submitCustomQuestion();
}

async function submitCustomQuestion() {
  const inputEl = document.getElementById('qa-custom-input');
  const question = inputEl.value.trim();
  if (!question) return;

  const history = document.getElementById('qa-chat-history');

  // Append user bubble
  history.innerHTML += `
    <div class="flex items-start justify-end space-x-3 text-xs">
      <div class="p-3.5 rounded-2xl bg-indigo-600 text-white max-w-xl shadow">
        ${escapeHtml(question)}
      </div>
      <div class="w-7 h-7 rounded-lg bg-indigo-500 flex items-center justify-center text-white font-bold shrink-0 text-xs">
        AM
      </div>
    </div>
  `;
  inputEl.value = '';
  history.scrollTop = history.scrollHeight;

  // Append loading state
  const loadingId = 'loading-' + Date.now();
  history.innerHTML += `
    <div id="${loadingId}" class="flex items-start space-x-3 text-xs text-slate-400">
      <div class="w-7 h-7 rounded-lg bg-indigo-600/30 flex items-center justify-center text-indigo-400 font-bold shrink-0">
        <i class="fa-solid fa-spinner animate-spin"></i>
      </div>
      <div class="glass-panel p-3.5 rounded-2xl border border-slate-800 text-slate-300">
        Verifying grounded data in assignment pack...
      </div>
    </div>
  `;
  history.scrollTop = history.scrollHeight;

  try {
    const res = await fetch('/api/qa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question })
    });
    const result = await res.json();
    document.getElementById(loadingId)?.remove();

    // Render bot answer
    const evidenceSnippets = (result.evidence || []).map(e => `
      <div class="mt-2 p-2 rounded bg-slate-950/80 border border-slate-800 font-mono text-[10px] text-slate-300">
        <span class="text-indigo-400">[${escapeHtml(e.channel)}] ${escapeHtml(e.source_id)}:</span> "${escapeHtml(e.verbatim_quote)}"
      </div>
    `).join('');

    history.innerHTML += `
      <div class="flex items-start space-x-3 text-xs text-slate-300">
        <div class="w-7 h-7 rounded-lg bg-indigo-600/30 flex items-center justify-center text-indigo-400 font-bold shrink-0">
          <i class="fa-solid fa-robot"></i>
        </div>
        <div class="glass-panel p-4 rounded-2xl border border-slate-800 max-w-2xl space-y-2">
          <div class="whitespace-pre-line leading-relaxed">${escapeHtml(result.answer)}</div>
          ${evidenceSnippets}
          <div class="pt-2 text-[10px] text-slate-500 border-t border-slate-800/60 flex items-center justify-between">
            <span>Status: ${escapeHtml(result.status)}</span>
            <span class="text-emerald-400"><i class="fa-solid fa-check mr-1"></i> Strictly Grounded</span>
          </div>
        </div>
      </div>
    `;
    history.scrollTop = history.scrollHeight;
  } catch (err) {
    document.getElementById(loadingId)?.remove();
    history.innerHTML += `
      <div class="p-3 text-xs text-rose-400">
        Error communicating with Grounded Q&A engine: ${err.message}
      </div>
    `;
  }
}

// ---------------- Ingestion / Load Data Modal ----------------
function populateModalDropdown(sources) {
  const select = document.getElementById('modal-source-select');
  if (!select) return;
  select.innerHTML = sources.map(s => `
    <option value="${s.id}">${s.title} (${s.is_loaded ? 'Loaded' : 'Empty'})</option>
  `).join('');
}

async function openIngestionModal() {
  const modal = document.getElementById('ingestion-modal');
  if (modal) modal.classList.remove('hidden');
  await loadSelectedSourceToModal();
}

function closeIngestionModal() {
  const modal = document.getElementById('ingestion-modal');
  if (modal) modal.classList.add('hidden');
}

async function openModalForSource(sourceId) {
  const select = document.getElementById('modal-source-select');
  if (select) select.value = sourceId;
  await openIngestionModal();
}

async function loadSelectedSourceToModal() {
  const select = document.getElementById('modal-source-select');
  const textarea = document.getElementById('modal-source-text');
  const statusMsg = document.getElementById('modal-status-msg');
  if (!select || !textarea) return;

  const sourceId = select.value;
  statusMsg.innerText = "Loading...";

  try {
    const res = await fetch(`/api/source/${sourceId}`);
    const data = await res.json();
    textarea.value = data.content || '';
    statusMsg.innerText = data.is_loaded ? `Loaded (${data.content.length} chars)` : "Source data not loaded";
  } catch (err) {
    statusMsg.innerText = "Error loading source";
  }
}

async function saveModalSourceContent() {
  const select = document.getElementById('modal-source-select');
  const textarea = document.getElementById('modal-source-text');
  const statusMsg = document.getElementById('modal-status-msg');
  if (!select || !textarea) return;

  const sourceId = select.value;
  const content = textarea.value;
  statusMsg.innerText = "Saving & Re-extracting actions...";

  try {
    const res = await fetch('/api/source/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_id: sourceId, content })
    });
    const result = await res.json();
    if (result.status === 'success') {
      statusMsg.innerText = "Saved successfully! Updated dashboard.";
      await fetchDashboard();
      setTimeout(closeIngestionModal, 700);
    } else {
      statusMsg.innerText = "Failed to save: " + result.message;
    }
  } catch (err) {
    statusMsg.innerText = "Error saving source: " + err.message;
  }
}

// ---------------- Helpers ----------------
function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Explicit window bindings for bulletproof event handling
window.switchView = switchView;
window.refreshData = refreshData;
window.filterActions = filterActions;
window.openEvidenceDrawer = openEvidenceDrawer;
window.closeEvidenceDrawer = closeEvidenceDrawer;
window.openIngestionModal = openIngestionModal;
window.closeIngestionModal = closeIngestionModal;
window.openModalForSource = openModalForSource;
window.loadSelectedSourceToModal = loadSelectedSourceToModal;
window.saveModalSourceContent = saveModalSourceContent;
window.askPreset = askPreset;
window.submitCustomQuestion = submitCustomQuestion;

