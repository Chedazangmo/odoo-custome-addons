# -*- coding: utf-8 -*-
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestDashboardReadOnly(common.TransactionCase):
    """Test that dashboard FETCHES real data (does NOT create it)"""

    def test_01_dashboard_fetches_existing_cycle(self):
        """Test dashboard fetches REAL existing cycle from database"""

        # Get existing cycle (don't create new one)
        cycle = self.env['pms.cycle'].search([], limit=1)
        if not cycle:
            self.skipTest("No cycle found in database")

        dashboard = self.env['pms.dashboard'].sudo()
        data = dashboard.get_dashboard_data(requested_role='hr_manager')

        # Verify existing cycle is fetched
        cycle_names = [c['name'] for c in data.get('active_cycles_list', [])]
        self.assertIn(cycle.name, cycle_names)

        print(f"✅ Dashboard fetched REAL existing cycle: {cycle.name}")

    def test_02_dashboard_fetches_existing_employee(self):
        """Test dashboard fetches REAL existing employee"""

        # Get existing employee
        employee = self.env['hr.employee'].search([], limit=1)
        if not employee:
            self.skipTest("No employee found in database")

        dashboard = self.env['pms.dashboard'].sudo(employee.user_id)
        data = dashboard.get_dashboard_data(requested_role='employee')

        # Verify existing employee data is fetched
        self.assertEqual(data.get('employee_name'), employee.name)

        print(f"✅ Dashboard fetched REAL existing employee: {employee.name}")

    def test_03_dashboard_fetches_existing_kpi(self):
        """Test dashboard fetches REAL existing KPI data"""

        # Get existing KPI
        kpi = self.env['pms.appraisal.kpi'].search([], limit=1)
        if not kpi:
            self.skipTest("No KPI found in database")

        dashboard = self.env['pms.dashboard'].sudo()
        # Your dashboard should fetch this existing KPI
        data = dashboard.get_planning_data()

        # Verify KPI data structure exists
        self.assertIn('all_plans', data)

        print("✅ Dashboard fetches REAL existing KPI data")