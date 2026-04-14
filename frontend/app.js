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

    // Auto-resize textarea
    inputField.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
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

        // 5. Generate ER Diagram
        generateERDiagram(data);

        // Show section
        resultsSection.classList.remove('hidden');
        
        // Scroll into view gently
        setTimeout(() => {
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }
});

// ========================================
// TOAST NOTIFICATION HELPER
// ========================================
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ========================================
// SQL EXPORT FUNCTIONS
// ========================================
function copyToClipboard() {
    const sqlElement = document.getElementById('sql-output');
    if (!sqlElement || !sqlElement.textContent) {
        showToast('❌ No SQL generated yet');
        return;
    }
    
    const sql = sqlElement.textContent;
    navigator.clipboard.writeText(sql).then(() => {
        showToast('✅ SQL copied to clipboard!');
    }).catch(() => {
        showToast('❌ Failed to copy');
    });
}

function downloadSQL() {
    const sqlElement = document.getElementById('sql-output');
    if (!sqlElement || !sqlElement.textContent) {
        showToast('❌ No SQL generated yet');
        return;
    }
    
    const sql = sqlElement.textContent;
    const blob = new Blob([sql], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `schema_${new Date().getTime()}.sql`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('✅ SQL downloaded!');
}

function downloadMigration() {
    const sqlElement = document.getElementById('sql-output');
    if (!sqlElement || !sqlElement.textContent) {
        showToast('❌ No SQL generated yet');
        return;
    }
    
    const sql = sqlElement.textContent;
    const timestamp = new Date().toISOString().split('T')[0];
    const migration = `-- SchemaAdvisor Auto-Generated Migration
-- Generated: ${new Date().toISOString()}
-- This migration was automatically generated from business requirements

BEGIN;

${sql}

COMMIT;
`;
    
    const blob = new Blob([migration], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `migration_${timestamp}.sql`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('✅ Migration file downloaded!');
}

// ========================================
// ER DIAGRAM GENERATION
// ========================================
function generateERDiagram(data) {
    if (!data || !data.schema || !data.schema.tables || data.schema.tables.length === 0) {
        console.warn('No schema data for diagram');
        return;
    }
    
    const schema = data.schema;
    let mermaidCode = 'erDiagram\n';
    
    // Add entities (tables)
    schema.tables.forEach(table => {
        mermaidCode += `  ${table.name} {\n`;
        table.columns.forEach(col => {
            const type = col.data_type.toUpperCase().substring(0, 10);
            const pk = col.constraints && col.constraints.includes('PRIMARY KEY') ? ' PK' : '';
            const fk = col.constraints && col.constraints.includes('FOREIGN KEY') ? ' FK' : '';
            mermaidCode += `    ${type} ${col.name}${pk}${fk}\n`;
        });
        mermaidCode += '  }\n';
    });
    
    // Add relationships (foreign keys)
    schema.tables.forEach(table => {
        if (table.foreign_keys && table.foreign_keys.length > 0) {
            table.foreign_keys.forEach(fk => {
                mermaidCode += `${table.name} ||--o| ${fk.referenced_table} : "${fk.constraint_name}"\n`;
            });
        }
    });
    
    // Render diagram
    const diagramSection = document.getElementById('diagram-section');
    const diagramElement = document.getElementById('er-diagram');
    
    if (diagramElement && diagramSection) {
        diagramElement.textContent = mermaidCode;
        diagramSection.style.display = 'block';
        
        // Re-render Mermaid
        if (window.mermaid) {
            mermaid.contentLoaded();
        }
    }
}

// ========================================
// DECISION PRESETS
// ========================================
const PRESETS = {
    ecommerce: {
        name: '🛒 E-Commerce',
        description: 'Orders, inventory, audit trail',
        decisions: {
            audit: 'true',
            versioned: 'true',
            soft_delete: 'true',
            sharding: 'false',
            multi_tenant: 'false',
            nested_set: 'false'
        }
    },
    saas: {
        name: '☁️ SaaS Multi-Tenant',
        description: 'Multi-tenant, audit, security-focused',
        decisions: {
            multi_tenant: 'true',
            tenancy_model: 'multi_tenant',
            audit: 'true',
            soft_delete: 'true',
            versioned: 'false',
            nested_set: 'false'
        }
    },
    analytics: {
        name: '📊 Analytics',
        description: 'Denormalized, fast queries, minimal overhead',
        decisions: {
            denormalization: 'true',
            soft_delete: 'false',
            audit: 'false',
            nested_set: 'false',
            versioned: 'false',
            multi_tenant: 'false'
        }
    },
    lean: {
        name: '⚡ Lean Startup',
        description: 'Minimal schema, maximum flexibility',
        decisions: {
            audit: 'false',
            versioned: 'false',
            soft_delete: 'false',
            sharding: 'false',
            multi_tenant: 'false',
            nested_set: 'false'
        }
    }
};

function applyPreset(presetKey) {
    const preset = PRESETS[presetKey];
    if (!preset) {
        showToast('❌ Preset not found');
        return;
    }
    
    Object.entries(preset.decisions).forEach(([key, value]) => {
        const input = document.querySelector(`input[name="${key}"], select[name="${key}"]`);
        if (input) {
            if (input.type === 'radio') {
                const radio = document.querySelector(`input[name="${key}"][value="${value}"]`);
                if (radio) radio.checked = true;
            } else if (input.type === 'checkbox') {
                input.checked = value === 'true';
            } else {
                input.value = value;
            }
        }
    });
    
    showToast(`✅ Applied ${preset.name}`);
}
