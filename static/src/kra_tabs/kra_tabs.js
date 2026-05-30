/** @odoo-module **/

import { Component, useState, onWillUpdateProps, useEffect, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

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
        historyType: String,
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
        close: Function,
        kraName: String,
        kpis: Array,
        record: Object,
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
        close: Function,
        groupName: String,
        scoreRows: Array,
        record: Object,
        onScoreChange: Function,
    };
}

// ─────────────────────────────────────────────────────────────────────────────
// KraTabs — main widget
// ─────────────────────────────────────────────────────────────────────────────
export class KraTabs extends Component {
    static template = "hr_employee_evaluation.KraTabs";
    static props = {
        record: Object,
        readonly: { type: Boolean, optional: true },
        name: String,
        id: { type: String, optional: true },
        options: { type: Object, optional: true },
    };

    setup() {
        this.kraRef = useRef("kraBlock");
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            activeTabIndex: 0,
            isCompetencyActive: false,
            isDeleting: false,
            showRestorePanel: false,
            activeCompGroup: 0,
            competencyGroups: [],
            competencyTotals: { max: 0, self: 0, supervisor: 0, secondary: 0, reviewer: 0 },
            hasCompetencyData: false,
            isLoading: true,
            kraAttachments: {}, 
            editingKraId: null,
            kraEditName: "",
            draggedKraId: null,
            dragOverKraId: null,
        });


        onWillUpdateProps(async (nextProps) => {
            const nextResId = nextProps.record.resId;

            // Only reload from server when the record itself changes
            // (e.g. user navigates to a different appraisal).
            if (nextResId !== this._loadedForResId) {
                await this._loadCompetencyDataFromServer(nextResId, nextProps.record);
            }
            await this._loadAttachmentsFromServer(nextProps.record);
            // Adjust the active KRA tab index if KRAs were added/removed.
            const nextCount = nextProps.record.data[this.props.name]?.records?.length || 0;
            if (this.state.activeTabIndex >= nextCount && nextCount > 0) {
                this.state.activeTabIndex = nextCount - 1;
            } else if (nextCount === 0) {
                this.state.activeTabIndex = 0;
            }
        });

        // Initial load
        (async () => {
            await this._loadCompetencyDataFromServer(
                this.props.record.resId,
                this.props.record
            );
            await this._loadAttachmentsFromServer(this.props.record); // <--- ADD THIS LINE
        })();

        this._loadedForResId = null;

        // Scroll-fade
        useEffect(() => {
            const header = this.kraRef.el?.querySelector('.o_kra_tabs_header');
            const nav = this.kraRef.el?.querySelector('.o_kra_tabs_nav');
            if (!header || !nav) return;
            const updateFades = () => {
                const s = nav.scrollLeft, m = nav.scrollWidth - nav.clientWidth;
                header.classList.toggle('can-scroll-left', s > 2);
                header.classList.toggle('can-scroll-right', s < m - 2);
            };
            nav.addEventListener('scroll', updateFades, { passive: true });
            updateFades();
            return () => nav.removeEventListener('scroll', updateFades);
        });

        // Auto-resize textareas
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
        
    }

    // ─── Internal: load from server and reset in-memory cache ────────────────

    async _loadCompetencyDataFromServer(resId, record) {
        if (!resId) {
            this.state.hasCompetencyData = false;
            this.state.isLoading = false;
            this._loadedForResId = null;
            return;
        }

        try {
            this.state.isLoading = true;
            const result = await this.orm.call(
                'pms.appraisal',
                'get_competency_data',
                [[resId]],
                {}
            );

            if (result) {
                this.state.hasCompetencyData = result.has_competency_data || false;

                const processedGroups = (result.competency_groups || []).map(group => ({
                    ...group,
                    rows: (group.rows || []).map(row => ({
                        id: row.id,
                        score_id: row.score_id || false,   // real appraisal.competency.score id
                        data: {
                            line_full_code: row.line_full_code || '',
                            line_name: row.line_name || '',
                            line_description: row.line_description || '',
                            line_points: row.line_points || 0.0,
                            // self_score: row.self_score !== undefined && row.self_score !== false ? row.self_score : false,
                            // self_remarks: row.self_remarks || '',
                            // supervisor_score: row.supervisor_score !== undefined && row.supervisor_score !== false ? row.supervisor_score : false,
                            // supervisor_remarks: row.supervisor_remarks || '',
                            // secondary_supervisor_score: row.secondary_supervisor_score !== undefined && row.secondary_supervisor_score !== false ? row.secondary_supervisor_score : false,
                            // secondary_supervisor_remarks: row.secondary_supervisor_remarks || '',
                            // reviewer_score: row.reviewer_score !== undefined && row.reviewer_score !== false ? row.reviewer_score : false,
                            // reviewer_remarks: row.reviewer_remarks || '',

                            self_score: row.self_score || false,
                            self_remarks: row.self_remarks || '',
                            supervisor_score: row.supervisor_score || false,
                            supervisor_remarks: row.supervisor_remarks || '',
                            secondary_supervisor_score: row.secondary_supervisor_score || false,
                            secondary_supervisor_remarks: row.secondary_supervisor_remarks || '',
                            reviewer_score: row.reviewer_score || false,
                            reviewer_remarks: row.reviewer_remarks || '',
                        },
                    }))
                }));

                this.state.competencyGroups = processedGroups;
                this.state.competencyTotals = result.competency_totals || {
                    max: 0, self: 0, supervisor: 0, secondary: 0, reviewer: 0,
                };
                this._loadedForResId = resId;
            }
        } catch (error) {
            console.error('Error loading competency data:', error);
            this.state.hasCompetencyData = false;
        } finally {
            this.state.isLoading = false;
        }
    }

    async _loadAttachmentsFromServer(record) {
        const kraRecords = record.data[this.props.name]?.records || [];
        const allAttachmentIds = [];
        
        kraRecords.forEach(kra => {
            const recs = kra.data.evidence_attachment_ids?.records || [];
            recs.forEach(r => {
                const id = r.resId || r.id;
                if (typeof id === 'number') allAttachmentIds.push(id);
            });
        });

        if (allAttachmentIds.length > 0) {
            const attachments = await this.orm.searchRead('ir.attachment', [['id', 'in', allAttachmentIds]], ['id', 'name', 'file_size']);
            const attMap = {};
            attachments.forEach(a => attMap[a.id] = a);

            kraRecords.forEach(kra => {
                const kraKey = kra.resId || kra.id;
                const recs = kra.data.evidence_attachment_ids?.records || [];
                this.state.kraAttachments[kraKey] = recs.map(r => attMap[r.resId || r.id]).filter(Boolean);
            });
        } else {
            kraRecords.forEach(kra => {
                this.state.kraAttachments[kra.resId || kra.id] = [];
            });
        }
    }

    // ─── Recompute totals from in-memory rows (no server call needed) ─────────

    _recomputeCompetencyTotals() {
        let max = 0, self = 0, supervisor = 0, secondary = 0, reviewer = 0;
        for (const group of this.state.competencyGroups) {
            for (const row of group.rows) {
                max        += row.data.line_points || 0;
                self       += row.data.self_score || 0;
                supervisor += row.data.supervisor_score || 0;
                secondary  += row.data.secondary_supervisor_score || 0;
                reviewer   += row.data.reviewer_score || 0;
            }
        }
        this.state.competencyTotals = { max, self, supervisor, secondary, reviewer };
    }

    // Mode detection
    get mode() {
        if (this.props.record.resModel === 'appraisal.template') return 'template';
        if (this.props.options?.mode) return this.props.options.mode;
        const fieldOptions = this.props.record.activeFields?.[this.props.name]?.options;
        if (fieldOptions?.mode) return fieldOptions.mode;
        return 'employee';
    }

    get isTemplateMode() { return this.mode === 'template'; }
    get isEmployeeMode() { return this.mode === 'employee'; }
    get isSupervisorMode() { return this.mode === 'supervisor'; }
    get isAppraisalEmployeeMode() { return this.mode === 'appraisal_employee'; }
    get isAppraisalSupervisorMode() { return this.mode === 'appraisal_supervisor'; }
    get isAppraisalPhase() { return this.isAppraisalEmployeeMode || this.isAppraisalSupervisorMode; }

    // KRA helpers
    get kraRecords() {
        const records = this.props.record.data.kra_ids?.records || [];

        return [...records].sort((a, b) => {
            const seqA = a.data.sequence || 0;
            const seqB = b.data.sequence || 0;
            return seqA - seqB;
        });
    }


    get hasKras() { return this.kraRecords.length > 0; }
    get activeKRA() { return this.kraRecords[this.state.activeTabIndex] || null; }
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

    // Competency helpers — read directly from reactive in-memory state
    get competencyGroups() { return this.state.competencyGroups; }
    get hasCompetencyData() { return this.state.hasCompetencyData; }
    get activeCompetencyGroup() { return this.competencyGroups[this.state.activeCompGroup] || null; }
    get activeCompetencyRows() { return this.activeCompetencyGroup?.rows || []; }
    get competencyTotals() { return this.state.competencyTotals; }
    get isCompetencyTabActive() { return this.state.isCompetencyActive; }

    // Tab switching
    setActiveKraTab(idx) {
        this.state.activeTabIndex = idx;
        this.state.isCompetencyActive = false;
        this.state.showRestorePanel = false;
    }

    onActivateCompetencyTab() {
        this.state.isCompetencyActive = true;
        this.state.showRestorePanel = false;
    }

    setActiveTab(idx) { this.setActiveKraTab(idx); }
    isActiveTab(idx) { return this.state.activeTabIndex === idx; }

    setActiveCompGroup(idx) { this.state.activeCompGroup = idx; }
    isActiveCompGroup(idx) { return this.state.activeCompGroup === idx; }

    onEditKraName(kra, ev) {
        ev.stopPropagation(); // Prevent tab from switching
        this.state.editingKraId = kra.id;
        this.state.kraEditName = kra.data.name || '';
    }

    async onSaveKraName(kra, ev) {
        if (ev) ev.stopPropagation();
        const newName = this.state.kraEditName.trim();
        if (newName && newName !== kra.data.name) {
            await kra.update({ name: newName });
        }
        this.state.editingKraId = null;
    }

    onCancelEditKraName(ev) {
        if (ev) ev.stopPropagation();
        this.state.editingKraId = null;
    }

    onKraNameKeydown(kra, ev) {
        if (ev.key === "Enter") {
            this.onSaveKraName(kra, ev);
        } else if (ev.key === "Escape") {
            this.onCancelEditKraName(ev);
        }
    }

    // for kra drag and drop
    onDragStart(kra, ev) {
        if (!this.isTemplateMode) return;
        this.state.draggedKraId = kra.id;
        // Make the tab look semi-transparent while dragging
        setTimeout(() => { ev.target.style.opacity = '0.4'; }, 0);
    }

    onDragEnd(ev) {
        ev.target.style.opacity = '1';
        this.state.draggedKraId = null;
        this.state.dragOverKraId = null;
    }

    onDragOver(kra, ev) {
        ev.preventDefault(); // Required to allow dropping
        if (!this.isTemplateMode || this.state.draggedKraId === kra.id) return;
        this.state.dragOverKraId = kra.id;
    }

    onDragLeave(kra, ev) {
        if (this.state.dragOverKraId === kra.id) {
            this.state.dragOverKraId = null;
        }
    }

    async onDrop(targetKra, ev) {
        ev.preventDefault();
        const draggedId = this.state.draggedKraId;
        this.state.dragOverKraId = null;

        if (!draggedId || draggedId === targetKra.id) return;

        const kras = this.kraRecords;
        const draggedIndex = kras.findIndex(k => k.id === draggedId);
        const targetIndex = kras.findIndex(k => k.id === targetKra.id);

        if (draggedIndex === -1 || targetIndex === -1) return;

        // Rearrange array logically
        const reordered = [...kras];
        const [draggedItem] = reordered.splice(draggedIndex, 1);
        reordered.splice(targetIndex, 0, draggedItem);

        // Save the new sequence to the database (10, 20, 30...)
        for (let i = 0; i < reordered.length; i++) {
            const newSeq = (i + 1) * 10;
            if (reordered[i].data.sequence !== newSeq) {
                await reordered[i].update({ sequence: newSeq });
            }
        }
    }

    async onCompetencyScoreChange(scoreRow, fieldName, event) {
        if (this.props.readonly) return;

        let value = event.target.value;

        const scoreFields = [
            'self_score', 'supervisor_score',
            'secondary_supervisor_score', 'reviewer_score',
        ];

        if (scoreFields.includes(fieldName)) {
            // Allow blank (empty string) — store as false
            if (value === '' || value === null || value === undefined) {
                value = false;
            } else {
                value = parseFloat(value);
                if (isNaN(value)) { value = false; }
            }

            if (value !== false) {
                const maxPoints = scoreRow.data.line_points || 0;

                if (value < 0) {
                    this.notification.add(
                        `${fieldName.replace(/_/g, ' ')} cannot be negative.`,
                        { type: 'warning' }
                    );
                    const prev = scoreRow.data[fieldName];
                    event.target.value = (prev !== false && prev !== null) ? prev : '';
                    return;
                }

                if (value > maxPoints) {
                    this.notification.add(
                        `${fieldName.replace(/_/g, ' ')} cannot exceed ${maxPoints} points.`,
                        { type: 'warning' }
                    );
                    const prev = scoreRow.data[fieldName];
                    event.target.value = (prev !== false && prev !== null) ? prev : '';
                    return;
                }
            }
        } else {
            // Remark text fields — keep as string
            value = String(value);
        }

    
        if (!scoreRow.score_id) {
            console.warn('score_id missing for competency row — attempting reload from server.');
            await this._loadCompetencyDataFromServer(this.props.record.resId, this.props.record);

            // After reload scoreRow is a stale reference; find the refreshed row.
            let refreshedRow = null;
            for (const group of this.state.competencyGroups) {
                refreshedRow = group.rows.find(r => r.id === scoreRow.id);
                if (refreshedRow) break;
            }

            if (!refreshedRow || !refreshedRow.score_id) {
                this.notification.add(
                    'Could not find the competency score record. Please save the record and try again.',
                    { type: 'danger' }
                );
                return;
            }

            scoreRow = refreshedRow;
        }

        const previousValue = scoreRow.data[fieldName];
        scoreRow.data[fieldName] = value;
        this._recomputeCompetencyTotals();

        try {
            await this.orm.call(
                'pms.appraisal',
                'save_competency_score',
                [[this.props.record.resId], scoreRow.score_id, fieldName, value],
                {}
            );
        } catch (err) {
            console.error('Could not persist competency score:', err);
            // Roll back the optimistic local update so the UI is not misleading.
            scoreRow.data[fieldName] = previousValue;
            this._recomputeCompetencyTotals();
            event.target.value = (previousValue !== false && previousValue !== null) ? previousValue : '';
            this.notification.add(
                'Could not save the score. Please try again.',
                { type: 'danger' }
            );
        }
    }

    onExpandCompetency() {
        if (!this.activeCompetencyGroup) return;
        this.dialog.add(CompetencyExpandDialog, {
            groupName: this.activeCompetencyGroup.groupName,
            scoreRows: this.activeCompetencyRows,
            record: this.props.record,
            onScoreChange: (row, field, ev) => this.onCompetencyScoreChange(row, field, ev),
        });
    }

    // KPI field change with immediate validation
    async onKPIFieldChange(kpiRecord, fieldName, event) {
        if (this.props.readonly) return;
        let value = event.target.value;

        if (['score', 'weightage', 'self_score', 'supervisor_score',
            'secondary_supervisor_score', 'reviewer_score'].includes(fieldName)) {
            
            // Allow blank : store as false which defaults to 0 as a score
            if (value === '' || value === null || value === undefined) {
                value = false;
            } else {
                value = parseFloat(value);
                if (isNaN(value)) { value = false; }
            }

            if (value !== false) {
                let maxValue = 0;
                if (['self_score', 'supervisor_score',
                     'secondary_supervisor_score', 'reviewer_score'].includes(fieldName)) {
                    maxValue = kpiRecord.data.weightage || 0;
                } else if (fieldName === 'score' || fieldName === 'weightage') {
                    maxValue = 999999;
                }

                if (value < 0) {
                    this.notification.add(
                        `${fieldName.replace(/_/g, ' ')} cannot be negative.`,
                        { type: 'warning' }
                    );
                    const prev = kpiRecord.data[fieldName];
                    event.target.value = (prev !== false && prev !== null) ? prev : '';
                    return;
                }

                if (maxValue > 0 && maxValue < 999999 && value > maxValue) {
                    this.notification.add(
                        `${fieldName.replace(/_/g, ' ')} cannot exceed ${maxValue}.`,
                        { type: 'warning' }
                    );
                    const prev = kpiRecord.data[fieldName];
                    event.target.value = (prev !== false && prev !== null) ? prev : '';
                    return;
                }
            }
        }

        await kpiRecord.update({ [fieldName]: value });
    }

    // KRA actions
    onViewKpiHistory(kpiRecord, historyType) {
        this.dialog.add(KpiHistoryDialog, {
            kpiName: kpiRecord.data.name || '',
            kpiData: kpiRecord.data,
            hasSecondary: !!this.props.record.data.secondary_supervisor_id,
            historyType: historyType,
        });
    }

    onExpandAppraisal() {
        this.dialog.add(AppraisalExpandDialog, {
            kraName: this.activeKRA?.data.name || 'KRA',
            kpis: this.activeKPIs,
            record: this.props.record,
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
        this.state.activeTabIndex = this.kraRecords.length - 1;
        this.state.isCompetencyActive = false;
    }

    async onDuplicateKPI(kpiRecord) {
        if (this.props.readonly || !this.activeKRA) return;
        await this.activeKRA.update({
            kpi_ids: [[0, 0, {
                name: kpiRecord.data.name,
                description: kpiRecord.data.description,
                criteria: kpiRecord.data.criteria,
                weightage: 0.0,
                template_kpi_id: kpiRecord.data.template_kpi_id
                    ? kpiRecord.data.template_kpi_id[0] : false,
                is_selected: true,
                is_clone: true,
                target: '',
                planning_remarks: '',
            }]],
        });
    }

    async onUploadDocuments(kra, ev) {
        const files = ev.target.files;
        if (!files || files.length === 0) return;

        const MAX_TOTAL_SIZE = 300 * 1024;
        const kraKey = kra.resId || kra.id;
        
        let newFilesSize = 0;
        for (let i = 0; i < files.length; i++) {
            newFilesSize += files[i].size;
        }

        const existingAttachments = this.state.kraAttachments[kraKey] || [];
        const existingSize = existingAttachments.reduce((sum, att) => sum + (att.file_size || 0), 0);

        if (existingSize + newFilesSize > MAX_TOTAL_SIZE) {
            this.notification.add(
                `Total KRA evidence size cannot exceed 300KB. You are trying to add ${(newFilesSize/1024).toFixed(1)}KB to the existing ${(existingSize/1024).toFixed(1)}KB.`,
                { type: 'danger' }
            );
            ev.target.value = ""; 
            return;
        }

        const newAtts = [];
        const commands = [];
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const base64Data = await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = (e) => resolve(e.target.result.split(',')[1]);
                reader.readAsDataURL(file);
            });

            const attId = await this.orm.create("ir.attachment", [{
                name: file.name,
                type: 'binary',
                datas: base64Data,
                res_model: 'pms.appraisal.kra',
                res_id: kra.resId || 0,
            }]);
            
            newAtts.push({ id: attId[0], name: file.name, file_size: file.size });
            
            commands.push([4, attId[0]]);
        }

        // Update local state for immediate perfect UI rendering
        this.state.kraAttachments[kraKey] = [...existingAttachments, ...newAtts];

        // Feed Odoo the "Append" commands so it safely tracks every single file
        await kra.update({ evidence_attachment_ids: commands });

        ev.target.value = ""; 
    }

    async onRemoveDocument(kra, attachmentResId) {
        if (!attachmentResId) return;
        const kraKey = kra.resId || kra.id;
        
        // Update local state immediately for fast UI
        const existingAttachments = this.state.kraAttachments[kraKey] || [];
        this.state.kraAttachments[kraKey] = existingAttachments.filter(a => a.id !== attachmentResId);
        
        // USE COMMAND 3 (DETACH) to safely remove it from Odoo's tracking list
        await kra.update({ evidence_attachment_ids: [[3, attachmentResId]] });
        
        try {
            // Delete the physical file from the DB to free up the 300KB quota
            await this.orm.unlink('ir.attachment', [attachmentResId]);
        } catch (e) {
            console.error("Could not delete attachment from DB", e);
        }
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
        finally { this.state.isDeleting = false; }
    }

    async onAddKPI() {
        if (this.props.readonly || !this.activeKRA || !this.isTemplateMode) return;
        await this.activeKRA.update({
            kpi_ids: [[0, 0, { name: '', description: '', criteria: '', score: 0.0 }]],
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
        finally { this.state.isDeleting = false; }
    }

    async onRestoreKPI(kpiRecord) {
        if (this.props.readonly) return;
        await kpiRecord.update({ is_selected: true });
    }

    onToggleRestorePanel() { this.state.showRestorePanel = !this.state.showRestorePanel; }

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