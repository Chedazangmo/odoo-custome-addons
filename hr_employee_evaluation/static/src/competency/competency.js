// ============================================================
//  competency.js  — v21  (export/print fully fixed)
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
    if (document.getElementById("cf-v21-styles")) return;
    const s = document.createElement("style");
    s.id = "cf-v21-styles";
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
.cf_banner_error   { background: linear-gradient(135deg,#fff1f2,#ffe4e6); border:1px solid #fecaca; }
.cf_banner_error .cf_banner_stripe { background:#dc2626; }
.cf_banner_error .cf_banner_icon   { color:#dc2626; }
.cf_banner_error .cf_banner_title  { color:#991b1b; }
.cf_banner_error .cf_banner_msg    { color:#7f1d1d; }
.cf_banner_error .cf_banner_num_val { color:#b91c1c; }
.cf_banner_warning { background: linear-gradient(135deg,#fffbeb,#fef3c7); border:1px solid #fde68a; }
.cf_banner_warning .cf_banner_stripe { background:#d97706; }
.cf_banner_warning .cf_banner_icon   { color:#d97706; }
.cf_banner_warning .cf_banner_title  { color:#92400e; }
.cf_banner_warning .cf_banner_msg    { color:#78350f; }
.cf_banner_warning .cf_banner_num_val { color:#b45309; }

.cf-add-blocked-tip {
    color:#b45309; font-size:0.75rem; font-weight:600; margin-left:12px;
    display:inline-block; background:#fef3c7; padding:4px 10px;
    border-radius:20px; animation:cf-fadeout 3s forwards;
}
@keyframes cf-fadeout { 0%,70%{opacity:1} 100%{opacity:0} }

/* ── Chatter toggle button ────────────────────────────────── */
.cf-chatter-toggle-btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 12px; border-radius: 16px;
    border: 1px solid #e2e8f0; background: #fff; color: #475569;
    font-size: 0.75rem; font-weight: 600; cursor: pointer;
    transition: all 0.2s ease; white-space: nowrap;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06); user-select: none;
}
.cf-chatter-toggle-btn:hover { background:#f1f5f9; border-color:#cbd5e1; color:#1e293b; }
.cf-chatter-toggle-btn.cf-active { background:#1a3c5e; border-color:#1a3c5e; color:#fff; }
.cf-chatter-toggle-btn.cf-active:hover { background:#1e4976; }

/* ── Chatter hidden state ─────────────────────────────────── */
.o_form_view.o_chatter_hidden .o_chatter,
.o_form_view.o_chatter_hidden .o_FormRenderer_chatterContainer {
    display: none !important; width: 0 !important; overflow: hidden !important;
}
.o_form_view.o_chatter_hidden .o_form_sheet_bg {
    max-width: 100% !important; width: 100% !important; flex: 1 !important;
}

/* ── Export/Print button hover colours ───────────────────── */
.cf-export-pdf-btn:hover   { background:#fee2e2!important; border-color:#fca5a5!important; color:#dc2626!important; }
.cf-export-excel-btn:hover { background:#dcfce7!important; border-color:#86efac!important; color:#16a34a!important; }
.cf-print-btn:hover        { background:#e0e7ff!important; border-color:#a5b4fc!important; color:#4f46e5!important; }

@media print {
    .o_control_panel,.o_chatter,.o_notebook_headers,button,.btn { display:none!important; }
    body { padding:20px; }
}

@keyframes cf-clamp-flash {
    0%   { background-color:#fee2e2; border-color:#f87171; }
    40%  { background-color:#fef3c7; border-color:#fbbf24; }
    100% { background-color:#ffffff; border-color:#cbd5e1; }
}
.cf-clamped-input { animation: cf-clamp-flash 1.4s ease-out forwards !important; }
@keyframes cf-shake {
    0%,100%{transform:translateX(0)} 20%{transform:translateX(-4px)}
    40%{transform:translateX(4px)} 60%{transform:translateX(-3px)} 80%{transform:translateX(2px)}
}
.cf-shake { animation: cf-shake 0.4s ease-in-out !important; }

`;
    document.head.appendChild(s);
})();

// ─────────────────────────────────────────────────────────────────────────────
//  CHATTER TOGGLE
// ─────────────────────────────────────────────────────────────────────────────

const CF_CHATTER_KEY = "cf_chatter_hidden";
function isChatterHidden() { try { return localStorage.getItem(CF_CHATTER_KEY) === "1"; } catch { return false; } }
function setChatterHidden(h) { try { localStorage.setItem(CF_CHATTER_KEY, h ? "1" : "0"); } catch {} }

function injectChatterToggle(formEl) {
    if (!formEl || formEl._cfChatterInjected) return;
    if (!formEl.querySelector(".o_competency_template_form")) return;

    const formView = formEl.closest(".o_form_view") || formEl;

    const anchor =
        formEl.querySelector(".o_control_panel_actions") ||
        formEl.querySelector(".o_statusbar_buttons") ||
        formEl.querySelector(".o_cp_buttons") ||
        formEl.querySelector(".o_form_buttons_view") ||
        formEl.querySelector(".o_notebook_headers");

    if (!anchor) return;
    formEl._cfChatterInjected = true;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cf-chatter-toggle-btn ms-2";

    function applyState() {
        const hidden = isChatterHidden();
        formView.classList.toggle("o_chatter_hidden", hidden);
        btn.classList.toggle("cf-active", hidden);
        btn.textContent = hidden ? "💬 Show activity" : "💬 Hide activity";
        btn.title = hidden ? "Show chatter / activity panel" : "Hide chatter / activity panel";
    }

    btn.addEventListener("click", (e) => {
        e.preventDefault(); e.stopPropagation();
        setChatterHidden(!isChatterHidden());
        applyState();
    });

    anchor.insertBefore(btn, anchor.firstChild);
    applyState();
}

// ─────────────────────────────────────────────────────────────────────────────
//  TABLE EXTRACTION
//
//  The competency_table_html field is a server-computed Html field rendered
//  read-only.  In Odoo 17 the HTML widget wraps content in one of several
//  possible containers depending on the version and whether the editor is
//  active.  We must extract the raw HTML string from the field value rather
//  than scraping a live <table> element, because:
//
//    • The "Competency Table" tab may never have been clicked (tab-pane not
//      yet in DOM).
//    • Even when the tab is active, Odoo 17's Html widget may render into an
//      iframe or a shadow-DOM-like editable whose table is invisible to a
//      normal querySelector from the form root.
//
//  STRATEGY (in priority order):
//    1. Walk the OWL component tree from the form's __owl__ root to find the
//       field component whose props.name === "competency_table_html" and read
//       its record.data value directly — this is 100 % reliable regardless
//       of tab visibility.
//    2. If OWL introspection is unavailable, switch to the tab, wait for the
//       DOM to settle, then query the live element.
//    3. Final fallback: a wider DOM scan across all tab-panes.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Walk the OWL __owl__ component tree rooted at `node` and return the first
 * component whose props.name matches `fieldName`.
 */
function findOwlFieldComponent(node, fieldName) {
    if (!node) return null;
    // node is a Component instance (has props)
    if (node.props && node.props.name === fieldName) return node;
    // Recurse into children
    const children = node.__owl__ ? node.__owl__.children : (node.children || {});
    for (const key of Object.keys(children)) {
        const child = children[key];
        // child is an internal OWL node; its `component` property is the instance
        const comp = child.component || child;
        const found = findOwlFieldComponent(comp, fieldName);
        if (found) return found;
    }
    return null;
}

/**
 * Attempt to read the raw HTML string of `competency_table_html` directly
 * from the OWL/record data layer, bypassing DOM rendering entirely.
 *
 * Returns a non-empty string, or null if unavailable.
 */
function readHtmlFieldValueFromOwl(formEl) {
    try {
        // Odoo 17: the form element's __owl__ key holds the internal OWL node
        const owlNode = formEl.__owl__;
        if (!owlNode) return null;

        // The FormRenderer component is a child of FormController.
        // We search the whole sub-tree for a field component named
        // "competency_table_html".
        const fieldComp = findOwlFieldComponent(owlNode.component || owlNode, "competency_table_html");
        if (!fieldComp) return null;

        // The field component exposes its record via props.record or this.props.record
        const record = fieldComp.props?.record || fieldComp.record;
        if (!record) return null;

        const html = record.data?.competency_table_html;
        if (html && typeof html === "string" && html.trim().length > 0) return html;

        // Some versions wrap in { value: "..." }
        if (html && typeof html === "object" && html.value) return html.value;

        return null;
    } catch (e) {
        return null;
    }
}

/**
 * Extract the HTML string for the competency table from the live DOM.
 * Searches every possible wrapper Odoo 17 might use.
 *
 * Returns { html: string, tableEl: Element } or null.
 */
function extractTableFromDOM(root) {
    const R = root || document;

    // Ordered list of selectors from most-specific to least-specific
    const selectors = [
        '[name="competency_table_html"] table',
        '[name="competency_table_html"] .odoo-editor-editable table',
        '[name="competency_table_html"] .o_editable table',
        '[name="competency_table_html"] .o_field_html_content table',
        '.o_competency_template_form [name="competency_table_html"] table',
        '.o_competency_template_form .o_field_html table',
        '.tab-pane.active [name="competency_table_html"] table',
        '.tab-pane.active .o_field_html table',
        // Last-resort: the largest table in the whole form view
    ];

    for (const sel of selectors) {
        const el = R.querySelector(sel);
        if (el) return { html: el.outerHTML, tableEl: el };
    }

    // Widest fallback: find largest table in the form
    const formView = R.querySelector('.o_form_view') || R;
    let best = null, bestRows = 0;
    for (const t of formView.querySelectorAll('table')) {
        // Ignore list-widget tables (they have o_list_table class)
        if (t.classList.contains('o_list_table')) continue;
        const rows = t.querySelectorAll('tr').length;
        if (rows > bestRows) { bestRows = rows; best = t; }
    }
    if (best) return { html: best.outerHTML, tableEl: best };

    return null;
}

function getTemplateName(root) {
    const R = root || document;
    const input = R.querySelector(
        '.o_competency_template_form [name="name"] input, ' +
        '.o_competency_template_form .o_field_char input'
    );
    return (input?.value || 'Competency Framework').trim();
}

// ─────────────────────────────────────────────────────────────────────────────
//  TAB SWITCHER  — finds and activates the "Competency Table" tab
// ─────────────────────────────────────────────────────────────────────────────

const POLL_MS   = 150;
const MAX_TRIES = 25;   // 25 × 150 ms = 3.75 s maximum wait

function findTableTabLink(formEl) {
    const R = formEl || document;
    for (const el of R.querySelectorAll(
        '.o_notebook_headers .nav-link, ' +
        '.o_notebook_headers li > a, ' +
        '.o_notebook .nav-tabs .nav-link, ' +
        '.o_notebook .nav-item > a'
    )) {
        if (el.textContent.trim().toLowerCase().includes('table')) return el;
    }
    return null;
}

/**
 * Switch to the "Competency Table" tab if needed, wait for the content to
 * appear in the DOM, then call callback(htmlString).
 *
 * `htmlString` is the outerHTML of the <table> (or the full field HTML).
 */
function withTableHtml(formEl, callback) {
    // ── Priority 1: read directly from OWL record data (tab-independent) ──
    const owlHtml = readHtmlFieldValueFromOwl(formEl);
    if (owlHtml) {
        // owlHtml may be the full field value, which IS a <table> or wraps one.
        // Parse it to a DOM element so we can extract outerHTML cleanly.
        const tmp = document.createElement('div');
        tmp.innerHTML = owlHtml;
        const tbl = tmp.querySelector('table');
        if (tbl) { callback(tbl.outerHTML); return; }
        // The whole value is the table HTML (no extra wrapper)
        if (owlHtml.trim().startsWith('<table')) { callback(owlHtml); return; }
        // Fallback: use whatever we got
        callback(owlHtml);
        return;
    }

    // ── Priority 2: try the live DOM without switching tabs ────────────────
    const domResult = extractTableFromDOM(formEl);
    if (domResult) { callback(domResult.html); return; }

    // ── Priority 3: switch to the tab, then poll ───────────────────────────
    const tabLink = findTableTabLink(formEl);
    if (!tabLink) {
        alert(
            'Could not find the "Competency Table" tab.\n\n' +
            'Make sure you are viewing a Competency Template form.'
        );
        return;
    }

    tabLink.click();

    let tries = 0;
    const poll = setInterval(() => {
        tries++;

        // Re-try OWL path after tab activation triggers a re-render
        const owlHtml2 = readHtmlFieldValueFromOwl(formEl);
        if (owlHtml2) {
            clearInterval(poll);
            const tmp = document.createElement('div');
            tmp.innerHTML = owlHtml2;
            const tbl = tmp.querySelector('table');
            callback(tbl ? tbl.outerHTML : owlHtml2);
            return;
        }

        const domResult2 = extractTableFromDOM(formEl);
        if (domResult2) {
            clearInterval(poll);
            callback(domResult2.html);
            return;
        }

        if (tries >= MAX_TRIES) {
            clearInterval(poll);
            alert(
                'Could not find the competency table content after switching tabs.\n\n' +
                'Please make sure:\n' +
                '• The template has at least one group with competency lines\n' +
                '• You have saved the template at least once\n\n' +
                'Try clicking the "Competency Table" tab manually first, then export.'
            );
        }
    }, POLL_MS);
}

// ─────────────────────────────────────────────────────────────────────────────
//  PRINT WINDOW BUILDER
// ─────────────────────────────────────────────────────────────────────────────

function buildPrintWindow(title, tableHTML) {
    const w = window.open('', '_blank');
    if (!w) {
        alert('Pop-up blocked.\nPlease allow pop-ups for this site in your browser settings and try again.');
        return null;
    }
    w.document.write(`<!DOCTYPE html>
<html>
<head>
  <title>${title}</title>
  <meta charset="UTF-8">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; padding: 32px; background: #fff; color: #1e293b; }
    h1 { color: #1a3c5e; font-size: 1.2rem; font-weight: 700;
         border-bottom: 3px solid #e8a020; padding-bottom: 10px; margin-bottom: 20px; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th { background: #1a3c5e; color: #fff; padding: 10px 12px; text-align: left;
         font-weight: 700; border-bottom: 3px solid #e8a020; }
    td { padding: 9px 12px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
    tr:nth-child(even) td { background: #f8faff; }
    td[colspan] { font-weight: 700 !important; }
    .footer { margin-top: 24px; font-size: 10px; color: #94a3b8;
              text-align: right; border-top: 1px solid #e2e8f0; padding-top: 12px; }
    @media print { body { padding: 12px; } }
  </style>
</head>
<body>
  <h1>${title}</h1>
  ${tableHTML}
  <div class="footer">Generated: ${new Date().toLocaleString()}</div>
</body>
</html>`);
    w.document.close();
    return w;
}

// ─────────────────────────────────────────────────────────────────────────────
//  EXPORT FUNCTIONS  — template level
// ─────────────────────────────────────────────────────────────────────────────

function exportToPDF(formEl) {
    withTableHtml(formEl, (tableHTML) => {
        const title = getTemplateName(formEl);
        const w = buildPrintWindow(title, tableHTML);
        if (!w) return;
        w.focus();
        setTimeout(() => { try { w.print(); } catch(e) { console.error('Print error:', e); } }, 700);
    });
}

function exportToExcel(formEl) {
    withTableHtml(formEl, (tableHTML) => {
        const name = getTemplateName(formEl);
        const slug = name.replace(/[^a-zA-Z0-9]+/g, '-').toLowerCase();

        const html = `<html xmlns:o="urn:schemas-microsoft-com:office:office"
  xmlns:x="urn:schemas-microsoft-com:office:excel"
  xmlns="http://www.w3.org/TR/REC-html40">
<head><meta charset="UTF-8">
<!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets>
<x:ExcelWorksheet><x:Name>${name.substring(0, 31)}</x:Name>
<x:WorksheetOptions><x:DisplayGridlines/></x:WorksheetOptions>
</x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]-->
<style>
  th { background:#1a3c5e; color:#fff; font-weight:bold; padding:8px 10px; }
  td { padding:7px 10px; border:1px solid #ddd; vertical-align:top; }
  table { border-collapse:collapse; width:100%; }
  h2 { font-family:Arial; color:#1a3c5e; font-size:14pt; margin-bottom:10px; }
  .footer { font-size:9pt; color:#999; margin-top:12px; }
</style>
</head>
<body>
<h2>${name}</h2>
${tableHTML}
<p class="footer">Generated: ${new Date().toLocaleString()}</p>
</body></html>`;

        const BOM  = '\uFEFF';
        const blob = new Blob([BOM + html], { type: 'application/vnd.ms-excel;charset=utf-8;' });
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href = url;
        a.download = `${slug}.xls`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 3000);
    });
}

function printTable(formEl) {
    // Identical to PDF export — opens print dialog
    exportToPDF(formEl);
}

// ── Group-dialog exports ──────────────────────────────────────────────────────

function exportGroupToPDF() {
    const tbl = (
        document.querySelector('.o_competency_group_form table') ||
        document.querySelector('.o_dialog .o_list_table') ||
        document.querySelector('.o_dialog table')
    );
    if (!tbl) { alert('No competency lines table found.'); return; }
    const nameInput = document.querySelector('.o_dialog [name="name"] input');
    const title = nameInput?.value || 'Competency Group';
    const w = buildPrintWindow(title, tbl.outerHTML);
    if (!w) return;
    w.focus();
    setTimeout(() => { try { w.print(); } catch(e) {} }, 700);
}

function exportGroupToExcel() {
    const tbl = (
        document.querySelector('.o_competency_group_form table') ||
        document.querySelector('.o_dialog .o_list_table') ||
        document.querySelector('.o_dialog table')
    );
    if (!tbl) { alert('No competency lines table found.'); return; }
    const nameInput = document.querySelector('.o_dialog [name="name"] input');
    const name = nameInput?.value || 'competency-group';
    const slug = name.replace(/[^a-zA-Z0-9]+/g, '-').toLowerCase();

    const html = `<html><head><meta charset="UTF-8">
<style>th{background:#1a3c5e;color:#fff;padding:8px;}td{padding:7px;border:1px solid #ddd;}table{border-collapse:collapse;width:100%;}h2{font-family:Arial;color:#1a3c5e;}</style>
</head><body><h2>${name}</h2>${tbl.outerHTML}
<p style="font-size:9pt;color:#999;">Generated: ${new Date().toLocaleString()}</p></body></html>`;

    const blob = new Blob(['\uFEFF' + html], { type: 'application/vnd.ms-excel;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `${slug}.xls`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 3000);
}

// ─────────────────────────────────────────────────────────────────────────────
//  BIND EXPORT BUTTONS — event delegation, attached once per form root
// ─────────────────────────────────────────────────────────────────────────────

function bindExportButtons(formEl) {
    if (!formEl || formEl._cfExportBound) return;
    formEl._cfExportBound = true;

    formEl.addEventListener('click', (e) => {
        const btn = e.target.closest('button, [role="button"]');
        if (!btn) return;

        const id  = btn.id  || '';
        const cls = btn.className || '';

        // Template-level buttons: only fire when no dialog is open
        const dialogOpen = !!document.querySelector('.o_dialog');
        if (dialogOpen) return;

        if (id === 'cf-template-export-pdf'  || (!id && cls.includes('cf-export-pdf-btn'))) {
            e.preventDefault(); e.stopPropagation();
            exportToPDF(formEl);
            return;
        }
        if (id === 'cf-template-export-excel' || (!id && cls.includes('cf-export-excel-btn'))) {
            e.preventDefault(); e.stopPropagation();
            exportToExcel(formEl);
            return;
        }
        if (id === 'cf-template-print' || (!id && cls.includes('cf-print-btn'))) {
            e.preventDefault(); e.stopPropagation();
            printTable(formEl);
            return;
        }
    });
}

function bindDialogExportButtons(dialogEl) {
    if (!dialogEl || dialogEl._cfExportBound) return;
    dialogEl._cfExportBound = true;

    dialogEl.addEventListener('click', (e) => {
        const btn = e.target.closest('button, [role="button"]');
        if (!btn) return;
        const id  = btn.id  || '';
        const cls = btn.className || '';
        if (id === 'cf-export-pdf'   || cls.includes('cf-export-pdf-btn'))   { e.preventDefault(); e.stopPropagation(); exportGroupToPDF();   return; }
        if (id === 'cf-export-excel' || cls.includes('cf-export-excel-btn')) { e.preventDefault(); e.stopPropagation(); exportGroupToExcel(); return; }
    });
}

// ─────────────────────────────────────────────────────────────────────────────
//  DOM HELPERS — dialog validation (unchanged)
// ─────────────────────────────────────────────────────────────────────────────

function getDialogEl(el) { return el?.closest?.(".o_dialog") ?? null; }

function readGroupCeiling(dialogEl) {
    if (!dialogEl) return 0;
    const widgets = [...dialogEl.querySelectorAll(".o_field_widget[name='points']")]
        .filter(w => !w.closest(".o_field_widget[name='line_ids']"));
    for (const w of widgets) {
        const inp = w.querySelector("input");
        const n = parseFloat(((inp ? inp.value : w.textContent) || "").replace(/,/g, ""));
        if (!isNaN(n)) return n;
    }
    return 0;
}

function readAllLinePoints(dialogEl) {
    if (!dialogEl) return 0;
    let sum = 0;
    for (const row of dialogEl.querySelectorAll(".o_field_widget[name='line_ids'] .o_data_row")) {
        const ptsCell  = row.querySelector("td[name='points']");
        if (!ptsCell) continue;
        const nameCell = row.querySelector("td[name='name']");
        const inp = ptsCell.querySelector("input");
        const pts = parseFloat(((inp ? inp.value : ptsCell.textContent) || "").replace(/,/g, "")) || 0;
        if ((nameCell?.textContent ?? "").trim() || pts > 0) sum += pts;
    }
    return Math.round(sum * 1000) / 1000;
}

function computeValidation(dialogEl) {
    if (!dialogEl) return { isValid: true };
    const groupCeiling = readGroupCeiling(dialogEl);
    const lineSum      = readAllLinePoints(dialogEl);
    const diff         = Math.round((lineSum - groupCeiling) * 1000) / 1000;
    if (diff >  0.005) return { isValid:false, type:"error",   title:_t("OVER ALLOCATED"),  msg:_t("Line total exceeds group points. Cannot save."),             lineSum, groupCeiling, diff };
    if (diff < -0.005) return { isValid:false, type:"warning", title:_t("UNDER ALLOCATED"), msg:_t("Not all group points have been distributed. Cannot save."), lineSum, groupCeiling, diff };
    return { isValid: true };
}

function removeBanner(dialogEl) { dialogEl?.querySelectorAll("[data-cf-banner]").forEach(n => n.remove()); }

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
                    <div class="cf_banner_num_item"><span class="cf_banner_num_label">Line Total</span><span class="cf_banner_num_val">${lineSum.toFixed(2)}</span></div>
                    <div class="cf_banner_num_item"><span class="cf_banner_num_label">Group Points</span><span class="cf_banner_num_val">${groupCeiling.toFixed(2)}</span></div>
                    ${excess   ? `<div class="cf_banner_num_item"><span class="cf_banner_num_label">Excess</span><span class="cf_banner_num_val">+${excess}</span></div>` : ""}
                    ${shortage ? `<div class="cf_banner_num_item"><span class="cf_banner_num_label">Remaining</span><span class="cf_banner_num_val">${shortage}</span></div>` : ""}
                </div>
            </div>
        </div>`;
    const footer = dialogEl.querySelector(".modal-footer, .o_dialog_footer, footer");
    if (footer) footer.insertAdjacentElement("beforebegin", wrap);
    else (dialogEl.querySelector(".o_form_sheet") ?? dialogEl).appendChild(wrap);
}

function updateSaveButton(dialogEl, enabled) {
    if (!dialogEl) return;
    dialogEl.querySelectorAll("button.btn-primary, button[name='save_manually'], .o_form_button_save")
        .forEach(btn => btn.classList.toggle("cf-save-blocked", !enabled));
}

function refreshValidationUI(dialogEl) {
    if (!dialogEl) return;
    const v = computeValidation(dialogEl);
    if (!v.isValid) { showValidationBanner(dialogEl, v); updateSaveButton(dialogEl, false); }
    else { removeBanner(dialogEl); updateSaveButton(dialogEl, true); }
}

function setupDialog(dialogEl) {
    if (!dialogEl || dialogEl._cfBound) return;
    dialogEl._cfBound = true;

    const pointsInput = dialogEl.querySelector(".o_field_widget[name='points'] input");
    if (pointsInput) pointsInput.addEventListener('input', () => setTimeout(() => refreshValidationUI(dialogEl), 50));

    dialogEl.addEventListener("click", ev => {
        const saveBtn = ev.target.closest("button.btn-primary, button[name='save_manually'], .o_form_button_save");
        if (!saveBtn || saveBtn.classList.contains("cf-save-blocked")) return;
        const v = computeValidation(dialogEl);
        if (!v.isValid) { ev.stopImmediatePropagation(); ev.preventDefault(); refreshValidationUI(dialogEl); }
    }, true);

    dialogEl.addEventListener("click", ev => {
        const addBtn = ev.target.closest(
            ".o_field_widget[name='line_ids'] .o_field_x2many_list_row_add a, " +
            ".o_field_widget[name='line_ids'] .o_field_x2many_list_row_add button"
        );
        if (!addBtn) return;
        const remaining = readGroupCeiling(dialogEl) - readAllLinePoints(dialogEl);
        if (remaining <= 0.01 && readGroupCeiling(dialogEl) > 0) {
            ev.stopImmediatePropagation(); ev.preventDefault();
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
//  FORM CONTROLLER PATCH
// ─────────────────────────────────────────────────────────────────────────────

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => this._cfSetup());
        onPatched(() => this._cfSetup());
    },

    _cfSetup() {
        if (!this.el) return;
        const model = this.model?.root?.resModel;

        if (model === "competency.framework.group") {
            const dialogEl = getDialogEl(this.el);
            if (dialogEl) {
                setupDialog(dialogEl);
                bindDialogExportButtons(dialogEl);
            }
            return;
        }

        if (model === "competency.framework.template") {
            injectChatterToggle(this.el);
            bindExportButtons(this.el);
        }
    },

    async beforeLeave() {
        if (!this.el) return super.beforeLeave(...arguments);
        const model = this.model?.root?.resModel;
        if (model === "competency.framework.group") {
            const dialogEl = getDialogEl(this.el);
            if (dialogEl) {
                const v = computeValidation(dialogEl);
                if (!v.isValid) { refreshValidationUI(dialogEl); throw new Error("CF_VALIDATION_BLOCKED"); }
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
                const v = computeValidation(dialogEl);
                if (!v.isValid) { refreshValidationUI(dialogEl); return false; }
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
                if (readGroupCeiling(dialogEl) - readAllLinePoints(dialogEl) <= 0.01) {
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