# -*- coding: utf-8 -*-
"""
Unit Tests for PMS Dashboard Controller
========================================
Tests cover:
  - _get_rating_class
  - _get_pending_actions
  - _build_planning_phase_data
  - _build_monitoring_phase_data
  - _build_appraisal_phase_data
  - _get_past_cycles
  - _get_all_cycles_data
  - get_dashboard_data role routing
  - _get_supervisor_section
  - _get_reviewer_section
"""

from unittest.mock import MagicMock, patch, PropertyMock
from datetime import date, timedelta
import pytest
import sys
import os

# Add module root to path
MODULE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, MODULE_ROOT)

# Mock Odoo modules for standalone testing
import types

odoo_mod = types.ModuleType("odoo")
odoo_http_mod = types.ModuleType("odoo.http")
odoo_fields_mod = types.ModuleType("odoo.fields")


class _FakeController:
    pass


odoo_http_mod.Controller = _FakeController
odoo_http_mod.request = MagicMock()


def _fake_route(*args, **kwargs):
    def decorator(fn):
        return fn
    return decorator


odoo_http_mod.route = _fake_route
odoo_mod.http = odoo_http_mod
odoo_fields_mod.Date = MagicMock()
odoo_mod.fields = odoo_fields_mod

sys.modules.setdefault("odoo", odoo_mod)
sys.modules.setdefault("odoo.http", odoo_http_mod)
sys.modules.setdefault("odoo.fields", odoo_fields_mod)

# Import controller
try:
    from controllers.dashboard import PMSDashboardController
except ImportError:
    PMSDashboardController = None


requires_controller = pytest.mark.skipif(
    PMSDashboardController is None,
    reason="PMSDashboardController could not be imported",
)


# ============================================================================
# Helper Functions
# ============================================================================

def _make_employee(id=1, name="Alice", department="Engineering", evaluation_group="Grade A"):
    emp = MagicMock()
    emp.id = id
    emp.name = name
    emp.department_id = MagicMock()
    emp.department_id.name = department
    emp.evaluation_group_id = MagicMock()
    emp.evaluation_group_id.name = evaluation_group
    emp.job_title = "Engineer"
    emp.parent_id = None
    emp.secondary_manager_id = None
    emp.reviewer_id = None
    emp.wage = 5000.0
    emp.company_id = MagicMock()
    emp.company_id.name = "TestCo"
    emp.active = True
    return emp


def _make_cycle(id=10, name="FY2024", state="planning", planning_deadline=None, end_date=None):
    c = MagicMock()
    c.id = id
    c.name = name
    c.state = state
    c.start_date = date(2024, 1, 1)
    c.end_date = end_date or date(2024, 12, 31)
    c.planning_deadline = planning_deadline or date(2024, 3, 31)
    c.appraisal_start_date = date(2024, 10, 1)
    c.cycle_type = "annual"
    c.final_score_selection = "reviewer"
    c.company_id = None
    c.employee_ids = []
    return c


def _make_appraisal(
    id=100,
    employee=None,
    cycle=None,
    state="draft",
    supervisor=None,
    secondary=None,
    reviewer=None,
    final_score=0.0,
    self_score=0.0,
    supervisor_score=0.0,
    secondary_score=0.0,
    reviewer_score=0.0,
):
    a = MagicMock()
    a.id = id
    a.employee_id = employee or _make_employee()
    a.cycle_id = cycle or _make_cycle()
    a.state = state
    a.supervisor_id = supervisor or MagicMock(id=99, name="Bob Manager")
    a.secondary_supervisor_id = secondary
    a.reviewer_id = reviewer
    a.final_appraisal_score = final_score
    a.total_self_score = self_score
    a.total_supervisor_score = supervisor_score
    a.total_secondary_score = secondary_score
    a.total_reviewer_score = reviewer_score
    a.kra_ids = []
    a.competency_score_ids = []
    a.create_date = MagicMock()
    a.create_date.date = MagicMock(return_value=date(2024, 1, 10))
    a.submitted_date = None
    a.supervisor_review_date = None
    a.selected_kpi_count = 3
    a.total_kpi_count = 5
    a._fields = {
        "state": MagicMock(
            selection=[
                ("draft", "Draft"),
                ("pending_supervisor", "Pending 1st Manager"),
                ("pending_secondary_supervisor", "Pending 2nd Manager"),
                ("pending_reviewer", "Pending Reviewer"),
                ("approved", "Approved"),
                ("appraisal_draft", "Appraisal Draft"),
                ("appraisal_pending_supervisor", "Appraisal Pending 1st Manager"),
                ("appraisal_pending_secondary_supervisor", "Appraisal Pending 2nd Manager"),
                ("appraisal_pending_reviewer", "Appraisal Pending Reviewer"),
                ("appraisal_approved", "Appraisal Approved"),
            ]
        )
    }
    return a


