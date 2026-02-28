/** @odoo-module **/

import { Component, useState, onWillUpdateProps, useEffect, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

class AddKraDialog extends Component {
    static template = "hr_employee_evaluation.AddKraDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        onConfirm: Function,
        existingNames: { type: Array, optional: true },
    };

    setup() {
        this.state = useState({
            kraName: "",
            error: "",
        });
    }

    onConfirm() {
        const name = this.state.kraName.trim();
        if (!name) {
            this.state.error = "KRA name is required";
            return;
        }
        if (this.props.existingNames && this.props.existingNames.includes(name)) {
            this.state.error = "A KRA with this name already exists";
            return;
        }
        this.props.onConfirm(name);
        this.props.close();
    }

    onKeydown(ev) {
        if (ev.key === "Enter") this.onConfirm();
    }

    onNameChange(ev) {
        this.state.kraName = ev.target.value;
        this.state.error = "";
    }
}

export class KraTabs extends Component {
    static template = "hr_employee_evaluation.KraTabs";
    static props = {
        record: Object,
        readonly: { type: Boolean, optional: true },
        name: String,
        id: { type: String, optional: true },
        // options is now reliably populated via extractProps below
        options: { type: Object, optional: true },
    };

    setup() {
        this.rootRef = useRef("root"); //Reference root container for dynamic textarea resizing
        this.dialog = useService("dialog");
        this.state = useState({
            activeTabIndex: 0,
            isDeleting: false,
            showRestorePanel: false, // toggles the restore panel for employee mode
        });

        useEffect(() => { //for setting height of textareas to fit content on initial render and when active tab changes on runtime
            if (this.rootRef.el) {
                setTimeout(() => {
                    if (!this.rootRef.el) return;
                    const textareas = this.rootRef.el.querySelectorAll('textarea');
                    textareas.forEach(ta => {
                        ta.style.height = 'auto'; // Reset height temporarily
                        if (ta.scrollHeight > 0) {
                            ta.style.height = ta.scrollHeight + 'px'; // Expand to fit content
                        }
                    });
                }, 0);
            }
        });

        onWillUpdateProps(async (nextProps) => {
            const nextKraCount = nextProps.record.data[this.props.name]?.records?.length || 0;
            if (this.state.activeTabIndex >= nextKraCount && nextKraCount > 0) {
                this.state.activeTabIndex = nextKraCount - 1;
            } else if (nextKraCount === 0) {
                this.state.activeTabIndex = 0;
            }
        });
    }

    // Mode detection (supervisor or employee) is based on options passed from XML or activeFields, with a fallback to 'employee' if not specified. Template mode is determined by the model.
    get mode() {
        // Check what database model we currently are on
        if (this.props.record.resModel === 'appraisal.template') {
            // If in template creation mode, show all buttons and editable fields
            return 'template';
        }

        // Read mode from options 
        // options="{'mode': 'supervisor'}" in XML → props.options.mode === 'supervisor'
        if (this.props.options && this.props.options.mode) {
            return this.props.options.mode;
        }

        // Fallback: read from activeFields in case the widget is used without
        if (
            this.props.record &&
            this.props.record.activeFields &&
            this.props.record.activeFields[this.props.name]
        ) {
            const fieldOptions = this.props.record.activeFields[this.props.name].options;
            if (fieldOptions && fieldOptions.mode) {
                return fieldOptions.mode;
            }
        }

        //Employee planning mode (hide all buttons and make target, remarks and score fields editable)
        return 'employee'; // Default
    }

    get isTemplateMode() {
        return this.mode === 'template';
    }

    get isEmployeeMode() {
        return this.mode === 'employee';
    }

    get isSupervisorMode() {
        return this.mode === 'supervisor';
    }

    // Controls whether the Supervisor Remarks column is visible in the employee table. (not needed for now)
    // get showSupervisorRemarks() {
    //     return !!(this.props.options && this.props.options.show_supervisor_remarks);
    // }

    isVirtualId(id) {
        return typeof id === 'string' || id < 0;
    }

    getRecordId(record) {
        return record.resId !== undefined ? record.resId : record.id;
    }

    get kraRecords() {
        return this.props.record.data[this.props.name]?.records || [];
    }

    get hasKras() {
        return this.kraRecords.length > 0;
    }

    get activeKRA() {
        return this.kraRecords[this.state.activeTabIndex] || null;
    }

    get activeKPIs() {
        return this.activeKRA?.data.kpi_ids?.records || [];
    }

    get activeDeselectedKPIs() {
        // KPIs that the employee has soft-deleted (deselected) — used by the restore panel.
        return this.activeKPIs.filter(kpi => !kpi.data.is_selected);
    }

    get activeTotalScore() {
        if (this.isTemplateMode) {
            // Template: sum of 'score' field
            return this.activeKPIs.reduce((sum, kpi) => sum + (kpi.data.score || 0), 0);
        } else {
            // Employee/Supervisor: sum of selected 'weightage' field
            return this.activeKPIs
                .filter(kpi => kpi.data.is_selected)
                .reduce((sum, kpi) => sum + (kpi.data.weightage || 0), 0);
        }
    }

    async onAddKRA() {
        if (this.props.readonly) return;
        // Only allow in template mode
        if (!this.isTemplateMode) return;
        
        const existingNames = this.kraRecords.map(kra => kra.data.name).filter(Boolean);

        this.dialog.add(AddKraDialog, {
            existingNames: existingNames,
            onConfirm: async (kraName) => {
                await this.createKRA(kraName);
            },
        });
    }

