import { patch } from "@web/core/utils/patch";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched } from "@odoo/owl";

(function _injectStyles() {
    if (document.getElementById("cf-complete-styles")) return;
    const s = document.createElement("style");
    s.id = "cf-complete-styles";
    s.textContent = `
        .o_competency_template_form [name="group_ids"] th[data-name="hr_code"],
        .o_competency_template_form [name="group_ids"] td[name="hr_code"],
        .o_dialog [name="line_ids"] th[data-name="full_code"],
        .o_dialog [name="line_ids"] td[name="full_code"] {
            display: none !important;
        }
        .cf-add-line-blocked {
            opacity: 0.4 !important;
            cursor: not-allowed !important;
            pointer-events: none !important;
        }
        .cf-dialog-save-blocked {
            opacity: 0.5 !important;
            cursor: not-allowed !important;
            pointer-events: none !important;
            background-color: #fecaca !important;
        }
        .cf-points-violation {
            border: 2px solid #dc2626 !important;
            background-color: #fef2f2 !important;
        }
        .cf-ceiling-status-bar {
            padding: 8px 12px;
            border-radius: 6px;
            margin: 8px 0;
            font-size: 0.82em;
            font-weight: 600;
        }
        .cf-ceiling-full { background: #fef2f2; border: 1px solid #fca5a5; color: #991b1b; }
        .cf-ceiling-warn { background: #fffbeb; border: 1px solid #fde047; color: #854d0e; }
        .cf-ceiling-ok   { background: #f0fdf4; border: 1px solid #86efac; color: #14532d; }
        .cf-save-btn-blocked,
        body.cf-alloc-invalid .o_control_panel .o_form_button_save,
        body.cf-alloc-invalid .o_cp_buttons .o_form_button_save {
            opacity: 0.45 !important;
            cursor: not-allowed !important;
            pointer-events: none !important;
            background-color: #fca5a5 !important;
            border-color: #ef4444 !important;
            color: #7f1d1d !important;
        }
        .cf-alloc-banner {
            display: flex; flex-wrap: wrap; align-items: center;
            gap: 12px; padding: 12px 16px; margin: 12px 0;
            border-radius: 6px; font-weight: 600; font-size: 0.88em;
        }
        .cf-alloc-bad  { background: #fee2e2; border: 2px solid #dc2626; color: #991b1b; }
        .cf-alloc-ok   { background: #d1fae5; border: 1px solid #34d399; color: #065f46; }
        .cf-export-bar { display: flex; gap: 8px; margin: 10px 0; padding: 8px 0; }
        .cf-export-btn {
            display: inline-flex; align-items: center; gap: 6px;
            padding: 7px 16px; border-radius: 6px; font-weight: 600;
            font-size: 0.85em; cursor: pointer; border: none; transition: opacity 0.15s;
        }
        .cf-export-btn:hover { opacity: 0.85; }
        .cf-export-btn-pdf   { background: #1a3c5e; color: #fff; }
        .cf-export-btn-excel { background: #15803d; color: #fff; }
        .cf-appraisal-progress-wrap { margin-top: 6px; }
        .cf-progress-track {
            height: 8px; border-radius: 4px; background: #e2e8f0;
            overflow: hidden; margin-bottom: 4px;
        }
        .cf-progress-fill {
            height: 100%; border-radius: 4px;
            transition: width 0.3s ease, background-color 0.3s ease;
        }
        .cf-progress-fill.kpi-fill  { background: #3b82f6; }
        .cf-progress-fill.comp-fill { background: #10b981; }
        .cf-progress-fill.over-fill { background: #ef4444; }
        .cf-progress-label { font-size: 0.78em; font-weight: 600; color: #64748b; }
        .cf-progress-label.exact { color: #059669; }
        .cf-progress-label.over  { color: #dc2626; }
        .cf-progress-label.under { color: #d97706; }
    `;
    document.head.appendChild(s);
})();

const TOLERANCE = 0.01;
const DEFAULT_CEILING = 16.0;

function _readFieldNum(root, fieldName) {
    const widget = root.querySelector(`[name="${fieldName}"]`);
    if (!widget) return null;
    const input = widget.querySelector('input');
    if (input) {
        const v = parseFloat((input.value || '').replace(/,/g, ''));
        return isNaN(v) ? null : v;
    }
    const span = widget.querySelector('span.o_field_widget, span[class*="o_field"]') || widget.querySelector('span');
    if (span) {
        const v = parseFloat((span.textContent || '').replace(/,/g, ''));
        return isNaN(v) ? null : v;
    }
    return null;
}

