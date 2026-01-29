/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class KraTabs extends Component {
    static template = "hr_employee_evaluation.KraTabs";
    static props = {
        record: Object,
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.isDestroyed = false;

        this.state = useState({
            kras: [],
            activeKraId: null,
            activeKraKpis: [],
        });

        onWillStart(async () => {
            await this.safeLoadKras();
        });

        onWillUpdateProps(async (nextProps) => {
            if (this.isDestroyed) return;

            const currentKraCount = this.props.record.data.kra_ids?.records?.length || 0;
            const nextKraCount = nextProps.record.data.kra_ids?.records?.length || 0;

            if (currentKraCount !== nextKraCount || nextProps.record !== this.props.record) {
                await this.safeLoadKras();
            }
        });

        onWillUnmount(() => {
            this.isDestroyed = true;
        });
    }

    async safeLoadKras() {
        if (this.isDestroyed) return;
        await this.loadKras();
    }

    async loadKras() {
        const templateId = this.props.record.data.id;
        if (!templateId) {
            this.state.kras = [];
            this.state.activeKraId = null;
            this.state.activeKraKpis = [];
            return;
        }

        const kras = await this.orm.searchRead(
            "appraisal.kra",
            [["template_id", "=", templateId]],
            ["id", "name", "sequence", "kpi_count", "total_score"],
            { order: "sequence, id" }
        );
        if (this.isDestroyed) return;

        this.state.kras = kras;

        const activeStillExists = kras.some(k => k.id === this.state.activeKraId);

        if (!activeStillExists && kras.length) {
            await this.setActiveKra(kras[0].id);
        } else if (!activeStillExists) {
            this.state.activeKraId = null;
            this.state.activeKraKpis = [];
        } else if (this.state.activeKraId) {
            await this.loadKpisForKra(this.state.activeKraId);
        }
    }

    async setActiveKra(kraId) {
        if (this.isDestroyed) return;

        this.state.activeKraId = kraId;
        await this.loadKpisForKra(kraId);

        if (this.props.record.data.id) {
            await this.orm.write(
                "appraisal.template",
                [this.props.record.data.id],
                { active_kra_id: kraId }
            );
        }
    }

    async loadKpisForKra(kraId) {
        if (!kraId || this.isDestroyed) {
            this.state.activeKraKpis = [];
            return;
        }

        const kpis = await this.orm.searchRead(
            "appraisal.kpi",
            [["kra_id", "=", kraId]],
            ["id", "name", "description", "score", "criteria"],
            { order: "id" }
        );
        if (this.isDestroyed) return;

        this.state.activeKraKpis = kpis;
    }

    async onKpiChange(kpiId, field, value) {
        const kpi = this.state.activeKraKpis.find(k => k.id === kpiId);
        if (!kpi) return;

        const newValue = field === "score" ? Number(value) || 0 : value;
        kpi[field] = newValue;

        try {
            await this.orm.write("appraisal.kpi", [kpiId], { [field]: newValue });
        } catch (err) {
            await this.loadKpisForKra(this.state.activeKraId);
            throw err;
        }
    }

    async addKpi() {
        if (this.props.readonly || !this.state.activeKraId || this.isDestroyed) return;

        try {
            await this.orm.create("appraisal.kpi", [{
                kra_id: this.state.activeKraId,
                name: "New KPI",
                description: "Describe KPI",
                criteria: "Define criteria",
                score: 0.0,
            }]);
            await this.safeLoadKras();
        } catch (err) {
            console.error("Failed to add KPI:", err);
        }
    }

    async deleteKpi(kpiId) {
        if (this.props.readonly || this.isDestroyed) return;

        await this.orm.unlink("appraisal.kpi", [kpiId]);
        await this.safeLoadKras();
    }

    isActiveKra(kraId) {
        return this.state.activeKraId === kraId;
    }

    hasKras() {
        return this.state.kras.length > 0;
    }

    getActiveKra() {
        return this.state.kras.find(k => k.id === this.state.activeKraId);
    }
}

registry.category("fields").add("kra_tabs_widget", { component: KraTabs });