    async createKRA(kraName) {
        const maxSequence = this.kraRecords.length > 0
            ? Math.max(...this.kraRecords.map(k => k.data.sequence || 0))
            : 0;

        await this.props.record.update({
            [this.props.name]: [
                [0, 0, {
                    name: kraName,
                    sequence: maxSequence + 10,
                }]
            ]
        });

        this.state.activeTabIndex = this.kraRecords.length - 1;
    }

    async onDuplicateKPI(kpiRecord) {
        if (this.props.readonly || !this.activeKRA) return;
        
        await this.activeKRA.update({
            kpi_ids: [
                [0, 0, {
                    name: kpiRecord.data.name,
                    description: kpiRecord.data.description,
                    criteria: kpiRecord.data.criteria,
                    weightage: 0.0, 
                    template_kpi_id: kpiRecord.data.template_kpi_id ? kpiRecord.data.template_kpi_id[0] : false,
                    is_selected: true,
                    is_clone: true, 
                    target: "", 
                    planning_remarks: "" 
                }]
            ]
        });
    }

    async onDeleteKRA() {
        if (this.props.readonly || !this.activeKRA || this.state.isDeleting) return;
        // Only allow in template mode
        if (!this.isTemplateMode) return;

        this.state.isDeleting = true;
        
        try {
            const kraList = this.props.record.data[this.props.name];
            await kraList.delete(this.activeKRA);

            const newLength = this.kraRecords.length;
            if (this.state.activeTabIndex >= newLength && newLength > 0) {
                this.state.activeTabIndex = newLength - 1;
            } else if (newLength === 0) {
                this.state.activeTabIndex = 0;
            }
        } catch (error) {
            console.error("Error deleting KRA:", error);
        } finally {
            this.state.isDeleting = false;
        }
    }
    

    setActiveTab(index) {
        this.state.activeTabIndex = index;
    }

    isActiveTab(index) {
        return this.state.activeTabIndex === index;
    }

    async onAddKPI() {
        if (this.props.readonly || !this.activeKRA) return;
        // Only allow in template mode
        if (!this.isTemplateMode) return;

        await this.activeKRA.update({
            kpi_ids: [
                [0, 0, {
                    name: "",
                    description: "",
                    criteria: "",
                    score: 0.0,
                }]
            ]
        });
    }

    // async onDeleteKPI(kpiRecord) {
    //     if (this.props.readonly || !this.activeKRA || this.state.isDeleting) return;
    //     // Allow in template AND employee modes, NOT supervisor (come here later for employee)
    //     if (this.isSupervisorMode) return;

    //     if (this.isEmployeeMode) {
    //         // Soft-delete: deselect the KPI rather than removing it from the database.
    //         // This preserves the template structure and allows the employee to restore it.
    //         // The server-side write() allows is_selected changes for employees.
    //         await kpiRecord.update({ is_selected: false });
    //         return;
    //     }
        
    //     this.state.isDeleting = true;

    //     try {
    //         const kpiList = this.activeKRA.data.kpi_ids;
    //         await kpiList.delete(kpiRecord);
    //     } catch (error) {
    //         console.error("Error deleting KPI:", error);
    //     } finally {
    //         this.state.isDeleting = false;
    //     }
    // }
    async onDeleteKPI(kpiRecord) {
        if (this.props.readonly || !this.activeKRA || this.state.isDeleting) return;
        if (this.isSupervisorMode) return;
        
        this.state.isDeleting = true;

        try {
            if (this.isTemplateMode) {
                // HR Mode: Hard Delete from the template database
                const kpiList = this.activeKRA.data.kpi_ids;
                await kpiList.delete(kpiRecord);
            } else if (this.isEmployeeMode) {
                // Employee Mode: Check if it's an unsaved ghost OR a saved clone
                if (kpiRecord.isNew || kpiRecord.data.is_clone) {
                    // Destroy clones permanently
                    const kpiList = this.activeKRA.data.kpi_ids;
                    await kpiList.delete(kpiRecord);
                } else {
                    // Original HR Template KPI: Soft-delete it so it goes to the Restore panel
                    await kpiRecord.update({ is_selected: false });
                }
            }
        } catch (error) {
            console.error("Error deleting KPI:", error);
        } finally {
            this.state.isDeleting = false;
        }
    }

    async onRestoreKPI(kpiRecord) {
        // Re-selects a soft-deleted KPI, making it visible in the employee table again.
        if (this.props.readonly) return;
        await kpiRecord.update({ is_selected: true });
    }

    onToggleRestorePanel() {
        // Shows/hides the restore panel listing all deselected KPIs for this KRA.
        this.state.showRestorePanel = !this.state.showRestorePanel;
    }

    async onKPIFieldChange(kpiRecord, fieldName, event) {
        if (this.props.readonly) return;
        
        let value = event.target.value;
        if (fieldName === "score" || fieldName === "weightage") {
            value = parseFloat(value) || 0.0;
        }
        
        await kpiRecord.update({ [fieldName]: value });
    }

    async onKPICheckboxChange(kpiRecord, event) {
        if (this.props.readonly) return;
        const checked = event.target.checked;
        await kpiRecord.update({ is_selected: checked });
    }
}

registry.category("fields").add("kra_tabs_widget", {
    component: KraTabs,
    supportedTypes: ["one2many"],
    extractProps: ({ options }, dynamicInfo) => ({
        options: options || {},
    }),
});