function getTemplateAllocation() {
    const form = document.querySelector('.o_competency_template_form');
    if (!form) return { ceiling: DEFAULT_CEILING, total: 0 };
    let ceiling = _readFieldNum(form, 'competency_ceiling');
    if (ceiling === null || ceiling <= 0) {
        const ppWidget = form.querySelector('[name="points_progress"]');
        if (ppWidget) {
            const m = (ppWidget.textContent || '').match(/([\d.,]+)\s*\/\s*([\d.,]+)/);
            if (m) ceiling = parseFloat(m[2].replace(/,/g, '')) || DEFAULT_CEILING;
        }
    }
    if (!ceiling || ceiling <= 0) ceiling = DEFAULT_CEILING;
    let total = 0;
    form.querySelectorAll('[name="group_ids"] .o_data_row td[name="points"]').forEach(cell => {
        const inp = cell.querySelector('input');
        total += parseFloat(((inp ? inp.value : cell.textContent) || '0').replace(/,/g, '')) || 0;
    });
    return { ceiling, total: Math.round(total * 100) / 100 };
}

function _appraisalFieldNum(form, fieldName) {
    const widget = form.querySelector(`[name="${fieldName}"]`);
    if (!widget) return null;
    const inp = widget.querySelector('input');
    if (inp) {
        const v = parseFloat((inp.value || '').replace(/,/g, ''));
        return isNaN(v) ? null : v;
    }
    const v = parseFloat((widget.textContent || '').trim().replace(/,/g, ''));
    return isNaN(v) ? null : v;
}

function _upsertProgressBar(anchor, id, current, total, fillClass, label) {
    if (!anchor) return;
    let wrap = document.getElementById(id);
    if (!wrap) {
        wrap = document.createElement('div');
        wrap.id = id;
        wrap.className = 'cf-appraisal-progress-wrap';
        wrap.innerHTML = `<div class="cf-progress-track"><div class="cf-progress-fill ${fillClass}" style="width:0%"></div></div><div class="cf-progress-label"></div>`;
        anchor.parentNode.insertBefore(wrap, anchor.nextSibling);
    }
    const fill = wrap.querySelector('.cf-progress-fill');
    const lbl  = wrap.querySelector('.cf-progress-label');
    if (!total || total <= 0) {
        fill.style.width = '0%';
        lbl.textContent  = `${label}: — / —`;
        lbl.className    = 'cf-progress-label';
        return;
    }
    const isOver  = current > total + TOLERANCE;
    const isExact = Math.abs(current - total) <= TOLERANCE;
    fill.style.width = `${Math.min((current / total) * 100, 100)}%`;
    fill.className   = `cf-progress-fill ${isOver ? 'over-fill' : fillClass}`;
    const diff = Math.abs(current - total).toFixed(2);
    if (isExact) {
        lbl.textContent = `✅ ${label}: ${current.toFixed(2)} / ${total.toFixed(2)} — Fully allocated`;
        lbl.className   = 'cf-progress-label exact';
    } else if (isOver) {
        lbl.textContent = `${label}: ${current.toFixed(2)} / ${total.toFixed(2)} — Over by ${diff} pts`;
        lbl.className   = 'cf-progress-label over';
    } else {
        lbl.textContent = `${label}: ${current.toFixed(2)} / ${total.toFixed(2)} — ${diff} pts remaining`;
        lbl.className   = 'cf-progress-label under';
    }
}

function updateAppraisalProgressBars() {
    const anyForm = [...document.querySelectorAll('.o_form_view')].find(f =>
        f.querySelector('[name="total_kpi_score"]') && f.querySelector('[name="kpi_weight"]')
    );
    if (!anyForm) return;
    _upsertProgressBar(
        anyForm.querySelector('[name="total_kpi_score"]'), 'cf-kpi-progress',
        _appraisalFieldNum(anyForm, 'total_kpi_score') || 0,
        _appraisalFieldNum(anyForm, 'kpi_weight') || 0,
        'kpi-fill', 'KPI'
    );
    _upsertProgressBar(
        anyForm.querySelector('[name="competency_total_hr_points"]'), 'cf-comp-progress',
        _appraisalFieldNum(anyForm, 'competency_total_hr_points') || 0,
        _appraisalFieldNum(anyForm, 'competency_weight') || 0,
        'comp-fill', 'Competency'
    );
}

