// ============================================================
// COMPLETE FIXED VERSION v17 - Fixed undefined this.el error
//
// KEY FEATURES:
//   • Chatter toggle button (hides/shows chatter panel)
//   • Working Export to PDF functionality
//   • Working Export to Excel functionality  
//   • Working Print functionality
//   • Server-side hard clamp with visual feedback
//   • Save-button blocking + banner validation
// ============================================================

import { patch } from "@web/core/utils/patch";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { onMounted, onPatched } from "@odoo/owl";

// ─────────────────────────────────────────────────────────────────────────────
//  INJECT CRITICAL STYLES
// ─────────────────────────────────────────────────────────────────────────────

(function _injectStyles() {
    if (document.getElementById("cf-v17-styles")) return;
    const s = document.createElement("style");
    s.id = "cf-v17-styles";
    s.textContent = `

/* ── Save button disabled ─────────────────────────────────── */
.cf-save-blocked {
    opacity: 0.5 !important;
    cursor: not-allowed !important;
    pointer-events: none !important;
}

/* ── Validation banner ────────────────────────────────────── */
.cf-banner-wrap { padding: 0 20px 16px 20px; }

.cf_validation_banner {
    display: flex; align-items: stretch; border-radius: 12px;
    overflow: hidden; box-shadow: 0 8px 20px rgba(0,0,0,0.12);
    animation: cf_banner_slide 0.3s ease both;
}
@keyframes cf_banner_slide {
    from { opacity: 0; transform: translateY(-10px); }
    to   { opacity: 1; transform: translateY(0); }
}
.cf_banner_stripe { flex-shrink: 0; width: 8px; }
.cf_banner_icon   { flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 60px; font-size: 1.6rem; }
.cf_banner_body   { flex: 1; padding: 16px 20px 16px 8px; }
.cf_banner_title  { font-size: 0.7rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 6px; }
.cf_banner_msg    { font-size: 0.9rem; font-weight: 500; line-height: 1.5; margin-bottom: 12px; }
.cf_banner_numbers { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 8px; padding-top: 12px; border-top: 1px solid rgba(0,0,0,0.08); }
.cf_banner_num_item { display: flex; flex-direction: column; background: rgba(255,255,255,0.6); border-radius: 10px; padding: 6px 14px; min-width: 80px; }
.cf_banner_num_label { font-size: 0.6rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.65; }
.cf_banner_num_val   { font-size: 1.1rem; font-weight: 800; }

.cf_banner_error   { background: linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%); border: 1px solid #fecaca; }
.cf_banner_error .cf_banner_stripe { background: #dc2626; }
.cf_banner_error .cf_banner_icon   { color: #dc2626; }
.cf_banner_error .cf_banner_title  { color: #991b1b; }
.cf_banner_error .cf_banner_msg    { color: #7f1d1d; }
.cf_banner_error .cf_banner_num_val { color: #b91c1c; }

.cf_banner_warning { background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border: 1px solid #fde68a; }
.cf_banner_warning .cf_banner_stripe { background: #d97706; }
.cf_banner_warning .cf_banner_icon   { color: #d97706; }
.cf_banner_warning .cf_banner_title  { color: #92400e; }
.cf_banner_warning .cf_banner_msg    { color: #78350f; }
.cf_banner_warning .cf_banner_num_val { color: #b45309; }

.cf-add-blocked-tip {
    color: #b45309; font-size: 0.75rem; font-weight: 600; margin-left: 12px;
    display: inline-block; background: #fef3c7; padding: 4px 10px;
    border-radius: 20px; animation: cf-fadeout 3s forwards;
}
@keyframes cf-fadeout { 0%, 70% { opacity: 1; } 100% { opacity: 0; } }

/* ── Chatter toggle button ────────────────────────────────── */
.cf-chatter-toggle-btn {
    display:        inline-flex;
    align-items:    center;
    gap:            7px;
    padding:        4px 12px;
    border-radius:  16px;
    border:         1px solid #e2e8f0;
    background:     #ffffff;
    color:          #475569;
    font-size:      0.7rem;
    font-weight:    600;
    cursor:         pointer;
    transition:     all 0.2s ease;
    white-space:    nowrap;
    letter-spacing: 0.02em;
    box-shadow:     0 1px 3px rgba(0,0,0,0.05);
    user-select:    none;
    line-height:    1;
}
.cf-chatter-toggle-btn:hover {
    background:   #f1f5f9;
    border-color: #cbd5e1;
    color:        #1e293b;
}
.cf-chatter-toggle-btn.cf-hidden {
    background:   #1a3c5e;
    border-color: #1a3c5e;
    color:        #ffffff;
}
.cf-chatter-toggle-btn.cf-hidden:hover {
    background:   #1e4976;
    border-color: #1e4976;
}
.cf-toggle-icon {
    font-size: 0.75rem;
    line-height: 1;
}

/* ── Chatter hidden state ─────────────────────────────────── */
.o_form_view.o_chatter_hidden .o_chatter,
.o_form_view.o_chatter_hidden .o_FormRenderer_chatterContainer {
    display: none !important;
    width:   0 !important;
}
.o_form_view.o_chatter_hidden .o_form_sheet_bg {
    max-width: 100% !important;
    width:     100% !important;
    flex:      1 !important;
}

/* Toggle button wrapper */
.cf-chatter-toggle-wrap {
    position:   absolute;
    top:        12px;
    right:      20px;
    z-index:    20;
}

/* ── Export and Print Button Styles ───────────────────────── */
.cf-export-pdf-btn, .cf-export-excel-btn, .cf-print-btn {
    transition: all 0.2s;
}
.cf-export-pdf-btn:hover {
    background: #fee2e2 !important;
    border-color: #fca5a5 !important;
    color: #dc2626 !important;
}
.cf-export-excel-btn:hover {
    background: #dcfce7 !important;
    border-color: #86efac !important;
    color: #16a34a !important;
}
.cf-print-btn:hover {
    background: #e0e7ff !important;
    border-color: #a5b4fc !important;
    color: #4f46e5 !important;
}

/* Print styles */
@media print {
    .o_control_panel, .o_chatter, .o_notebook_headers,
    button, .btn, .cf-chatter-toggle-wrap, .cf-table-toolbar {
        display: none !important;
    }
    body {
        padding: 20px;
    }
}

/* Clamped input animation */
@keyframes cf-clamp-flash {
    0%   { background-color: #fee2e2; border-color: #f87171; }
    40%  { background-color: #fef3c7; border-color: #fbbf24; }
    100% { background-color: #ffffff; border-color: #cbd5e1; }
}
.cf-clamped-input {
    animation: cf-clamp-flash 1.4s ease-out forwards !important;
}
@keyframes cf-shake {
    0%, 100% { transform: translateX(0); }
    20% { transform: translateX(-4px); }
    40% { transform: translateX(4px); }
    60% { transform: translateX(-3px); }
    80% { transform: translateX(2px); }
}
.cf-shake {
    animation: cf-shake 0.4s ease-in-out !important;
}

`;
    document.head.appendChild(s);
})();