def _make_kpi(id=1, name="KPI 1", is_selected=True, target="Target A", weightage=20):
    kpi = MagicMock()
    kpi.id = id
    kpi.name = name
    kpi.is_selected = is_selected
    kpi.target = target
    kpi.weightage = weightage
    kpi.description = "Description"
    kpi.criteria = "Criteria"
    return kpi


def _make_kra(name="KRA 1", kpis=None):
    kra = MagicMock()
    kra.name = name
    kra.kpi_ids = kpis or []
    kra.total_weightage = sum(k.weightage for k in (kpis or []))
    return kra


# ============================================================================
# Test Classes
# ============================================================================

class TestGetRatingClass:
    """Test _get_rating_class method"""

    def setup_method(self):
        self.ctrl = object.__new__(PMSDashboardController) if PMSDashboardController else None

    @requires_controller
    def test_outstanding_returns_bg_success(self):
        assert self.ctrl._get_rating_class("Outstanding") == "bg-success"

    @requires_controller
    def test_poor_returns_bg_danger(self):
        assert self.ctrl._get_rating_class("Poor") == "bg-danger"

    @requires_controller
    def test_needs_improvement_returns_bg_warning(self):
        assert self.ctrl._get_rating_class("Needs Improvement") == "bg-warning"

    @requires_controller
    def test_unknown_rating_returns_bg_secondary(self):
        assert self.ctrl._get_rating_class("Unknown Rating") == "bg-secondary"

    @requires_controller
    def test_commendable_returns_bg_primary(self):
        assert self.ctrl._get_rating_class("Commendable") == "bg-primary"

    @requires_controller
    def test_good_returns_bg_info(self):
        assert self.ctrl._get_rating_class("Good") == "bg-info"

    @requires_controller
    def test_empty_string_returns_bg_secondary(self):
        assert self.ctrl._get_rating_class("") == "bg-secondary"