function setupAppraisalFormObserver() {
    const anyForm = [...document.querySelectorAll('.o_form_view')].find(f =>
        f.querySelector('[name="total_kpi_score"]') && f.querySelector('[name="kpi_weight"]')
    );
    if (!anyForm || anyForm._cfAppraisalObserved) return;
    anyForm._cfAppraisalObserved = true;
    updateAppraisalProgressBars();
    const obs = new MutationObserver(() => {
        clearTimeout(anyForm._cfAppraisalTimer);
        anyForm._cfAppraisalTimer = setTimeout(updateAppraisalProgressBars, 80);
    });
    obs.observe(anyForm, { childList: true, subtree: true, characterData: true });
    const cp = document.querySelector('.o_control_panel');
    if (cp && !cp._cfAppraisalObserved) {
        cp._cfAppraisalObserved = true;
        new MutationObserver(() => setTimeout(updateAppraisalProgressBars, 80))
            .observe(cp, { childList: true, subtree: true });
    }
}

function getCurrentCeiling() {
    const dialog = document.querySelector('.o_dialog');
    if (dialog) {
        const tc = _readFieldNum(dialog, 'template_ceiling');
        if (tc !== null && tc > 0) return tc;
    }
    return getTemplateAllocation().ceiling;
}

function getLineSumFromDialog() {
    const dialog = document.querySelector('.o_dialog');
    if (!dialog) return 0;
    let sum = 0;
    dialog.querySelectorAll('.o_data_row td[name="points"]').forEach(cell => {
        const inp = cell.querySelector('input');
        sum += parseFloat(((inp ? inp.value : cell.textContent) || '0').replace(/,/g, '')) || 0;
    });
    return Math.round(sum * 100) / 100;
}

function getAllPointsInputs() {
    const dialog = document.querySelector('.o_dialog');
    if (!dialog) return [];
    return Array.from(dialog.querySelectorAll('.o_data_row td[name="points"] input'));
}

function updateAddLineButton(sum, ceiling) {
    const dialog = document.querySelector('.o_dialog');
    if (!dialog) return;
    const addBtn = dialog.querySelector('.o_field_x2many_list_row_add a, .o_field_x2many_list_row_add span');
    if (!addBtn) return;
    const reached = sum >= ceiling - TOLERANCE;
    addBtn.classList.toggle('cf-add-line-blocked', reached);
    addBtn.style.pointerEvents = reached ? 'none' : '';
}

function updateSaveButtons(sum, ceiling) {
    const dialog = document.querySelector('.o_dialog');
    if (!dialog) return;
    const canSave = Math.abs(sum - ceiling) <= TOLERANCE;
    dialog.querySelectorAll('.o_form_button_save, button[name="save_manually"], .btn-primary').forEach(btn => {
        const isSave = btn.textContent.toLowerCase().includes('save') ||
                       btn.classList.contains('o_form_button_save') ||
                       btn.getAttribute('name') === 'save_manually';
        if (!isSave) return;
        btn.classList.toggle('cf-dialog-save-blocked', !canSave);
        btn.disabled = !canSave;
    });
    const existing = dialog.querySelector('.cf-ceiling-status-bar');
    if (existing) existing.remove();
    const sheet = dialog.querySelector('.o_form_sheet');
    if (!sheet) return;
    const bar = document.createElement('div');
    bar.className = 'cf-ceiling-status-bar ' + (canSave ? 'cf-ceiling-ok' : (sum > ceiling ? 'cf-ceiling-full' : 'cf-ceiling-warn'));
    if (canSave) {
        bar.textContent = `✅ ${sum.toFixed(2)} / ${ceiling.toFixed(2)} — Ready to save`;
    } else if (sum > ceiling) {
        bar.textContent = `${sum.toFixed(2)} / ${ceiling.toFixed(2)} — Reduce by ${(sum - ceiling).toFixed(2)} pts`;
    } else {
        bar.textContent = `${sum.toFixed(2)} / ${ceiling.toFixed(2)} — ${(ceiling - sum).toFixed(2)} pts remaining`;
    }
    const ptsField = sheet.querySelector('.o_field_widget[name="points"]');
    if (ptsField && ptsField.parentNode) ptsField.parentNode.insertBefore(bar, ptsField.nextSibling);
    else sheet.appendChild(bar);
}