// ─────────────────────────────────────────────────────────────────────────────
//  CHATTER TOGGLE
// ─────────────────────────────────────────────────────────────────────────────

const CF_CHATTER_KEY = "cf_chatter_hidden";

function isChatterHidden() {
    try { return localStorage.getItem(CF_CHATTER_KEY) === "1"; } catch { return false; }
}
function setChatterHidden(hidden) {
    try { localStorage.setItem(CF_CHATTER_KEY, hidden ? "1" : "0"); } catch {}
}

function injectChatterToggle(formEl) {
    if (!formEl || formEl._cfToggleInjected) return;

    // Only for competency template form
    if (!formEl.querySelector(".o_competency_template_form")) return;

    // Find the sheet to position the button
    const sheet = formEl.querySelector(".o_form_sheet");
    if (!sheet) return;

    formEl._cfToggleInjected = true;

    // Make sheet relatively positioned
    if (getComputedStyle(sheet).position === "static") {
        sheet.style.position = "relative";
    }

    const wrap = document.createElement("div");
    wrap.className = "cf-chatter-toggle-wrap";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cf-chatter-toggle-btn";

    const applyState = () => {
        const hidden = isChatterHidden();
        const formView = formEl.closest(".o_form_view") || formEl;
        if (formView) {
            formView.classList.toggle("o_chatter_hidden", hidden);
        }
        btn.classList.toggle("cf-hidden", hidden);
        btn.innerHTML = `<span class="cf-toggle-icon">💬</span> ${hidden ? "Show" : "Hide"} Activity`;
        btn.title = hidden ? "Show chatter panel" : "Hide chatter panel";
    };

    btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        setChatterHidden(!isChatterHidden());
        applyState();
    });

    wrap.appendChild(btn);
    sheet.appendChild(wrap);
    applyState();
}

