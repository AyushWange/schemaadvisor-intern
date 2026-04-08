/* ════════════════════════════════════════════════════════
   SchemaAdvisor — app.js  v2.8
   • Welcome hero
   • Tab system (Schema / Dependency Graph / Explainability / Raw JSON)
   • Interactive force-directed dependency graph (Canvas)
   • Collapsible JSON tree viewer
   • Example chips, char counter, health check
   ════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {

    /* ── DOM refs ─────────────────────────────────────── */
    const inputField        = document.getElementById('prompt-input');
    const generateBtn       = document.getElementById('generate-btn');
    const btnText           = generateBtn.querySelector('.btn-text');
    const btnLoader         = generateBtn.querySelector('.btn-loader');
    const btnIcon           = generateBtn.querySelector('.btn-icon');
    const charCount         = document.getElementById('char-count');
    const errorMsg          = document.getElementById('error-message');
    const welcomeSection    = document.getElementById('welcome-section');
    const resultsSection    = document.getElementById('results-section');
    const discoverySection  = document.getElementById('discovery-section');
    const discoveryCards    = document.getElementById('discovery-cards');

    // Schema tab
    const sqlOutput         = document.getElementById('sql-output');
    const badge             = document.getElementById('validation-badge');
    const creationOrderVal  = document.getElementById('creation-order-val');
    const tableCountVal     = document.getElementById('table-count-val');
    const decisionsRow      = document.getElementById('decisions-row');
    const decisionsVal      = document.getElementById('decisions-val');
    const tableSummaryCards = document.getElementById('table-summary-cards');
    const copySqlBtn        = document.getElementById('copy-sql-btn');

    // Conflicts panel
    const conflictsPanel    = document.getElementById('conflicts-panel');
    const conflictsList     = document.getElementById('conflicts-list');
    const conflictsTitle    = document.getElementById('conflicts-title');
    const conflictsClose    = document.getElementById('conflicts-close');

    // Explain tab
    const explainTbody      = document.getElementById('explain-tbody');

    // JSON tab
    const jsonTree          = document.getElementById('json-tree');
    const copyJsonBtn       = document.getElementById('copy-json-btn');
    const expandJsonBtn     = document.getElementById('expand-json-btn');

    // Graph tab
    const canvas            = document.getElementById('dep-graph-canvas');
    const graphContainer    = document.getElementById('graph-container');
    const graphTooltip      = document.getElementById('graph-tooltip');
    const zoomInBtn         = document.getElementById('graph-zoom-in');
    const zoomOutBtn        = document.getElementById('graph-zoom-out');
    const resetBtn          = document.getElementById('graph-reset');

    // Store last API result
    let lastData = null;

    /* ── Health check ────────────────────────────────── */
    const healthDot = document.getElementById('health-dot');
    async function checkHealth() {
        try {
            const r = await fetch('/health');
            const d = await r.json();
            if (d.status === 'ok') {
                healthDot.className = 'health-dot ok';
                healthDot.title = `LLM: ${d.llm_ready ? '✅' : '❌'}  Neo4j: ${d.neo4j_ready ? '✅' : '❌'}`;
            } else { healthDot.className = 'health-dot err'; }
        } catch { healthDot.className = 'health-dot err'; healthDot.title = 'API unreachable'; }
    }
    checkHealth();

    /* ── Char counter ────────────────────────────────── */
    inputField.addEventListener('input', function () {
        const n = this.value.length;
        charCount.textContent = `${n} char${n !== 1 ? 's' : ''}`;
        this.style.height = 'auto';
        this.style.height = this.scrollHeight + 'px';
    });

    /* ── Example chips ───────────────────────────────── */
    const EXAMPLES = {
        'example-ecommerce': 'I need an e-commerce platform with product catalog, shopping cart, order management, payment processing and GST compliance.',
        'example-hrm':       'Build an HR system with employee management, departments, payroll processing, leave tracking and performance reviews.',
        'example-saas':      'I need a multi-tenant SaaS platform with user authentication, project tracking, reporting analytics and multi-currency billing.',
    };
    Object.entries(EXAMPLES).forEach(([id, text]) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('click', () => {
            inputField.value = text;
            inputField.dispatchEvent(new Event('input'));
            inputField.focus();
        });
    });

    /* ── Tab system ──────────────────────────────────── */
    const tabs = ['schema', 'graph', 'explain', 'json'];
    tabs.forEach(tabId => {
        const btn     = document.getElementById(`tab-${tabId}`);
        const content = document.getElementById(`tab-content-${tabId}`);
        if (!btn || !content) return;
        btn.addEventListener('click', () => {
            tabs.forEach(t => {
                document.getElementById(`tab-${t}`)?.classList.remove('active');
                document.getElementById(`tab-content-${t}`)?.classList.remove('active');
                document.getElementById(`tab-content-${t}`)?.classList.add('hidden');
            });
            btn.classList.add('active');
            content.classList.remove('hidden');
            content.classList.add('active');
            if (tabId === 'graph' && lastData) renderGraph(lastData);
        });
    });

    /* ── Conflicts panel close ───────────────────────── */
    if (conflictsClose) {
        conflictsClose.addEventListener('click', () => {
            conflictsPanel.classList.add('hidden');
        });
    }

    /* ── Copy helpers ────────────────────────────────── */
    function setupCopy(btn, getText) {
        btn.addEventListener('click', async () => {
            const text = getText();
            if (!text) return;
            try {
                await navigator.clipboard.writeText(text);
                const icon = btn.querySelector('.copy-icon');
                const lbl  = btn.querySelector('.copy-text');
                icon.textContent = '✓';
                if (lbl) lbl.textContent = 'Copied!';
                btn.classList.add('copy-btn--success');
                setTimeout(() => {
                    icon.textContent = '⎘';
                    if (lbl) lbl.textContent = btn === copySqlBtn ? 'Copy' : 'Copy JSON';
                    btn.classList.remove('copy-btn--success');
                }, 2000);
            } catch (e) { console.error('Copy failed:', e); }
        });
    }
    setupCopy(copySqlBtn,  () => sqlOutput.textContent);
    setupCopy(copyJsonBtn, () => lastData ? JSON.stringify(lastData, null, 2) : '');

    /* ── Generate schema ─────────────────────────────── */
    generateBtn.addEventListener('click', async () => {
        const reqText = inputField.value.trim();
        if (!reqText) return;

        generateBtn.disabled = true;
        btnText.textContent  = 'Generating…';
        btnIcon.textContent  = '';
        btnLoader.classList.remove('hidden');
        errorMsg.classList.add('hidden');
        resultsSection.classList.add('hidden');
        discoverySection.classList.add('hidden');

        try {
            const resp = await fetch('/schema', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ requirements: reqText }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail || 'Failed to generate schema. Try rephrasing.');
            lastData = data;
            renderResults(data);
        } catch (err) {
            errorMsg.textContent = err.message;
            errorMsg.classList.remove('hidden');
        } finally {
            generateBtn.disabled = false;
            btnText.textContent  = 'Generate Schema';
            btnIcon.textContent  = '✦';
            btnLoader.classList.add('hidden');
        }
    });

    /* ════════════════════════════════════════════════
       RENDER ALL RESULTS
    ════════════════════════════════════════════════ */
    function renderResults(data) {
        // Switch to Schema tab
        tabs.forEach(t => {
            document.getElementById(`tab-${t}`)?.classList.remove('active');
            document.getElementById(`tab-content-${t}`)?.classList.remove('hidden');
            document.getElementById(`tab-content-${t}`)?.classList.remove('active');
        });
        document.getElementById('tab-schema')?.classList.add('active');
        document.getElementById('tab-content-schema')?.classList.add('active');
        ['graph','explain','json'].forEach(t => {
            document.getElementById(`tab-content-${t}`)?.classList.add('hidden');
            document.getElementById(`tab-content-${t}`)?.classList.remove('active');
        });

        renderSQL(data);
        renderMeta(data);
        renderConflicts(data.conflicts || []);
        renderExplainability(data.explainability || []);
        renderJSONTree(data);
        renderDiscoveryCards(data.unmatched || []);

        // Hide welcome hero after first generation
        welcomeSection.style.display = 'none';

        resultsSection.classList.remove('hidden');
        setTimeout(() => resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
    }

    /* ── 1. SQL ──────────────────────────────────────── */
    function renderSQL(data) {
        sqlOutput.textContent = data.ddl || '';
        if (typeof Prism !== 'undefined') Prism.highlightElement(sqlOutput);

        badge.className = 'badge';
        const v = data.validation || {};
        if (v.skipped) {
            badge.textContent = 'Unvalidated';
            badge.classList.add('badge-info');
        } else if (v.success === v.total && v.total > 0) {
            badge.textContent = `✓ Valid (${v.success}/${v.total})`;
            badge.classList.add('badge-success');
        } else {
            badge.textContent = `✗ Failed (${v.success}/${v.total})`;
            badge.classList.add('badge-error');
        }
    }

    /* ── 2. Meta ─────────────────────────────────────── */
    function renderMeta(data) {
        const order = data.creation_order || [];
        creationOrderVal.textContent = order.join(' → ');

        tableCountVal.textContent = `${(data.tables || []).length} tables`;

        const decisions = data.active_decisions || {};
        if (Object.keys(decisions).length > 0) {
            decisionsRow.style.display = 'flex';
            decisionsVal.innerHTML = Object.entries(decisions)
                .map(([k, v]) => `<span class="tag-chip tag-pattern">${k}=${v}</span>`)
                .join('');
        } else {
            decisionsRow.style.display = 'none';
        }

        // Table chips colour-coded by tier
        tableSummaryCards.innerHTML = '';
        const explRows = data.explainability || [];
        explRows.forEach(row => {
            const chip = document.createElement('span');
            chip.className = `table-chip ${row.tier}`;
            chip.textContent = row.table;
            chip.title = `${row.tier} · ${((row.confidence||0)*100).toFixed(0)}% confidence`;
            tableSummaryCards.appendChild(chip);
        });
    }

    /* ── 2.5. Conflicts & Warnings ─────────────────────── */
    function renderConflicts(conflicts) {
        conflictsList.innerHTML = '';
        if (!conflicts || conflicts.length === 0) {
            conflictsPanel.classList.add('hidden');
            return;
        }

        conflictsPanel.classList.remove('hidden');

        // Separate hard incompatibilities from preference tradeoffs
        const hardBlocks = conflicts.filter(c => c.category === 'hard_incompatibility');
        const warnings = conflicts.filter(c => c.category === 'preference_tradeoff');

        // Update title based on conflict type
        if (hardBlocks.length > 0) {
            conflictsTitle.textContent = '✗ Hard Incompatibilities Detected';
            conflictsPanel.classList.add('conflicts-critical');
            conflictsPanel.classList.remove('conflicts-warning');
        } else {
            conflictsTitle.textContent = '⚠️ Design Trade-offs & Warnings';
            conflictsPanel.classList.add('conflicts-warning');
            conflictsPanel.classList.remove('conflicts-critical');
        }

        // Render all conflicts
        const allConflicts = [...hardBlocks, ...warnings];
        allConflicts.forEach(conflict => {
            const item = document.createElement('div');
            item.className = `conflict-item conflict-${conflict.category}`;
            
            const icon = conflict.category === 'hard_incompatibility' ? '✗' : '⚠';
            const categoryLabel = conflict.category === 'hard_incompatibility' 
                ? 'Hard Incompatibility' 
                : 'Design Trade-off';

            item.innerHTML = `
                <div class="conflict-header">
                    <span class="conflict-icon">${icon}</span>
                    <span class="conflict-category">${categoryLabel}</span>
                </div>
                <div class="conflict-body">
                    <div class="conflict-conflict">
                        <strong>${conflict.decision_a}</strong> = <code>${conflict.choice_a}</code>
                        <span class="conflict-vs">×</span>
                        <strong>${conflict.decision_b}</strong> = <code>${conflict.choice_b}</code>
                    </div>
                    <div class="conflict-reason">
                        <span class="conflict-reason-label">Why:</span>
                        ${conflict.reason}
                    </div>
                    <div class="conflict-resolution">
                        <span class="conflict-resolution-label">Resolution:</span>
                        ${conflict.resolution}
                    </div>
                </div>
            `;
            conflictsList.appendChild(item);
        });
    }

    /* ── 3. Explainability ───────────────────────────── */
    function renderExplainability(rows) {
        explainTbody.innerHTML = '';
        rows.forEach(row => {
            const tr = document.createElement('tr');
            const triggers = (row.triggered_by || [])
                .map(t => `<span class="tag-chip tag-trigger">${t}</span>`).join('');
            const patterns = (row.patterns || [])
                .map(p => `<span class="tag-chip tag-pattern">${p}</span>`).join('');
            tr.innerHTML = `
                <td style="font-family:var(--font-mono);font-size:0.82rem;">${row.table}</td>
                <td class="tier-${row.tier}">${row.tier}</td>
                <td style="font-family:var(--font-mono);">${((row.confidence||0)*100).toFixed(0)}%</td>
                <td>${triggers}</td>
                <td>${patterns || '<span style="color:var(--text-lo)">—</span>'}</td>
            `;
            explainTbody.appendChild(tr);
        });
    }

    /* ── 4. Discovery Cards ──────────────────────────– */
    function renderDiscoveryCards(unmatched) {
        discoveryCards.innerHTML = '';
        const items = (unmatched || []).filter(u => u.category === 'potential_table');
        if (items.length === 0) { discoverySection.classList.add('hidden'); return; }
        const icons = { potential_table: '🗃️', potential_column: '📋', unsupported_logic: '⚙️' };
        items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'discovery-card';
            const nearestHtml = item.nearest_concept
                ? `<div class="discovery-nearest">💡 Nearest: <strong>${item.nearest_concept.replace(/_/g,' ')}</strong></div>`
                : `<div class="discovery-nearest">💡 No match — candidate for taxonomy expansion</div>`;
            card.innerHTML = `
                <div class="discovery-header">
                    <span class="discovery-icon">${icons[item.category]||'❓'}</span>
                    <span class="discovery-raw">${item.raw_text}</span>
                    <span class="discovery-category">${item.category.replace(/_/g,' ')}</span>
                </div>
                ${nearestHtml}
                <div class="discovery-footer"><span class="discovery-logged">✓ Logged to Neo4j</span></div>
            `;
            discoveryCards.appendChild(card);
        });
        discoverySection.classList.remove('hidden');
    }

    /* ════════════════════════════════════════════════
       5. JSON TREE VIEWER
    ════════════════════════════════════════════════ */
    function renderJSONTree(data) {
        jsonTree.innerHTML = '';
        jsonTree.appendChild(buildJSONNode(data, null, true));
    }

    function buildJSONNode(val, key, expanded) {
        const wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex;flex-direction:column;';

        const type = val === null ? 'null'
                   : Array.isArray(val)  ? 'array'
                   : typeof val;

        const isComplex = type === 'object' || type === 'array';
        const keyHtml = key !== null
            ? `<span class="jt-key">"${key}"</span><span class="jt-brace">: </span>`
            : '';

        if (!isComplex) {
            const valHtml = type === 'string' ? `<span class="jt-str">"${escHtml(val)}"</span>`
                          : type === 'number' ? `<span class="jt-num">${val}</span>`
                          : type === 'boolean'? `<span class="jt-bool">${val}</span>`
                          :                    `<span class="jt-null">null</span>`;
            wrap.innerHTML = `<div>${keyHtml}${valHtml}</div>`;
            return wrap;
        }

        const entries = type === 'array' ? val.map((v,i)=>[i,v]) : Object.entries(val);
        const open  = type === 'array' ? '[' : '{';
        const close = type === 'array' ? ']' : '}';
        const count = entries.length;

        // Header row with toggle
        const header = document.createElement('div');
        header.style.display = 'flex';
        header.style.alignItems = 'center';
        header.style.cursor = 'pointer';
        header.style.userSelect = 'none';

        const toggle = document.createElement('span');
        toggle.className = 'jt-toggle' + (expanded ? ' open' : '');
        toggle.textContent = expanded ? '▾' : '▸';

        header.innerHTML = `${keyHtml}<span class="jt-brace">${open}</span>`;
        header.insertBefore(toggle, header.firstChild);

        const collapsedLabel = document.createElement('span');
        collapsedLabel.style.cssText = 'color:var(--text-lo);font-size:0.78rem;margin-left:4px;';
        collapsedLabel.textContent = `… ${count} item${count!==1?'s':''}`;
        collapsedLabel.style.display = expanded ? 'none' : 'inline';
        header.appendChild(collapsedLabel);

        const closeSpan = document.createElement('span');
        closeSpan.className = 'jt-brace';
        closeSpan.textContent = close;

        wrap.appendChild(header);

        // Children container
        const children = document.createElement('div');
        children.className = 'jt-collapsible';
        if (!expanded) children.classList.add('jt-collapsed');

        entries.forEach(([k, v], idx) => {
            const child = buildJSONNode(v, type==='array'?null:k, false);
            // add comma
            if (idx < entries.length - 1) {
                const nodes = child.children;
                if (nodes.length > 0) {
                    const lastNode = nodes[nodes.length - 1];
                    lastNode.innerHTML += '<span class="jt-brace">,</span>';
                }
            }
            children.appendChild(child);
        });
        wrap.appendChild(children);
        wrap.appendChild(closeSpan);

        header.addEventListener('click', () => {
            const isOpen = !children.classList.contains('jt-collapsed');
            children.classList.toggle('jt-collapsed', isOpen);
            toggle.textContent = isOpen ? '▸' : '▾';
            toggle.classList.toggle('open', !isOpen);
            collapsedLabel.style.display = isOpen ? 'inline' : 'none';
        });

        return wrap;
    }

    function escHtml(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    // Expand/collapse all
    let allExpanded = false;
    expandJsonBtn.addEventListener('click', () => {
        allExpanded = !allExpanded;
        jsonTree.querySelectorAll('.jt-collapsible').forEach(el => {
            el.classList.toggle('jt-collapsed', !allExpanded);
        });
        jsonTree.querySelectorAll('.jt-toggle').forEach(el => {
            el.textContent = allExpanded ? '▾' : '▸';
            el.classList.toggle('open', allExpanded);
        });
        jsonTree.querySelectorAll('.jt-collapsible').forEach((el, i) => {
            const sib = el.previousElementSibling;
            if (sib) {
                const label = sib.querySelector('span[style*="color:var"]');
                if (label) label.style.display = allExpanded ? 'none' : 'inline';
            }
        });
        expandJsonBtn.textContent = allExpanded ? '⊟ Collapse All' : '⊞ Expand All';
    });

    /* ════════════════════════════════════════════════
       6. INTERACTIVE DEPENDENCY GRAPH  (Canvas)
    ════════════════════════════════════════════════ */

    const TIER_COLOR = {
        required:    '#f472b6',
        recommended: '#60a5fa',
        suggested:   '#94a3b8',
    };
    const TIER_GLOW = {
        required:    'rgba(244,114,182,0.35)',
        recommended: 'rgba(96,165,250,0.30)',
        suggested:   'rgba(148,163,184,0.20)',
    };

    // Graph state
    let nodes = [], edges = [];
    let dragging = null, dragOffX = 0, dragOffY = 0;
    let selectedNode = null;
    let pan = { x: 0, y: 0 }, panStart = null, panBase = null;
    let scale = 1;
    const MIN_SCALE = 0.3, MAX_SCALE = 3;
    let animationId = null;
    let simRunning = false;

    function parseFKEdges(ddl, tableNames) {
        const edges = [];
        const tableSet = new Set(tableNames);
        // REFERENCES tablename(col)
        const re = /CREATE TABLE (\w+)\s*\([\s\S]*?FOREIGN KEY \((\w+)\)\s+REFERENCES (\w+)\s*\(/gi;
        let m;
        while ((m = re.exec(ddl)) !== null) {
            const from = m[1], to = m[3];
            if (tableSet.has(from) && tableSet.has(to)) {
                edges.push({ from, to, col: m[2] });
            }
        }
        return edges;
    }

    function layoutNodes(nodeList, w, h) {
        // Group by tier priority, lay out in layers
        const tierOrder = { required: 0, recommended: 1, suggested: 2 };
        const groups = [[], [], []];
        nodeList.forEach(n => { groups[tierOrder[n.tier] ?? 1].push(n); });

        const layerH = h / (groups.length + 1);
        groups.forEach((group, gi) => {
            const y = layerH * (gi + 1);
            group.forEach((n, i) => {
                n.x = (w / (group.length + 1)) * (i + 1);
                n.y = y;
                n.vx = 0; n.vy = 0;
            });
        });
    }

    let physicsFrames = 0;

    function runPhysics() {
        if (!simRunning) return;
        physicsFrames++;

        const K    = 8000;   // repulsion
        const L    = 140;    // rest length
        const DAMP = 0.75;

        // Repulsion
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i+1; j < nodes.length; j++) {
                const a = nodes[i], b = nodes[j];
                let dx = b.x - a.x, dy = b.y - a.y;
                const dist = Math.sqrt(dx*dx+dy*dy) || 1;
                const f = K / (dist * dist);
                nodes[i].vx -= f * dx/dist;
                nodes[i].vy -= f * dy/dist;
                nodes[j].vx += f * dx/dist;
                nodes[j].vy += f * dy/dist;
            }
        }
        // Attraction along edges
        edges.forEach(e => {
            const a = nodes.find(n=>n.id===e.from);
            const b = nodes.find(n=>n.id===e.to);
            if (!a||!b) return;
            let dx = b.x-a.x, dy = b.y-a.y;
            const dist = Math.sqrt(dx*dx+dy*dy) || 1;
            const f = (dist-L)/dist * 0.06;
            a.vx += f*dx; a.vy += f*dy;
            b.vx -= f*dx; b.vy -= f*dy;
        });
        // Gravity to centre
        const cx = canvas.width/2, cy = canvas.height/2;
        nodes.forEach(n => {
            n.vx += (cx - n.x) * 0.004;
            n.vy += (cy - n.y) * 0.004;
        });
        // Integrate
        nodes.forEach(n => {
            if (n === dragging) return;
            n.vx *= DAMP; n.vy *= DAMP;
            n.x += n.vx; n.y += n.vy;
            // wall bounce
            const pad = 60;
            if (n.x < pad) { n.x = pad; n.vx = 0; }
            if (n.x > canvas.width-pad)  { n.x = canvas.width-pad;  n.vx = 0; }
            if (n.y < pad) { n.y = pad; n.vy = 0; }
            if (n.y > canvas.height-pad) { n.y = canvas.height-pad; n.vy = 0; }
        });
        if (physicsFrames > 300) simRunning = false;
    }

    function drawGraph() {
        const ctx = canvas.getContext('2d');
        const W = canvas.width, H = canvas.height;

        ctx.clearRect(0, 0, W, H);

        ctx.save();
        ctx.translate(pan.x, pan.y);
        ctx.scale(scale, scale);

        // Draw edges
        edges.forEach(e => {
            const a = nodes.find(n=>n.id===e.from);
            const b = nodes.find(n=>n.id===e.to);
            if (!a||!b) return;

            const isHighlighted = !selectedNode || selectedNode === a.id || selectedNode === b.id;
            const alpha = isHighlighted ? 0.7 : 0.12;

            // Arrow
            const dx = b.x-a.x, dy = b.y-a.y;
            const dist = Math.sqrt(dx*dx+dy*dy)||1;
            const ux = dx/dist, uy = dy/dist;
            const nodeR = 30;
            const sx = a.x + ux*nodeR, sy = a.y + uy*nodeR;
            const ex = b.x - ux*(nodeR+6), ey = b.y - uy*(nodeR+6);

            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.lineTo(ex, ey);
            const grad = ctx.createLinearGradient(sx, sy, ex, ey);
            grad.addColorStop(0, `rgba(99,102,241,${alpha})`);
            grad.addColorStop(1, `rgba(167,139,250,${alpha})`);
            ctx.strokeStyle = grad;
            ctx.lineWidth = isHighlighted ? 1.8 : 0.9;
            ctx.setLineDash(isHighlighted ? [] : [4,4]);
            ctx.stroke();
            ctx.setLineDash([]);

            // Arrowhead
            const angle = Math.atan2(ey-sy, ex-sx);
            ctx.beginPath();
            ctx.moveTo(ex, ey);
            ctx.lineTo(ex - 9*Math.cos(angle-0.4), ey - 9*Math.sin(angle-0.4));
            ctx.lineTo(ex - 9*Math.cos(angle+0.4), ey - 9*Math.sin(angle+0.4));
            ctx.closePath();
            ctx.fillStyle = `rgba(167,139,250,${alpha})`;
            ctx.fill();

            // Label (col name)
            if (isHighlighted && e.col) {
                const mx = (sx+ex)/2, my = (sy+ey)/2;
                ctx.save();
                ctx.font = '9px JetBrains Mono, monospace';
                ctx.fillStyle = `rgba(100,116,139,${alpha})`;
                ctx.textAlign = 'center';
                ctx.fillText(e.col, mx, my-5);
                ctx.restore();
            }
        });

        // Draw nodes
        nodes.forEach(n => {
            const selected   = n.id === selectedNode;
            const dimmed     = selectedNode && !selected
                && !edges.some(e => (e.from===n.id&&e.to===selectedNode)||(e.to===n.id&&e.from===selectedNode)||(e.from===selectedNode&&e.to===n.id)||(e.to===selectedNode&&e.from===n.id));
            const r = 30;
            const color = TIER_COLOR[n.tier] || '#94a3b8';
            const glow  = TIER_GLOW[n.tier]  || 'rgba(148,163,184,0.2)';

            // Glow
            if (!dimmed) {
                const radGrad = ctx.createRadialGradient(n.x, n.y, r*0.5, n.x, n.y, r*2.5);
                radGrad.addColorStop(0, glow);
                radGrad.addColorStop(1, 'transparent');
                ctx.beginPath();
                ctx.arc(n.x, n.y, r*2.5, 0, Math.PI*2);
                ctx.fillStyle = radGrad;
                ctx.fill();
            }

            // Node circle
            ctx.beginPath();
            ctx.arc(n.x, n.y, r, 0, Math.PI*2);
            const fill = ctx.createRadialGradient(n.x-r*0.3, n.y-r*0.3, 0, n.x, n.y, r);
            fill.addColorStop(0, dimmed ? 'rgba(20,25,40,0.5)' : 'rgba(20,25,50,0.92)');
            fill.addColorStop(1, dimmed ? 'rgba(10,12,20,0.4)' : 'rgba(7,11,25,0.85)');
            ctx.fillStyle = fill;
            ctx.fill();

            // Border
            ctx.beginPath();
            ctx.arc(n.x, n.y, r, 0, Math.PI*2);
            ctx.strokeStyle = dimmed ? 'rgba(100,116,139,0.2)' : (selected ? '#fff' : color);
            ctx.lineWidth   = selected ? 2.5 : 1.5;
            if (dimmed) ctx.globalAlpha = 0.35;
            ctx.stroke();
            ctx.globalAlpha = 1;

            // Label
            ctx.save();
            ctx.font = `${selected?600:500} 10px Inter, sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = dimmed ? 'rgba(148,163,184,0.3)' : (selected ? '#fff' : color);
            const label = n.id.length > 11 ? n.id.slice(0,10)+'…' : n.id;
            ctx.fillText(label, n.x, n.y);
            ctx.restore();
        });

        ctx.restore();
    }

    function graphLoop() {
        runPhysics();
        drawGraph();
        animationId = requestAnimationFrame(graphLoop);
    }

    function renderGraph(data) {
        if (animationId) cancelAnimationFrame(animationId);
        nodes = []; edges = [];

        const tableMap = {};
        (data.explainability || []).forEach(row => {
            tableMap[row.table] = row.tier;
        });

        nodes = Object.entries(tableMap).map(([id, tier]) => ({
            id, tier, x: 0, y: 0, vx: 0, vy: 0,
        }));

        edges = parseFKEdges(data.ddl || '', Object.keys(tableMap));

        // Size canvas
        const rect = graphContainer.getBoundingClientRect();
        canvas.width  = rect.width  || 900;
        canvas.height = rect.height || 560;

        pan   = { x: 0, y: 0 };
        scale = 1;
        selectedNode = null;
        physicsFrames = 0;
        simRunning = true;

        layoutNodes(nodes, canvas.width, canvas.height);
        graphLoop();
    }

    /* ── Graph interaction ─────────────────────────── */
    function canvasXY(e) {
        const rect = canvas.getBoundingClientRect();
        const cx = (e.clientX ?? e.touches[0].clientX) - rect.left;
        const cy = (e.clientY ?? e.touches[0].clientY) - rect.top;
        return { x: (cx - pan.x) / scale, y: (cy - pan.y) / scale };
    }

    function hitNode(worldX, worldY) {
        return nodes.find(n => Math.hypot(n.x - worldX, n.y - worldY) < 32);
    }

    canvas.addEventListener('mousedown', e => {
        const { x, y } = canvasXY(e);
        const hit = hitNode(x, y);
        if (hit) {
            dragging = hit;
            dragOffX = x - hit.x;
            dragOffY = y - hit.y;
            selectedNode = hit.id;
            simRunning   = true;
            physicsFrames = 0;
        } else {
            panStart = { x: e.clientX, y: e.clientY };
            panBase  = { ...pan };
            dragging = null;
        }
        e.preventDefault();
    });

    window.addEventListener('mousemove', e => {
        if (dragging) {
            const { x, y } = canvasXY(e);
            dragging.x = x - dragOffX;
            dragging.y = y - dragOffY;
            dragging.vx = 0; dragging.vy = 0;
        } else if (panStart) {
            pan.x = panBase.x + (e.clientX - panStart.x);
            pan.y = panBase.y + (e.clientY - panStart.y);
        } else {
            // Hover tooltip
            const { x, y } = canvasXY(e);
            const hit = hitNode(x, y);
            if (hit) {
                const fkOuts = edges.filter(e => e.from === hit.id);
                const fkIns  = edges.filter(e => e.to   === hit.id);
                graphTooltip.innerHTML = `
                    <strong style="color:${TIER_COLOR[hit.tier]||'#fff'}">${hit.id}</strong><br>
                    <span style="color:var(--text-lo);font-size:0.73rem;text-transform:uppercase;letter-spacing:0.05em;">${hit.tier}</span>
                    ${fkOuts.length ? `<br><span style="color:#64748b">→ </span>${fkOuts.map(e=>e.to).join(', ')}` : ''}
                    ${fkIns.length  ? `<br><span style="color:#64748b">← </span>${fkIns.map(e=>e.from).join(', ')}` : ''}
                `;
                const rect = graphContainer.getBoundingClientRect();
                const cRect = canvas.getBoundingClientRect();
                let tx = e.clientX - rect.left + 16;
                let ty = e.clientY - rect.top  - 10;
                if (tx + 230 > rect.width)  tx -= 250;
                if (ty + 100 > rect.height) ty -= 100;
                graphTooltip.style.left = tx + 'px';
                graphTooltip.style.top  = ty + 'px';
                graphTooltip.classList.remove('hidden');
            } else {
                graphTooltip.classList.add('hidden');
            }
        }
    });

    window.addEventListener('mouseup', () => {
        dragging = null;
        panStart = null;
    });

    canvas.addEventListener('click', e => {
        if (panStart) return; // was panning
        const { x, y } = canvasXY(e);
        const hit = hitNode(x, y);
        selectedNode = hit ? (selectedNode === hit.id ? null : hit.id) : null;
    });

    // Scroll to zoom
    canvas.addEventListener('wheel', e => {
        e.preventDefault();
        const factor = e.deltaY < 0 ? 1.12 : 0.88;
        const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        pan.x = mx - (mx - pan.x) * (newScale / scale);
        pan.y = my - (my - pan.y) * (newScale / scale);
        scale = newScale;
    }, { passive: false });

    // Zoom buttons
    zoomInBtn.addEventListener('click',  () => { scale = Math.min(MAX_SCALE, scale * 1.2); });
    zoomOutBtn.addEventListener('click', () => { scale = Math.max(MIN_SCALE, scale * 0.83); });
    resetBtn.addEventListener('click',   () => {
        scale = 1; pan = { x: 0, y: 0 }; selectedNode = null;
        physicsFrames = 0; simRunning = true;
        if (lastData) layoutNodes(nodes, canvas.width, canvas.height);
    });

    // Resize observer
    const ro = new ResizeObserver(() => {
        if (!lastData) return;
        const rect = graphContainer.getBoundingClientRect();
        canvas.width  = rect.width;
        canvas.height = rect.height;
    });
    ro.observe(graphContainer);

});