function updateTemplateUI() {
    const form = document.querySelector('.o_competency_template_form');
    if (!form) return;

    const skeletonField = form.querySelector('[name="is_skeleton"] input');
    const isSkeleton = skeletonField ? skeletonField.value === 'true' || skeletonField.checked : false;

    const { ceiling, total } = getTemplateAllocation();
    const isExact = Math.abs(total - ceiling) <= TOLERANCE;
    const shouldBlock = !isExact && !isSkeleton;

    const saveBtns = [
        ...document.querySelectorAll('.o_control_panel .o_form_button_save'),
        ...document.querySelectorAll('.o_cp_buttons .o_form_button_save'),
    ];
    const seen = new Set();
    saveBtns.filter(btn => { if (seen.has(btn)) return false; seen.add(btn); return true; })
    .forEach(btn => {
        if (!shouldBlock) {
            btn.removeAttribute('disabled');
            btn.classList.remove('cf-save-btn-blocked');
            btn.style.cssText = '';
            document.body.classList.remove('cf-alloc-invalid');
        } else {
            btn.setAttribute('disabled', 'disabled');
            btn.classList.add('cf-save-btn-blocked');
            btn.style.opacity = '0.45';
            btn.style.pointerEvents = 'none';
            btn.style.backgroundColor = '#fca5a5';
            btn.style.borderColor = '#ef4444';
            btn.style.color = '#7f1d1d';
            document.body.classList.add('cf-alloc-invalid');
        }
    });

    form.querySelectorAll('.cf-alloc-banner').forEach(el => el.remove());
    const sheet = form.querySelector('.o_form_sheet');
    if (!sheet) return;

    if (!isSkeleton) {
        const banner = document.createElement('div');
        if (!isExact) {
            banner.className = 'cf-alloc-banner cf-alloc-bad';
            const diff = Math.abs(total - ceiling).toFixed(2);
            banner.textContent = total < ceiling
                ? `${total.toFixed(2)} / ${ceiling.toFixed(2)} pts — ${diff} pts remaining to reach ceiling`
                : `${total.toFixed(2)} / ${ceiling.toFixed(2)} pts — reduce by ${diff} pts`;
        } else {
            banner.className = 'cf-alloc-banner cf-alloc-ok';
            banner.textContent = `✅ ${total.toFixed(2)} / ${ceiling.toFixed(2)} — Allocation complete`;
        }
        sheet.insertBefore(banner, sheet.firstChild);
    }
}

