/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

patch(X2ManyField.prototype, {

    // ── inject the notification service once, during component setup ──
    setup() {
        super.setup(...arguments);
        this._notification = useService("notification");
    },

    /**
     * onAdd is called by the "Add a line" footer button in every
     * editable One2many list.  We intercept it before the default
     * behaviour (inline row creation or dialog open) takes place.
     */
    async onAdd(context, editable) {

        const fieldName = this.props.name;          // e.g. "group_ids" / "line_ids"
        const record = this.props.record;        // parent RelationalRecord

        // ── Guard 1: group_ids on the Template form ───────────────────
        if (fieldName === "group_ids") {
            const status = record?.data?.points_status;
            const hr = record?.data?.total_hr_points ?? 0;

            if (status === "exact" || status === "over") {
                this._notification.add(
                    _t(
                        "All %(hr)s HR point(s) are fully allocated. " +
                        "Increase Total HR Points to add more groups.",
                        { hr: hr.toFixed(2) }
                    ),
                    {
                        title: _t("No Points Remaining — Cannot Add Group"),
                        type: "danger",
                        sticky: true,
                    }
                );
                return;     // ← abort: no row, no dialog
            }
        }

        // ── Guard 2: line_ids on the Group popup form ─────────────────
        if (fieldName === "line_ids") {
            const status = record?.data?.points_status;
            const ceiling = record?.data?.points ?? 0;
            const grpName = record?.data?.name ?? "";

            if (status === "exact" || status === "over") {
                this._notification.add(
                    _t(
                        "All %(ceiling)s pt(s) for \"%(group)s\" are fully allocated. " +
                        "Increase Group Points to add more lines.",
                        { ceiling: ceiling.toFixed(2), group: grpName }
                    ),
                    {
                        title: _t("No Points Remaining — Cannot Add Line"),
                        type: "danger",
                        sticky: true,
                    }
                );
                return;     // ← abort: no row, no dialog
            }
        }

        // Default behaviour for all other lists / when not blocked
        return super.onAdd(context, editable);
    },
});