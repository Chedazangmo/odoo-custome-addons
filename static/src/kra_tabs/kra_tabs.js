/** @odoo-module **/

import { Component, useState, onWillUpdateProps, useEffect, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

// ─────────────────────────────────────────────────────────────────────────────
// AddKraDialog
// ─────────────────────────────────────────────────────────────────────────────
class AddKraDialog extends Component {
    static template = "hr_employee_evaluation.AddKraDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        onConfirm: Function,
        existingNames: { type: Array, optional: true },
    };

    setup() {
        this.state = useState({ kraName: "", error: "" });
    }

    onConfirm() {
        const name = this.state.kraName.trim();
        if (!name) { this.state.error = "KRA name is required"; return; }
        if (this.props.existingNames && this.props.existingNames.includes(name)) {
            this.state.error = "A KRA with this name already exists"; return;
        }
        this.props.onConfirm(name);
        this.props.close();
    }

    onKeydown(ev) { if (ev.key === "Enter") this.onConfirm(); }
    onNameChange(ev) { this.state.kraName = ev.target.value; this.state.error = ""; }
}

// ─────────────────────────────────────────────────────────────────────────────
// KpiHistoryDialog
// ─────────────────────────────────────────────────────────────────────────────
class KpiHistoryDialog extends Component {
    static template = "hr_employee_evaluation.KpiHistoryDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        kpiName: String,
        kpiData: Object,
        hasSecondary: { type: Boolean, optional: true },
        historyType: String, // 'criteria' or 'target'
    };

    get dialogTitle() {
        const typeLabel = this.props.historyType === 'criteria' ? 'Criteria' : 'Target';
        return `${this.props.kpiName} - ${typeLabel} History`;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// AppraisalExpandDialog
// ─────────────────────────────────────────────────────────────────────────────
class AppraisalExpandDialog extends Component {
    static template = "hr_employee_evaluation.AppraisalExpandDialog";
    static components = { Dialog };
    static props = {
        close:         Function,
        kraName:       String,
        kpis:          Array,
        record:        Object,
        onFieldChange: Function,
    };
}

// ─────────────────────────────────────────────────────────────────────────────
// CompetencyExpandDialog
// ─────────────────────────────────────────────────────────────────────────────
class CompetencyExpandDialog extends Component {
    static template = "hr_employee_evaluation.CompetencyExpandDialog";
    static components = { Dialog };
    static props = {
        close:          Function,
        groupName:      String,
        scoreRows:      Array,
        record:         Object,
        onScoreChange:  Function,
    };
}

// ─────────────────────────────────────────────────────────────────────────────
// KraTabs  — main widget
// ─────────────────────────────────────────────────────────────────────────────
export class KraTabs extends Component {
    static template = "hr_employee_evaluation.KraTabs";
    static props = {
        record:   Object,
        readonly: { type: Boolean, optional: true },
        name:     String,
        id:       { type: String, optional: true },
        options:  { type: Object, optional: true },
    };

    setup() {
        this.kraRef        = useRef("kraBlock");
        this.dialog        = useService("dialog");
        this.orm           = useService("orm");
        this.notification  = useService("notification");

        this.state = useState({
            activeTabIndex:      0,
            isCompetencyActive:  false,   // true when the Competency Framework tab is selected
            isAdhocActive:       false,   // true when the Adhoc tab is selected
            isDeleting:          false,
            showRestorePanel:    false,
            activeCompGroup:     0,
        });

        // Scroll-fade — scoped strictly to the KRA block ref
        useEffect(() => {
            const header = this.kraRef.el?.querySelector('.o_kra_tabs_header');
            const nav    = this.kraRef.el?.querySelector('.o_kra_tabs_nav');
            if (!header || !nav) return;
            const updateFades = () => {
                const s = nav.scrollLeft, m = nav.scrollWidth - nav.clientWidth;
                header.classList.toggle('can-scroll-left',  s > 2);
                header.classList.toggle('can-scroll-right', s < m - 2);
            };
            nav.addEventListener('scroll', updateFades, { passive: true });
            updateFades();
            return () => nav.removeEventListener('scroll', updateFades);
        });

        // Auto-resize textareas — scoped to KRA block only
        useEffect(() => {
            if (!this.kraRef.el) return;
            setTimeout(() => {
                if (!this.kraRef.el) return;
                this.kraRef.el.querySelectorAll('textarea').forEach(ta => {
                    ta.style.height = 'auto';
                    if (ta.scrollHeight > 0) ta.style.height = ta.scrollHeight + 'px';
                });
            }, 0);
        });

        // Keep active KRA tab in range when records change
        onWillUpdateProps(async (nextProps) => {
            const nextCount = nextProps.record.data[this.props.name]?.records?.length || 0;
            if (this.state.activeTabIndex >= nextCount && nextCount > 0) {
                this.state.activeTabIndex = nextCount - 1;
            } else if (nextCount === 0) {
                this.state.activeTabIndex = 0;
            }
        });
    }

    // ══════════════════════════════════════════════════════════════════════════
    // Mode detection
    // ══════════════════════════════════════════════════════════════════════════

    get mode() {
        if (this.props.record.resModel === 'appraisal.template') return 'template';
        if (this.props.options?.mode) return this.props.options.mode;
        const fieldOptions = this.props.record.activeFields?.[this.props.name]?.options;
        if (fieldOptions?.mode) return fieldOptions.mode;
        return 'employee';
    }

    get isTemplateMode()            { return this.mode === 'template'; }
    get isEmployeeMode()            { return this.mode === 'employee'; }
    get isSupervisorMode()          { return this.mode === 'supervisor'; }
    get isAppraisalEmployeeMode()   { return this.mode === 'appraisal_employee'; }
    get isAppraisalSupervisorMode() { return this.mode === 'appraisal_supervisor'; }
    get isAppraisalPhase()          { return this.isAppraisalEmployeeMode || this.isAppraisalSupervisorMode; }

    // ══════════════════════════════════════════════════════════════════════════
    // Adhoc helpers
    // ══════════════════════════════════════════════════════════════════════════

    get adhocTabVisible() {
        return this.isAppraisalPhase && !!this.props.record.data.adhoc_tab_active;
    }

    get isAdhocTabActive() {
        return this.state.isAdhocActive;
    }

    get adhocRecords() {
        const field = this.props.record.data['adhoc_activity_ids'];
        if (!field) return [];
        return field.records || [];
    }

    get canEditAdhoc() {
        return !this.props.readonly && !!this.props.record.data.can_employee_self_rate;
    }

    async onAddAdhocActivity() {
        if (!this.canEditAdhoc) return;
        
        // 1. Create directly in the database using ORM
        await this.orm.create('pms.adhoc.activity', [{
            appraisal_id: this.props.record.resId,
            title: 'New Activity',
            description: '',
            category: 'project',
            completed_date: window.luxon.DateTime.now().toISODate()
        }]);
        
        // 2. Reload the UI to show the newly saved row
        await this.props.record.load();
    }

    async onDeleteAdhocActivity(adhocRecord) {
        if (!this.canEditAdhoc) return;
        this.dialog.add(ConfirmationDialog, {
            title: 'Remove Activity',
            body: 'Are you sure you want to remove this activity?',
            confirmLabel: 'Remove',
            confirm: async () => {
                try {
                    if (adhocRecord.resId) {
                        // Delete directly from database
                        await this.orm.unlink('pms.adhoc.activity', [adhocRecord.resId]);
                    }
                    await this.props.record.load();
                } catch (e) {
                    console.error('Error deleting adhoc activity:', e);
                }
            },
            cancel: () => {},
        });
    }

    async onAdhocFieldChange(record, fieldName, event) {
        if (this.props.readonly) return;
        let value = event.target.value;
        let ormValue = value;

        // Ensure dates are parsed properly for OWL vs Backend
        if (fieldName === 'completed_date') {
            ormValue = value ? value : false; // Backend wants string
            value = value ? window.luxon.DateTime.fromISO(value) : false; // OWL wants Luxon
        }

        // 1. Update local UI so typing feels instant
        await record.update({ [fieldName]: value });

        // 2. Save directly to the database in real-time
        if (record.resId) {
            await this.orm.write('pms.adhoc.activity', [record.resId], {
                [fieldName]: ormValue
            });
        }
    }

    async onUploadAdhocDocument(adhocRecord, ev) {
        const files = ev.target.files;
        if (!files || files.length === 0) return;
        const maxSize = 300 * 1024;
        const attachmentIds = [];
        
        for (const file of files) {
            if (file.size > maxSize) {
                this.notification.add(`File "${file.name}" exceeds 300KB limit.`, { type: 'danger' });
                continue;
            }
            const base64Data = await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = (e) => resolve(e.target.result.split(',')[1]);
                reader.readAsDataURL(file);
            });
            const ids = await this.orm.create('ir.attachment', [{
                name: file.name,
                type: 'binary',
                datas: base64Data,
                res_model: 'pms.adhoc.activity',
                res_id: adhocRecord.resId || 0,
            }]);
            attachmentIds.push(ids[0]);
        }
        
        if (attachmentIds.length && adhocRecord.resId) {
            // Link attachments in the database directly (Command 4 = link)
            const commands = attachmentIds.map(id => [4, id]);
            await this.orm.write('pms.adhoc.activity', [adhocRecord.resId], {
                evidence_attachment_ids: commands
            });
            await this.props.record.load();
        }
        ev.target.value = '';
    }

    async onRemoveAdhocDocument(adhocRecord, attachmentResId) {
        if (adhocRecord.resId) {
            // Unlink attachment in the database directly (Command 3 = unlink)
            await this.orm.write('pms.adhoc.activity', [adhocRecord.resId], {
                evidence_attachment_ids: [[3, attachmentResId]]
            });
            await this.props.record.load();
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // KRA helpers
    // ══════════════════════════════════════════════════════════════════════════

    get kraRecords() {
        return this.props.record.data[this.props.name]?.records || [];
    }

    get hasKras()    { return this.kraRecords.length > 0; }
    get activeKRA()  { return this.kraRecords[this.state.activeTabIndex] || null; }
    get activeKPIs() { return this.activeKRA?.data.kpi_ids?.records || []; }

    get activeDeselectedKPIs() {
        return this.activeKPIs.filter(kpi => !kpi.data.is_selected);
    }

    get activeTotalScore() {
        if (this.isTemplateMode)
            return this.activeKPIs.reduce((s, k) => s + (k.data.score || 0), 0);
        return this.activeKPIs
            .filter(k => k.data.is_selected)
            .reduce((s, k) => s + (k.data.weightage || 0), 0);
    }

    // ══════════════════════════════════════════════════════════════════════════
    // Tab switching — KRA tabs and Competency tab are mutually exclusive
    // ══════════════════════════════════════════════════════════════════════════

    /** True when the "Competency Framework" tab is the active tab */
    get isCompetencyTabActive() {
        return this.state.isCompetencyActive;
    }

    /** Click a KRA tab — deactivates Competency and Adhoc tabs */
    setActiveKraTab(idx) {
        this.state.activeTabIndex     = idx;
        this.state.isCompetencyActive = false;
        this.state.isAdhocActive      = false;
        this.state.showRestorePanel   = false;
    }

    /** Click the Competency Framework tab */
    onActivateCompetencyTab() {
        this.state.isCompetencyActive = true;
        this.state.isAdhocActive      = false;
        this.state.showRestorePanel   = false;
    }

    /** Click the Adhoc tab */
    onActivateAdhocTab() {
        this.state.isAdhocActive      = true;
        this.state.isCompetencyActive = false;
        this.state.showRestorePanel   = false;
    }

    // Legacy alias used by older template references
    setActiveTab(idx) { this.setActiveKraTab(idx); }
    isActiveTab(idx)  { return this.state.activeTabIndex === idx; }

    // ══════════════════════════════════════════════════════════════════════════
    // Competency section
    // ══════════════════════════════════════════════════════════════════════════

    _getM2oId(val) {
        if (!val) return undefined;
        if (Array.isArray(val)) return val[0];
        if (typeof val === 'object') return val.id;
        return val;
    }

    get competencyScoreRecords() {
        const field = this.props.record.data['competency_score_ids'];
        if (!field) return [];
        return field.records || [];
    }

    get competencyGroups() {
        const rows = this.competencyScoreRecords;
        if (!rows.length) return [];

        const map   = new Map();
        const order = [];

        for (const row of rows) {
            const gid   = this._getM2oId(row.data.group_id);
            const gname = row.data.group_name    || 'Group';
            const gcode = row.data.group_hr_code || '';
            const gseq  = row.data.group_sequence || 0;
            const key   = (gid !== undefined && gid !== false) ? gid : gname;

            if (!map.has(key)) {
                map.set(key, { groupKey: key, groupId: gid, groupName: gname,
                               groupCode: gcode, groupSeq: gseq, rows: [] });
                order.push(key);
            }
            map.get(key).rows.push(row);
        }

        const sorted = order
            .map(k => map.get(k))
            .sort((a, b) => (a.groupSeq - b.groupSeq) ||
                             String(a.groupName).localeCompare(String(b.groupName)));

        for (const grp of sorted) {
            grp.rows.sort((a, b) =>
                (a.data.line_sequence || 0) - (b.data.line_sequence || 0));
        }

        return sorted;
    }

    get hasCompetencyData()       { return this.competencyGroups.length > 0; }
    get activeCompetencyGroup()   { return this.competencyGroups[this.state.activeCompGroup] || null; }
    get activeCompetencyRows()    { return this.activeCompetencyGroup?.rows || []; }
    get activeCompGroupTotalPts() {
        return this.activeCompetencyRows.reduce((s, r) => s + (r.data.line_points || 0), 0);
    }

    /** Aggregate totals across ALL competency score rows (used in summary bar) */
    get competencyTotals() {
        const rows = this.competencyScoreRecords;
        return {
            max:        rows.reduce((s, r) => s + (r.data.line_points                || 0), 0),
            self:       rows.reduce((s, r) => s + (r.data.self_score                 || 0), 0),
            supervisor: rows.reduce((s, r) => s + (r.data.supervisor_score           || 0), 0),
            secondary:  rows.reduce((s, r) => s + (r.data.secondary_supervisor_score || 0), 0),
            reviewer:   rows.reduce((s, r) => s + (r.data.reviewer_score             || 0), 0),
        };
    }

    setActiveCompGroup(idx) { this.state.activeCompGroup = idx; }
    isActiveCompGroup(idx)  { return this.state.activeCompGroup === idx; }

    async onCompetencyScoreChange(scoreRecord, fieldName, event) {
        if (this.props.readonly) return;
        let value = event.target.value;
        if (['self_score','supervisor_score','secondary_supervisor_score','reviewer_score']
                .includes(fieldName)) {
            value = parseFloat(value) || 0.0;
        }
        await scoreRecord.update({ [fieldName]: value });
    }

    onExpandCompetency() {
        if (!this.activeCompetencyGroup) return;
        this.dialog.add(CompetencyExpandDialog, {
            groupName:     this.activeCompetencyGroup.groupName,
            scoreRows:     this.activeCompetencyRows,
            record:        this.props.record,
            onScoreChange: (row, field, ev) => this.onCompetencyScoreChange(row, field, ev),
        });
    }

    // ══════════════════════════════════════════════════════════════════════════
    // KRA actions
    // ══════════════════════════════════════════════════════════════════════════

    onViewKpiHistory(kpiRecord, historyType) {
        this.dialog.add(KpiHistoryDialog, {
            kpiName:      kpiRecord.data.name || '',
            kpiData:      kpiRecord.data,
            hasSecondary: !!this.props.record.data.secondary_supervisor_id,
            historyType:  historyType,
        });
    }

    onExpandAppraisal() {
        this.dialog.add(AppraisalExpandDialog, {
            kraName:       this.activeKRA?.data.name || 'KRA',
            kpis:          this.activeKPIs,
            record:        this.props.record,
            onFieldChange: (kpi, field, ev) => this.onKPIFieldChange(kpi, field, ev),
        });
    }

    async onAddKRA() {
        if (this.props.readonly || !this.isTemplateMode) return;
        const existingNames = this.kraRecords.map(k => k.data.name).filter(Boolean);
        this.dialog.add(AddKraDialog, {
            existingNames,
            onConfirm: async (kraName) => { await this.createKRA(kraName); },
        });
    }

    async createKRA(kraName) {
        const maxSeq = this.kraRecords.length > 0
            ? Math.max(...this.kraRecords.map(k => k.data.sequence || 0)) : 0;
        await this.props.record.update({
            [this.props.name]: [[0, 0, { name: kraName, sequence: maxSeq + 10 }]],
        });
        this.state.activeTabIndex     = this.kraRecords.length - 1;
        this.state.isCompetencyActive = false;
    }

    async onDuplicateKPI(kpiRecord) {
        if (this.props.readonly || !this.activeKRA) return;
        await this.activeKRA.update({
            kpi_ids: [[0, 0, {
                name:            kpiRecord.data.name,
                description:     kpiRecord.data.description,
                criteria:        kpiRecord.data.criteria,
                weightage:       0.0,
                template_kpi_id: kpiRecord.data.template_kpi_id
                                   ? this._getM2oId(kpiRecord.data.template_kpi_id) : false,
                is_selected:     true,
                is_clone:        true,
                target:          '',
                planning_remarks:'',
            }]],
        });
    }

async onUploadDocuments(kra, ev) {
        const files = ev.target.files;
        if (!files || files.length === 0) return;

        // NEW: Show a warning if they drag-and-drop multiple files
        if (files.length > 1) {
            this.env.services.notification.add(
                `You can only attach one document per KRA. Only the first file ("${files[0].name}") was kept.`, 
                { type: 'warning' }
            );
        }

        // 1. Force the system to ONLY look at the very first file selected
        const file = files[0];
        const maxSize = 300 * 1024; // 300KB

        if (file.size > maxSize) {
            this.env.services.notification.add(
                `File "${file.name}" exceeds 300KB limit.`, 
                { type: 'danger' }
            );
            ev.target.value = "";
            return;
        }

        // 2. Convert to Base64
        const base64Data = await new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result.split(',')[1]);
            reader.readAsDataURL(file);
        });

        // 3. Create the single file in the database
        const attachmentId = await this.env.services.orm.create("ir.attachment", [{
            name: file.name,
            type: 'binary',
            datas: base64Data,
            res_model: 'pms.appraisal.kra',
            res_id: kra.resId || 0,
        }]);

        // 4. Command 6 overwrites any existing file with this NEW single file.
        await kra.update({
            evidence_attachment_ids: [[6, 0, [attachmentId[0]]]]
        });

        // Clear the input 
        ev.target.value = "";
    }

    async onRemoveDocument(kra, attachmentResId) {
        await kra.update({
            evidence_attachment_ids: [[3, attachmentResId]]
        });
    }

    onViewDocument(attachmentResId) {
        if (!attachmentResId || typeof attachmentResId !== 'number') return;
        window.open(`/web/content/${attachmentResId}?download=false`, '_blank');
    }

    async onDeleteKRA() {
        if (this.props.readonly || !this.activeKRA || this.state.isDeleting || !this.isTemplateMode) return;
        this.state.isDeleting = true;
        try {
            await this.props.record.data[this.props.name].delete(this.activeKRA);
            const newLen = this.kraRecords.length;
            if (this.state.activeTabIndex >= newLen && newLen > 0)
                this.state.activeTabIndex = newLen - 1;
            else if (newLen === 0) this.state.activeTabIndex = 0;
        } catch (e) { console.error("Error deleting KRA:", e); }
        finally     { this.state.isDeleting = false; }
    }

    async onAddKPI() {
        if (this.props.readonly || !this.activeKRA || !this.isTemplateMode) return;
        await this.activeKRA.update({
            kpi_ids: [[0, 0, { name:'', description:'', criteria:'', score:0.0 }]],
        });
    }

    async onDeleteKPI(kpiRecord) {
        if (this.props.readonly || !this.activeKRA || this.state.isDeleting || this.isSupervisorMode) return;
        this.state.isDeleting = true;
        try {
            if (this.isTemplateMode) {
                await this.activeKRA.data.kpi_ids.delete(kpiRecord);
            } else if (this.isEmployeeMode) {
                if (kpiRecord.isNew || kpiRecord.data.is_clone) {
                    await this.activeKRA.data.kpi_ids.delete(kpiRecord);
                } else {
                    await kpiRecord.update({ is_selected: false });
                }
            }
        } catch (e) { console.error("Error deleting KPI:", e); }
        finally     { this.state.isDeleting = false; }
    }

    async onRestoreKPI(kpiRecord) {
        if (this.props.readonly) return;
        await kpiRecord.update({ is_selected: true });
    }

    onToggleRestorePanel() { this.state.showRestorePanel = !this.state.showRestorePanel; }

    async onKPIFieldChange(kpiRecord, fieldName, event) {
        if (this.props.readonly) return;
        let value = event.target.value;
        if (['score','weightage','self_score','supervisor_score',
             'secondary_supervisor_score','reviewer_score'].includes(fieldName)) {
            value = parseFloat(value) || 0.0;
        }
        await kpiRecord.update({ [fieldName]: value });
    }

    async onKPICheckboxChange(kpiRecord, event) {
        if (this.props.readonly) return;
        await kpiRecord.update({ is_selected: event.target.checked });
    }
}

registry.category("fields").add("kra_tabs_widget", {
    component: KraTabs,
    supportedTypes: ["one2many"],
    extractProps: ({ options }) => ({ options: options || {} }),
});