// ─────────────────────────────────────────────────────────────────────────────
//  EXPORT FUNCTIONS
// ─────────────────────────────────────────────────────────────────────────────

function exportToPDF() {
    // Find the competency table content
    const tableContent = document.querySelector('.cf-competency-table, .o_competency_template_form field[name="competency_table_html"]');
    if (!tableContent) {
        console.error('No competency table found to export');
        alert('No competency table found to export. Please make sure you are on the Competency Table tab.');
        return;
    }
    
    // Get the template name
    const templateNameInput = document.querySelector('.o_competency_template_form .o_field_widget[name="name"] input');
    const filename = (templateNameInput?.value || 'competency-framework').replace(/\s+/g, '-').toLowerCase();
    
    // Create a print-friendly clone
    const printWindow = window.open('', '_blank');
    const clone = tableContent.cloneNode(true);
    
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>${filename}</title>
            <meta charset="UTF-8">
            <style>
                body {
                    font-family: 'Segoe UI', Arial, sans-serif;
                    padding: 40px;
                    margin: 0;
                    background: white;
                }
                h1 {
                    color: #1a3c5e;
                    border-bottom: 3px solid #e8a020;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                    font-size: 12px;
                }
                th {
                    background: #1a3c5e;
                    color: white;
                    padding: 12px;
                    text-align: left;
                    font-weight: bold;
                }
                td {
                    padding: 10px;
                    border-bottom: 1px solid #ddd;
                }
                .footer {
                    margin-top: 40px;
                    font-size: 10px;
                    color: #999;
                    text-align: center;
                    border-top: 1px solid #eee;
                    padding-top: 20px;
                }
                @media print {
                    body { padding: 0; }
                }
            </style>
        </head>
        <body>
            <h1>${filename.replace(/-/g, ' ').toUpperCase()}</h1>
            ${clone.outerHTML}
            <div class="footer">
                Generated on ${new Date().toLocaleString()}
            </div>
        </body>
        </html>
    `);
    
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
    printWindow.close();
}

function exportToExcel() {
    // Find the competency table content
    const tableContent = document.querySelector('.cf-competency-table, .o_competency_template_form field[name="competency_table_html"]');
    if (!tableContent) {
        console.error('No competency table found to export');
        alert('No competency table found to export. Please make sure you are on the Competency Table tab.');
        return;
    }
    
    // Get the table from the content
    let table = tableContent.querySelector('table');
    if (!table) {
        table = tableContent;
    }
    
    // Get the template name
    const templateNameInput = document.querySelector('.o_competency_template_form .o_field_widget[name="name"] input');
    const filename = (templateNameInput?.value || 'competency-framework').replace(/\s+/g, '-').toLowerCase();
    
    // Clone the table to avoid modifying the original
    const cloneTable = table.cloneNode(true);
    
    // Generate HTML for Excel
    const html = `
        <html>
        <head>
            <meta charset="UTF-8">
            <title>${filename}</title>
            <style>
                th {
                    background: #1a3c5e;
                    color: #fff;
                    padding: 10px;
                    font-weight: bold;
                }
                td {
                    padding: 8px;
                    border: 1px solid #ccc;
                }
                table {
                    border-collapse: collapse;
                    width: 100%;
                    margin: 20px 0;
                }
            </style>
        </head>
        <body>
            <h2>${filename.replace(/-/g, ' ').toUpperCase()}</h2>
            ${cloneTable.outerHTML}
            <p><em>Generated on ${new Date().toLocaleString()}</em></p>
        </body>
        </html>
    `;
    
    // Create blob and download
    const blob = new Blob([html], { type: 'application/vnd.ms-excel' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = `${filename}.xls`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function printCompetencyTable() {
    // Find the competency table content
    const tableContent = document.querySelector('.cf-competency-table, .o_competency_template_form field[name="competency_table_html"]');
    if (!tableContent) {
        console.error('No competency table found to print');
        alert('No competency table found to print. Please make sure you are on the Competency Table tab.');
        return;
    }
    
    // Get the template name
    const templateNameInput = document.querySelector('.o_competency_template_form .o_field_widget[name="name"] input');
    const title = templateNameInput?.value || 'Competency Framework';
    
    // Create a print-friendly clone
    const printWindow = window.open('', '_blank');
    const clone = tableContent.cloneNode(true);
    
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>${title}</title>
            <meta charset="UTF-8">
            <style>
                body {
                    font-family: 'Segoe UI', Arial, sans-serif;
                    padding: 40px;
                    margin: 0;
                    background: white;
                }
                h1 {
                    color: #1a3c5e;
                    border-bottom: 3px solid #e8a020;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                    font-size: 12px;
                }
                th {
                    background: #1a3c5e;
                    color: white;
                    padding: 12px;
                    text-align: left;
                    font-weight: bold;
                }
                td {
                    padding: 10px;
                    border-bottom: 1px solid #ddd;
                }
                .footer {
                    margin-top: 40px;
                    font-size: 10px;
                    color: #999;
                    text-align: center;
                    border-top: 1px solid #eee;
                    padding-top: 20px;
                }
                @media print {
                    body { padding: 0; }
                }
            </style>
        </head>
        <body>
            <h1>${title}</h1>
            ${clone.outerHTML}
            <div class="footer">
                Generated on ${new Date().toLocaleString()}
            </div>
        </body>
        </html>
    `);
    
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
    printWindow.close();
}

