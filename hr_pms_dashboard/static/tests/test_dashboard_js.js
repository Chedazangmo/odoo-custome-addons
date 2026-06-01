/** @odoo-module **/

import { test, mount, getFixture, onRpc, expect } from "@web/../tests/hoot";
import { PMSDashboard } from "../../src/js/dashboard";

test("HR Manager dashboard renders", async () => {
    const target = getFixture();

    onRpc("/hr_pms_dashboard/data", () => Promise.resolve({
        role: "hr_manager",
        employee_id: 1,
        employee_name: "HR Admin",
        stats: { total_employees: 50, active_cycles_count: 3 },
        active_cycles_list: [],
        completed_cycles_list: [],
    }));

    await mount(PMSDashboard, { target });

    // Add a simple assertion
    expect(target.querySelector(".pms_dashboard")).toBeTruthy();
});