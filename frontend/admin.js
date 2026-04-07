// admin.js — SchemaAdvisor Admin Panel

const API = '';   // same origin

// ── DOM refs ────────────────────────────────────────────────
const conceptsList    = document.getElementById('concepts-list');
const candidatesList  = document.getElementById('candidates-list');
const addForm         = document.getElementById('add-concept-form');
const addError        = document.getElementById('add-error');
const addSuccess      = document.getElementById('add-success');
const addBtn          = document.getElementById('add-btn');
const addBtnText      = addBtn.querySelector('.btn-text');
const addBtnLoader    = addBtn.querySelector('.btn-loader');

const statActive      = document.getElementById('stat-active');
const statCandidates  = document.getElementById('stat-candidates');
const statRejected    = document.getElementById('stat-rejected');
const activeBadge     = document.getElementById('active-count-badge');
const candidateBadge  = document.getElementById('candidate-count-badge');

let rejectedCount = 0;  // in-session rejected tally

// ── Load active concepts ─────────────────────────────────────
async function loadConcepts() {
    try {
        const res  = await fetch(`${API}/admin/concepts`);
        const data = await res.json();
        renderConcepts(data.concepts);
        statActive.textContent = Object.keys(data.concepts).length;
        activeBadge.textContent = `${Object.keys(data.concepts).length} active`;
    } catch (e) {
        conceptsList.innerHTML = `<div class="empty-state"><span class="empty-icon">⚠️</span>Could not load concepts. Is the server running?</div>`;
    }
}

function renderConcepts(concepts) {
    if (!concepts || Object.keys(concepts).length === 0) {
        conceptsList.innerHTML = `<div class="empty-state"><span class="empty-icon">📭</span>No active concepts.</div>`;
        return;
    }
    conceptsList.innerHTML = '';
    Object.entries(concepts).forEach(([key, desc]) => {
        const item = document.createElement('div');
        item.className = 'concept-item';
        item.id = `concept-item-${key}`;
        item.innerHTML = `
            <div class="concept-info">
                <div class="concept-key">${key}</div>
                <div class="concept-desc" title="${desc}">${desc}</div>
            </div>
            <div class="concept-actions">
                <button class="btn-remove" data-key="${key}" title="Remove concept">Remove</button>
            </div>
        `;
        conceptsList.appendChild(item);
    });

    // Wire remove buttons
    conceptsList.querySelectorAll('.btn-remove').forEach(btn => {
        btn.addEventListener('click', () => removeConcept(btn.dataset.key));
    });
}

// ── Load candidates ──────────────────────────────────────────
async function loadCandidates() {
    try {
        const res  = await fetch(`${API}/admin/candidates`);
        const data = await res.json();
        renderCandidates(data.candidates);
        statCandidates.textContent = data.candidates.length;
        candidateBadge.textContent = `${data.candidates.length} pending`;
    } catch (e) {
        candidatesList.innerHTML = `<div class="empty-state"><span class="empty-icon">⚠️</span>Could not load candidates.</div>`;
    }
}

function renderCandidates(candidates) {
    if (!candidates || candidates.length === 0) {
        candidatesList.innerHTML = `<div class="empty-state"><span class="empty-icon">✅</span>No pending candidates — inbox is clear!</div>`;
        statCandidates.textContent = '0';
        candidateBadge.textContent = '0 pending';
        return;
    }
    candidatesList.innerHTML = '';
    candidates.forEach((c, idx) => {
        const item = document.createElement('div');
        item.className = 'candidate-item';
        item.id = `candidate-${idx}`;
        item.innerHTML = `
            <div>
                <div class="candidate-text">${c.raw_text}</div>
                <div class="candidate-meta">category: ${c.category}</div>
            </div>
            <div class="concept-actions">
                <button class="btn-map" data-raw="${c.raw_text}" title="Map to existing logic">Map</button>
                <button class="btn-approve" data-raw="${c.raw_text}" data-cat="${c.category}" title="Move to registry">Approve</button>
                <button class="btn-reject"  data-raw="${c.raw_text}" title="Remove from queue">Reject</button>
            </div>
        `;
        candidatesList.appendChild(item);
    });

    // Wire map
    candidatesList.querySelectorAll('.btn-map').forEach(btn => {
        btn.addEventListener('click', () => mapCandidate(btn.dataset.raw, btn.closest('.candidate-item')));
    });
    // Wire approve
    candidatesList.querySelectorAll('.btn-approve').forEach(btn => {
        btn.addEventListener('click', () => approveCandidate(btn.dataset.raw, btn.closest('.candidate-item')));
    });
    // Wire reject
    candidatesList.querySelectorAll('.btn-reject').forEach(btn => {
        btn.addEventListener('click', () => rejectCandidate(btn.dataset.raw, btn.closest('.candidate-item')));
    });
}