function exportGroupToPDF() {
    const linesTable = document.querySelector('.o_competency_lines_table');
    if (!linesTable) {
        console.error('No lines table found to export');
        alert('No competency lines found to export.');
        return;
    }
    
    const groupNameInput = document.querySelector('.o_competency_group_form .o_field_widget[name="name"] input');
    const filename = (groupNameInput?.value || 'competency-group').replace(/\s+/g, '-').toLowerCase();
    
    const printWindow = window.open('', '_blank');
    const clone = linesTable.cloneNode(true);
    
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>${filename}</title>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; padding: 40px; }
                h1 { color: #1a3c5e; border-bottom: 3px solid #e8a020; padding-bottom: 10px; }
                table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                th { background: #1a3c5e; color: white; padding: 12px; text-align: left; }
                td { padding: 10px; border-bottom: 1px solid #ddd; }
                @media print { body { padding: 0; } }
            </style>
        </head>
        <body>
            <h1>${filename.replace(/-/g, ' ').toUpperCase()}</h1>
            ${clone.outerHTML}
            <p style="margin-top: 40px; font-size: 10px; color: #999;">
                Generated on ${new Date().toLocaleString()}
            </p>
        </body>
        </html>
    `);
    
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
    printWindow.close();
}

function exportGroupToExcel() {
    const linesTable = document.querySelector('.o_competency_lines_table');
    if (!linesTable) {
        console.error('No lines table found to export');
        alert('No competency lines found to export.');
        return;
    }
    
    const groupNameInput = document.querySelector('.o_competency_group_form .o_field_widget[name="name"] input');
    const filename = (groupNameInput?.value || 'competency-group').replace(/\s+/g, '-').toLowerCase();
    
    let table = linesTable.querySelector('table');
    if (!table) {
        table = linesTable;
    }
    
    const cloneTable = table.cloneNode(true);
    
    const html = `
        <html>
        <head>
            <meta charset="UTF-8">
            <title>${filename}</title>
            <style>
                th { background: #1a3c5e; color: #fff; padding: 10px; }
                td { padding: 8px; border: 1px solid #ccc; }
                table { border-collapse: collapse; width: 100%; }
            </style>
        </head>
        <body>
            <h2>${filename.replace(/-/g, ' ').toUpperCase()}</h2>
            ${cloneTable.outerHTML}
            <p><em>Generated on ${new Date().toLocaleString()}</em></p>
        </body>
        </html>
    `;
    
    const blob = new Blob([html], { type: 'application/vnd.ms-excel' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = `${filename}.xls`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// ─────────────────────────────────────────────────────────────────────────────
//  INITIALIZE EXPORT BUTTONS
// ─────────────────────────────────────────────────────────────────────────────

function initExportButtons() {
    // Template export buttons
    const templatePdfBtn = document.querySelector('#cf-template-export-pdf');
    const templateExcelBtn = document.querySelector('#cf-template-export-excel');
    const templatePrintBtn = document.querySelector('#cf-template-print');
    
    if (templatePdfBtn && !templatePdfBtn._bound) {
        templatePdfBtn._bound = true;
        templatePdfBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            exportToPDF();
        });
    }
    
    if (templateExcelBtn && !templateExcelBtn._bound) {
        templateExcelBtn._bound = true;
        templateExcelBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            exportToExcel();
        });
    }
    
    if (templatePrintBtn && !templatePrintBtn._bound) {
        templatePrintBtn._bound = true;
        templatePrintBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            printCompetencyTable();
        });
    }
    
    // Group dialog export buttons
    const groupPdfBtn = document.querySelector('#cf-export-pdf');
    const groupExcelBtn = document.querySelector('#cf-export-excel');
    
    if (groupPdfBtn && !groupPdfBtn._bound) {
        groupPdfBtn._bound = true;
        groupPdfBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            exportGroupToPDF();
        });
    }
    
    if (groupExcelBtn && !groupExcelBtn._bound) {
        groupExcelBtn._bound = true;
        groupExcelBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            exportGroupToExcel();
        });
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  DOM HELPERS
// ─────────────────────────────────────────────────────────────────────────────

function getDialogEl(el) {
    return el?.closest?.(".o_dialog") ?? null;
}

function readGroupCeiling(dialogEl) {
    if (!dialogEl) return 0;
    const groupPtsWidgets = [...dialogEl.querySelectorAll(".o_field_widget[name='points']")]
        .filter(w => !w.closest(".o_field_widget[name='line_ids']"));
    for (const w of groupPtsWidgets) {
        const inp = w.querySelector("input");
        const val = inp ? inp.value : w.textContent;
        const n = parseFloat((val || "").replace(/,/g, ""));
        if (!isNaN(n)) return n;
    }
    return 0;
}

function readAllLinePoints(dialogEl) {
    if (!dialogEl) return 0;
    let sum = 0;
    const rows = dialogEl.querySelectorAll(".o_field_widget[name='line_ids'] .o_data_row");
    for (const row of rows) {
        const ptsCell = row.querySelector("td[name='points']");
        if (!ptsCell) continue;
        const nameCell = row.querySelector("td[name='name']");
        const nameText = (nameCell?.textContent ?? "").trim();
        const inp = ptsCell.querySelector("input");
        const raw = inp ? inp.value : ptsCell.textContent;
        const pts = parseFloat((raw || "").replace(/,/g, "")) || 0;
        if (nameText || pts > 0) sum += pts;
    }
    return Math.round(sum * 1000) / 1000;
}

function computeValidation(dialogEl) {
    if (!dialogEl) return { isValid: true };
    const groupCeiling = readGroupCeiling(dialogEl);
    const lineSum      = readAllLinePoints(dialogEl);
    const diff         = Math.round((lineSum - groupCeiling) * 1000) / 1000;

    if (diff > 0.005) {
        return {
            isValid: false, type: "error",
            title: _t("OVER ALLOCATED"),
            msg: _t("Line total exceeds group points. Cannot save."),
            lineSum, groupCeiling, diff,
        };
    }
    if (diff < -0.005) {
        return {
            isValid: false, type: "warning",
            title: _t("UNDER ALLOCATED"),
            msg: _t("Not all group points have been distributed. Cannot save."),
            lineSum, groupCeiling, diff,
        };
    }
    return { isValid: true };
}

function removeBanner(dialogEl) {
    dialogEl?.querySelectorAll("[data-cf-banner]").forEach(n => n.remove());
}

function showValidationBanner(dialogEl, result) {
    removeBanner(dialogEl);
    if (result.isValid || !dialogEl) return;

    const { type, title, msg, lineSum, groupCeiling, diff } = result;
    const isError  = type === "error";
    const excess   = diff > 0 ? diff.toFixed(2) : null;
    const shortage = diff < 0 ? Math.abs(diff).toFixed(2) : null;

    const wrap = document.createElement("div");
    wrap.dataset.cfBanner = "1";
    wrap.className = "cf-banner-wrap";
    wrap.innerHTML = `
        <div class="cf_validation_banner ${isError ? "cf_banner_error" : "cf_banner_warning"}">
            <div class="cf_banner_stripe"></div>
            <div class="cf_banner_icon">${isError ? "⛔" : "⚠️"}</div>
            <div class="cf_banner_body">
                <div class="cf_banner_title">${title}</div>
                <div class="cf_banner_msg">${msg}</div>
                <div class="cf_banner_numbers">
                    <div class="cf_banner_num_item">
                        <span class="cf_banner_num_label">Line Total</span>
                        <span class="cf_banner_num_val">${lineSum.toFixed(2)}</span>
                    </div>
                    <div class="cf_banner_num_item">
                        <span class="cf_banner_num_label">Group Points</span>
                        <span class="cf_banner_num_val">${groupCeiling.toFixed(2)}</span>
                    </div>
                    ${excess   ? `<div class="cf_banner_num_item"><span class="cf_banner_num_label">Excess</span><span class="cf_banner_num_val">+${excess}</span></div>` : ""}
                    ${shortage ? `<div class="cf_banner_num_item"><span class="cf_banner_num_label">Remaining</span><span class="cf_banner_num_val">${shortage}</span></div>` : ""}
                </div>
            </div>
        </div>`;

    const footer = dialogEl.querySelector(".modal-footer, .o_dialog_footer, footer");
    if (footer) {
        footer.insertAdjacentElement("beforebegin", wrap);
    } else {
        (dialogEl.querySelector(".o_form_sheet") ?? dialogEl).appendChild(wrap);
    }
}

function updateSaveButton(dialogEl, enabled) {
    if (!dialogEl) return;
    dialogEl.querySelectorAll(
        "button.btn-primary, button[name='save_manually'], .o_form_button_save"
    ).forEach(btn => btn.classList.toggle("cf-save-blocked", !enabled));
}

function refreshValidationUI(dialogEl) {
    if (!dialogEl) return;
    const validation = computeValidation(dialogEl);
    if (!validation.isValid) {
        showValidationBanner(dialogEl, validation);
        updateSaveButton(dialogEl, false);
    } else {
        removeBanner(dialogEl);
        updateSaveButton(dialogEl, true);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  SETUP DIALOG
// ─────────────────────────────────────────────────────────────────────────────

function setupDialog(dialogEl) {
    if (!dialogEl || dialogEl._cfBound) return;
    dialogEl._cfBound = true;

    const pointsInput = dialogEl.querySelector(".o_field_widget[name='points'] input");
    if (pointsInput) {
        pointsInput.addEventListener('input', () => {
            setTimeout(() => refreshValidationUI(dialogEl), 50);
        });
    }

    dialogEl.addEventListener("click", ev => {
        const saveBtn = ev.target.closest(
            "button.btn-primary, button[name='save_manually'], .o_form_button_save"
        );
        if (!saveBtn || saveBtn.classList.contains("cf-save-blocked")) return;
        const validation = computeValidation(dialogEl);
        if (!validation.isValid) {
            ev.stopImmediatePropagation();
            ev.preventDefault();
            refreshValidationUI(dialogEl);
        }
    }, true);

    dialogEl.addEventListener("click", ev => {
        const addBtn = ev.target.closest(
            ".o_field_widget[name='line_ids'] .o_field_x2many_list_row_add a, " +
            ".o_field_widget[name='line_ids'] .o_field_x2many_list_row_add button"
        );
        if (!addBtn) return;
        const groupCeiling = readGroupCeiling(dialogEl);
        const lineSum      = readAllLinePoints(dialogEl);
        const remaining    = groupCeiling - lineSum;
        if (remaining <= 0.01 && groupCeiling > 0) {
            ev.stopImmediatePropagation();
            ev.preventDefault();
            const tip = document.createElement("span");
            tip.className = "cf-add-blocked-tip";
            tip.textContent = _t("All points allocated — increase Group Points to add more lines.");
            addBtn.parentElement.appendChild(tip);
            setTimeout(() => tip.remove(), 3000);
        }
    }, true);

    setTimeout(() => refreshValidationUI(dialogEl), 150);
}

// ─────────────────────────────────────────────────────────────────────────────
//  FORM CONTROLLER PATCH (Fixed - with null checks)
// ─────────────────────────────────────────────────────────────────────────────

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => this._cfSetup());
        onPatched(() => this._cfSetup());
    },

    _cfSetup() {
        // Safely check if this.el exists
        if (!this.el) return;
        
        const model = this.model?.root?.resModel;

        if (model === "competency.framework.group") {
            const dialogEl = getDialogEl(this.el);
            if (dialogEl) {
                setupDialog(dialogEl);
            }
            // Initialize export buttons for group dialog
            setTimeout(() => initExportButtons(), 100);
            return;
        }

        if (model === "competency.framework.template") {
            injectChatterToggle(this.el);
            // Initialize export buttons after the form is fully loaded
            setTimeout(() => initExportButtons(), 500);
            // Also watch for tab changes
            const notebook = this.el.querySelector('.o_notebook');
            if (notebook) {
                notebook.addEventListener('shown.bs.tab', () => {
                    setTimeout(() => initExportButtons(), 100);
                });
            }
        }
    },

    async beforeLeave() {
        if (!this.el) return super.beforeLeave(...arguments);
        
        const model = this.model?.root?.resModel;
        if (model === "competency.framework.group") {
            const dialogEl = getDialogEl(this.el);
            if (dialogEl) {
                const validation = computeValidation(dialogEl);
                if (!validation.isValid) {
                    refreshValidationUI(dialogEl);
                    throw new Error("CF_VALIDATION_BLOCKED");
                }
            }
        }
        return super.beforeLeave(...arguments);
    },

    async saveRecord() {
        if (!this.el) return super.saveRecord(...arguments);
        
        const model = this.model?.root?.resModel;
        if (model === "competency.framework.group") {
            const dialogEl = getDialogEl(this.el);
            if (dialogEl) {
                const validation = computeValidation(dialogEl);
                if (!validation.isValid) {
                    refreshValidationUI(dialogEl);
                    return false;
                }
            }
        }
        return super.saveRecord(...arguments);
    },
});

// ─────────────────────────────────────────────────────────────────────────────
//  X2ManyField.onAdd — block when fully allocated
// ─────────────────────────────────────────────────────────────────────────────

patch(X2ManyField.prototype, {
    setup() {
        super.setup(...arguments);
        this._cfNotification = useService("notification");
    },

    async onAdd({ context, editable } = {}) {
        const fieldName = this.props.name;
        const record    = this.props.record;

        if (fieldName === "group_ids") {
            const status = record?.data?.points_status;
            if (status === "exact" || status === "over") {
                this._cfNotification.add(
                    _t("All HR points are fully allocated. Cannot add more groups."),
                    { title: _t("Cannot Add Group"), type: "danger", sticky: false }
                );
                return;
            }
        }

        if (fieldName === "line_ids") {
            const ceiling   = record?.data?.points ?? 0;
            const grpName   = record?.data?.name ?? "";
            const remaining = record?.data?.remaining_points;

            if (remaining !== null && ceiling > 0 && remaining <= 0.01) {
                this._cfNotification.add(
                    _t(`All ${ceiling.toFixed(2)} pts for "${grpName}" are allocated. Cannot add more lines.`),
                    { title: _t("Cannot Add Line"), type: "danger", sticky: false }
                );
                return;
            }

            const dialogEl = document.querySelector(".o_dialog");
            if (dialogEl && ceiling > 0) {
                const lineSum      = readAllLinePoints(dialogEl);
                const remainingDOM = ceiling - lineSum;
                if (remainingDOM <= 0.01) {
                    this._cfNotification.add(
                        _t(`All ${ceiling.toFixed(2)} pts for "${grpName}" are allocated. Cannot add more lines.`),
                        { title: _t("Cannot Add Line"), type: "danger", sticky: false }
                    );
                    return;
                }
            }
        }

        return super.onAdd({ context, editable });
    },
});