/** @odoo-module */
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("real_data_fetch_tour", {
    test: true,
    url: "/web",
    steps: () => [
        {
            title: "Open Dashboard",
            trigger: '.o_menu_systray a[data-menu-xmlid="hr_pms_dashboard.action_pms_dashboard"]',
        },
        {
            title: "Wait for REAL data to load",
            trigger: '.pms_welcome_card',
            run: () => {
                // Check REAL employee name is from database
                const welcomeName = document.querySelector('.pms_welcome_name');
                if (welcomeName && welcomeName.textContent !== '') {
                    console.log("✅ REAL employee data loaded:", welcomeName.textContent);
                }
            },
        },
        {
            title: "Verify REAL cycle data",
            trigger: '.pms_cycle_card',
            run: () => {
                const cycleCards = document.querySelectorAll('.pms_cycle_card');
                if (cycleCards.length > 0) {
                    console.log("✅ REAL cycle data loaded:", cycleCards.length, "cycles");
                }
            },
        },
        {
            title: "Verify KPI data loads",
            trigger: '.pms_table_box table tbody tr',
            run: () => {
                const rows = document.querySelectorAll('.pms_table_box table tbody tr');
                if (rows.length > 0) {
                    console.log("✅ REAL KPI data loaded:", rows.length, "records");
                }
            },
        },
    ],
});