// ── Actions ──────────────────────────────────────────────────
async function mapCandidate(rawText, itemEl) {
    const targetConcept = prompt(`Map "${rawText}" to which existing Concept (e.g., e_commerce_orders)?`);
    if (!targetConcept) return;
    const targetTable = prompt(`Map "${rawText}" to which Logical Table (e.g., shopping_cart)?`);
    if (!targetTable) return;
    
    try {
        await fetch(`${API}/admin/candidates/map`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ raw_text: rawText, target_concept: targetConcept, target_table: targetTable })
        });
        alert(`Mapped "${rawText}" to ${targetTable} under ${targetConcept}`);
    } catch(e) { alert('Map failed'); }
    
    itemEl.classList.add('fade-out');
    setTimeout(() => {
        itemEl.remove();
        decrementCandidates();
    }, 300);
}
async function removeConcept(key) {
    if (!confirm(`Remove "${key}" from the active concept registry?`)) return;
    try {
        await fetch(`${API}/admin/concepts/${key}`, { method: 'DELETE' });
        document.getElementById(`concept-item-${key}`)?.remove();
        const current = parseInt(statActive.textContent || '0', 10);
        statActive.textContent = Math.max(0, current - 1);
        activeBadge.textContent = `${Math.max(0, current - 1)} active`;
    } catch (e) {
        alert('Failed to remove concept. Check server logs.');
    }
}

async function approveCandidate(rawText, itemEl) {
    // Pre-fill Add form with the raw text as concept key suggestion
    document.getElementById('new-concept-name').value = rawText.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z_]/g, '');
    document.getElementById('new-concept-desc').value = rawText;
    itemEl.remove();
    decrementCandidates();
    document.getElementById('add-concept-form').scrollIntoView({ behavior: 'smooth' });
}

async function rejectCandidate(rawText, itemEl) {
    try {
        await fetch(`${API}/admin/candidates/reject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ raw_text: rawText })
        });
    } catch(e) { /* best-effort */ }
    itemEl.classList.add('fade-out');
    setTimeout(() => {
        itemEl.remove();
        decrementCandidates();
        rejectedCount++;
        statRejected.textContent = rejectedCount;
    }, 300);
}

function decrementCandidates() {
    const current = parseInt(statCandidates.textContent || '0', 10);
    const next = Math.max(0, current - 1);
    statCandidates.textContent = next;
    candidateBadge.textContent = `${next} pending`;
    if (next === 0) {
        candidatesList.innerHTML = `<div class="empty-state"><span class="empty-icon">✅</span>No pending candidates — inbox is clear!</div>`;
    }
}

// ── Add concept form ─────────────────────────────────────────
addForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    addError.classList.add('hidden');
    addSuccess.classList.add('hidden');

    const key  = document.getElementById('new-concept-name').value.trim();
    const desc = document.getElementById('new-concept-desc').value.trim();

    if (!key) { showAddError('Concept key is required.'); return; }
    if (!/^[a-z_]+$/.test(key)) { showAddError('Key must be lowercase letters and underscores only.'); return; }

    addBtnText.textContent = 'Proposing…';
    addBtnLoader.classList.remove('hidden');
    addBtn.disabled = true;

    try {
        const res = await fetch(`${API}/admin/concepts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: key, description: desc || `${key} concept` })
        });
        const data = await res.json();
        if (!res.ok) { showAddError(data.detail || 'Failed to add concept.'); return; }

        addSuccess.textContent = `✓ "${key}" added to the live registry.`;
        addSuccess.classList.remove('hidden');
        addForm.reset();
        setTimeout(() => addSuccess.classList.add('hidden'), 3000);
        loadConcepts(); // refresh list
    } catch(err) {
        showAddError('Server error — is the API running?');
    } finally {
        addBtnText.textContent = 'Propose Concept';
        addBtnLoader.classList.add('hidden');
        addBtn.disabled = false;
    }
});

function showAddError(msg) {
    addError.textContent = msg;
    addError.classList.remove('hidden');
}

// ── Fade-out animation ───────────────────────────────────────
const style = document.createElement('style');
style.textContent = `.fade-out { opacity: 0; transform: translateX(20px); transition: opacity 0.3s, transform 0.3s; }`;
document.head.appendChild(style);

// ── Init ─────────────────────────────────────────────────────
statRejected.textContent = '0';
loadConcepts();
loadCandidates();
