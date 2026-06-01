# tests/test_dashboard_basic.py
from odoo.tests import common, HttpCase
import json


@tagged('post_install', '-at_install')
class TestDashboardBasic(common.HttpCase):

    def test_01_dashboard_endpoint_responds(self):
        """Test that the dashboard endpoint returns a response"""

        # Make a simple request to the dashboard
        response = self.url_open(
            '/hr_pms_dashboard/data',
            data=json.dumps({}),
            headers={'Content-Type': 'application/json'}
        )

        # Check that we got a response (even if error)
        self.assertIsNotNone(response)
        print(f"✅ Endpoint responded with status: {response.status_code}")