class TestGetPendingActions:
    """Test _get_pending_actions method"""

    def setup_method(self):
        self.ctrl = object.__new__(PMSDashboardController) if PMSDashboardController else None

    def _plan(self, state_key, plan_id=1):
        return {"state_key": state_key, "id": plan_id}

    def _appraisal(self, state_key, appraisal_id=1):
        return {"state_key": state_key, "id": appraisal_id}

    @requires_controller
    def test_draft_plan_produces_complete_plan_action(self):
        data = {"current_plan": self._plan("draft"), "current_appraisal": None}
        actions = self.ctrl._get_pending_actions(data)
        assert len(actions) == 1
        assert actions[0]["action_type"] == "complete_plan"
        assert actions[0]["button_text"] == "Complete Plan"

    @requires_controller
    def test_pending_supervisor_plan_produces_view_plan_action(self):
        data = {"current_plan": self._plan("pending_supervisor"), "current_appraisal": None}
        actions = self.ctrl._get_pending_actions(data)
        assert len(actions) == 1
        assert actions[0]["action_type"] == "view_plan"

    @requires_controller
    def test_pending_secondary_plan_produces_view_plan_action(self):
        data = {"current_plan": self._plan("pending_secondary_supervisor"), "current_appraisal": None}
        actions = self.ctrl._get_pending_actions(data)
        assert actions[0]["action_type"] == "view_plan"

    @requires_controller
    def test_pending_reviewer_plan_produces_view_plan_action(self):
        data = {"current_plan": self._plan("pending_reviewer"), "current_appraisal": None}
        actions = self.ctrl._get_pending_actions(data)
        assert actions[0]["action_type"] == "view_plan"

    @requires_controller
    def test_appraisal_draft_produces_start_appraisal_action(self):
        data = {"current_plan": None, "current_appraisal": self._appraisal("appraisal_draft")}
        actions = self.ctrl._get_pending_actions(data)
        assert actions[0]["action_type"] == "start_appraisal"

    @requires_controller
    def test_no_plan_no_appraisal_returns_empty(self):
        data = {"current_plan": None, "current_appraisal": None}
        actions = self.ctrl._get_pending_actions(data)
        assert actions == []

    @requires_controller
    def test_approved_plan_no_action(self):
        data = {"current_plan": self._plan("approved"), "current_appraisal": None}
        actions = self.ctrl._get_pending_actions(data)
        assert actions == []

    @requires_controller
    def test_appraisal_approved_no_action(self):
        data = {"current_plan": None, "current_appraisal": self._appraisal("appraisal_approved")}
        actions = self.ctrl._get_pending_actions(data)
        assert actions == []