function autoCapLastLine() {
    const ceiling = getCurrentCeiling();
    const inputs  = getAllPointsInputs();
    if (!inputs.length) return;
    const lastInput = inputs[inputs.length - 1];
    let sumWithoutLast = 0;
    for (let i = 0; i < inputs.length - 1; i++) {
        sumWithoutLast += parseFloat((inputs[i].value || '').replace(/,/g, '')) || 0;
    }
    const maxForLast = Math.max(0, ceiling - sumWithoutLast);
    const currentVal = parseFloat((lastInput.value || '').replace(/,/g, '')) || 0;
    if (currentVal > maxForLast + TOLERANCE) {
        lastInput.value = maxForLast.toFixed(2);
        lastInput.classList.add('cf-points-violation');
        setTimeout(() => lastInput.classList.remove('cf-points-violation'), 2000);
        lastInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
}

function setupPointsValidation() {
    const inputs  = getAllPointsInputs();
    const ceiling = getCurrentCeiling();
    inputs.forEach(input => {
        if (input._cfWired) return;
        input._cfWired = true;
        const validate = () => {
            const allVals    = inputs.map(i => parseFloat((i.value || '').replace(/,/g, '')) || 0);
            const otherSum   = allVals.reduce((acc, v, idx) => inputs[idx] !== input ? acc + v : acc, 0);
            const maxAllowed = Math.max(0, ceiling - otherSum);
            const currentVal = parseFloat((input.value || '').replace(/,/g, '')) || 0;
            if (currentVal > maxAllowed + TOLERANCE) {
                input.value = maxAllowed.toFixed(2);
                input.classList.add('cf-points-violation');
                setTimeout(() => input.classList.remove('cf-points-violation'), 2000);
            }
            updateAddLineButton(getLineSumFromDialog(), ceiling);
            updateSaveButtons(getLineSumFromDialog(), ceiling);
        };
        input.addEventListener('input',  validate);
        input.addEventListener('change', validate);
        input.addEventListener('blur',   validate);
    });
}

function setupDialogObserver() {
    const dialog = document.querySelector('.o_dialog');
    if (!dialog || dialog._cfObserved) return;
    dialog._cfObserved = true;
    const refresh = () => {
        setupPointsValidation();
        autoCapLastLine();
        updateAddLineButton(getLineSumFromDialog(), getCurrentCeiling());
        updateSaveButtons(getLineSumFromDialog(), getCurrentCeiling());
    };
    new MutationObserver(() => setTimeout(refresh, 100))
        .observe(dialog, { childList: true, subtree: true, attributes: true });
    document.addEventListener('click', function cfAddLineGuard(e) {
        const addBtn = e.target.closest('.o_field_x2many_list_row_add a, .o_field_x2many_list_row_add span');
        if (addBtn && dialog.contains(addBtn)) {
            const sum = getLineSumFromDialog();
            const ceil = getCurrentCeiling();
            if (sum >= ceil - TOLERANCE) {
                e.preventDefault();
                e.stopImmediatePropagation();
                return false;
            }
        }
    }, true);
    setTimeout(refresh, 500);
}

function interceptDialogSave() {
    const dialog = document.querySelector('.o_dialog');
    if (!dialog || dialog._cfSaveIntercepted) return;
    dialog._cfSaveIntercepted = true;
    dialog.querySelectorAll('.o_form_button_save, button[name="save_manually"], .btn-primary').forEach(btn => {
        const clone = btn.cloneNode(true);
        btn.parentNode.replaceChild(clone, btn);
        clone.addEventListener('click', function(e) {
            autoCapLastLine();
            const sum     = getLineSumFromDialog();
            const ceiling = getCurrentCeiling();
            if (Math.abs(sum - ceiling) > TOLERANCE) {
                e.preventDefault();
                e.stopImmediatePropagation();
                const msg = sum > ceiling
                    ? `Cannot save — exceeds ceiling by ${(sum - ceiling).toFixed(2)} pts. Reduce to ${ceiling.toFixed(2)}.`
                    : `Cannot save — ${(ceiling - sum).toFixed(2)} pts remaining to reach ${ceiling.toFixed(2)}.`;
                alert(msg);
                return false;
            }
        });
    });
}

function _escapeHtml(text) {
    if (!text) return '';
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace('>', '&gt;').replace(/"/g, '&quot;');
}

function _escapeCSV(text) {
    if (text === null || text === undefined) return '""';
    return `"${String(text).replace(/"/g, '""')}"`;
}

function _getTemplateName() {
    const form = document.querySelector('.o_competency_template_form');
    if (!form) return 'Competency Template';
    const inp  = form.querySelector('[name="name"] input');
    if (inp && inp.value) return inp.value;
    const span = form.querySelector('[name="name"] span');
    return span ? span.textContent.trim() : 'Competency Template';
}

let jsPDFLoaded = false;
let autoTableLoaded = false;

function loadJsPDF() {
    return new Promise((resolve, reject) => {
        if (window.jspdf && window.jspdf.jsPDF && window.jspdf.autoTable) {
            jsPDFLoaded = true;
            autoTableLoaded = true;
            resolve();
            return;
        }
        const script1 = document.createElement('script');
        script1.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
        script1.onload = () => {
            const script2 = document.createElement('script');
            script2.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.31/jspdf.plugin.autotable.min.js';
            script2.onload = () => {
                if (window.jspdf && window.jspdf.jsPDF) {
                    jsPDFLoaded = true;
                    autoTableLoaded = true;
                    resolve();
                } else {
                    reject(new Error('Failed to load jsPDF'));
                }
            };
            script2.onerror = () => reject(new Error('Failed to load autoTable'));
            document.head.appendChild(script2);
        };
        script1.onerror = () => reject(new Error('Failed to load jsPDF'));
        document.head.appendChild(script1);
    });
}

async function exportToDirectPDF() {
    const form = document.querySelector('.o_competency_template_form');
    if (!form) { alert('Open the template form first.'); return; }
    
    const templateName = _getTemplateName();
    
    const tableHtmlWidget = form.querySelector('[name="competency_table_html"] .o_field_html, [name="competency_table_html"]');
    const rows = [];
    
    if (tableHtmlWidget && tableHtmlWidget.innerHTML) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(tableHtmlWidget.innerHTML, 'text/html');
        const table = doc.querySelector('table');
        if (table) {
            const tbody = table.querySelector('tbody');
            if (tbody) {
                for (const tr of tbody.querySelectorAll('tr')) {
                    const cells = tr.querySelectorAll('td');
                    if (cells.length >= 2) {
                        const colspan = parseInt(cells[0].getAttribute('colspan') || '1');
                        if (colspan >= 3 && cells.length === 2) {
                            rows.push({
                                type: 'group',
                                name: cells[0].textContent.trim(),
                                points: cells[1].textContent.trim()
                            });
                        } else if (colspan === 4) {
                            rows.push({
                                type: 'group_desc',
                                description: cells[0].textContent.replace(/Targets:/i, '').trim()
                            });
                        } else if (cells.length >= 4) {
                            rows.push({
                                type: 'line',
                                code: cells[0].textContent.trim(),
                                competency: cells[1].textContent.trim(),
                                targets: cells[2].textContent.trim(),
                                points: cells[3].textContent.trim()
                            });
                        }
                    }
                }
            }
            const tfoot = table.querySelector('tfoot');
            if (tfoot) {
                for (const tr of tfoot.querySelectorAll('tr')) {
                    const cells = tr.querySelectorAll('td');
                    if (cells.length >= 2) {
                        rows.push({ type: 'footer', label: cells[0].textContent.trim(), points: cells[1].textContent.trim() });
                    }
                }
            }
        }
    }
    
    if (rows.length === 0) {
        alert('No data to export.');
        return;
    }
    
    try {
        await loadJsPDF();
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
        
        doc.setFontSize(16);
        doc.setTextColor(26, 60, 94);
        doc.text(templateName, 14, 20);
        
        doc.setFontSize(9);
        doc.setTextColor(100, 116, 139);
        doc.text(`Generated: ${new Date().toLocaleString()}`, 14, 28);
        
        const headers = [['Sl. No', 'Competency / Group', 'Targets', 'Points']];
        const bodyRows = [];
        
        for (const row of rows) {
            if (row.type === 'group') {
                bodyRows.push([
                    { content: '', styles: { fontStyle: 'bold', fillColor: [26, 60, 94], textColor: [255, 255, 255] } },
                    { content: row.name, styles: { fontStyle: 'bold', fillColor: [26, 60, 94], textColor: [255, 255, 255] } },
                    { content: '', styles: { fillColor: [26, 60, 94], textColor: [255, 255, 255] } },
                    { content: row.points, styles: { fontStyle: 'bold', fillColor: [26, 60, 94], textColor: [255, 255, 255], halign: 'right' } }
                ]);
            } else if (row.type === 'group_desc') {
                bodyRows.push([
                    { content: '', styles: { fillColor: [26, 60, 94], textColor: [220, 220, 220], fontStyle: 'italic' } },
                    { content: '', styles: { fillColor: [26, 60, 94], textColor: [220, 220, 220], fontStyle: 'italic' } },
                    { content: row.description, styles: { fillColor: [26, 60, 94], textColor: [220, 220, 220], fontStyle: 'italic' } },
                    { content: '', styles: { fillColor: [26, 60, 94], textColor: [220, 220, 220] } }
                ]);
            } else if (row.type === 'line') {
                bodyRows.push([
                    row.code || '',
                    row.competency || '',
                    row.targets || '',
                    { content: row.points || '0.00', styles: { halign: 'right' } }
                ]);
            } else if (row.type === 'footer') {
                bodyRows.push([
                    { content: '', colSpan: 2, styles: { fillColor: [219, 234, 254], fontStyle: 'bold' } },
                    { content: row.label, styles: { fillColor: [219, 234, 254], fontStyle: 'bold' } },
                    { content: row.points, styles: { fillColor: [219, 234, 254], fontStyle: 'bold', halign: 'right' } }
                ]);
            }
        }
        
        doc.autoTable({
            head: headers,
            body: bodyRows,
            startY: 40,
            theme: 'striped',
            headStyles: { fillColor: [26, 60, 94], textColor: [255, 255, 255], fontStyle: 'bold', halign: 'center' },
            columnStyles: { 0: { cellWidth: 25, halign: 'center' }, 1: { cellWidth: 'auto' }, 2: { cellWidth: 'auto' }, 3: { cellWidth: 30, halign: 'right' } },
            margin: { left: 14, right: 14, top: 40 },
            pageBreak: 'auto'
        });
        
        const safeName = templateName.replace(/[^a-z0-9_\-]/gi, '_').substring(0, 50);
        doc.save(`${safeName}_competency_framework.pdf`);
    } catch (err) {
        console.error('PDF Export Error:', err);
        alert('PDF export failed. Please check console for details.');
    }
}

function exportToCleanCSV() {
    const form = document.querySelector('.o_competency_template_form');
    if (!form) { alert('Open the template form first.'); return; }
    
    const templateName = _getTemplateName();
    const csvRows = [];
    
    csvRows.push(`"${_escapeCSV(templateName)}"`);
    csvRows.push(`"Generated: ${new Date().toLocaleString()}"`);
    csvRows.push('');
    csvRows.push('"Sl. No","Competency / Group","Targets","Points"');
    
    const tableHtmlWidget = form.querySelector('[name="competency_table_html"] .o_field_html, [name="competency_table_html"]');
    if (tableHtmlWidget && tableHtmlWidget.innerHTML) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(tableHtmlWidget.innerHTML, 'text/html');
        const table = doc.querySelector('table');
        if (table) {
            const tbody = table.querySelector('tbody');
            if (tbody) {
                for (const tr of tbody.querySelectorAll('tr')) {
                    const cells = tr.querySelectorAll('td');
                    if (cells.length >= 2) {
                        const colspan = parseInt(cells[0].getAttribute('colspan') || '1');
                        if (colspan >= 3 && cells.length === 2) {
                            csvRows.push(`"","${_escapeCSV(cells[0].textContent.trim())}","","${_escapeCSV(cells[1].textContent.trim())}"`);
                        } else if (colspan === 4) {
                            csvRows.push(`"","","${_escapeCSV(cells[0].textContent.replace(/Targets:/i, '').trim())}",""`);
                        } else if (cells.length >= 4) {
                            csvRows.push(`"${_escapeCSV(cells[0].textContent.trim())}","${_escapeCSV(cells[1].textContent.trim())}","${_escapeCSV(cells[2].textContent.trim())}","${_escapeCSV(cells[3].textContent.trim())}"`);
                        }
                    }
                }
            }
            const tfoot = table.querySelector('tfoot');
            if (tfoot) {
                for (const tr of tfoot.querySelectorAll('tr')) {
                    const cells = tr.querySelectorAll('td');
                    if (cells.length >= 2) {
                        csvRows.push(`"","","${_escapeCSV(cells[0].textContent.trim())}","${_escapeCSV(cells[1].textContent.trim())}"`);
                    }
                }
            }
        }
    }
    
    const csvContent = csvRows.join('\r\n');
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${templateName.replace(/[^a-z0-9_\-]/gi, '_').substring(0, 50)}_competency.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function wireExportButtons() {
    const pdfBtn = document.querySelector('#cf-template-export-pdf');
    if (pdfBtn && !pdfBtn._cfDirectWired) {
        const newBtn = pdfBtn.cloneNode(true);
        pdfBtn.parentNode.replaceChild(newBtn, pdfBtn);
        newBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            exportToDirectPDF();
        });
        newBtn._cfDirectWired = true;
    }
    const excelBtn = document.querySelector('#cf-template-export-excel');
    if (excelBtn && !excelBtn._cfCleanWired) {
        const newExcelBtn = excelBtn.cloneNode(true);
        excelBtn.parentNode.replaceChild(newExcelBtn, excelBtn);
        newExcelBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            exportToCleanCSV();
        });
        newExcelBtn._cfCleanWired = true;
    }
}

