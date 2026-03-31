document.addEventListener('DOMContentLoaded', () => {
    const inputField = document.getElementById('prompt-input');
    const generateBtn = document.getElementById('generate-btn');
    const btnText = document.querySelector('.btn-text');
    const btnLoader = document.querySelector('.btn-loader');
    const errorMsg = document.getElementById('error-message');
    
    const resultsSection = document.getElementById('results-section');
    const sqlOutput = document.getElementById('sql-output');
    const tbody = document.getElementById('explain-tbody');
    const badge = document.getElementById('validation-badge');
    const creationOrderVal = document.getElementById('creation-order-val');
    const copySqlBtn = document.getElementById('copy-sql-btn');

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
                copyIcon.textContent = '⍘';
                copyText.textContent = 'Copy';
                copySqlBtn.classList.remove('copy-btn--success');
            }, 2000);
        } catch (err) {
            console.error('Copy failed:', err);
        }
    });

    generateBtn.addEventListener('click', async () => {
        const reqText = inputField.value.trim();
        if (!reqText) return;

        // Set Loading State
        generateBtn.disabled = true;
        btnText.textContent = 'Generating...';
        btnLoader.classList.remove('hidden');
        errorMsg.classList.add('hidden');
        resultsSection.classList.add('hidden');
        
        try {
            const response = await fetch('/schema', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ requirements: reqText })
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
            // Unset Loading State
            generateBtn.disabled = false;
            btnText.textContent = 'Generate Schema';
            btnLoader.classList.add('hidden');
        }
    });

    function renderResults(data) {
        // 1. Render SQL
        sqlOutput.textContent = data.ddl;
        // Apply Prism.js syntax highlighting
        if (typeof Prism !== 'undefined') {
            Prism.highlightElement(sqlOutput);
        }

        // 2. Render Validation Badge
        badge.className = 'badge';
        if (data.validation.skipped) {
            badge.textContent = 'Unvalidated (No DB)';
            badge.classList.add('badge-info');
        } else if (data.validation.success === data.validation.total && data.validation.total > 0) {
            badge.textContent = `Valid (${data.validation.success}/${data.validation.total})`;
            badge.classList.add('badge-success');
        } else {
            badge.textContent = `Failed (${data.validation.success}/${data.validation.total})`;
            badge.classList.add('badge-error');
        }

        // 3. Render Explainability Table
        tbody.innerHTML = '';
        data.explainability.forEach(row => {
            const tr = document.createElement('tr');
            
            // Tier coloring
            const tierClass = `tier-${row.tier}`;
            
            // Triggered formatting
            const triggers = row.triggered_by.map(t => `<span style="background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px;margin-right:4px;">${t}</span>`).join('');

            tr.innerHTML = `
                <td style="font-family:'JetBrains Mono',monospace;">${row.table}</td>
                <td class="${tierClass}">${row.tier}</td>
                <td>${(row.confidence * 100).toFixed(0)}%</td>
                <td style="font-size:0.8rem;">${triggers}</td>
            `;
            tbody.appendChild(tr);
        });

        // 4. Render Creation Order
        creationOrderVal.textContent = data.creation_order.join(' → ');

        // Show section
        resultsSection.classList.remove('hidden');
        
        // Scroll into view gently
        setTimeout(() => {
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }
});