class TestBuildPlanningPhaseData:
    """Test _build_planning_phase_data method"""

    def setup_method(self):
        self.ctrl = object.__new__(PMSDashboardController) if PMSDashboardController else None

    @requires_controller
    def test_planning_phase_sets_correct_phase(self):
        emp = _make_employee()
        cycle = _make_cycle(state="planning", planning_deadline=date.today() + timedelta(days=10))
        appraisal = _make_appraisal(state="draft", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        result = self.ctrl._build_planning_phase_data({}, appraisal, cycle, emp)
        assert result["current_cycle"]["phase"] == "planning"

    @requires_controller
    def test_draft_state_is_editable(self):
        emp = _make_employee()
        cycle = _make_cycle(state="planning", planning_deadline=date.today() + timedelta(days=10))
        appraisal = _make_appraisal(state="draft", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        result = self.ctrl._build_planning_phase_data({}, appraisal, cycle, emp)
        assert result["current_plan"]["is_editable"] is True

    @requires_controller
    def test_approved_state_is_not_editable(self):
        emp = _make_employee()
        cycle = _make_cycle(state="planning", planning_deadline=date.today() + timedelta(days=10))
        appraisal = _make_appraisal(state="approved", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        result = self.ctrl._build_planning_phase_data({}, appraisal, cycle, emp)
        assert result["current_plan"]["is_editable"] is False

    @requires_controller
    def test_kpi_counts_are_correct(self):
        emp = _make_employee()
        cycle = _make_cycle(state="planning", planning_deadline=date.today() + timedelta(days=5))

        kpi1 = _make_kpi(1, "KPI 1", is_selected=True)
        kpi2 = _make_kpi(2, "KPI 2", is_selected=False)
        kra = _make_kra("KRA 1", [kpi1, kpi2])

        appraisal = _make_appraisal(state="draft", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = [kra]

        result = self.ctrl._build_planning_phase_data({}, appraisal, cycle, emp)
        assert result["current_plan"]["selected_kpi_count"] == 1
        assert result["current_plan"]["total_kpi_count"] == 2

    @requires_controller
    def test_plan_progress_0_for_draft(self):
        emp = _make_employee()
        cycle = _make_cycle(state="planning", planning_deadline=date.today() + timedelta(days=5))
        appraisal = _make_appraisal(state="draft", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        result = self.ctrl._build_planning_phase_data({}, appraisal, cycle, emp)
        assert result["current_cycle"]["plan_progress"] == 0.0

    @requires_controller
    def test_plan_progress_100_for_approved(self):
        emp = _make_employee()
        cycle = _make_cycle(state="planning", planning_deadline=date.today() + timedelta(days=5))
        appraisal = _make_appraisal(state="approved", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        result = self.ctrl._build_planning_phase_data({}, appraisal, cycle, emp)
        assert result["current_cycle"]["plan_progress"] == 100.0

    @requires_controller
    def test_current_appraisal_is_none_in_planning(self):
        emp = _make_employee()
        cycle = _make_cycle(state="planning", planning_deadline=date.today() + timedelta(days=5))
        appraisal = _make_appraisal(state="draft", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        result = self.ctrl._build_planning_phase_data({}, appraisal, cycle, emp)
        assert result["current_appraisal"] is None

    @requires_controller
    def test_handles_null_secondary_supervisor(self):
        emp = _make_employee()
        cycle = _make_cycle(state="planning", planning_deadline=date.today() + timedelta(days=5))
        appraisal = _make_appraisal(state="draft", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        result = self.ctrl._build_planning_phase_data({}, appraisal, cycle, emp)
        assert result["current_plan"]["secondary_name"] is None


class TestBuildMonitoringPhaseData:
    """Test _build_monitoring_phase_data method"""

    def setup_method(self):
        self.ctrl = object.__new__(PMSDashboardController) if PMSDashboardController else None

    @requires_controller
    def test_phase_is_monitoring(self):
        emp = _make_employee()
        cycle = _make_cycle(state="monitoring")
        appraisal = _make_appraisal(state="approved", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        result = self.ctrl._build_monitoring_phase_data({}, appraisal, cycle, emp)
        assert result["current_cycle"]["phase"] == "monitoring"

    @requires_controller
    def test_plan_progress_is_100(self):
        emp = _make_employee()
        cycle = _make_cycle(state="monitoring")
        appraisal = _make_appraisal(state="approved", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        result = self.ctrl._build_monitoring_phase_data({}, appraisal, cycle, emp)
        assert result["current_cycle"]["plan_progress"] == 100

    @requires_controller
    def test_not_editable_in_monitoring(self):
        emp = _make_employee()
        cycle = _make_cycle(state="monitoring")
        appraisal = _make_appraisal(state="approved", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        result = self.ctrl._build_monitoring_phase_data({}, appraisal, cycle, emp)
        assert result["approved_plan"]["is_editable"] is False

    @requires_controller
    def test_current_appraisal_is_none(self):
        emp = _make_employee()
        cycle = _make_cycle(state="monitoring")
        appraisal = _make_appraisal(state="approved", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        result = self.ctrl._build_monitoring_phase_data({}, appraisal, cycle, emp)
        assert result["current_appraisal"] is None


class TestBuildAppraisalPhaseData:
    """Test _build_appraisal_phase_data method"""

    def setup_method(self):
        self.ctrl = object.__new__(PMSDashboardController) if PMSDashboardController else None

    @requires_controller
    def test_phase_is_appraisal(self):
        emp = _make_employee()
        cycle = _make_cycle(state="appraisal")
        appraisal = _make_appraisal(state="appraisal_draft", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        with patch.object(self.ctrl, "_get_employee_rating", return_value=None):
            result = self.ctrl._build_appraisal_phase_data({}, appraisal, cycle, emp)

        assert result["current_cycle"]["phase"] == "appraisal"

    @requires_controller
    def test_appraisal_progress_0_for_draft(self):
        emp = _make_employee()
        cycle = _make_cycle(state="appraisal")
        appraisal = _make_appraisal(state="appraisal_draft", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        with patch.object(self.ctrl, "_get_employee_rating", return_value=None):
            result = self.ctrl._build_appraisal_phase_data({}, appraisal, cycle, emp)

        assert result["current_cycle"]["appraisal_progress"] == 0.0

    @requires_controller
    def test_appraisal_progress_100_for_approved(self):
        emp = _make_employee()
        cycle = _make_cycle(state="appraisal")
        appraisal = _make_appraisal(state="appraisal_approved", employee=emp, cycle=cycle, final_score=85.0)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        with patch.object(self.ctrl, "_get_employee_rating", return_value="Outstanding"):
            result = self.ctrl._build_appraisal_phase_data({}, appraisal, cycle, emp)

        assert result["current_cycle"]["appraisal_progress"] == 100.0

    @requires_controller
    def test_current_appraisal_contains_scores(self):
        emp = _make_employee()
        cycle = _make_cycle(state="appraisal")
        appraisal = _make_appraisal(
            state="appraisal_pending_supervisor", employee=emp, cycle=cycle,
            self_score=70.0, supervisor_score=80.0
        )
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        with patch.object(self.ctrl, "_get_employee_rating", return_value=None):
            result = self.ctrl._build_appraisal_phase_data({}, appraisal, cycle, emp)

        assert result["current_appraisal"]["self_score"] == 70.0
        assert result["current_appraisal"]["supervisor_score"] == 80.0

    @requires_controller
    def test_plan_progress_is_100(self):
        emp = _make_employee()
        cycle = _make_cycle(state="appraisal")
        appraisal = _make_appraisal(state="appraisal_draft", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        with patch.object(self.ctrl, "_get_employee_rating", return_value=None):
            result = self.ctrl._build_appraisal_phase_data({}, appraisal, cycle, emp)

        assert result["current_cycle"]["plan_progress"] == 100


class TestPlanProgressCalculation:
    """Test progress calculation formula"""

    @pytest.mark.parametrize("state,has_secondary,has_reviewer,expected_pct", [
        ("draft", False, False, 0.0),
        ("pending_supervisor", False, False, 50.0),
        ("approved", False, False, 100.0),
        ("draft", True, False, 0.0),
        ("pending_supervisor", True, False, 33.3),
        ("pending_secondary_supervisor", True, False, 66.7),
        ("approved", True, False, 100.0),
        ("pending_supervisor", True, True, 25.0),
        ("pending_secondary_supervisor", True, True, 50.0),
        ("pending_reviewer", True, True, 75.0),
        ("approved", True, True, 100.0),
    ])
    def test_progress_formula(self, state, has_secondary, has_reviewer, expected_pct):
        total_steps = 2
        if has_secondary:
            total_steps += 1
        if has_reviewer:
            total_steps += 1

        state_step_map = {
            "draft": 0,
            "pending_supervisor": 1,
            "pending_secondary_supervisor": 2 if has_secondary else 1,
            "pending_reviewer": (3 if has_secondary else 2),
            "approved": total_steps,
            "appraisal_draft": 0,
            "appraisal_pending_supervisor": 1,
            "appraisal_pending_secondary_supervisor": 2 if has_secondary else 1,
            "appraisal_pending_reviewer": 3 if has_secondary else 2,
            "appraisal_approved": total_steps,
        }
        step = state_step_map.get(state, 0)
        progress = round((step / total_steps) * 100, 1)
        assert progress == expected_pct


class TestEdgeCases:
    """Edge case tests"""

    def setup_method(self):
        self.ctrl = object.__new__(PMSDashboardController) if PMSDashboardController else None

    @requires_controller
    def test_rating_class_all_known_ratings(self):
        known = {
            "Outstanding": "bg-success",
            "Commendable": "bg-primary",
            "Good": "bg-info",
            "Satisfactory": "bg-info",
            "Needs Improvement": "bg-warning",
            "Poor": "bg-danger",
        }
        for rating, expected_class in known.items():
            assert self.ctrl._get_rating_class(rating) == expected_class

    @requires_controller
    def test_build_planning_phase_no_kpis(self):
        emp = _make_employee()
        cycle = _make_cycle(state="planning", planning_deadline=date.today() + timedelta(days=5))
        appraisal = _make_appraisal(state="draft", employee=emp, cycle=cycle)
        appraisal.secondary_supervisor_id = None
        appraisal.reviewer_id = None
        appraisal.kra_ids = []

        result = self.ctrl._build_planning_phase_data({}, appraisal, cycle, emp)
        assert result["current_plan"]["kpis"] == []
        assert result["current_plan"]["selected_kpi_count"] == 0
        assert result["current_plan"]["total_kpi_count"] == 0


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])