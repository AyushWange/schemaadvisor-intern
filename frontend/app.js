document.addEventListener('DOMContentLoaded', () => {
    const inputField       = document.getElementById('prompt-input');
    const generateBtn      = document.getElementById('generate-btn');
    const btnText          = document.querySelector('.btn-text');
    const btnLoader        = document.querySelector('.btn-loader');
    const errorMsg         = document.getElementById('error-message');
    const resultsSection   = document.getElementById('results-section');
    const discoverySection = document.getElementById('discovery-section');
    const discoveryCards   = document.getElementById('discovery-cards');
    const sqlOutput        = document.getElementById('sql-output');
    const tbody            = document.getElementById('explain-tbody');
    const badge            = document.getElementById('validation-badge');
    const creationOrderVal = document.getElementById('creation-order-val');
    const copySqlBtn       = document.getElementById('copy-sql-btn');

    // Auto-resize textarea
    inputField.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    // Copy SQL to clipboard
    copySqlBtn.addEventListener('click', async () => {
        const sql = sqlOutput.textContent;
        if (!sql) return;
        try {
            await navigator.clipboard.writeText(sql);
            const copyText = copySqlBtn.querySelector('.copy-text');
            const copyIcon = copySqlBtn.querySelector('.copy-icon');
            copyIcon.textContent = '✓';
            copyText.textContent = 'Copied!';
            copySqlBtn.classList.add('copy-btn--success');
            setTimeout(() => {
                copyIcon.textContent = '⎘';
                copyText.textContent = 'Copy';
                copySqlBtn.classList.remove('copy-btn--success');
            }, 2000);
        } catch (err) {
            console.error('Copy failed:', err);
        }
    });

    // Generate button
    generateBtn.addEventListener('click', async () => {
        const reqText = inputField.value.trim();
        if (!reqText) return;

        generateBtn.disabled = true;
        btnText.textContent  = 'Generating...';
        btnLoader.classList.remove('hidden');
        errorMsg.classList.add('hidden');
        resultsSection.classList.add('hidden');
        discoverySection.classList.add('hidden');

        try {
            const response = await fetch('/schema', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ requirements: reqText }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to extract concepts. Try rephrasing.');
            }

            renderResults(data);

        } catch (err) {
            errorMsg.textContent = err.message;
            errorMsg.classList.remove('hidden');
        } finally {
            generateBtn.disabled = false;
            btnText.textContent  = 'Generate Schema';
            btnLoader.classList.add('hidden');
        }
    });

    // ── Render all results ────────────────────────────────────────────────────
    function renderResults(data) {

        // 1. SQL with syntax highlighting
        sqlOutput.textContent = data.ddl;
        if (typeof Prism !== 'undefined') Prism.highlightElement(sqlOutput);

        // 2. Validation badge
        badge.className = 'badge';
        const v = data.validation || {};
        if (v.skipped) {
            badge.textContent = 'Unvalidated (No DB)';
            badge.classList.add('badge-info');
        } else if (v.success === v.total && v.total > 0) {
            badge.textContent = `Valid (${v.success}/${v.total})`;
            badge.classList.add('badge-success');
        } else {
            badge.textContent = `Failed (${v.success}/${v.total})`;
            badge.classList.add('badge-error');
        }

        // 3. Explainability table
        tbody.innerHTML = '';
        (data.explainability || []).forEach(row => {
            const tr        = document.createElement('tr');
            const tierClass = `tier-${row.tier}`;
            const triggers  = (row.triggered_by || []).map(t =>
                `<span style="background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px;margin-right:4px;">${t}</span>`
            ).join('');
            const patterns  = (row.patterns || []).map(p =>
                `<span style="background:rgba(99,202,183,0.15);color:#63cab7;padding:1px 5px;border-radius:3px;font-size:0.75rem;margin-right:3px;">${p}</span>`
            ).join('');
            tr.innerHTML = `
                <td style="font-family:'JetBrains Mono',monospace;">${row.table}</td>
                <td class="${tierClass}">${row.tier}</td>
                <td>${((row.confidence || 0) * 100).toFixed(0)}%</td>
                <td style="font-size:0.8rem;">${triggers}${patterns}</td>
            `;
            tbody.appendChild(tr);
        });

        // 4. Creation order
        creationOrderVal.textContent = (data.creation_order || []).join(' → ');

        // 5. Active decisions (shown below creation order if any non-default)
        const metaDiv  = document.querySelector('.pipeline-meta');
        const existing = document.getElementById('decisions-row');
        if (existing) existing.remove();
        const decisions = data.active_decisions || {};
        if (Object.keys(decisions).length > 0) {
            const chips = Object.entries(decisions)
                .map(([k, v]) =>
                    `<span style="background:rgba(255,180,50,0.15);color:#ffb432;padding:2px 7px;border-radius:4px;margin-right:5px;font-size:0.8rem;">${k}=${v}</span>`
                ).join('');
            const row   = document.createElement('p');
            row.id      = 'decisions-row';
            row.innerHTML = `<strong>Active Decisions:</strong> ${chips}`;
            metaDiv.appendChild(row);
        }

        // Show results section
        resultsSection.classList.remove('hidden');

        // 6. Discovery Cards
        renderDiscoveryCards(data.unmatched || []);

        setTimeout(() => resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    }

    // ── Discovery Cards (spec §8.6) ───────────────────────────────────────────
    function renderDiscoveryCards(unmatched) {
        discoveryCards.innerHTML = '';

        const potentialTables = (unmatched || []).filter(u => u.category === 'potential_table');

        if (potentialTables.length === 0) {
            discoverySection.classList.add('hidden');
            return;
        }

        const icons = { potential_table: '🗃️', potential_column: '📋', unsupported_logic: '⚙️' };

        potentialTables.forEach(item => {
            const card = document.createElement('div');
            card.className = 'discovery-card';

            const nearestHtml = item.nearest_concept
                ? `<div class="discovery-nearest">💡 Nearest known concept: <strong>${item.nearest_concept.replace(/_/g, ' ')}</strong></div>`
                : `<div class="discovery-nearest">💡 No similar concept found — candidate for new taxonomy</div>`;

            card.innerHTML = `
                <div class="discovery-header">
                    <span class="discovery-icon">${icons[item.category] || '❓'}</span>
                    <span class="discovery-raw">${item.raw_text}</span>
                    <span class="discovery-category">${item.category.replace(/_/g, ' ')}</span>
                </div>
                ${nearestHtml}
                <div class="discovery-footer">
                    <span class="discovery-logged">✓ Logged to Neo4j for review</span>
                </div>
            `;
            discoveryCards.appendChild(card);
        });

        discoverySection.classList.remove('hidden');
        setTimeout(() => discoverySection.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 200);
    }
});