function setupExportObserver() {
    const observer = new MutationObserver(() => {
        wireExportButtons();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    wireExportButtons();
}

function setupTemplateMonitor() {
    const form = document.querySelector('.o_competency_template_form');
    if (!form || form._cfMonitorActive) return;
    form._cfMonitorActive = true;
    updateTemplateUI();
    new MutationObserver(() => setTimeout(updateTemplateUI, 80))
        .observe(form, { childList: true, subtree: true, attributes: true, characterData: true });
    const cp = document.querySelector('.o_control_panel');
    if (cp) {
        new MutationObserver(() => setTimeout(updateTemplateUI, 80))
            .observe(cp, { childList: true, subtree: true, attributes: true });
    }
    document.addEventListener('click', function cfTemplateSaveGuard(e) {
        if (!document.querySelector('.o_competency_template_form')) {
            document.removeEventListener('click', cfTemplateSaveGuard, true);
            return;
        }
        const saveBtn = e.target.closest('.o_form_button_save, button[name="save_manually"]');
        if (!saveBtn) return;
        const skeletonField = form.querySelector('[name="is_skeleton"] input');
        const isSkeleton = skeletonField ? skeletonField.value === 'true' || skeletonField.checked : false;
        if (isSkeleton) return;
        const { ceiling, total } = getTemplateAllocation();
        if (Math.abs(total - ceiling) > TOLERANCE) {
            e.preventDefault();
            e.stopImmediatePropagation();
            const diff = Math.abs(total - ceiling).toFixed(2);
            alert(total > ceiling
                ? `Cannot save — reduce by ${diff} pts to reach exactly ${ceiling.toFixed(2)}.`
                : `Cannot save — ${diff} pts remaining to reach ${ceiling.toFixed(2)}.`);
            updateTemplateUI();
            return false;
        }
    }, true);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupExportObserver);
} else {
    setupExportObserver();
}

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => this._cfSetup());
        onPatched(() => this._cfSetup());
    },
    _cfSetup() {
        if (!this.el) return;
        const model = this.model?.root?.resModel;
        if (model === 'competency.framework.group') {
            setTimeout(() => { setupDialogObserver(); interceptDialogSave(); }, 300);
        }
        if (model === 'competency.framework.template') {
            setTimeout(() => setupTemplateMonitor(), 400);
        }
        if (model === 'appraisal.template') {
            setTimeout(() => setupAppraisalFormObserver(), 400);
        }
    },
    async beforeLeave() {
        if (!this.el) return super.beforeLeave(...arguments);
        const model = this.model?.root?.resModel;
        if (model === 'competency.framework.template') {
            const form = document.querySelector('.o_competency_template_form');
            const skeletonField = form && form.querySelector('[name="is_skeleton"] input');
            const isSkeleton = skeletonField ? skeletonField.value === 'true' || skeletonField.checked : false;
            if (!isSkeleton) {
                const { ceiling, total } = getTemplateAllocation();
                if (Math.abs(total - ceiling) > TOLERANCE) {
                    const diff = Math.abs(total - ceiling).toFixed(2);
                    alert(total > ceiling
                        ? `Cannot save — reduce by ${diff} pts to reach exactly ${ceiling.toFixed(2)}.`
                        : `Cannot save — ${diff} pts remaining to reach ${ceiling.toFixed(2)}.`);
                    throw new Error('Allocation mismatch');
                }
            }
        }
        if (model === 'competency.framework.group') {
            const sum     = getLineSumFromDialog();
            const ceiling = getCurrentCeiling();
            if (Math.abs(sum - ceiling) > TOLERANCE) {
                const diff = Math.abs(sum - ceiling).toFixed(2);
                alert(sum > ceiling
                    ? `Cannot save group — reduce by ${diff} pts to reach exactly ${ceiling.toFixed(2)}.`
                    : `Cannot save group — ${diff} pts remaining to reach ${ceiling.toFixed(2)}.`);
                throw new Error('Allocation mismatch');
            }
        }
        return super.beforeLeave(...arguments);
    },
});

patch(X2ManyField.prototype, {
    setup() {
        super.setup(...arguments);
        this._cfNotification = useService('notification');
    },
    async onAdd({ context, editable } = {}) {
        if (this.props.name === 'line_ids') {
            const sum     = getLineSumFromDialog();
            const ceiling = getCurrentCeiling();
            if (sum >= ceiling - TOLERANCE) {
                this._cfNotification.add(
                    `Ceiling reached (${sum.toFixed(2)} / ${ceiling.toFixed(2)} pts). Cannot add more lines.`,
                    { title: 'Ceiling Reached', type: 'warning', sticky: false }
                );
                return;
            }
        }
        if (this.props.name === 'group_ids') {
            const { total, ceiling } = getTemplateAllocation();
            if (total >= ceiling - TOLERANCE) {
                this._cfNotification.add(
                    `Ceiling reached (${total.toFixed(2)} / ${ceiling.toFixed(2)} pts). Cannot add more groups.`,
                    { title: 'Ceiling Reached', type: 'warning', sticky: false }
                );
                return;
            }
        }
        return super.onAdd({ context, editable });
    },
});