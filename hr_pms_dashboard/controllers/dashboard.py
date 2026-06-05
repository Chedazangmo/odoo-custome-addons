from odoo import http
from odoo.http import request
from datetime import date
import logging
import traceback

_logger = logging.getLogger(__name__)

class PMSDashboardController(http.Controller):



    @http.route('/hr_pms_dashboard/data', type='json', auth='user')
    def get_dashboard_data(self, requested_role=None):
        try:
            user = request.env.user
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)

            is_hr = user.has_group('hr_employee_evaluation.group_pms_hr_manager')
            is_supervisor = user.has_group('hr_employee_evaluation.group_pms_supervisor')
            is_reviewer = user.has_group('hr_employee_evaluation.group_pms_reviewer')

            employee_data = self._get_employee_section(employee)
            transformed_employee = self._transform_for_employee_dashboard(employee, employee_data)

            if requested_role == 'auto':
                if is_supervisor:
                    requested_role = 'supervisor'
                elif is_reviewer:
                    requested_role = 'reviewer'
                else:
                    requested_role = 'employee'
                # Deliberately skip hr_manager here — HR uses its own menu

            if requested_role == 'supervisor' and is_supervisor:
                stats = self._get_manager_stats(employee)
                return {

                    'role': 'supervisor',
                    'employee_id': employee.id if employee else 0,
                    'employee_name': employee.name if employee else user.name,
                    'supervisor': self._get_supervisor_section(employee),
                    'employee': transformed_employee,
                    'stats': stats,
                }

            if requested_role == 'reviewer' and is_reviewer:
                stats = self._get_manager_stats(employee)
                return {

                    'role': 'reviewer',
                    'employee_id': employee.id if employee else 0,
                    'employee_name': employee.name if employee else user.name,
                    'reviewer': self._get_reviewer_section(employee),
                    'stats': stats,
                }

            if requested_role == 'employee':
                return {
                    'role': 'combined',
                    'roles': ['employee'],
                    'employee_id': employee.id if employee else 0,
                    'employee_name': employee.name if employee else user.name,
                    'employee': transformed_employee,
                }

            if requested_role == 'hr_manager' and is_hr:
                data = self._get_hr_manager_data()
                data['employee_id'] = employee.id if employee else 0
                data['employee_name'] = employee.name if employee else user.name
                data['role'] = 'hr_manager'
                return data

            # Fallback
            if is_hr:
                data = self._get_hr_manager_data()
                data['employee_id'] = employee.id if employee else 0
                data['employee_name'] = employee.name if employee else user.name
                data['role'] = 'hr_manager'
                return data

            data = {
                'role': 'combined',
                'roles': [],
                'employee_id': employee.id if employee else 0,
                'employee_name': employee.name if employee else user.name,
            }

            if employee and is_supervisor:
                data['roles'].append('supervisor')
                data['supervisor'] = self._get_supervisor_section(employee)

            if employee:
                sec_data = self._get_secondary_section(employee)
                if sec_data['total'] > 0:
                    data['roles'].append('secondary')
                    data['secondary'] = sec_data

            if employee and is_reviewer:
                data['roles'].append('reviewer')
                data['reviewer'] = self._get_reviewer_section(employee)

            data['roles'].append('employee')
            data['employee'] = transformed_employee

            return data

        except Exception as e:
            return {'error': str(e), 'traceback': traceback.format_exc()}


    def _transform_for_employee_dashboard(self, employee, employee_data):
        result = {
            'current_cycle': None,
            'current_plan': None,
            'current_appraisal': None,
            'approved_plan': None,
            'past_cycles': [],
            'pending_actions': []
        }
        Appraisal = request.env['pms.appraisal'].sudo()

        active_appraisal = Appraisal.search([
            ('employee_id', '=', employee.id),
            ('cycle_id.state', 'in', ['planning', 'monitoring', 'appraisal']),
        ], limit=1)

        if active_appraisal:
            active_cycle = active_appraisal.cycle_id

            if active_cycle.state == 'planning':
                result = self._build_planning_phase_data(result, active_appraisal, active_cycle, employee)
            elif active_cycle.state == 'monitoring':
                result = self._build_monitoring_phase_data(result, active_appraisal, active_cycle, employee)
            elif active_cycle.state == 'appraisal':
                result = self._build_appraisal_phase_data(result, active_appraisal, active_cycle, employee)

        result['past_cycles'] = self._get_past_cycles(employee)

        result['pending_actions'] = self._get_pending_actions(result)

        return result

    def _build_planning_phase_data(self, result, appraisal, cycle, employee):
        """Build data for planning phase with full KPI details"""
        from datetime import date
        # Define has_secondary and has_reviewer from the appraisal
        has_secondary = bool(appraisal.secondary_supervisor_id)
        has_reviewer = bool(appraisal.reviewer_id)

        total_steps = 2
        if has_secondary:
            total_steps += 1
        if has_reviewer:
            total_steps += 1

        state_step_map = {
            'draft': 0,
            'pending_supervisor': 1,
            'pending_secondary_supervisor': 2 if has_secondary else 1,
            'pending_reviewer': 3 if has_secondary else 2,
            'approved': total_steps,
        }
        step = state_step_map.get(appraisal.state, 0)
        plan_progress = round((step / total_steps) * 100, 1) if total_steps else 0

        # ============================================================
        # FIXED: Get FULL KPI details including description, criteria, score
        # ============================================================
        kpis = []
        total_weightage = 0

        for kra in appraisal.kra_ids:
            for kpi in kra.kpi_ids:
                # Get the KPI line (pms.kpi.line) if it exists
                kpi_line = False
                if hasattr(kpi, 'line_id') and kpi.line_id:
                    kpi_line = kpi.line_id

                # Get score for this KPI
                kpi_score = 0
                if hasattr(appraisal, 'kpi_line_ids'):
                    for line in appraisal.kpi_line_ids:
                        if line.kpi_id.id == kpi.id:
                            kpi_score = line.score or 0
                            break

                kpi_data = {
                    'id': kpi.id,
                    'kra_name': kra.name,
                    'kpi_name': kpi.name,
                    'description': kpi.description or '',
                    'target': kpi.target or None,
                    'criteria': kpi.criteria or '',
                    'score': kpi_score,
                    'weightage':  kpi.weightage if kpi.is_selected else 0,
                    'is_selected': bool(kpi.is_selected),  # ← ADD THIS
                    'status': 'set' if (kpi.is_selected and kpi.target) else 'pending',  # ← ADD THIS
                }
                kpis.append(kpi_data)
                total_weightage += kpi.weightage or 0

        selected_kpi_count = len([k for k in kpis if k['is_selected']])
        total_kpi_count = len(kpis)

        # Get state label from appraisal's _fields
        state_label = dict(appraisal._fields['state'].selection).get(appraisal.state, appraisal.state)

        result['current_cycle'] = {
            'cycle_name': cycle.name,
            'phase': 'planning',
            'start_date': str(cycle.start_date) if cycle.start_date else '-',
            'deadline': str(cycle.planning_deadline) if cycle.planning_deadline else '-',
            'end_date':str(cycle.appraisal_end_date) if cycle.appraisal_end_date else '—',
            'completion_date': '-',
            'days_left': (cycle.planning_deadline - date.today()).days if cycle.planning_deadline else None,
            'final_score': None,
            'rating': None,
            'plan_progress': plan_progress,
            'appraisal_progress': 0,
            'selected_kpi_count': selected_kpi_count,
            'total_kpi_count': total_kpi_count,
            'appraisal_end_date': str(appraisal.appraisal_end_date) if appraisal.appraisal_end_date else None,
        }

        result['current_plan'] = {
            'id': appraisal.id,
            'cycle_id': cycle.id,
            'name': employee.name,
            'evaluation_group': employee.evaluation_group_id.name if employee.evaluation_group_id else '-',
            'supervisor_name': appraisal.supervisor_id.name if appraisal.supervisor_id else '-',
            'secondary_name': appraisal.secondary_supervisor_id.name if appraisal.secondary_supervisor_id else None,
            'reviewer_name': appraisal.reviewer_id.name if appraisal.reviewer_id else None,
            'selected_kpi_count': selected_kpi_count,
            'total_kpi_count': total_kpi_count,
            'total_weightage': total_weightage,  # Add total weightage
            'progress': plan_progress,
            'state': state_label,
            'state_key': appraisal.state,
            'cycle': cycle.name,
            'department': employee.department_id.name or '-',
            'kpis': kpis,  # Now includes description, criteria, score
            'has_secondary': has_secondary,
            'has_reviewer': has_reviewer,
            'is_editable': appraisal.state == 'draft',
            'cycle_type': cycle.cycle_type or '—',
            'start_date': str(cycle.start_date) if cycle.start_date else '—',
            'end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else '—',
            'self_planning_deadline': str(
                appraisal.self_planning_deadline) if appraisal.self_planning_deadline else None,
            'planning_end_date': str(appraisal.planning_end_date) if appraisal.planning_end_date else None,
            'self_planning_days_left': (
                        appraisal.self_planning_deadline - date.today()).days if appraisal.self_planning_deadline else None,
            'planning_days_left': (
                        appraisal.planning_end_date - date.today()).days if appraisal.planning_end_date else None,
            'appraisal_end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else '—',

        }
        return result

    def _build_monitoring_phase_data(self, result, appraisal, cycle, employee):
        """Build data for monitoring phase"""
        from datetime import date

        # ============================================================
        # CHECK: Is the plan actually approved?
        # ============================================================
        plan_is_approved = appraisal.state == 'approved'

        has_secondary = bool(appraisal.secondary_supervisor_id)
        has_reviewer = bool(appraisal.reviewer_id)
        total_steps = 2
        if has_secondary:
            total_steps += 1
        if has_reviewer:
            total_steps += 1

        state_step_map = {
            'draft': 0,
            'pending_supervisor': 1,
            'pending_secondary_supervisor': 2 if has_secondary else 1,
            'pending_reviewer': 3 if has_secondary else 2,
            'approved': total_steps,
        }
        step = state_step_map.get(appraisal.state, 0)
        plan_progress = round((step / total_steps) * 100, 1) if total_steps else 0

        state_label = dict(appraisal._fields['state'].selection).get(appraisal.state, appraisal.state)

        kpis = []
        total_weightage = 0

        for kra in appraisal.kra_ids:
            for kpi in kra.kpi_ids:
                # If approved, only show selected KPIs; if not approved, show all
                if plan_is_approved and not kpi.is_selected:
                    continue
                kpi_data = {
                    'id': kpi.id,
                    'kra_name': kra.name,
                    'kra_weightage': kra.total_weightage,
                    'kpi_name': kpi.name,
                    'description': kpi.description or '',
                    'target': kpi.target or None,
                    'criteria': kpi.criteria or '',
                    'weightage': kpi.weightage if kpi.is_selected else 0,
                    'is_selected': bool(kpi.is_selected),
                    'status': 'set' if (kpi.is_selected and kpi.target) else 'pending',
                }
                kpis.append(kpi_data)
                total_weightage += kpi.weightage or 0

        selected_kpi_count = len([k for k in kpis if k['is_selected']])
        total_kpi_count = len(kpis)

        result['current_cycle'] = {
            'cycle_name': cycle.name,
            'phase': 'monitoring',
            'start_date': str(cycle.start_date) if cycle.start_date else '-',
            'deadline': '-',
            'end_date': str(cycle.end_date) if cycle.end_date else '-',
            'completion_date': '-',
            'days_left': (cycle.planning_deadline - date.today()).days if cycle.planning_deadline else None,
            'final_score': None,
            'rating': None,
            'plan_progress': plan_progress,  # ← Now reflects actual progress
            'appraisal_progress': 0,
            'selected_kpi_count': selected_kpi_count,
            'total_kpi_count': total_kpi_count,
            'cycle_start_date': str(cycle.start_date) if cycle.start_date else '-',
            'appraisal_start_date': str(cycle.appraisal_start_date) if cycle.appraisal_start_date else '-',
            'appraisal_end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else None,
            'appraisal_duration_days': (
                    cycle.end_date - cycle.appraisal_start_date
            ).days if cycle.end_date and cycle.appraisal_start_date else None,
            'planning_duration': cycle.planning_duration,
        }

        plan_data = {
            'id': appraisal.id,
            'name': employee.name,
            'selected_kpi_count': selected_kpi_count,
            'total_kpi_count': total_kpi_count,
            'total_weightage': total_weightage,
            'progress': plan_progress,
            'state': state_label,
            'state_key': appraisal.state,  # ← Real state, not hardcoded 'approved'
            'cycle': cycle.name,
            'cycle_type': cycle.cycle_type or '—',
            'department': employee.department_id.name or '-',
            'kpis': kpis,
            'has_secondary': has_secondary,
            'has_reviewer': has_reviewer,
            'is_editable': appraisal.state == 'draft',
            'start_date': str(cycle.start_date) if cycle.start_date else '—',
            'end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else '—',
            'appraisal_end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else '—',
            'evaluation_group': employee.evaluation_group_id.name if employee.evaluation_group_id else '-',
            'supervisor_name': appraisal.supervisor_id.name if appraisal.supervisor_id else '-',
            'secondary_name': appraisal.secondary_supervisor_id.name if appraisal.secondary_supervisor_id else None,
            'reviewer_name': appraisal.reviewer_id.name if appraisal.reviewer_id else None,
            # ← Planning deadline fields (needed for the orange/purple cards in template)
            'self_planning_deadline': str(
                appraisal.self_planning_deadline) if appraisal.self_planning_deadline else None,
            'planning_end_date': str(appraisal.planning_end_date) if appraisal.planning_end_date else None,
            'self_planning_days_left': (
                    appraisal.self_planning_deadline - date.today()
            ).days if appraisal.self_planning_deadline else None,
            'planning_days_left': (
                    appraisal.planning_end_date - date.today()
            ).days if appraisal.planning_end_date else None,
            'approval_duration': (
                    appraisal.planning_end_date - appraisal.self_planning_deadline
            ).days if appraisal.planning_end_date and appraisal.self_planning_deadline else None,
            'self_planning_duration': (
                    appraisal.self_planning_deadline - cycle.start_date
            ).days if appraisal.self_planning_deadline and cycle.start_date else None,
        }

        # ============================================================
        # Set approved_plan only if actually approved
        # ============================================================
        if plan_is_approved:
            result['approved_plan'] = plan_data
        else:
            result['approved_plan'] = None

        result['current_plan'] = plan_data
        result['current_appraisal'] = None

        return result

    def _build_appraisal_phase_data(self, result, appraisal, cycle, employee):
        """Build data for appraisal phase - include approved plan and appraisal details"""
        from datetime import date

        has_secondary = bool(appraisal.secondary_supervisor_id)
        has_reviewer = bool(appraisal.reviewer_id)
        total_steps = 2
        if has_secondary:
            total_steps += 1
        if has_reviewer:
            total_steps += 1

        state_step_map = {
            'appraisal_draft': 0,
            'appraisal_pending_supervisor': 1,
            'appraisal_pending_secondary_supervisor': 2 if has_secondary else 1,
            'appraisal_pending_reviewer': 3 if has_secondary else 2,
            'appraisal_approved': total_steps,
        }
        step = state_step_map.get(appraisal.state, 0)
        appraisal_progress = round((step / total_steps) * 100, 1) if total_steps else 0

        rating = self._get_employee_rating(appraisal.final_appraisal_score) if appraisal.final_appraisal_score else None

        state_label = dict(appraisal._fields['state'].selection).get(appraisal.state, appraisal.state)

        # Build approved plan data (from the same appraisal, the plan is already approved)
        kpis = []
        total_weightage = 0
        for kra in appraisal.kra_ids:
            for kpi in kra.kpi_ids:
                if kpi.is_selected:
                    kpi_data = {
                        'id': kpi.id,
                        'kra_name': kra.name,
                        'kpi_name': kpi.name,
                        'description': kpi.description or '',
                        'target': kpi.target or None,
                        'criteria': kpi.criteria or '',
                        'weightage':  kpi.weightage if kpi.is_selected else 0,
                        'is_selected': bool(kpi.is_selected),
                        'status': 'set' if (kpi.is_selected and kpi.target) else 'pending',
                    }
                    kpis.append(kpi_data)
                    total_weightage += kpi.weightage or 0

        selected_kpi_count = len([k for k in kpis if k['is_selected']])
        total_kpi_count = len(kpis)

        result['current_cycle'] = {
            'cycle_name': cycle.name,
            'phase': 'appraisal',
            'cycle_start_date': str(cycle.start_date) if cycle.start_date else '-',  # ← cycle start
            'start_date': str(cycle.appraisal_start_date) if cycle.appraisal_start_date else '-',
            'appraisal_start_date': str(cycle.appraisal_start_date) if cycle.appraisal_start_date else '-',
            'deadline': '-',
            'end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else '-',
            'appraisal_end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else None,
            'appraisal_duration_days': (
                        cycle.end_date - cycle.appraisal_start_date).days if cycle.end_date and cycle.appraisal_start_date else None,
            'completion_date': '-',
            'days_left': (cycle.appraisal_end_date - date.today()).days if cycle.appraisal_end_date else None,
            'final_score': appraisal.final_appraisal_score,
            'rating': rating,
            'plan_progress': 100,
            'appraisal_progress': appraisal_progress,
            'selected_kpi_count': selected_kpi_count,
            'total_kpi_count': total_kpi_count,
            'planning_duration': cycle.planning_duration,
        }

        # Add approved plan (read-only) for display
        result['approved_plan'] = {
            'id': appraisal.id,
            'name': employee.name,
            'selected_kpi_count': selected_kpi_count,
            'total_kpi_count': total_kpi_count,
            'total_weightage': total_weightage,
            'progress': 100,
            'state': 'Approved',
            'state_key': 'approved',
            'cycle': cycle.name,
            'department': employee.department_id.name or '-',
            'kpis': kpis,
            'has_secondary': has_secondary,
            'has_reviewer': has_reviewer,
            'is_editable': False,
            'cycle_type': cycle.cycle_type or '—',
            'start_date': str(cycle.start_date) if cycle.start_date else '—',
            'end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else '—',
            'appraisal_end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else '—',  # ← is this here?
            'evaluation_group': employee.evaluation_group_id.name if employee.evaluation_group_id else '-',
            'supervisor_name': appraisal.supervisor_id.name if appraisal.supervisor_id else '-',
            'secondary_name': appraisal.secondary_supervisor_id.name if appraisal.secondary_supervisor_id else None,
            'reviewer_name': appraisal.reviewer_id.name if appraisal.reviewer_id else None,
        }

        # Determine if appraisal is editable
        is_editable = appraisal.state in [
            'appraisal_draft',
            'appraisal_pending_supervisor',
            'appraisal_pending_secondary_supervisor',
            'appraisal_pending_reviewer'
        ]

        result['current_appraisal'] = {
            'id': appraisal.id,
            'progress': appraisal_progress,
            'state': state_label,
            'state_key': appraisal.state,
            'self_score': appraisal.total_self_score or None,
            'supervisor_score': appraisal.total_supervisor_score or None,
            'secondary_score': appraisal.total_secondary_score or None,
            'reviewer_score': appraisal.total_reviewer_score or None,
            'final_score': appraisal.final_appraisal_score or None,
            'rating': rating,
            'has_secondary': has_secondary,
            'has_reviewer': has_reviewer,
            'is_editable': is_editable,
            'supervisor_name': appraisal.supervisor_id.name if appraisal.supervisor_id else '',
            'secondary_name': appraisal.secondary_supervisor_id.name if appraisal.secondary_supervisor_id else '',
            'reviewer_name': appraisal.reviewer_id.name if appraisal.reviewer_id else '',
            'self_appraisal_deadline': str(
                appraisal.self_appraisal_deadline) if appraisal.self_appraisal_deadline else None,
            'appraisal_end_date': str(appraisal.appraisal_end_date) if appraisal.appraisal_end_date else None,
            'self_appraisal_days_left': (
                        appraisal.self_appraisal_deadline - date.today()).days if appraisal.self_appraisal_deadline else None,
            'appraisal_days_left': (
                        appraisal.appraisal_end_date - date.today()).days if appraisal.appraisal_end_date else None,
        }

        result['current_plan'] = result['approved_plan']

        return result

    def _get_past_cycles(self, employee):
        """Get completed cycles for employee history"""
        Cycle = request.env['pms.cycle'].sudo()
        Appraisal = request.env['pms.appraisal'].sudo()

        completed_cycles = Cycle.search([('state', 'not in', ['planning', 'appraisal'])])
        past_cycles = []

        for cycle in completed_cycles:
            appraisal = Appraisal.search([
                ('employee_id', '=', employee.id),
                ('cycle_id', '=', cycle.id)
            ], limit=1)

            if appraisal and appraisal.state == 'appraisal_approved':
                rating = self._get_employee_rating(appraisal.final_appraisal_score)
                past_cycles.append({
                    'id': cycle.id,
                    'cycle_name': cycle.name,
                    'start_date': str(cycle.start_date) if cycle.start_date else '-',
                    'end_date': str(cycle.end_date) if cycle.end_date else '-',
                    'appraisal_end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else str(
                        cycle.end_date) if cycle.end_date else '-',
                    'plan_progress': 100,
                    'final_score': appraisal.final_appraisal_score if appraisal.final_appraisal_score is not None else None,
                    'rating': rating,

                    'completed_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else str(
                        cycle.end_date) if cycle.end_date else '-',
                })

        return past_cycles

    def _get_pending_actions(self, dashboard_data):
        """Generate pending actions based on current state"""
        from datetime import date
        today = date.today
        pending_actions = []
        action_id = 1

        # Planning phase pending actions
        if dashboard_data.get('current_plan'):
            plan = dashboard_data['current_plan']

            cycle = dashboard_data.get('current_cycle')
            planning_deadline = None
            if cycle and cycle.get('deadline') and cycle['deadline'] != '-':
                try:
                    from datetime import datetime
                    planning_deadline = datetime.strptime(cycle['deadline'], '%Y-%m-%d').date()
                except:
                    pass

            if plan['state_key'] == 'draft':
                is_overdue = bool(planning_deadline and today > planning_deadline)
                pending_actions.append({
                    'id': action_id,
                    'description': 'Complete your performance plan by setting targets for all KPIs',
                    'icon': 'fa-edit',
                    'button_text': 'Complete Plan',
                    'is_overdue': is_overdue,
                    'action_type': 'complete_plan',
                    'plan_id': plan['id'],
                })

                action_id += 1
            elif plan['state_key'] == 'pending_supervisor':
                pending_actions.append({
                    'id': action_id,
                    'description': 'Your plan is waiting for 1st Level Manager approval',
                    'with_name': plan.get('supervisor_name', ''),
                    'icon': 'fa-clock-o',
                    'button_text': 'View Plan',
                    'is_overdue': False,
                    'action_type': 'view_plan',
                    'plan_id': plan['id'],
                })
                action_id += 1
            elif plan['state_key'] == 'pending_secondary_supervisor':
                pending_actions.append({
                    'id': action_id,
                    'description': 'Your plan is waiting for 2nd Level Manager approval',
                    'with_name': plan.get('secondary_name', ''),
                    'icon': 'fa-clock-o',
                    'button_text': 'View Plan',
                    'is_overdue': False,
                    'action_type': 'view_plan',
                    'plan_id': plan['id'],
                })
                action_id += 1
            elif plan['state_key'] == 'pending_reviewer':
                pending_actions.append({
                    'id': action_id,
                    'description': 'Your plan is waiting for Final Reviewer approval',
                    'with_name': plan.get('reviewer_name', ''),
                    'icon': 'fa-clock-o',
                    'button_text': 'View Plan',
                    'is_overdue': False,
                    'action_type': 'view_plan',
                    'plan_id': plan['id'],
                })
                action_id += 1

        # Appraisal phase pending actions
        if dashboard_data.get('current_appraisal'):
            appraisal = dashboard_data['current_appraisal']
            if appraisal['state_key'] == 'appraisal_draft':
                pending_actions.append({
                    'id': action_id,
                    'description': 'Complete your self-assessment rating',
                    'icon': 'fa-star',
                    'button_text': 'Start Appraisal',
                    'is_overdue': False,
                    'action_type': 'start_appraisal',
                    'appraisal_id': appraisal['id'],
                })
                action_id += 1
            elif appraisal['state_key'] == 'appraisal_pending_supervisor':
                pending_actions.append({
                    'id': action_id,
                    'description': 'Your self-assessment is waiting for 1st Level Manager rating',
                    'with_name': appraisal.get('supervisor_name', ''),
                    'icon': 'fa-clock-o',
                    'button_text': 'View Appraisal',
                    'is_overdue': False,
                    'action_type': 'view_appraisal',
                    'appraisal_id': appraisal['id'],
                })
                action_id += 1
            elif appraisal['state_key'] == 'appraisal_pending_secondary_supervisor':
                pending_actions.append({
                    'id': action_id,
                    'description': 'Your appraisal is waiting for 2nd Level Manager rating',
                    'with_name': appraisal.get('secondary_name', ''),
                    'icon': 'fa-clock-o',
                    'button_text': 'View Appraisal',
                    'is_overdue': False,
                    'action_type': 'view_appraisal',
                    'appraisal_id': appraisal['id'],
                })
                action_id += 1
            elif appraisal['state_key'] == 'appraisal_pending_reviewer':
                pending_actions.append({
                    'id': action_id,
                    'description': 'Your appraisal is waiting for Final Reviewer rating',
                    'with_name': appraisal.get('reviewer_name', ''),
                    'icon': 'fa-clock-o',
                    'button_text': 'View Appraisal',
                    'is_overdue': False,
                    'action_type': 'view_appraisal',
                    'appraisal_id': appraisal['id'],
                })
                action_id += 1

        return pending_actions

    @http.route('/hr_pms_dashboard/get_cycle_all_appraisals', type='json', auth='user')
    def get_cycle_all_appraisals(self, cycle_id):
        """Get all employee appraisals for a cycle with detailed information"""
        try:
            if not cycle_id:
                return {'error': 'No cycle_id provided', 'appraisals': []}

            Cycle = request.env['pms.cycle'].sudo()
            Appraisal = request.env['pms.appraisal'].sudo()
            RatingDefinition = request.env['pms.rating.definition'].sudo()
            BonusLine = request.env['pms.bonus.calculation.line'].sudo()

            cycle = Cycle.browse(int(cycle_id))
            if not cycle.exists():
                return {'error': f'Cycle not found with id: {cycle_id}', 'appraisals': []}

            if cycle.company_id:
                company_name = cycle.company_id.name
            elif cycle.employee_ids and cycle.employee_ids[0].company_id:
                company_name = cycle.employee_ids[0].company_id.name
            elif request.env.user.company_id:
                company_name = request.env.user.company_id.name
            elif request.env.company:
                company_name = request.env.company.name
            else:
                company_name = 'Company'

            appraisals = Appraisal.search([('cycle_id', '=', cycle.id)])
            employees_data = []
            total_final_score = 0
            completed_count = 0

            for appraisal in appraisals:
                emp = appraisal.employee_id

                # ── assign state FIRST before using it ──────────────────────
                appraisal_state = appraisal.state
                has_secondary = bool(appraisal.secondary_supervisor_id)
                has_reviewer = bool(appraisal.reviewer_id)
                # ── stage-aware score flags ──────────────────────────────────
                self_given = appraisal_state not in ['appraisal_draft']
                supervisor_given = appraisal_state in [
                    'appraisal_pending_secondary_supervisor',
                    'appraisal_pending_reviewer',
                    'appraisal_approved',
                ]
                secondary_given = has_secondary and appraisal_state in [
                    'appraisal_pending_reviewer',
                    'appraisal_approved',
                ]
                reviewer_given = has_reviewer and appraisal_state == 'appraisal_approved'

                # ── rating only for completed appraisals ─────────────────────
                raw_final = appraisal.final_appraisal_score
                if appraisal_state == 'appraisal_approved' and raw_final is not None:
                    rating_obj = RatingDefinition.get_rating(raw_final)
                    rating = rating_obj.name if rating_obj else ''
                    completed_count += 1
                    total_final_score += raw_final
                else:
                    rating = ''

                bonus_line = BonusLine.search([
                    ('employee_id', '=', emp.id),
                    ('cycle_id', '=', cycle.id),
                    ('calculation_state', '=', 'calculated'),
                ], order='calculation_date desc', limit=1)

                eligibility_pct = bonus_line.eligibility_percentage if bonus_line else 0.0
                bonus_amount = bonus_line.bonus_amount if bonus_line else 0.0

                # ── append is INSIDE the loop ────────────────────────────────
                employees_data.append({
                    'employee_id': emp.id,
                    'name': emp.name,
                    'designation': emp.job_title or '-',
                    'doj': '-',
                    'self_score': appraisal.total_self_score if self_given else None,
                    'supervisor_score': appraisal.total_supervisor_score if supervisor_given else None,
                    'secondary_score': appraisal.total_secondary_score if secondary_given else None,
                    'reviewer_score': appraisal.total_reviewer_score if reviewer_given else None,
                    'final_score': raw_final if appraisal_state == 'appraisal_approved' else None,
                    'rating': rating,
                    'eligibility_pct': eligibility_pct,
                    'basic_pay': emp.wage if emp.wage is not None else None,
                    'bonus_amount': bonus_amount,
                    'state_key': appraisal_state,
                    'supervisor_name': appraisal.supervisor_id.name if appraisal.supervisor_id else '',
                    'secondary_name': appraisal.secondary_supervisor_id.name if appraisal.secondary_supervisor_id else '',
                    'reviewer_name': appraisal.reviewer_id.name if appraisal.reviewer_id else '',
                })

            avg_final_score = round(total_final_score / completed_count, 1) if completed_count > 0 else 0

            result = {
                'appraisals': employees_data,
                'summary': {
                    'total_employees': len(employees_data),
                    'completed_count': completed_count,
                    'avg_final_score': avg_final_score,
                    'cycle_name': cycle.name,
                    'cycle_start': str(cycle.start_date) if cycle.start_date else '-',
                    'cycle_end': str(cycle.end_date) if cycle.end_date else '-',
                    'company_name': company_name,
                }
            }

            return result

        except Exception as e:
            _logger.error("ERROR in get_cycle_all_appraisals: %s\n%s", str(e), traceback.format_exc())
            return {
                'error': str(e),
                'appraisals': [],
                'summary': {}
            }

    @http.route('/hr_pms_dashboard/get_cycle_performance_data', type='json', auth='user')
    def get_cycle_performance_data(self, cycle_id):
        """Get employee performance data for a cycle"""
        try:
            Cycle = request.env['pms.cycle'].sudo()
            Appraisal = request.env['pms.appraisal'].sudo()

            cycle = Cycle.browse(int(cycle_id))
            if not cycle.exists():
                return {'error': 'Cycle not found'}

            appraisals = Appraisal.search([
                ('cycle_id', '=', cycle.id),
                ('state', '=', 'appraisal_approved')
            ])

            employees_data = []
            for appraisal in appraisals:
                emp = appraisal.employee_id
                rating = self._get_employee_rating(appraisal.final_appraisal_score or 0)

                employees_data.append({
                    'employee_id': emp.id,
                    'name': emp.name,
                    'department': emp.department_id.name or '-',
                    'evaluation_group': emp.evaluation_group_id.name or '-',
                    'total_score': appraisal.final_appraisal_score or 0,
                    'rating': rating,
                    'state_key': appraisal.state,
                    'supervisor_name': appraisal.supervisor_id.name if appraisal.supervisor_id else '',
                    'secondary_name': appraisal.secondary_supervisor_id.name if appraisal.secondary_supervisor_id else '',
                    'reviewer_name': appraisal.reviewer_id.name if appraisal.reviewer_id else '',
                })

            avg_score = sum(e['total_score'] for e in employees_data) / len(employees_data) if employees_data else 0

            return {
                'employees': employees_data,
                'total_employees': len(employees_data),
                'avg_score': round(avg_score, 1),
            }

        except Exception as e:
            return {'error': str(e), 'employees': []}

    def _get_all_cycles_data(self):
        """Get all cycles (planning, monitoring, appraisal, completed) with their statistics"""
        Cycle = request.env['pms.cycle'].sudo()
        Appraisal = request.env['pms.appraisal'].sudo()
        Employee = request.env['hr.employee'].sudo()
        today = date.today()

        all_cycles = Cycle.search([], order='id desc')
        cycles_data = []
        active_cycles = []
        completed_cycles = []

        for cycle in all_cycles:
            # Skip cancelled cycles
            if cycle.state == 'cancelled':
                continue

            plans = Appraisal.search([('cycle_id', '=', cycle.id)])
            employees_in_cycle = plans.mapped('employee_id')
            employees_in_cycle_count = len(employees_in_cycle)

            # Calculate basic counts
            # Calculate basic counts
            draft_count = len(plans.filtered(lambda p: p.state == 'draft'))
            pending_supervisor_count = len(plans.filtered(lambda p: p.state == 'pending_supervisor'))
            pending_secondary_count = len(plans.filtered(lambda p: p.state == 'pending_secondary_supervisor'))  # ← new
            pending_reviewer_count = len(plans.filtered(lambda p: p.state == 'pending_reviewer'))  # ← fixed
            approved_count = len(plans.filtered(lambda p: p.state == 'approved'))

            # Appraisal counts
            appraisal_draft_count = len(plans.filtered(lambda p: p.state == 'appraisal_draft'))
            appraisal_pending_supervisor_count = len(
                plans.filtered(lambda p: p.state == 'appraisal_pending_supervisor'))
            appraisal_pending_secondary_count = len(
                plans.filtered(lambda p: p.state == 'appraisal_pending_secondary_supervisor'))
            appraisal_pending_reviewer_count = len(plans.filtered(lambda p: p.state == 'appraisal_pending_reviewer'))
            appraisal_completed_count = len(plans.filtered(lambda p: p.state == 'appraisal_approved'))

            # Calculate monitoring metrics (if in monitoring phase)
            monitoring_progress = 0
            monitoring_total_checks = 0
            monitoring_completed_checks = 0

            if cycle.state == 'monitoring':
                # Count appraisals that have completed monitoring check-ins
                # You can add a monitoring_check model or use existing fields
                monitoring_total_checks = employees_in_cycle_count
                monitoring_completed_checks = approved_count  # Plans approved = ready for appraisal
                monitoring_progress = round((monitoring_completed_checks / monitoring_total_checks) * 100,
                                            1) if monitoring_total_checks > 0 else 0

            # Calculate progress based on cycle state
            if cycle.state == 'planning':
                total_planning = draft_count + pending_supervisor_count + pending_reviewer_count + approved_count
                progress = round((approved_count / total_planning) * 100, 1) if total_planning > 0 else 0
            elif cycle.state == 'monitoring':
                progress = monitoring_progress
            elif cycle.state == 'appraisal':
                total_appraisal = appraisal_draft_count + appraisal_pending_supervisor_count + appraisal_pending_reviewer_count + appraisal_completed_count
                progress = round((appraisal_completed_count / total_appraisal) * 100, 1) if total_appraisal > 0 else 0
            else:  # completed
                progress = 100

            # Calculate days left
            days_left = None
            if cycle.state == 'planning' and cycle.planning_deadline:
                days_left = (cycle.planning_deadline - today).days
            elif cycle.state == 'monitoring' and cycle.planning_deadline:
                days_left = (cycle.planning_deadline - today).days
            elif cycle.state == 'appraisal' and cycle.end_date:
                days_left = (cycle.appraisal_start_date - today).days

            # Calculate average score (only for appraisal and completed cycles)
            avg_score = 0
            if cycle.state in ['appraisal', 'completed']:
                completed_appraisals = plans.filtered(lambda p: p.state == 'appraisal_approved')
                if completed_appraisals:
                    total_score = sum(a.final_appraisal_score or 0 for a in completed_appraisals)
                    avg_score = round(total_score / len(completed_appraisals), 1)

            if cycle.state == 'planning':
                phase_data = {
                    'draft_count': draft_count,
                    'draft_percent': round((draft_count / employees_in_cycle_count) * 100,
                                           1) if employees_in_cycle_count > 0 else 0,
                    'pending_supervisor_count': pending_supervisor_count,
                    'pending_supervisor_percent': round((pending_supervisor_count / employees_in_cycle_count) * 100,
                                                        1) if employees_in_cycle_count > 0 else 0,
                    'pending_secondary_count': pending_secondary_count,
                    'pending_secondary_percent': round((pending_secondary_count / employees_in_cycle_count) * 100,
                                                       1) if employees_in_cycle_count > 0 else 0,
                    'pending_reviewer_count': pending_reviewer_count,
                    'pending_reviewer_percent': round((pending_reviewer_count / employees_in_cycle_count) * 100,
                                                      1) if employees_in_cycle_count > 0 else 0,
                    'approved_count': approved_count,
                    'approved_percent': round((approved_count / employees_in_cycle_count) * 100,
                                              1) if employees_in_cycle_count > 0 else 0,
                }
            elif cycle.state == 'monitoring':
                phase_data = {
                    'total_plans': employees_in_cycle_count,
                    'approved_plans': approved_count,
                    'monitoring_progress': monitoring_progress,
                    'remaining_for_appraisal': employees_in_cycle_count - approved_count,
                }
            elif cycle.state == 'appraisal':
                phase_data = {
                    'self_count': appraisal_draft_count,
                    'self_percent': round((appraisal_draft_count / employees_in_cycle_count) * 100,
                                          1) if employees_in_cycle_count > 0 else 0,
                    'first_rating_count': appraisal_pending_supervisor_count,
                    'first_rating_percent': round((appraisal_pending_supervisor_count / employees_in_cycle_count) * 100,
                                                  1) if employees_in_cycle_count > 0 else 0,
                    'second_rating_count': appraisal_pending_secondary_count,  # ← new
                    'second_rating_percent': round((appraisal_pending_secondary_count / employees_in_cycle_count) * 100,
                                                   1) if employees_in_cycle_count > 0 else 0,  # ← new
                    'final_rating_count': appraisal_pending_reviewer_count,
                    'final_rating_percent': round((appraisal_pending_reviewer_count / employees_in_cycle_count) * 100,
                                                  1) if employees_in_cycle_count > 0 else 0,
                    'completed_count': appraisal_completed_count,
                    'completed_percent': round((appraisal_completed_count / employees_in_cycle_count) * 100,
                                               1) if employees_in_cycle_count > 0 else 0,
                }
            else:
                phase_data = {}

            # Determine if cycle is active (not completed or cancelled)
            is_active = cycle.state in ['planning', 'monitoring', 'appraisal']

            cycle_data = {
                'id': cycle.id,
                'name': cycle.name,
                'state': cycle.state,  # planning, monitoring, appraisal, completed
                'type': cycle.cycle_type,
                'start_date': str(cycle.start_date) if cycle.start_date else '-',
                'end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else '-',
                'planning_deadline': str(cycle.planning_deadline) if cycle.planning_deadline else '-',
                'appraisal_start_date': str(cycle.appraisal_start_date) if cycle.appraisal_start_date else '-',
                'days_left': days_left,
                'total_employees': employees_in_cycle_count,
                'plans_submitted': len(plans.filtered(lambda p: p.state != 'draft' and 'appraisal' not in p.state)),
                'completed_count': appraisal_completed_count,
                'plans_approved': len(plans.filtered(lambda p: p.state == 'approved')),
                'progress': progress,
                'phase_data': phase_data,
                'avg_score': avg_score,
                'is_active': is_active,
                # Monitoring specific
                'monitoring_progress': monitoring_progress,
                'appraisal_end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else None,
                # ← ADD (end_date = appraisal end)
                'appraisal_duration_days': (
                        cycle.end_date - cycle.appraisal_start_date).days if cycle.end_date and cycle.appraisal_start_date else None,

            }

            cycles_data.append(cycle_data)

            if is_active:
                active_cycles.append(cycle_data)
            else:
                completed_cycles.append(cycle_data)

        return {
            'all_cycles': cycles_data,
            'active_cycles': active_cycles,
            'completed_cycles': completed_cycles,
            'active_cycles_count': len(active_cycles),
        }

    def _get_overview_stats(self):
        """Get overview statistics including cycle counts"""
        Appraisal = request.env['pms.appraisal'].sudo()
        Cycle = request.env['pms.cycle'].sudo()
        Employee = request.env['hr.employee'].sudo()

        all_appraisals = Appraisal.search([])
        all_employees = Employee.search([('active', '=', True)])

        employees_with_plan_ids = set(all_appraisals.mapped('employee_id').ids)
        employees_without_plan = len(all_employees) - len(employees_with_plan_ids)

        completed_count = len(all_appraisals.filtered(lambda a: a.state == 'appraisal_approved'))

        pending_states = [
            'pending_supervisor', 'pending_secondary_supervisor', 'pending_reviewer',
            'appraisal_pending_supervisor', 'appraisal_pending_secondary_supervisor',
            'appraisal_pending_reviewer',
        ]
        pending_count = 0
        for state in pending_states:
            pending_count += len(all_appraisals.filtered(lambda a: a.state == state))

        active_cycles = Cycle.search([('state', 'in', ['planning', 'monitoring', 'appraisal'])])

        return {
            'total_employees': len(all_employees),
            'total_appraisals': len(all_appraisals),
            'employees_without_plan': employees_without_plan,
            'active_cycles_count': len(active_cycles),
            'pending_reviews': pending_count,
            'completed': completed_count,
        }

    # ============================================================
    # PLANNING TAB DATA
    # ============================================================
    @http.route('/hr_pms_dashboard/planning_data', type='json', auth='user')
    def get_planning_data(self):
        try:
            Appraisal = request.env['pms.appraisal'].sudo()
            Cycle = request.env['pms.cycle'].sudo()
            Employee = request.env['hr.employee'].sudo()
            today = date.today()

            active_planning_cycle = Cycle.search([('state', '=', 'planning')], limit=1)

            cycle_to_use = active_planning_cycle
            is_historical = False

            if not cycle_to_use:
                cycles_with_planning = Cycle.search([
                    ('id', 'in', Appraisal.search([
                        ('state', 'in', ['draft', 'pending_supervisor', 'pending_secondary_supervisor',
                                         'pending_reviewer', 'approved'])
                    ]).mapped('cycle_id').ids)
                ], order='id desc', limit=1)

                if cycles_with_planning:
                    cycle_to_use = cycles_with_planning
                    is_historical = True
                else:
                    return {
                        'pending_supervisor': [],
                        'pending_reviewer': [],
                        'employees_not_started': [],
                        'all_plans': [],
                        'no_active_cycle': True,
                        'is_historical': False,
                        'cycle_name': '',
                        'cycle_end_date': '',
                        'cycle_state': '',
                        'message': 'No planning cycles found',
                    }

            plans = Appraisal.search([('cycle_id', '=', cycle_to_use.id)])

            # Detect available fields
            appraisal_fields = Appraisal._fields
            has_kra_ids = 'kra_ids' in appraisal_fields
            has_submission_date = 'submission_date' in appraisal_fields
            has_kra_count_field = 'kra_count' in appraisal_fields

            all_plans = []
            pending_supervisor = []
            pending_reviewer = []
            submitted_employee_ids = []
            draft_employee_ids = []

            for plan in plans:
                try:
                    # ── KRA count ─────────────────────────────────────────
                    if has_kra_count_field:
                        kra_count = plan.kra_count
                    elif has_kra_ids:
                        kra_count = len(plan.kra_ids)
                    else:
                        kra_count = 0

                    # ── KPI counts (through kra_ids) ────────────────────────
                    all_kpis = plan.kra_ids.mapped('kpi_ids')
                    total_kpi = len(all_kpis)
                    selected_kpi = len(all_kpis.filtered(lambda k: k.is_selected))

                    has_secondary = bool(plan.secondary_supervisor_id)
                    has_reviewer = bool(plan.reviewer_id)
                    total_steps = 2
                    if has_secondary:
                        total_steps += 1
                    if has_reviewer:
                        total_steps += 1

                    state_step_map = {
                        'draft': 0,
                        'pending_supervisor': 1,
                        'pending_secondary_supervisor': 2 if has_secondary else 1,
                        'pending_reviewer': 3 if has_secondary else 2,
                        'approved': total_steps,
                    }
                    step = state_step_map.get(plan.state, 0)
                    progress = round((step / total_steps) * 100, 1) if total_steps else 0

                    # ── Submission date ───────────────────────────────────
                    submitted_date = ''
                    if has_submission_date and plan.submission_date:
                        submitted_date = str(plan.submission_date)

                    # Calculate days stuck
                    days_stuck = 0
                    if plan.state in ['draft', 'pending_supervisor', 'pending_secondary_supervisor',
                                      'pending_reviewer']:
                        if plan.state == 'draft' and plan.create_date:
                            days_stuck = (date.today() - plan.create_date.date()).days
                        elif plan.state == 'pending_supervisor' and plan.submission_date:
                            days_stuck = (date.today() - plan.submission_date.date()).days
                        elif plan.state in ['pending_secondary_supervisor',
                                            'pending_reviewer'] and plan.supervisor_review_date:
                            days_stuck = (date.today() - plan.supervisor_review_date.date()).days

                    row = {
                        'plan_id': plan.id,
                        'employee_id': plan.employee_id.id,
                        'name': plan.employee_id.name,
                        'department': plan.employee_id.department_id.name or '—',
                        'evaluation_group': plan.employee_id.evaluation_group_id.name or '—',
                        'cycle': cycle_to_use.name,
                        'kra_count': kra_count,
                        'selected_kpi': selected_kpi,
                        'total_kpi': total_kpi,
                        'state': dict(Appraisal._fields['state'].selection).get(plan.state, plan.state),
                        'state_key': plan.state,
                        'progress': progress,
                        'has_secondary': has_secondary,
                        'has_reviewer': has_reviewer,
                        'supervisor_name': plan.supervisor_id.name or '',
                        'secondary_name': plan.secondary_supervisor_id.name or '',
                        'reviewer_name': plan.reviewer_id.name or '',
                        'submitted_date': submitted_date,
                        'days_stuck': days_stuck,
                    }
                    all_plans.append(row)

                    if plan.state == 'pending_supervisor':
                        pending_supervisor.append(row)
                    elif plan.state in ('pending_secondary_supervisor', 'pending_reviewer'):
                        pending_reviewer.append(row)

                    if plan.state == 'draft':
                        draft_employee_ids.append(plan.employee_id.id)
                    else:
                        submitted_employee_ids.append(plan.employee_id.id)

                except Exception as row_error:
                    _logger.error("Error processing plan %s: %s\n%s",
                                  plan.id, str(row_error), traceback.format_exc())
                    continue

            all_employees = Employee.search([('active', '=', True)])
            employees_not_started = []
            deadline = cycle_to_use.planning_deadline

            for emp in all_employees:
                if emp.id not in submitted_employee_ids:
                    days_overdue = 0
                    if deadline and today > deadline:
                        days_overdue = (today - deadline).days
                    has_draft = emp.id in draft_employee_ids
                    employees_not_started.append({
                        'id': emp.id,
                        'name': emp.name,
                        'department': emp.department_id.name or '—',
                        'eval_group': emp.evaluation_group_id.name or '—' if hasattr(emp,
                                                                                     'evaluation_group_id') else '—',
                        'days_overdue': days_overdue,
                        'has_draft': has_draft,
                    })

            end_date = str(cycle_to_use.planning_deadline) if cycle_to_use.planning_deadline else ''

            return {
                'pending_supervisor': pending_supervisor,
                'pending_reviewer': pending_reviewer,
                'employees_not_started': employees_not_started,
                'all_plans': all_plans,
                'no_active_cycle': is_historical,
                'is_historical': is_historical,
                'cycle_name': cycle_to_use.name,
                'cycle_end_date': end_date,
                'cycle_state': cycle_to_use.state,
                'message': 'Showing historical data from last planning cycle' if is_historical else 'Current active planning cycle',
            }

        except Exception as e:
            _logger.error("CRITICAL ERROR in get_planning_data: %s\n%s", str(e), traceback.format_exc())
            return {
                'error': str(e),
                'traceback': traceback.format_exc(),
                'pending_supervisor': [],
                'pending_reviewer': [],
                'employees_not_started': [],
                'all_plans': [],
                'no_active_cycle': True,
                'is_historical': False,
                'cycle_name': '',
                'cycle_end_date': '',
                'cycle_state': '',
                'message': 'Error loading data',
            }

    @http.route('/hr_pms_dashboard/get_appraisal_details', type='json', auth='user')
    def get_appraisal_details(self, appraisal_id):
        try:
            Appraisal = request.env['pms.appraisal'].sudo()
            BonusLine = request.env['pms.bonus.calculation.line'].sudo()

            appraisal = Appraisal.browse(int(appraisal_id))
            if not appraisal.exists():
                return {'success': False, 'error': 'Appraisal not found'}

            # ── Stage-aware flags ────────────────────────────────────────
            appraisal_state = appraisal.state
            has_secondary = bool(appraisal.secondary_supervisor_id)
            has_reviewer = bool(appraisal.reviewer_id)

            self_given = appraisal_state not in ['appraisal_draft']
            supervisor_given = appraisal_state in [
                'appraisal_pending_secondary_supervisor',
                'appraisal_pending_reviewer',
                'appraisal_approved',
            ]
            secondary_given = has_secondary and appraisal_state in [
                'appraisal_pending_reviewer',
                'appraisal_approved',
            ]
            reviewer_given = has_reviewer and appraisal_state == 'appraisal_approved'

            # ── KPI lines ────────────────────────────────────────────────
            kpi_lines = []
            for kra in appraisal.kra_ids:
                for kpi in kra.kpi_ids:
                    if kpi.is_selected:
                        kpi_lines.append({
                            'id': kpi.id,
                            'kpi_name': kpi.name,
                            'weightage': kpi.weightage or 0,
                            'self_score': kpi.self_score if self_given else None,
                            'supervisor_score': kpi.supervisor_score if supervisor_given else None,
                            'secondary_score': kpi.secondary_supervisor_score if secondary_given else None,
                            'reviewer_score': kpi.reviewer_score if reviewer_given else None,
                        })

            # ── Competency lines ─────────────────────────────────────────
            competency_lines = []
            competency_total = 0
            cycle = appraisal.cycle_id

            for competency in appraisal.competency_score_ids:
                line_data = {
                    'id': competency.id,
                    'competency_name': competency.line_name or '-',
                    'self_score': competency.self_score if self_given else None,
                    'supervisor_score': competency.supervisor_score if supervisor_given else None,
                    'secondary_score': competency.secondary_supervisor_score if secondary_given else None,
                    'reviewer_score': competency.reviewer_score if reviewer_given else None,
                    'max_points': competency.line_points or 0,
                }
                competency_lines.append(line_data)

                if cycle.final_score_selection == 'reviewer':
                    competency_total += line_data['reviewer_score'] or 0
                elif cycle.final_score_selection == 'average':
                    scores = [s for s in [
                        line_data['supervisor_score'],
                        line_data['secondary_score'],
                        line_data['reviewer_score'],
                    ] if s]
                    competency_total += sum(scores) / len(scores) if scores else 0
                else:
                    competency_total += line_data['supervisor_score'] or 0

            # ── KPI totals (only for stages reached) ─────────────────────
            kpi_self_total = sum(
                l['self_score'] for l in kpi_lines if isinstance(l['self_score'], (int, float))) if self_given else None
            kpi_supervisor_total = sum(l['supervisor_score'] for l in kpi_lines if
                                       isinstance(l['supervisor_score'], (int, float))) if supervisor_given else None
            kpi_secondary_total = sum(l['secondary_score'] for l in kpi_lines if
                                      isinstance(l['secondary_score'], (int, float))) if secondary_given else None
            kpi_reviewer_total = sum(l['reviewer_score'] for l in kpi_lines if
                                     isinstance(l['reviewer_score'], (int, float))) if reviewer_given else None
            kpi_total_weightage = sum(l['weightage'] for l in kpi_lines if isinstance(l['weightage'], (int, float)))

            # ── Competency totals ─────────────────────────────────────────
            competency_self_total = sum(l['self_score'] for l in competency_lines if
                                        isinstance(l['self_score'], (int, float))) if self_given else None
            competency_supervisor_total = sum(l['supervisor_score'] for l in competency_lines if
                                              isinstance(l['supervisor_score'],
                                                         (int, float))) if supervisor_given else None
            competency_secondary_total = sum(l['secondary_score'] for l in competency_lines if
                                             isinstance(l['secondary_score'],
                                                        (int, float))) if secondary_given else None
            competency_reviewer_total = sum(l['reviewer_score'] for l in competency_lines if
                                            isinstance(l['reviewer_score'], (int, float))) if reviewer_given else None

            # ── KPI total for final score calculation ─────────────────────
            if cycle.final_score_selection == 'reviewer':
                kpi_total = appraisal.total_reviewer_score or 0
            elif cycle.final_score_selection == 'average':
                scores = [s for s in [
                    appraisal.total_supervisor_score,
                    appraisal.total_secondary_score,
                    appraisal.total_reviewer_score,
                ] if s]
                kpi_total = sum(scores) / len(scores) if scores else 0
            else:
                kpi_total = appraisal.total_supervisor_score or 0

            final_score = kpi_total + competency_total
            rating = self._get_employee_rating(
                final_score) if appraisal_state == 'appraisal_approved' and final_score is not None else '-'

            # ── Bonus ─────────────────────────────────────────────────────
            bonus_line = BonusLine.search([
                ('employee_id', '=', appraisal.employee_id.id),
                ('cycle_id', '=', cycle.id),
                ('calculation_state', '=', 'calculated'),
            ], order='calculation_date desc', limit=1)

            eligibility_pct = bonus_line.eligibility_percentage if bonus_line else 0.0
            bonus_amount = bonus_line.bonus_amount if bonus_line else 0.0
            basic_pay = bonus_line.base_salary if bonus_line else (appraisal.employee_id.wage or 0.0)

            currency_symbol = (
                bonus_line.currency_id.symbol
                if bonus_line and bonus_line.currency_id
                else request.env.company.currency_id.symbol
            )

            def fmt(amount):
                return f"{currency_symbol} {amount:,.2f}"

            return {
                'success': True,
                'data': {
                    'id': appraisal.id,
                    'name': appraisal.employee_id.name,
                    'cycle': cycle.name,
                    'start_date': str(cycle.start_date) if cycle.start_date else '—',
                    'appraisal_end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else '—',
                    'department': appraisal.employee_id.department_id.name or '-',
                    'state': dict(Appraisal._fields['state'].selection).get(appraisal.state, appraisal.state),
                    'state_key': appraisal_state,
                    'supervisor_name': appraisal.supervisor_id.name if appraisal.supervisor_id else '-',
                    'secondary_name': appraisal.secondary_supervisor_id.name if appraisal.secondary_supervisor_id else None,
                    'reviewer_name': appraisal.reviewer_id.name if appraisal.reviewer_id else None,
                    'total_weightage': sum(l['weightage'] for l in kpi_lines),
                    'kpi_lines': kpi_lines,
                    'competency_lines': competency_lines,
                    'kpi_total': round(kpi_total, 1),
                    'competency_total': round(competency_total, 1),
                    'final_score': round(final_score, 1) if appraisal_state == 'appraisal_approved' else None,
                    'rating': rating,
                    'kpi_self_total': round(kpi_self_total, 1) if kpi_self_total is not None else None,
                    'kpi_supervisor_total': round(kpi_supervisor_total,
                                                  1) if kpi_supervisor_total is not None else None,
                    'kpi_secondary_total': round(kpi_secondary_total, 1) if kpi_secondary_total is not None else None,
                    'kpi_reviewer_total': round(kpi_reviewer_total, 1) if kpi_reviewer_total is not None else None,
                    'kpi_total_weightage': round(kpi_total_weightage, 1),
                    'competency_self_total': round(competency_self_total,
                                                   1) if competency_self_total is not None else None,
                    'competency_supervisor_total': round(competency_supervisor_total,
                                                         1) if competency_supervisor_total is not None else None,
                    'competency_secondary_total': round(competency_secondary_total,
                                                        1) if competency_secondary_total is not None else None,
                    'competency_reviewer_total': round(competency_reviewer_total,
                                                       1) if competency_reviewer_total is not None else None,
                    'calculation_method': cycle.final_score_selection,
                    'eligibility_pct': eligibility_pct,
                    'bonus_amount': bonus_amount,
                    'basic_pay': basic_pay,
                    'bonus_amount_display': fmt(bonus_amount) if bonus_amount else None,
                    'basic_pay_display': fmt(basic_pay) if basic_pay else None,

                }
            }


        except Exception as e:

            _logger.error("ERROR in get_appraisal_details: %s\n%s", str(e), traceback.format_exc())

            return {'success': False, 'error': str(e)}

    @http.route('/hr_pms_dashboard/get_employee_completed_cycle_detail', type='json', auth='user')
    def get_employee_completed_cycle_detail(self, cycle_id, employee_id):
        try:
            Appraisal = request.env['pms.appraisal'].sudo()
            Employee = request.env['hr.employee'].sudo()
            BonusLine = request.env['pms.bonus.calculation.line'].sudo()

            employee = Employee.browse(employee_id)
            if not employee.exists():
                return {'error': 'Employee not found'}

            # Find the appraisal for this employee and cycle
            appraisal = Appraisal.search([
                ('employee_id', '=', employee_id),
                ('cycle_id', '=', cycle_id),
            ], limit=1)

            if not appraisal:
                return {
                    'employee_name': employee.name,
                    'department': employee.department_id.name or '-',
                    'supervisor_name': '-',
                    'secondary_name': None,
                    'reviewer_name': None,
                    'total_weightage': 0,
                    'kpi_total': 0,
                    'competency_total': 0,
                    'final_score': 0,
                    'kpi_lines': [],
                    'competency_lines': [],
                    'eligibility_pct': 0.0,
                    'bonus_amount': 0.0,
                    'basic_pay': 0.0,
                    'bonus_amount_display': None,
                    'basic_pay_display': None,
                    'calculation_method': '-',
                }

            # ── Bonus data ────────────────────────────────────────────────
            bonus_line = BonusLine.search([
                ('employee_id', '=', employee.id),
                ('cycle_id', '=', cycle_id),
                ('calculation_state', '=', 'calculated'),
            ], order='calculation_date desc', limit=1)

            eligibility_pct = bonus_line.eligibility_percentage if bonus_line else 0.0
            bonus_amount = bonus_line.bonus_amount if bonus_line else 0.0
            basic_pay = bonus_line.base_salary if bonus_line else (employee.wage or 0.0)

            currency_symbol = (
                bonus_line.currency_id.symbol
                if bonus_line and bonus_line.currency_id
                else request.env.company.currency_id.symbol
            )

            def fmt(amount):
                return f"{currency_symbol} {amount:,.2f}"

            # ── Get KPI lines (for display only) ─────────────────────────
            kpi_lines = []
            for kra in appraisal.kra_ids:
                for kpi in kra.kpi_ids:
                    if kpi.is_selected:
                        kpi_lines.append({
                            'id': kpi.id,
                            'kpi_name': kpi.name,
                            'weightage': kpi.weightage or 0,
                            'self_score': kpi.self_score if kpi.self_score is not None else None,
                            'supervisor_score': kpi.supervisor_score if kpi.supervisor_score is not None else None,
                            'secondary_score': kpi.secondary_supervisor_score if kpi.secondary_supervisor_score is not None else None,
                            'reviewer_score': kpi.reviewer_score if kpi.reviewer_score is not None else None,
                        })

            # ── Get Competency lines (for display only) ───────────────────
            competency_lines = []

            if hasattr(appraisal, 'competency_score_ids') and appraisal.competency_score_ids:
                for comp in appraisal.competency_score_ids:
                    competency_lines.append({
                        'id': comp.id,
                        'competency_name': comp.line_name or comp.name or '-',
                        'self_score': comp.self_score if comp.self_score is not None else None,
                        'supervisor_score': comp.supervisor_score if comp.supervisor_score is not None else None,
                        'secondary_score': getattr(comp, 'secondary_supervisor_score', None),
                        'reviewer_score': comp.reviewer_score if comp.reviewer_score is not None else None,
                        'max_points': comp.line_points or 0,
                    })
            elif hasattr(appraisal, 'competency_line_ids') and appraisal.competency_line_ids:
                for line in appraisal.competency_line_ids:
                    competency_lines.append({
                        'id': line.id,
                        'competency_name': line.competency_id.name if line.competency_id else '-',
                        'self_score': line.self_score if line.self_score is not None else None,
                        'supervisor_score': line.supervisor_score if line.supervisor_score is not None else None,
                        'secondary_score': line.secondary_supervisor_score if line.secondary_supervisor_score is not None else None,
                        'reviewer_score': line.reviewer_score if line.reviewer_score is not None else None,
                        'max_points': line.max_points or 0,
                    })

            # ── Use SYSTEM-CALCULATED values ─────────────────────────────
            cycle = appraisal.cycle_id

            # Determine calculation method for display only
            if cycle.final_score_selection == 'reviewer':
                calculation_method = 'Reviewer Score'
            else:
                calculation_method = 'Average Score'

            # ✅ JUST USE THE SYSTEM-CALCULATED FINAL SCORE
            final_score = appraisal.final_appraisal_score or 0

            return {
                'employee_name': employee.name,
                'department': employee.department_id.name or '-',
                'supervisor_name': appraisal.supervisor_id.name if appraisal.supervisor_id else '-',
                'secondary_name': appraisal.secondary_supervisor_id.name if appraisal.secondary_supervisor_id else None,
                'reviewer_name': appraisal.reviewer_id.name if appraisal.reviewer_id else None,
                'total_weightage': sum(l['weightage'] for l in kpi_lines),
                'kpi_total': 0,  # Not needed - system calculates final_score directly
                'competency_total': 0,  # Not needed - system calculates final_score directly
                'final_score': round(final_score, 1),
                'kpi_lines': kpi_lines,
                'competency_lines': competency_lines,
                'eligibility_pct': eligibility_pct,
                'bonus_amount': bonus_amount,
                'basic_pay': basic_pay,
                'bonus_amount_display': fmt(bonus_amount) if bonus_amount else None,
                'basic_pay_display': fmt(basic_pay) if basic_pay else None,
                'calculation_method': calculation_method,
            }
        except Exception as e:
            _logger.error("ERROR in get_employee_completed_cycle_detail: %s\n%s", str(e), traceback.format_exc())
            return {'error': str(e)}

    # ============================================================
    # DEPARTMENT COMPLETION DATA
    # ============================================================
    @http.route('/hr_pms_dashboard/dept_completion_data', type='json', auth='user')
    def get_dept_completion_data(self):
        """
        Returns per-department plan state breakdown for the planning cycle.
        """
        try:
            Appraisal = request.env['pms.appraisal'].sudo()
            Cycle = request.env['pms.cycle'].sudo()
            Employee = request.env['hr.employee'].sudo()

            # Find active planning cycle OR most recent cycle with planning data
            active_cycle = Cycle.search([('state', '=', 'planning')], limit=1)

            # If no active planning cycle, get the most recent cycle that has appraisals
            if not active_cycle:
                cycles_with_planning = Cycle.search([
                    ('id', 'in', Appraisal.search([
                        ('state', 'in', ['draft', 'pending_supervisor', 'pending_secondary_supervisor',
                                         'pending_reviewer', 'approved'])
                    ]).mapped('cycle_id').ids)
                ], order='id desc', limit=1)

                if cycles_with_planning:
                    active_cycle = cycles_with_planning

            if not active_cycle:
                return {'dept_rows': [], 'dept_lagging': []}

            # Get ALL plans for this cycle
            plans = Appraisal.search([('cycle_id', '=', active_cycle.id)])
            # Map employee_id → plan state
            plan_map = {}
            for plan in plans:
                eid = plan.employee_id.id
                state = plan.state
                plan_map[eid] = state  # Store actual state

            # Group employees by department
            all_employees = Employee.search([('active', '=', True)])
            dept_map = {}

            for emp in all_employees:
                dept = emp.department_id.name or 'No Department'
                if dept not in dept_map:
                    dept_map[dept] = {
                        'name': dept,
                        'total': 0,
                        'not_started': 0,
                        'draft': 0,
                        'pending_supervisor': 0,
                        'pending_reviewer': 0,
                        'approved': 0,
                    }
                dept_map[dept]['total'] += 1

                state = plan_map.get(emp.id)

                if state is None:
                    dept_map[dept]['not_started'] += 1
                elif state == 'draft':
                    dept_map[dept]['draft'] += 1
                elif state == 'pending_supervisor':
                    dept_map[dept]['pending_supervisor'] += 1
                elif state in ['pending_secondary_supervisor', 'pending_reviewer']:
                    dept_map[dept]['pending_reviewer'] += 1
                elif state == 'approved':
                    dept_map[dept]['approved'] += 1

            # Convert to list and sort by approval rate
            dept_rows = list(dept_map.values())
            for d in dept_rows:
                approval_rate = (d['approved'] / d['total'] * 100) if d['total'] else 0

            dept_rows.sort(key=lambda d: d['approved'] / d['total'] if d['total'] else 0)

            # Get lagging departments (lowest approval rate)
            dept_lagging = [d for d in dept_rows if d['total'] > 0][:3]

            return {
                'dept_rows': dept_rows,
                'dept_lagging': dept_lagging,
            }


        except Exception as e:

            _logger.error("ERROR in get_dept_completion_data: %s\n%s", str(e), traceback.format_exc())

            return {

                'dept_rows': [],

                'dept_lagging': [],

            }
    # ------------------------------------------------------------------
    # HR MANAGER
    # ------------------------------------------------------------------
    def _get_hr_manager_data(self):
        Appraisal = request.env['pms.appraisal'].sudo()
        Cycle = request.env['pms.cycle'].sudo()
        Employee = request.env['hr.employee'].sudo()
        today = date.today()

        # Get cycle data for overview
        cycle_data = self._get_all_cycles_data()
        overview_stats = self._get_overview_stats()

        all_appraisals = Appraisal.search([])
        all_employees = Employee.search([
            ('active', '=', True),
            ('company_id', '=', request.env.company.id)
        ])

        # ============================================================
        # ONLY COUNT PLANS FROM ACTIVE CYCLES (planning or appraisal)
        # ============================================================
        active_cycles = Cycle.search([('state', 'in', ['planning', 'monitoring', 'appraisal'])])
        active_cycle_ids = active_cycles.mapped('id')

        employees_in_active_cycles_ids = []
        for cycle in active_cycles:
            cycle_appraisals = Appraisal.search([('cycle_id', '=', cycle.id)])
            employee_ids = cycle_appraisals.mapped('employee_id').ids
            employees_in_active_cycles_ids.extend(employee_ids)

        # Deduplicate
        employees_in_active_cycles_ids = list(set(employees_in_active_cycles_ids))
        employees_in_active_cycles = len(employees_in_active_cycles_ids)

        # Only count appraisals from active cycles
        active_cycle_appraisals = all_appraisals.filtered(lambda a: a.cycle_id.id in active_cycle_ids)

        # State counts only for active cycles
        state_counts = {}
        for appraisal in active_cycle_appraisals:
            state_counts[appraisal.state] = state_counts.get(appraisal.state, 0) + 1

        # Define state lists
        planning_states = [
            'draft', 'pending_supervisor', 'pending_secondary_supervisor',
            'pending_reviewer', 'approved',
        ]

        appraisal_states = [
            'appraisal_draft',
            'appraisal_pending_supervisor',
            'appraisal_pending_secondary_supervisor',
            'appraisal_pending_reviewer',
            'appraisal_approved'
        ]

        planning_count = sum(state_counts.get(s, 0) for s in planning_states)
        appraisal_count = sum(state_counts.get(s, 0) for s in appraisal_states)

        pending_states = [
            'pending_supervisor', 'pending_secondary_supervisor', 'pending_reviewer',
            'appraisal_pending_supervisor', 'appraisal_pending_secondary_supervisor',
            'appraisal_pending_reviewer',
        ]
        pending_count = sum(state_counts.get(s, 0) for s in pending_states)

        # ============================================================
        # FIX: Only count employees with plans in ACTIVE cycles
        # ============================================================
        employees_with_any_plan = len(active_cycle_appraisals.mapped('employee_id'))
        employees_with_submitted_plan = len(
            active_cycle_appraisals.filtered(lambda a: a.state != 'draft').mapped('employee_id')
        )
        total_employees = len(all_employees)

        participation = {
            'participated': employees_with_any_plan,
            'not_participated': max(0, total_employees - employees_with_any_plan),
            'submitted': employees_with_submitted_plan,
            'not_started': max(0, total_employees - employees_with_submitted_plan),
            'total': total_employees,
        }

        # Planning dates
        planning_dates = None
        planning_cycle = Cycle.search([('state', '=', 'planning')], limit=1)
        if planning_cycle:
            deadline = planning_cycle.planning_deadline
            days_left = (deadline - today).days if deadline else None
            planning_dates = {
                'cycle_name': planning_cycle.name,
                'start': str(planning_cycle.start_date) if planning_cycle.start_date else '-',
                'deadline': str(deadline) if deadline else '-',
                'days_left': days_left,
            }

        # Appraisal dates
        appraisal_dates = None
        appraisal_cycle = Cycle.search([('state', '=', 'appraisal')], limit=1)
        if appraisal_cycle:
            end = appraisal_cycle.end_date
            days_left = (end - today).days if end else None
            appraisal_dates = {
                'cycle_name': appraisal_cycle.name,
                'start': str(appraisal_cycle.appraisal_start_date) if appraisal_cycle.appraisal_start_date else '-',
                'end': str(end) if end else '-',
                'days_left': days_left,
            }

        # Eval group charts (using active cycle appraisals)
        eval_group_planning = {}
        eval_group_appraisal = {}
        for appraisal in active_cycle_appraisals:
            group_name = appraisal.employee_id.evaluation_group_id.name or 'No Group'
            if appraisal.state in planning_states:
                eval_group_planning[group_name] = eval_group_planning.get(group_name, 0) + 1
            if appraisal.state in appraisal_states:
                eval_group_appraisal[group_name] = eval_group_appraisal.get(group_name, 0) + 1

        all_groups = sorted(set(list(eval_group_planning.keys()) + list(eval_group_appraisal.keys())))
        eval_group_chart = {
            'labels': all_groups,
            'planning': [eval_group_planning.get(g, 0) for g in all_groups],
            'appraisal': [eval_group_appraisal.get(g, 0) for g in all_groups],
        }

        # Dept group chart
        dept_group_employees = {}
        for emp in all_employees:
            dept = emp.department_id.name or 'No Department'
            group = emp.evaluation_group_id.name or 'No Group'
            if dept not in dept_group_employees:
                dept_group_employees[dept] = {}
            dept_group_employees[dept][group] = dept_group_employees[dept].get(group, 0) + 1

        all_group_names = sorted(set(g for groups in dept_group_employees.values() for g in groups))
        dept_names = list(dept_group_employees.keys())
        dept_group_chart = {
            'departments': dept_names,
            'groups': all_group_names,
            'datasets': [
                {
                    'label': group,
                    'data': [dept_group_employees.get(dept, {}).get(group, 0) for dept in dept_names],
                }
                for group in all_group_names
            ],
        }

        # Appraisal breakdown
        appraisal_state_labels = {
            'appraisal_draft': 'Draft',
            'appraisal_pending_supervisor': '1st Rating',
            'appraisal_pending_secondary_supervisor': '2nd Rating',
            'appraisal_pending_reviewer': 'Final Rating',
            'appraisal_approved': 'Completed',
        }
        appraisal_breakdown = [
            {'label': label, 'count': state_counts.get(state_key, 0)}
            for state_key, label in appraisal_state_labels.items()
            if state_counts.get(state_key, 0) > 0
        ]

        score_engine = self._get_score_engine()

        # Employee charts
        dept_counts = {}
        eval_group_counts = {}
        for emp in all_employees:
            dept = emp.department_id.name or 'No Department'
            group = emp.evaluation_group_id.name or 'No Group'
            dept_counts[dept] = dept_counts.get(dept, 0) + 1
            eval_group_counts[group] = eval_group_counts.get(group, 0) + 1

        employee_dept_chart = {
            'labels': list(dept_counts.keys()),
            'data': list(dept_counts.values()),
        }
        employee_eval_group_chart = {
            'labels': list(eval_group_counts.keys()),
            'data': list(eval_group_counts.values()),
        }


        appraisal_eval_group = {}
        for appraisal in active_cycle_appraisals:
            if appraisal.state in appraisal_states:
                group_name = appraisal.employee_id.evaluation_group_id.name or 'No Group'
                appraisal_eval_group[group_name] = appraisal_eval_group.get(group_name, 0) + 1

        appraisal_eval_group_chart = {
            'labels': list(appraisal_eval_group.keys()),
            'data': list(appraisal_eval_group.values()),
        }

        # Employees without plan / appraisal
        employees_with_plan_ids = set(active_cycle_appraisals.mapped('employee_id').ids)

        if planning_cycle:
            employees_with_plan_in_cycle_ids = set(
                Appraisal.search([('cycle_id', '=', planning_cycle.id)]).mapped('employee_id').ids
            )
            employees_no_plan = all_employees.filtered(lambda e: e.id not in employees_with_plan_in_cycle_ids)
            employees_no_plan_list = [
                {
                    'id': emp.id,
                    'name': emp.name,
                    'department': emp.department_id.name or '-',
                    'evaluation_group': emp.evaluation_group_id.name or '-',
                }
                for emp in employees_no_plan
            ]
            employees_no_plan_count = len(employees_no_plan_list)
        else:
            employees_no_plan_list = []
            employees_no_plan_count = 0

        if appraisal_cycle:
            employees_with_appraisal_ids = set(
                Appraisal.search([
                    ('cycle_id', '=', appraisal_cycle.id),
                    ('state', '=', 'appraisal_approved'),
                ]).mapped('employee_id').ids
            )
            employees_no_appraisal = all_employees.filtered(lambda e: e.id not in employees_with_appraisal_ids)
            employees_no_appraisal_list = [
                {
                    'id': emp.id,
                    'name': emp.name,
                    'department': emp.department_id.name or '-',
                    'evaluation_group': emp.evaluation_group_id.name or '-',
                }
                for emp in employees_no_appraisal
            ]
            employees_no_appraisal_count = len(employees_no_appraisal_list)
        else:
            employees_no_appraisal_list = []
            employees_no_appraisal_count = 0

        # Hierarchy employees list
        hierarchy_employees_list = [
            {
                'id': emp.id,
                'name': emp.name,
                'department': emp.department_id.name or '-',
                'evaluation_group': emp.evaluation_group_id.name or '-',
                'supervisor': emp.parent_id.name or None,
                'secondary_supervisor': emp.secondary_manager_id.name or None,
                'reviewer': emp.reviewer_id.name or None,
                'plan_status': 'completed' if emp.id in employees_with_plan_ids else 'not_started',
                'plan_status_label': 'Completed' if emp.id in employees_with_plan_ids else 'Not Started',
            }
            for emp in all_employees
        ]

        department_list = list(set(emp.department_id.name for emp in all_employees if emp.department_id))
        evaluation_group_list = list(
            set(emp.evaluation_group_id.name for emp in all_employees if emp.evaluation_group_id))

        # ============================================================
        # APPRAISAL SECTION DATA - Shows data even if phase is closed
        # ============================================================

        # Get the cycle that was used for appraisal (the one with appraisal dates)
        appraisal_cycle_for_data = None
        if appraisal_cycle:
            appraisal_cycle_for_data = appraisal_cycle
        else:
            appraisal_cycle_for_data = Cycle.search([('appraisal_start_date', '!=', False)], order='id desc', limit=1)

        # Get all appraisals in this cycle
        appraisals_to_show = all_appraisals
        if appraisal_cycle_for_data:
            appraisals_to_show = all_appraisals.filtered(lambda a: a.cycle_id.id == appraisal_cycle_for_data.id)

        # ============================================================
        # LIST 1: Employees with NO appraisal record at all
        # ============================================================
        employees_with_appraisal_ids_in_cycle = set(appraisals_to_show.mapped('employee_id').ids)

        appraisal_no_record_list = []
        for emp in all_employees:
            if emp.id not in employees_with_appraisal_ids_in_cycle:
                appraisal_no_record_list.append({
                    'id': emp.id,
                    'name': emp.name,
                    'department': emp.department_id.name or '-',
                    'evaluation_group': emp.evaluation_group_id.name or '-',
                })

        # ============================================================
        # LIST 2: Employees with appraisal in DRAFT (not started self-rating)
        # ============================================================
        appraisal_draft_list = []
        for appraisal in appraisals_to_show.filtered(lambda a: a.state == 'appraisal_draft'):
            appraisal_draft_list.append({
                'id': appraisal.employee_id.id,
                'appraisal_id': appraisal.id,
                'name': appraisal.employee_id.name,
                'department': appraisal.employee_id.department_id.name or '-',
                'evaluation_group': appraisal.employee_id.evaluation_group_id.name or '-',
                'created_date': appraisal.create_date.strftime('%Y-%m-%d') if appraisal.create_date else '-',
            })

        # ============================================================
        # LIST 3: Employees who HAVE started appraisal (in progress)
        # ============================================================
        appraisal_employees = []
        for appraisal in appraisals_to_show.filtered(
                lambda a: a.state != 'appraisal_draft' and a.state in appraisal_states):
            has_secondary = bool(appraisal.secondary_supervisor_id)
            has_reviewer = bool(appraisal.reviewer_id)
            total_steps = 2
            if has_secondary:
                total_steps += 1
            if has_reviewer:
                total_steps += 1

            state_step_map = {
                'appraisal_draft': 0,
                'appraisal_pending_supervisor': 1,
                'appraisal_pending_secondary_supervisor': 2 if has_secondary else 1,
                'appraisal_pending_reviewer': 3 if has_secondary else 2,
                'appraisal_approved': total_steps,
            }
            step = state_step_map.get(appraisal.state, 0)
            progress = round((step / total_steps) * 100, 1) if total_steps else 0

            appraisal_employees.append({
                'id': appraisal.employee_id.id,
                'appraisal_id': appraisal.id,
                'name': appraisal.employee_id.name,
                'department': appraisal.employee_id.department_id.name or '-',
                'evaluation_group': appraisal.employee_id.evaluation_group_id.name or '-',
                'state': dict(Appraisal._fields['state'].selection).get(appraisal.state, appraisal.state),
                'state_key': appraisal.state,
                'progress': progress,
                'has_secondary': has_secondary,
                'has_reviewer': has_reviewer,
                'supervisor_name': appraisal.supervisor_id.name or '',
                'secondary_name': appraisal.secondary_supervisor_id.name or '',
                'reviewer_name': appraisal.reviewer_id.name or '',
                'self_score': appraisal.total_self_score if appraisal.total_self_score is not None else None,
                'supervisor_score': appraisal.total_supervisor_score if appraisal.total_supervisor_score is not None else None,
                'final_score': appraisal.final_appraisal_score if appraisal.final_appraisal_score is not None else None,
                'cycle': appraisal.cycle_id.name if appraisal.cycle_id else '-',
            })

        # Total not started count for stat card
        appraisal_not_started_count = len(appraisal_no_record_list) + len(appraisal_draft_list)

        # ============================================================
        # RETURN STATEMENT WITH NEW CYCLE DATA
        # ============================================================
        return {
            # New cycle data for overview tab
            'all_cycles': cycle_data['all_cycles'],
            'active_cycles_list': cycle_data['active_cycles'],
            'completed_cycles_list': cycle_data['completed_cycles'],
            'active_cycles_count': cycle_data['active_cycles_count'],
            'overview_stats': overview_stats,

            'employees_in_active_cycles': employees_in_active_cycles,
            'employees_in_active_cycles_ids': employees_in_active_cycles_ids,

            # Existing data
            'appraisal_no_record_list': appraisal_no_record_list,
            'appraisal_draft_list': appraisal_draft_list,
            'appraisal_employees': appraisal_employees,
            'appraisal_not_started_count': appraisal_not_started_count,
            'stats': {
                'total_employees': total_employees,
                'total_appraisals': len(active_cycle_appraisals),  # FIXED: Only active cycles
                'active_cycles': len(active_cycles),
                'active_cycles_count': len(active_cycles),
                'pending_reviews': pending_count,
                'completed': state_counts.get('appraisal_approved', 0),
                'planning_count': planning_count,
                'appraisal_count': appraisal_count,
                'pending_manager_approval': state_counts.get('pending_supervisor', 0),
                'pending_secondary_approval': state_counts.get('pending_secondary_supervisor', 0),
                'pending_reviewer_approval': state_counts.get('pending_reviewer', 0),
                'pending_appraisal_manager': state_counts.get('appraisal_pending_supervisor', 0),
                'pending_appraisal_secondary': state_counts.get('appraisal_pending_secondary_supervisor', 0),
                'pending_appraisal_reviewer': state_counts.get('appraisal_pending_reviewer', 0),
                'appraisal_not_started': appraisal_not_started_count,
                'total_cycles_count': len(cycle_data['all_cycles']),  # Total cycles (all cycles)
                'probation_active_cycles_count': len(
                    [c for c in cycle_data['active_cycles'] if c.get('type') == 'probation']),  # Probation cycles
                'total_active_employees': len([e for e in all_employees if e.active]),  # Total active employees
                'employees_in_active_cycles': employees_in_active_cycles,
            },
            'employees_no_plan': employees_no_plan_list,
            'employees_no_appraisal': employees_no_appraisal_list,
            'employees_no_plan_count': employees_no_plan_count,
            'employees_no_appraisal_count': employees_no_appraisal_count,
            'hierarchy_employees': hierarchy_employees_list,
            'department_list': department_list,
            'evaluation_group_list': evaluation_group_list,
            'employees_with_plan': list(employees_with_plan_ids),
            'pending_manager_list': [
                {'id': a.id, 'name': a.employee_id.name, 'department': a.employee_id.department_id.name or '-'}
                for a in active_cycle_appraisals if a.state == 'pending_supervisor'
            ],
            'pending_secondary_list': [
                {'id': a.id, 'name': a.employee_id.name, 'department': a.employee_id.department_id.name or '-'}
                for a in active_cycle_appraisals if a.state == 'pending_secondary_supervisor'
            ],
            'pending_reviewer_list': [
                {'id': a.id, 'name': a.employee_id.name, 'department': a.employee_id.department_id.name or '-'}
                for a in active_cycle_appraisals if a.state == 'pending_reviewer'
            ],
            'pending_appraisal_manager_list': [
                {'id': a.id, 'name': a.employee_id.name, 'department': a.employee_id.department_id.name or '-'}
                for a in active_cycle_appraisals if a.state == 'appraisal_pending_supervisor'

            ],
            'pending_appraisal_secondary_list': [
                {'id': a.id, 'name': a.employee_id.name, 'department': a.employee_id.department_id.name or '-'}
                for a in active_cycle_appraisals if a.state == 'appraisal_pending_secondary_supervisor'

            ],
            'pending_appraisal_reviewer_list': [
                {'id': a.id, 'name': a.employee_id.name, 'department': a.employee_id.department_id.name or '-'}
                for a in active_cycle_appraisals if a.state == 'appraisal_pending_reviewer'

            ],
            'participation': participation,
            'planning_dates': planning_dates,
            'appraisal_dates': appraisal_dates,
            'state_chart': {
                'labels': [
                    'Draft', '1st Review', '2nd Review', 'Final Review', 'Approved',
                    'Appraisal Draft', '1st Appraisal', '2nd Appraisal', 'Final Appraisal', 'Completed',
                ],
                'data': [
                    state_counts.get('draft', 0),
                    state_counts.get('pending_supervisor', 0),
                    state_counts.get('pending_secondary_supervisor', 0),
                    state_counts.get('pending_reviewer', 0),
                    state_counts.get('approved', 0),
                    state_counts.get('appraisal_draft', 0),
                    state_counts.get('appraisal_pending_supervisor', 0),
                    state_counts.get('appraisal_pending_secondary_supervisor', 0),
                    state_counts.get('appraisal_pending_reviewer', 0),
                    state_counts.get('appraisal_approved', 0),
                ],
            },
            'phase_chart': {
                'labels': ['Planning Phase', 'Appraisal Phase'],
                'data': [planning_count, appraisal_count],
            },
            'eval_group_chart': eval_group_chart,
            'appraisal_breakdown': appraisal_breakdown,
            'score_engine': score_engine,
            'active_cycles': [{'name': c.name, 'state': c.state} for c in active_cycles],
            'employee_dept_chart': employee_dept_chart,
            'employee_eval_group_chart': employee_eval_group_chart,
            'appraisal_eval_group_chart': appraisal_eval_group_chart,
        }

    @http.route('/hr_pms_dashboard/get_all_employee_ids', type='json', auth='user')
    def get_all_employee_ids(self):
        Employee = request.env['hr.employee'].sudo()
        employees = Employee.search([('active', '=', True)])
        return {'employee_ids': employees.mapped('id')}

    @http.route('/hr_pms_dashboard/get_completed_cycle_appraisals', type='json', auth='user')
    def get_completed_cycle_appraisals(self, cycle_id=None):  # Accept as argument directly
        try:

            if not cycle_id:
                return {'appraisals': [], 'error': 'No cycle_id provided'}

            try:
                cycle_id = int(cycle_id)
            except (ValueError, TypeError):
                return {'appraisals': [], 'error': f'Invalid cycle_id: {cycle_id}'}

            Cycle = request.env['pms.cycle'].sudo()
            Appraisal = request.env['pms.appraisal'].sudo()
            BonusLine = request.env['pms.bonus.calculation.line'].sudo()

            cycle = Cycle.browse(cycle_id)
            if not cycle.exists():
                return {'appraisals': [], 'error': f'Cycle not found with id: {cycle_id}'}

            # Get ALL appraisals for this cycle - NO STATE FILTER
            appraisals = Appraisal.search([('cycle_id', '=', cycle.id)])
            currency_symbol = request.env.company.currency_id.symbol

            def fmt(amount):
                return f"{currency_symbol} {amount:,.2f}"

            appraisal_data = []
            for appraisal in appraisals:
                emp = appraisal.employee_id  # ← ADD this line

                rating = '-'
                if appraisal.final_appraisal_score is not None:
                    rating = self._get_employee_rating(appraisal.final_appraisal_score)

                bonus_line = BonusLine.search([
                    ('employee_id', '=', emp.id),
                    ('cycle_id', '=', cycle.id),
                    ('calculation_state', '=', 'calculated'),
                ], order='calculation_date desc', limit=1)

                eligibility_pct = bonus_line.eligibility_percentage if bonus_line else 0.0
                bonus_amount = bonus_line.bonus_amount if bonus_line else 0.0
                basic_pay = bonus_line.base_salary if bonus_line else (emp.wage or 0.0)

                if bonus_line and bonus_line.currency_id:
                    currency_symbol = bonus_line.currency_id.symbol

                kpi_weightage = 0.0
                for kra in appraisal.kra_ids:
                    for kpi in kra.kpi_ids:
                        if kpi.is_selected:
                            kpi_weightage += kpi.weightage or 0.0

                competency_weightage = 0.0
                if hasattr(appraisal, 'competency_score_ids') and appraisal.competency_score_ids:
                    for comp in appraisal.competency_score_ids:
                        competency_weightage += comp.line_points or 0.0

                total_weightage = kpi_weightage + competency_weightage

                appraisal_data.append({
                    'employee_id': appraisal.employee_id.id,
                    'name': appraisal.employee_id.name,
                    'department': appraisal.employee_id.department_id.name or '-',
                    'evaluation_group': appraisal.employee_id.evaluation_group_id.name or '-',
                    'self_score': appraisal.total_self_score if appraisal.total_self_score is not None else None,
                    'supervisor_score': appraisal.total_supervisor_score if appraisal.total_supervisor_score is not None else None,
                    'secondary_score': appraisal.total_secondary_score if appraisal.total_secondary_score is not None else None,
                    'reviewer_score': appraisal.total_reviewer_score if appraisal.total_reviewer_score is not None else None,
                    'final_score': appraisal.final_appraisal_score if appraisal.final_appraisal_score is not None else None,
                    'rating': rating,
                    'eligibility_pct': eligibility_pct,
                    'basic_pay': basic_pay,
                    'bonus_amount': bonus_amount,
                    'basic_pay_display': fmt(basic_pay) if basic_pay else None,
                    'bonus_amount_display': fmt(bonus_amount) if bonus_amount else None,
                    'weightage': round(total_weightage, 1),

                })

            # Calculate average score from all appraisals
            scores = [a['final_score'] for a in appraisal_data if a['final_score'] and a['final_score'] > 0]
            avg_score = round(sum(scores) / len(scores), 1) if scores else 0

            return {
                'appraisals': appraisal_data,
                'summary': {
                    'total_employees': len(appraisal_data),
                    'avg_score': avg_score,
                    'top_rating': '-',
                    'completed_count': len([a for a in appraisal_data if a['final_score'] > 0]),
                }
            }


        except Exception as e:

            _logger.error("ERROR in get_completed_cycle_appraisals: %s\n%s", str(e), traceback.format_exc())

            return {'appraisals': [], 'error': str(e)}

    @http.route('/hr_pms_dashboard/test_completed', type='json', auth='user')
    def test_completed(self):
        """Simple test endpoint"""
        return {'success': True, 'message': 'Test endpoint works!'}

    @http.route('/hr_pms_dashboard/test_appraisals', type='json', auth='user')
    def test_appraisals(self, cycle_id):
        """Simple test to check if appraisals are found"""
        Cycle = request.env['pms.cycle'].sudo()
        Appraisal = request.env['pms.appraisal'].sudo()

        cycle = Cycle.browse(int(cycle_id))
        appraisals = Appraisal.search([('cycle_id', '=', cycle.id)])

        return {
            'cycle_name': cycle.name,
            'cycle_state': cycle.state,
            'total_appraisals': len(appraisals),
            'appraisal_ids': [a.id for a in appraisals],
            'employee_names': [a.employee_id.name for a in appraisals],
        }

    @http.route('/hr_pms_dashboard/cycle_data', type='json', auth='user')
    def get_cycle_data(self, cycle_id=None):
        """Get planning, appraisal, and score data for a specific cycle"""
        try:
            Appraisal = request.env['pms.appraisal'].sudo()
            Cycle = request.env['pms.cycle'].sudo()
            from datetime import date

            cycle = Cycle.browse(int(cycle_id))
            if not cycle.exists():
                return {'error': 'Cycle not found'}

            # Get all appraisals for this cycle
            appraisals = Appraisal.search([('cycle_id', '=', cycle.id)])

            # Get current logged-in employee
            current_employee = request.env.user.employee_id

            planning_data = []
            appraisal_data = []
            today = date.today()
            # ============================================================
            # BUILD pending_plan_list for supervisor/reviewer views
            # ============================================================
            pending_plan_list = []

            for plan in appraisals:
                # Check if current user is supervisor/reviewer for this plan
                is_primary = plan.supervisor_id and plan.supervisor_id.id == current_employee.id
                is_secondary = plan.secondary_supervisor_id and plan.secondary_supervisor_id.id == current_employee.id
                is_reviewer = plan.reviewer_id and plan.reviewer_id.id == current_employee.id

                # Determine if this plan needs action from current user
                needs_action = False
                if is_primary and plan.state == 'pending_supervisor':
                    needs_action = True
                elif is_secondary and plan.state == 'pending_secondary_supervisor':
                    needs_action = True

                elif is_reviewer and plan.state == 'pending_reviewer':
                    needs_action = True

                if needs_action:
                    pending_plan_list.append({
                        'id': plan.id,
                        'employee_id': plan.employee_id.id,
                        'name': plan.employee_id.name,
                        'department': plan.employee_id.department_id.name or '-',
                        'plan_id': plan.id,
                        'state_key': plan.state,
                        'state': dict(Appraisal._fields['state'].selection).get(plan.state, plan.state),
                        'submitted_date': str(plan.submitted_date) if plan.submitted_date else None,
                    })

            for plan in appraisals:
                # Determine user_role
                user_role = None
                if plan.supervisor_id and plan.supervisor_id.id == current_employee.id:
                    user_role = 'primary'
                elif plan.secondary_supervisor_id and plan.secondary_supervisor_id.id == current_employee.id:
                    user_role = 'secondary'
                elif plan.reviewer_id and plan.reviewer_id.id == current_employee.id:
                    user_role = 'reviewer'

                kra_count = len(plan.kra_ids)
                all_kpis = plan.kra_ids.mapped('kpi_ids')
                total_kpi = len(all_kpis)
                selected_kpi = len(all_kpis.filtered(lambda k: k.is_selected))

                has_secondary = bool(plan.secondary_supervisor_id)
                has_reviewer = bool(plan.reviewer_id)
                total_steps = 2
                if has_secondary:
                    total_steps += 1
                if has_reviewer:
                    total_steps += 1

                state_step_map = {
                    'draft': 0,
                    'pending_supervisor': 1,
                    'pending_secondary_supervisor': 2 if has_secondary else 1,
                    'pending_reviewer': 3 if has_secondary else 2,
                    'approved': total_steps,
                    'appraisal_draft': 0,
                    'appraisal_pending_supervisor': 1,
                    'appraisal_pending_secondary_supervisor': 2 if has_secondary else 1,
                    'appraisal_pending_reviewer': 3 if has_secondary else 2,
                    'appraisal_approved': total_steps,
                }
                step = state_step_map.get(plan.state, 0)
                progress = round((step / total_steps) * 100, 1) if total_steps else 0

                submitted_date = str(plan.submitted_date) if plan.submitted_date else ''

                days_stuck = 0
                if plan.state == 'draft' and plan.create_date:
                    days_stuck = (today - plan.create_date.date()).days
                elif plan.state == 'pending_supervisor' and plan.submitted_date:
                    days_stuck = (today - plan.submitted_date.date()).days
                elif plan.state in ['pending_secondary_supervisor', 'pending_reviewer'] and plan.supervisor_review_date:
                    days_stuck = (today - plan.supervisor_review_date.date()).days

                # ── Stage-aware score nulling (NO nested loop) ──────────────────
                state = plan.state
                self_given = state not in ['appraisal_draft']
                supervisor_given = state in [
                    'appraisal_pending_secondary_supervisor',
                    'appraisal_pending_reviewer',
                    'appraisal_approved',
                ]
                secondary_given = has_secondary and state in [
                    'appraisal_pending_reviewer',
                    'appraisal_approved',
                ]
                reviewer_given = has_reviewer and state == 'appraisal_approved'

                row = {
                    'plan_id': plan.id,
                    'employee_id': plan.employee_id.id,
                    'name': plan.employee_id.name,
                    'department': plan.employee_id.department_id.name or '—',
                    'evaluation_group': plan.employee_id.evaluation_group_id.name or '—',
                    'kra_count': kra_count,
                    'selected_kpi': selected_kpi,
                    'total_kpi': total_kpi,
                    'state': dict(Appraisal._fields['state'].selection).get(plan.state, plan.state),
                    'state_key': plan.state,
                    'progress': progress,
                    'has_secondary': has_secondary,
                    'has_reviewer': has_reviewer,
                    'supervisor_name': plan.supervisor_id.name or '',
                    'secondary_name': plan.secondary_supervisor_id.name or '',
                    'reviewer_name': plan.reviewer_id.name or '',
                    'self_score': plan.total_self_score if self_given else None,
                    'supervisor_score': plan.total_supervisor_score if supervisor_given else None,
                    'secondary_score': plan.total_secondary_score if secondary_given else None,
                    'reviewer_score': plan.total_reviewer_score if reviewer_given else None,
                    'supervisor_id': plan.supervisor_id.id if plan.supervisor_id else None,
                    'secondary_id': plan.secondary_supervisor_id.id if plan.secondary_supervisor_id else None,
                    'reviewer_id': plan.reviewer_id.id if plan.reviewer_id else None,
                    'final_score': plan.final_appraisal_score if plan.state == 'appraisal_approved' else None,
                    'rating': self._get_employee_rating(
                        plan.final_appraisal_score) if plan.state == 'appraisal_approved' and plan.final_appraisal_score is not None else '',
                    'total_weightage': (
                            plan.template_id.score_allocation_id.kpi_weight +
                            plan.template_id.score_allocation_id.competency_weight
                    ) if plan.template_id and plan.template_id.score_allocation_id else 100.0,
                    'submitted_date': submitted_date,
                    'days_stuck': days_stuck,
                    'user_role': user_role,

                }

                planning_data.append(row)

                if 'appraisal' in plan.state:
                    appraisal_data.append(row)
            # ============================================================
            # CYCLE-SPECIFIC SCORE DATA
            # ============================================================
            plans_submitted = len([p for p in appraisals if p.state != 'draft'])
            plans_approved = len([p for p in appraisals if p.state == 'approved'])

            return {
                'planning_data': planning_data,
                'appraisal_data': appraisal_data,
                'plans_submitted': plans_submitted,
                'plans_approved': plans_approved,

                # ── Cycle date/duration info ──────────────────────────────
                'cycle_info': {
                    'id': cycle.id,
                    'name': cycle.name,
                    'state': cycle.state,
                    'type': cycle.cycle_type,

                    # Planning
                    'planning_start_date': str(cycle.start_date) if cycle.start_date else '-',
                    'planning_end_date': str(cycle.planning_deadline) if cycle.planning_deadline else '-',
                    'planning_duration': cycle.planning_duration,
                    'planning_days_left': (
                            cycle.planning_deadline - today).days if cycle.planning_deadline and cycle.state == 'planning' else None,

                    # Appraisal
                    'appraisal_start_date': str(cycle.appraisal_start_date) if cycle.appraisal_start_date else '-',
                    'appraisal_end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else None,
                    'appraisal_duration_days': (
                            cycle.end_date - cycle.appraisal_start_date).days if cycle.end_date and cycle.appraisal_start_date else None,
                    'appraisal_days_left': (
                                cycle.appraisal_end_date - today).days if cycle.appraisal_end_date and cycle.state in [
                        'monitoring', 'appraisal'] else None,
                },
            }

        except Exception as e:
            _logger.error("ERROR in get_cycle_data: %s\n%s", str(e), traceback.format_exc())
            return {
                'error': str(e),
                'traceback': traceback.format_exc(),
                'planning_data': [],
                'appraisal_data': [],

            }

    @http.route('/hr_pms_dashboard/get_plan_kra_details', type='json', auth='user')
    def get_plan_kra_details(self, plan_id):
        try:
            Appraisal = request.env['pms.appraisal'].sudo()
            plan = Appraisal.browse(int(plan_id))

            kra_lines = []
            for kra in plan.kra_ids:
                for kpi in kra.kpi_ids:
                    kra_lines.append({
                        'kra': kra.name,
                        'kpi': kpi.name,
                        'description': kpi.description or '',
                        'criteria': kpi.criteria or '',
                        'score': kpi.weightage if kpi.is_selected else 0,
                        'target': kpi.target or '',
                        'is_selected': bool(kpi.is_selected),
                    })

            company_name = plan.employee_id.company_id.name or 'My Company'

            return {
                'kra_lines': kra_lines,
                'company_name': company_name
            }

        except Exception as e:
            _logger.error("ERROR in get_plan_kra_details: %s\n%s", str(e), traceback.format_exc())
            return {'kra_lines': [], 'company_name': 'My Company', 'error': str(e)}
    # ------------------------------------------------------------------
    # SCORE ENGINE
    # ------------------------------------------------------------------
    def _get_score_engine(self):
        """Get active score engine and its lines."""
        try:
            ScoringEngine = request.env['pms.scoring.engine'].sudo()
            engine = ScoringEngine.search([('active', '=', True)], limit=1)
            if not engine:
                return None

            completed = request.env['pms.appraisal'].sudo().search([('state', '=', 'appraisal_approved')])
            lines = []
            for line in engine.line_ids.sorted('min_score', reverse=True):
                count = len(completed.filtered(
                    lambda a: line.min_score <= a.final_appraisal_score <= line.max_score
                ))
                lines.append({
                    'rating': line.rating,
                    'range_display': f'{line.min_score} – {line.max_score}',
                    'employee_count': count,
                })

            return {'engine_name': engine.name, 'lines': lines}
        except Exception:
            return None

    def _get_manager_stats(self, employee):
        Appraisal = request.env['pms.appraisal'].sudo()
        Cycle = request.env['pms.cycle'].sudo()
        Employee = request.env['hr.employee'].sudo()

        all_cycles = Cycle.search([('state', '!=', 'cancelled')])
        active_cycles = Cycle.search([('state', 'in', ['planning', 'monitoring', 'appraisal'])])
        all_employees = Employee.search([('active', '=', True)])

        # Employees in active cycles
        employees_in_active_cycles_ids = set()
        for cycle in active_cycles:
            cycle_appraisals = Appraisal.search([('cycle_id', '=', cycle.id)])
            employees_in_active_cycles_ids.update(cycle_appraisals.mapped('employee_id').ids)

        probation_active = len([c for c in active_cycles if c.cycle_type == 'probation'])

        return {
            'total_cycles_count': len(all_cycles),
            'probation_active_cycles_count': probation_active,
            'total_active_employees': len(all_employees),
            'total_employees': len(all_employees),
            'active_cycles_count': len(active_cycles),
            'employees_in_active_cycles': len(employees_in_active_cycles_ids),
        }

        # ------------------------------------------------------------------
        # SUPERVISOR SECTION
        # ------------------------------------------------------------------
    def _get_supervisor_section(self, employee):
            """Get enhanced supervisor data with cycle details for manager dashboard"""
            Appraisal = request.env['pms.appraisal'].sudo()
            Cycle = request.env['pms.cycle'].sudo()
            today = date.today()

            active_cycles = Cycle.search([('state', 'in', ['planning', 'monitoring', 'appraisal'])])

            supervisor_cycles = []

            for cycle in active_cycles:
                team_appraisals = Appraisal.search([
                    ('cycle_id', '=', cycle.id),
                    ('employee_id', '!=', employee.id),
                    '|',
                    ('supervisor_id', '=', employee.id),
                    ('secondary_supervisor_id', '=', employee.id)
                ])

                seen = set()
                unique_appraisals = []
                for a in team_appraisals:
                    if a.employee_id.id not in seen:
                        seen.add(a.employee_id.id)
                        unique_appraisals.append(a)
                team_appraisals = request.env['pms.appraisal'].sudo().browse(
                    [a.id for a in unique_appraisals]
                )

                total_team = len(team_appraisals)

                if not team_appraisals:
                    continue

                total_team = len(team_appraisals)

                # ── Planning phase stats ──────────────────────────────────────────
                planning_pending = len(team_appraisals.filtered(
                    lambda a: a.state in ['draft', 'pending_supervisor',
                                          'pending_secondary_supervisor', 'pending_reviewer']
                ))
                planning_approved = len(team_appraisals.filtered(lambda a: a.state == 'approved'))
                planning_submitted = len(team_appraisals.filtered(lambda a: a.state != 'draft'))

                employees_without_plan = []
                for appraisal in team_appraisals.filtered(lambda a: a.state == 'draft'):
                    employees_without_plan.append({
                        'id': appraisal.employee_id.id,
                        'name': appraisal.employee_id.name,
                        'department': appraisal.employee_id.department_id.name or '-',
                    })

                # ── BUILD pending_plan_list (what the template actually renders) ──
                pending_plan_list = []
                for appraisal in team_appraisals:
                    is_primary = appraisal.supervisor_id.id == employee.id
                    is_secondary = appraisal.secondary_supervisor_id.id == employee.id

                    needs_my_plan_action = (
                            (is_primary and appraisal.state == 'pending_supervisor') or
                            (is_secondary and appraisal.state == 'pending_secondary_supervisor')
                    )
                    if needs_my_plan_action:
                        pending_plan_list.append({
                            'id': appraisal.id,
                            'employee_id': appraisal.employee_id.id,
                            'name': appraisal.employee_id.name,
                            'department': appraisal.employee_id.department_id.name or '-',
                            'plan_id': appraisal.id,
                            'state_key': appraisal.state,
                        })

                # ── Team plans (full list) ────────────────────────────────────────
                team_plans = []
                for appraisal in team_appraisals:
                    has_secondary = bool(appraisal.secondary_supervisor_id)
                    has_reviewer = bool(appraisal.reviewer_id)
                    total_steps = 2 + (1 if has_secondary else 0) + (1 if has_reviewer else 0)

                    state_step_map = {
                        'draft': 0,
                        'pending_supervisor': 1,
                        'pending_secondary_supervisor': 2 if has_secondary else 1,
                        'pending_reviewer': 3 if has_secondary else 2,
                        'approved': total_steps,
                    }
                    step = state_step_map.get(appraisal.state, 0)
                    progress = round((step / total_steps) * 100, 1) if total_steps else 0

                    user_role = 'primary' if appraisal.supervisor_id.id == employee.id else 'secondary'

                    team_plans.append({
                        'id': appraisal.id,
                        'plan_id': appraisal.id,
                        'employee_id': appraisal.employee_id.id,
                        'name': appraisal.employee_id.name,
                        'department': appraisal.employee_id.department_id.name or '-',
                        'selected_kpi': appraisal.selected_kpi_count or 0,
                        'total_kpi': appraisal.total_kpi_count or 0,
                        'state': dict(Appraisal._fields['state'].selection).get(
                            appraisal.state, appraisal.state),
                        'state_key': appraisal.state,
                        'progress': progress,
                        'submitted_date': str(appraisal.submitted_date) if appraisal.submitted_date else None,
                        'supervisor_name': appraisal.supervisor_id.name if appraisal.supervisor_id else '',
                        'secondary_name': appraisal.secondary_supervisor_id.name if appraisal.secondary_supervisor_id else '',
                        'reviewer_name': appraisal.reviewer_id.name if appraisal.reviewer_id else '',
                        'user_role': user_role,

                    })

                # ── Appraisal phase stats ─────────────────────────────────────────
                appraisal_pending = len(team_appraisals.filtered(
                    lambda a: a.state in ['appraisal_draft', 'appraisal_pending_supervisor',
                                          'appraisal_pending_secondary_supervisor', 'appraisal_pending_reviewer']
                ))
                appraisal_completed = len(team_appraisals.filtered(lambda a: a.state == 'appraisal_approved'))

                employees_without_appraisal = []
                for appraisal in team_appraisals.filtered(lambda a: a.state == 'appraisal_draft'):
                    employees_without_appraisal.append({
                        'id': appraisal.employee_id.id,
                        'name': appraisal.employee_id.name,
                        'department': appraisal.employee_id.department_id.name or '-',
                    })

                # ── BUILD appraisal pending lists (role-aware) ────────────────────
                pending_appraisal_reviewer_list = []
                pending_appraisal_supervisor_list = []
                pending_appraisal_secondary_list = []

                team_appraisals_data = []  # FIX: moved outside the per-appraisal role checks

                for appraisal in team_appraisals:
                    is_primary = appraisal.supervisor_id.id == employee.id
                    is_secondary = appraisal.secondary_supervisor_id.id == employee.id
                    is_reviewer = appraisal.reviewer_id.id == employee.id

                    # -- Populate per-role pending buckets --
                    if is_primary and appraisal.state == 'appraisal_pending_supervisor':
                        pending_appraisal_supervisor_list.append({
                            'employee_id': appraisal.employee_id.id,
                            'name': appraisal.employee_id.name,
                            'department': appraisal.employee_id.department_id.name or '-',
                            'self_score': appraisal.total_self_score if appraisal.total_self_score is not None else None,
                            'appraisal_id': appraisal.id,
                            'state_key': appraisal.state,
                        })

                    if is_secondary and appraisal.state == 'appraisal_pending_secondary_supervisor':
                        pending_appraisal_secondary_list.append({
                            'employee_id': appraisal.employee_id.id,
                            'name': appraisal.employee_id.name,
                            'department': appraisal.employee_id.department_id.name or '-',
                            'self_score': appraisal.total_self_score if appraisal.total_self_score is not None else None,
                            'appraisal_id': appraisal.id,
                            'state_key': appraisal.state,
                        })


                    if is_reviewer and appraisal.state == 'appraisal_pending_reviewer':
                        pending_appraisal_reviewer_list.append({
                            'employee_id': appraisal.employee_id.id,
                            'name': appraisal.employee_id.name,
                            'department': appraisal.employee_id.department_id.name or '-',
                            'self_score': appraisal.total_self_score if appraisal.total_self_score is not None else None,
                            'appraisal_id': appraisal.id,
                            'state_key': appraisal.state,
                        })


                    appraisal_state = appraisal.state
                    has_secondary = bool(appraisal.secondary_supervisor_id)
                    has_reviewer = bool(appraisal.reviewer_id)
                    total_steps = 2 + (1 if has_secondary else 0) + (1 if has_reviewer else 0)

                    state_step_map = {
                        'appraisal_draft': 0,
                        'appraisal_pending_supervisor': 1,
                        'appraisal_pending_secondary_supervisor': 2 if has_secondary else 1,
                        'appraisal_pending_reviewer': 3 if has_secondary else 2,
                        'appraisal_approved': total_steps,
                    }
                    step = state_step_map.get(appraisal.state, 0)
                    progress = round((step / total_steps) * 100, 1) if total_steps else 0

                    # ── Stage-aware score flags ──────────────────────────────────
                    self_given = appraisal_state not in ['appraisal_draft']
                    supervisor_given = appraisal_state in [
                        'appraisal_pending_secondary_supervisor',
                        'appraisal_pending_reviewer',
                        'appraisal_approved',
                    ]
                    secondary_given = has_secondary and appraisal_state in [
                        'appraisal_pending_reviewer',
                        'appraisal_approved',
                    ]
                    reviewer_given = has_reviewer and appraisal_state == 'appraisal_approved'

                    rating = self._get_employee_rating(
                        appraisal.final_appraisal_score) if appraisal_state == 'appraisal_approved' and appraisal.final_appraisal_score is not None else ''

                    team_appraisals_data.append({
                        'employee_id': appraisal.employee_id.id,
                        'name': appraisal.employee_id.name,
                        'department': appraisal.employee_id.department_id.name or '-',
                        'rating': rating,
                        'state': dict(Appraisal._fields['state'].selection).get(
                            appraisal.state, appraisal.state),
                        'state_key': appraisal.state,
                        'progress': progress,
                        'appraisal_id': appraisal.id,
                        'supervisor_name': appraisal.supervisor_id.name if appraisal.supervisor_id else '',
                        'secondary_name': appraisal.secondary_supervisor_id.name if appraisal.secondary_supervisor_id else '',
                        'reviewer_name': appraisal.reviewer_id.name if appraisal.reviewer_id else '',
                        'self_score': appraisal.total_self_score if self_given else None,
                        'supervisor_score': appraisal.total_supervisor_score if supervisor_given else None,
                        'secondary_score': appraisal.total_secondary_score if secondary_given else None,
                        'reviewer_score': appraisal.total_reviewer_score if reviewer_given else None,
                        'final_score': appraisal.final_appraisal_score if appraisal_state == 'appraisal_approved' else None,
                    })

                pending_appraisal_pending_list = (
                        pending_appraisal_supervisor_list + pending_appraisal_secondary_list
                )

                # ── Performance summaries ─────────────────────────────────────────
                completed_appraisals = team_appraisals.filtered(lambda a: a.state == 'appraisal_approved')
                avg_score = 0
                if completed_appraisals:
                    avg_score = round(
                        sum(a.final_appraisal_score or 0 for a in completed_appraisals) / len(completed_appraisals), 1
                    )

                sorted_appraisals = sorted(completed_appraisals,
                                           key=lambda a: a.final_appraisal_score or 0, reverse=True)

                def _perf_entry(a):
                    rating = self._get_employee_rating(
                        appraisal.final_appraisal_score) if appraisal_state == 'appraisal_approved' and appraisal.final_appraisal_score is not None else ''
                    return {
                        'name': a.employee_id.name,
                        'department': a.employee_id.department_id.name or '-',
                        'score': a.final_appraisal_score or 0,
                        'rating': rating,
                    }

                top_performers = [_perf_entry(a) for a in sorted_appraisals[:5]]
                bottom_performers = [_perf_entry(a) for a in sorted_appraisals[-5:]]

                dept_distribution = {}
                for plan in team_plans:
                    dept = plan['department']
                    dept_distribution[dept] = dept_distribution.get(dept, 0) + 1

                supervisor_cycles.append({
                    'id': cycle.id,
                    'name': cycle.name,
                    'state': cycle.state,
                    'start_date': str(cycle.start_date) if cycle.start_date else '-',
                    'end_date': str(cycle.end_date) if cycle.end_date else '-',

                    # ── Planning dates ────────────────────────────────────────
                    'planning_start_date': str(cycle.start_date) if cycle.start_date else '-',
                    'planning_end_date': str(cycle.planning_deadline) if cycle.planning_deadline else '-',
                    'planning_duration': cycle.planning_duration,

                    # ── Appraisal dates ───────────────────────────────────────
                    'appraisal_start_date': str(cycle.appraisal_start_date) if cycle.appraisal_start_date else '-',
                    'appraisal_end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else None,
                    'appraisal_duration_days': (
                            cycle.end_date - cycle.appraisal_start_date
                    ).days if cycle.end_date and cycle.appraisal_start_date else None,

                    'total_pending_plans': len(team_appraisals.filtered(
                        lambda a: a.state in ['draft', 'pending_supervisor',
                                              'pending_secondary_supervisor', 'pending_reviewer']
                    )),
                    'total_pending_appraisals': len(team_appraisals.filtered(
                        lambda a: 'appraisal' in a.state and a.state != 'appraisal_approved'
                    )),

                    # ── Days left (phase-aware) ───────────────────────────────
                    'days_left': (
                        (cycle.planning_deadline - today).days
                        if cycle.planning_deadline and cycle.state in ['planning', 'monitoring']
                        else (cycle.appraisal_end_date - today).days
                        if cycle.appraisal_end_date and cycle.state == 'appraisal'
                        else None
                    ),

                    'total_team_members': total_team,
                    'pending_plan_count': len(pending_plan_list),
                    'approved_plan_count': planning_approved,
                    'submitted_plan_count': planning_submitted,
                    'pending_plan_list': pending_plan_list,
                    'pending_appraisal_count': appraisal_pending,
                    'completed_appraisal_count': appraisal_completed,
                    'avg_score': avg_score,
                    'employees_without_plan': employees_without_plan,
                    'employees_without_plan_count': len(employees_without_plan),
                    'employees_without_appraisal': employees_without_appraisal,
                    'employees_without_appraisal_count': len(employees_without_appraisal),
                    'team_plans': team_plans,
                    'team_appraisals': team_appraisals_data,
                    'top_performers': top_performers,
                    'bottom_performers': bottom_performers,
                    'dept_distribution': dept_distribution,
                    'pending_approval_appraisals': pending_appraisal_pending_list,
                    'pending_appraisal_supervisor_list': pending_appraisal_supervisor_list,
                    'pending_appraisal_secondary_list': pending_appraisal_secondary_list,
                    'pending_appraisal_reviewer_list': pending_appraisal_reviewer_list,
                    'pending_appraisal_supervisor_count': len(pending_appraisal_supervisor_list),
                    'pending_appraisal_secondary_count': len(pending_appraisal_secondary_list),
                    'pending_appraisal_reviewer_count': len(pending_appraisal_reviewer_list),
                    'pending_appraisal_pending_list': pending_appraisal_pending_list,

                })

            return {
                'active_cycles': supervisor_cycles,
                'active_cycles_count': len(supervisor_cycles),
            }

    # ------------------------------------------------------------------
    # SECONDARY SECTION
    # ------------------------------------------------------------------
    def _get_secondary_section(self, employee):
        Appraisal = request.env['pms.appraisal'].sudo()
        Cycle = request.env['pms.cycle'].sudo()  # Add this line

        active_cycles = Cycle.search([('state', 'in', ['planning', 'appraisal'])])
        active_cycle_ids = active_cycles.mapped('id')

        appraisals = Appraisal.search([
            ('secondary_supervisor_id', '=', employee.id),
            ('employee_id', '!=', employee.id),
            ('cycle_id', 'in', active_cycle_ids),
        ])
        pending = appraisals.filtered(
            lambda a: a.state in ['pending_secondary_supervisor', 'appraisal_pending_secondary_supervisor']
        )
        approved = appraisals.filtered(
            lambda a: a.state in ['pending_reviewer', 'approved', 'appraisal_pending_reviewer', 'appraisal_approved']
        )

        sec_list = []
        for appraisal in appraisals:
            state_label = dict(Appraisal._fields['state'].selection).get(appraisal.state, appraisal.state)
            sec_list.append({
                'name': appraisal.employee_id.name,
                'plan': appraisal.name,
                'cycle': appraisal.cycle_id.name,
                'state': state_label,
                'state_key': appraisal.state,
                'department': appraisal.employee_id.department_id.name or '-',
                'appraisal_id': appraisal.id,  # ← ADD
                'self_score': appraisal.total_self_score if appraisal.total_self_score is not None else None,  # ← ADD
                'supervisor_score': appraisal.total_supervisor_score if appraisal.total_supervisor_score is not None else None,

                'secondary_score': appraisal.total_secondary_score if appraisal.total_secondary_score is not None else None,

                'reviewer_score': appraisal.total_reviewer_score if appraisal.total_reviewer_score is not None else None,

                'final_score': appraisal.final_appraisal_score if appraisal.final_appraisal_score is not None else None,

            })

        return {
            'total': len(appraisals),
            'pending': len(pending),
            'approved': len(approved),
            'sec_list': sec_list,
        }

    # ------------------------------------------------------------------
    # EMPLOYEE SECTION
    # ------------------------------------------------------------------
    def _get_employee_section(self, employee):
        if not employee:
            return {'appraisals': [], 'appraisal_phase': [], 'has_appraisal_phase': False, 'stats': {}}

        Appraisal = request.env['pms.appraisal'].sudo()
        Cycle = request.env['pms.cycle'].sudo()
        today = date.today()

        active_cycles = Cycle.search([('state', 'in', ['planning', 'monitoring', 'appraisal'])])
        active_cycle_ids = active_cycles.mapped('id')
        my_appraisals = Appraisal.search([
            ('employee_id', '=', employee.id),
            ('cycle_id', 'in', active_cycle_ids),
        ])

        planning_states = ['draft', 'pending_supervisor', 'pending_secondary_supervisor', 'pending_reviewer',
                           'approved']
        appraisal_states = [
            'appraisal_draft', 'appraisal_pending_supervisor', 'appraisal_pending_secondary_supervisor',
            'appraisal_pending_reviewer', 'appraisal_approved',
        ]

        def get_stage_color(state):
            colors = {
                'draft': 'badge-light border',
                'pending_supervisor': 'badge-soft-primary',
                'pending_secondary_supervisor': 'badge-soft-warning',
                'pending_reviewer': 'badge-soft-info',
                'approved': 'badge-soft-success',
                'appraisal_draft': 'badge-light border',
                'appraisal_pending_supervisor': 'badge-soft-primary',
                'appraisal_pending_secondary_supervisor': 'badge-soft-warning',
                'appraisal_pending_reviewer': 'badge-soft-info',
                'appraisal_approved': 'badge-soft-success',
            }
            return colors.get(state, 'badge-light border')

        def get_stage_progress(appraisal):
            state = appraisal.state
            has_secondary = bool(appraisal.secondary_supervisor_id)
            has_reviewer = bool(appraisal.reviewer_id)
            total_steps = 2
            if has_secondary:
                total_steps += 1
            if has_reviewer:
                total_steps += 1
            step_map = {
                'draft': 0, 'appraisal_draft': 0,
                'pending_supervisor': 1, 'appraisal_pending_supervisor': 1,
                'pending_secondary_supervisor': 2 if has_secondary else 1,
                'appraisal_pending_secondary_supervisor': 2 if has_secondary else 1,
                'pending_reviewer': 3 if has_secondary else 2,
                'appraisal_pending_reviewer': 3 if has_secondary else 2,
                'approved': total_steps, 'appraisal_approved': total_steps,
            }
            step = step_map.get(state, 0)
            return round((step / total_steps) * 100, 1) if total_steps else 0.0

        def build_kpis(appraisal):
            kpis = []
            appraisal_kpis = request.env['pms.appraisal.kpi'].sudo().search([
                ('appraisal_id', '=', appraisal.id)
            ])
            for kpi in appraisal_kpis:

                status = 'set' if (kpi.is_selected and kpi.target) else 'pending'

                kpis.append({
                    'id': kpi.id,
                    'kra_name': kpi.kra_id.name,
                    'kra_weightage': kpi.kra_id.total_weightage,
                    'kpi_name': kpi.name,
                    'target': kpi.target or '',
                    'weightage': kpi.weightage,
                    'is_selected': bool(kpi.is_selected),
                    'status': 'set' if (kpi.is_selected and kpi.target) else 'pending',
                })

            return kpis

        def build_list(appraisals):
            result = []
            for a in appraisals:
                state_label = dict(Appraisal._fields['state'].selection).get(a.state, a.state)
                kpis_built = build_kpis(a)

                result.append({
                    'name': a.name,
                    'cycle': a.cycle_id.name,
                    'cycle_state': a.cycle_id.state,
                    'state': state_label,
                    'state_key': a.state,
                    'progress': get_stage_progress(a),
                    'progress_color': get_stage_color(a.state),
                    'has_secondary': bool(a.secondary_supervisor_id),
                    'has_reviewer': bool(a.reviewer_id),
                    'kra_count': a.kra_count,
                    'selected_kpi': len([k for k in kpis_built if k['is_selected']]),
                    'total_kpi': len(kpis_built),
                    'self_score': a.total_self_score if a.total_self_score is not None else None,
                    'supervisor_score': a.total_supervisor_score if a.total_supervisor_score is not None else None,
                    'secondary_score': a.total_secondary_score if a.total_secondary_score is not None else None,
                    'final_score': a.final_appraisal_score if a.final_appraisal_score is not None else None,
                    'rating': self._get_employee_rating(
                        a.final_appraisal_score) if a.state == 'appraisal_approved' else '',
                    'kpis': kpis_built,
                })
            return result

        planning_appraisals = my_appraisals.filtered(lambda a: a.state in planning_states)
        appraisal_appraisals = my_appraisals.filtered(lambda a: a.state in appraisal_states)

        planning_cycle_name = '-'
        planning_start = '-'
        planning_deadline = '-'
        planning_duration = None
        planning_days_left = None
        if planning_appraisals:
            cycle = planning_appraisals[0].cycle_id
            planning_cycle_name = cycle.name
            planning_start = str(cycle.start_date) if cycle.start_date else '-'
            planning_duration = cycle.planning_duration
            if cycle.planning_deadline:
                planning_deadline = str(cycle.planning_deadline)
                planning_days_left = (cycle.planning_deadline - today).days

        appraisal_cycle_name = '-'
        appraisal_start = '-'
        appraisal_end = '-'
        appraisal_days_left = None
        appraisal_duration_days = None
        if appraisal_appraisals:
            cycle = appraisal_appraisals[0].cycle_id
            appraisal_cycle_name = cycle.name
            appraisal_start = str(cycle.appraisal_start_date) if cycle.appraisal_start_date else '-'
            if cycle.end_date:
                appraisal_end = str(cycle.end_date)
                appraisal_days_left = (cycle.appraisal_end_date - today).days

            if cycle.end_date and cycle.appraisal_start_date:  # ← ADD
                appraisal_duration_days = (cycle.end_date - cycle.appraisal_start_date).days


        latest = my_appraisals[:1]
        latest_state = dict(Appraisal._fields['state'].selection).get(latest.state, '') if latest else ''
        latest_color = get_stage_color(latest.state) if latest else 'bg-secondary'

        return {
            'appraisals': build_list(planning_appraisals),
            'appraisal_phase': build_list(appraisal_appraisals),
            'has_appraisal_phase': len(appraisal_appraisals) > 0,
            'stats': {
                'total_appraisals': len(my_appraisals),
                'in_planning': len(planning_appraisals),
                'in_appraisal': len(appraisal_appraisals),
                'latest_state': latest_state,
                'latest_color': latest_color,
                'completed': len(my_appraisals.filtered(lambda a: a.state == 'appraisal_approved')),
                'planning_cycle_name': planning_cycle_name,
                'planning_start': planning_start,
                'planning_deadline': planning_deadline,
                'planning_days_left': planning_days_left,
                'appraisal_cycle_name': appraisal_cycle_name,
                'appraisal_start': appraisal_start,
                'appraisal_end': appraisal_end,
                'appraisal_days_left': appraisal_days_left,
                'planning_duration': planning_duration,
                'appraisal_duration_days': appraisal_duration_days,
            },
        }

    def _get_employee_rating(self, score):
        """Get rating label for a given score from rating definition."""
        try:
            RatingDefinition = request.env['pms.rating.definition'].sudo()
            rating_obj = RatingDefinition.get_rating(score)
            return rating_obj.name if rating_obj else ''
        except Exception:
            return ''

    # ------------------------------------------------------------------
    # ENHANCED REVIEWER SECTION WITH CYCLE DATA
    # ------------------------------------------------------------------
    def _get_reviewer_section(self, employee):
        """Get enhanced reviewer data with cycle details"""
        Appraisal = request.env['pms.appraisal'].sudo()
        Cycle = request.env['pms.cycle'].sudo()
        today = date.today()

        active_cycles = Cycle.search([('state', 'in', ['planning', 'monitoring', 'appraisal'])])

        reviewer_cycles = []

        for cycle in active_cycles:
            all_reviewer_appraisals = Appraisal.search([
                ('cycle_id', '=', cycle.id),
                ('reviewer_id', '=', employee.id)
            ])

            if not all_reviewer_appraisals:
                continue

            # Pending plans for reviewer
            pending_plans = all_reviewer_appraisals.filtered(lambda a: a.state == 'pending_reviewer')

            # Pending appraisals for reviewer
            pending_appraisals = all_reviewer_appraisals.filtered(lambda a: a.state == 'appraisal_pending_reviewer')

            total_employees = len(all_reviewer_appraisals)

            # Employees without plan
            employees_without_plan = []
            for appraisal in all_reviewer_appraisals.filtered(lambda a: a.state == 'draft'):
                employees_without_plan.append({
                    'id': appraisal.employee_id.id,
                    'name': appraisal.employee_id.name,
                    'department': appraisal.employee_id.department_id.name or '-',
                })

            # All plans data
            all_plans = []
            for appraisal in all_reviewer_appraisals:
                if 'appraisal' not in appraisal.state:
                    all_plans.append({
                        'employee_id': appraisal.employee_id.id,
                        'name': appraisal.employee_id.name,
                        'department': appraisal.employee_id.department_id.name or '-',
                        'selected_kpi': appraisal.selected_kpi_count or 0,
                        'total_kpi': appraisal.total_kpi_count or 0,
                        'state': dict(Appraisal._fields['state'].selection).get(appraisal.state, appraisal.state),
                        'state_key': appraisal.state,
                        'submitted_date': str(appraisal.submitted_date) if appraisal.submitted_date else None,
                        'supervisor_name': appraisal.supervisor_id.name if appraisal.supervisor_id else '-',
                        'secondary_name': appraisal.secondary_supervisor_id.name if appraisal.secondary_supervisor_id else None,
                        'reviewer_name': appraisal.reviewer_id.name if appraisal.reviewer_id else None,
                        'cycle': appraisal.cycle_id.name if appraisal.cycle_id else '-',

                    })

            all_appraisals_data = []
            for appraisal in all_reviewer_appraisals:
                if 'appraisal' in appraisal.state:
                    appraisal_state = appraisal.state
                    has_secondary = bool(appraisal.secondary_supervisor_id)
                    has_reviewer = bool(appraisal.reviewer_id)

                    self_given = appraisal_state not in ['appraisal_draft']
                    supervisor_given = appraisal_state in [
                        'appraisal_pending_secondary_supervisor',
                        'appraisal_pending_reviewer',
                        'appraisal_approved',
                    ]
                    secondary_given = has_secondary and appraisal_state in [
                        'appraisal_pending_reviewer', 'appraisal_approved',
                    ]
                    reviewer_given = has_reviewer and appraisal_state == 'appraisal_approved'

                    rating = self._get_employee_rating(
                        appraisal.final_appraisal_score
                    ) if appraisal_state == 'appraisal_approved' and appraisal.final_appraisal_score is not None else ''

                    all_appraisals_data.append({
                        'appraisal_id': appraisal.id,
                        'employee_id': appraisal.employee_id.id,
                        'name': appraisal.employee_id.name,
                        'department': appraisal.employee_id.department_id.name or '-',
                        'self_score': appraisal.total_self_score if self_given else None,
                        'supervisor_score': appraisal.total_supervisor_score if supervisor_given else None,
                        'secondary_score': appraisal.total_secondary_score if secondary_given else None,
                        'reviewer_score': appraisal.total_reviewer_score if reviewer_given else None,
                        'final_score': appraisal.final_appraisal_score if appraisal_state == 'appraisal_approved' else None,
                        'rating': rating,
                        'state': dict(Appraisal._fields['state'].selection).get(appraisal.state, appraisal.state),
                        'state_key': appraisal_state,

                    })


            # Completed appraisals for score calculation
            completed_appraisals = all_reviewer_appraisals.filtered(lambda a: a.state == 'appraisal_approved')
            avg_score = 0
            if completed_appraisals:
                total_score = sum(a.final_appraisal_score or 0 for a in completed_appraisals)
                avg_score = round(total_score / len(completed_appraisals), 1)

            reviewer_cycles.append({
                'id': cycle.id,
                'name': cycle.name,
                'state': cycle.state,
                'start_date': str(cycle.start_date) if cycle.start_date else '-',
                'end_date': str(cycle.end_date) if cycle.end_date else '-',
                'planning_end_date': str(cycle.planning_deadline) if cycle.planning_deadline else '-',
                'planning_deadline': str(cycle.planning_deadline) if cycle.planning_deadline else '-',
                'planning_duration': cycle.planning_duration,

                'days_left': (
                    (cycle.planning_deadline - today).days
                    if cycle.planning_deadline and cycle.state == 'planning'
                    else (cycle.appraisal_end_date - today).days
                    if cycle.appraisal_end_date and cycle.state == 'appraisal'
                    else None
                ),
                'total_employees': total_employees,
                'pending_plan_count': len(pending_plans),
                'pending_appraisal_count': len(pending_appraisals),
                'completed_appraisal_count': len(completed_appraisals),
                'avg_score': avg_score,
                'employees_without_plan': employees_without_plan,
                'employees_without_plan_count': len(employees_without_plan),
                'appraisal_start_date': str(cycle.appraisal_start_date) if cycle.appraisal_start_date else '-',
                'appraisal_end_date': str(cycle.appraisal_end_date) if cycle.appraisal_end_date else None,
                'appraisal_duration_days': (
                        cycle.end_date - cycle.appraisal_start_date
                ).days if cycle.end_date and cycle.appraisal_start_date else None,
                'pending_plan_list': [{
                    'id': p.id,
                    'plan_id': p.id,
                    'employee_id': p.employee_id.id,
                    'name': p.employee_id.name,
                    'department': p.employee_id.department_id.name or '-',
                    'selected_kpi': p.selected_kpi_count or 0,
                    'total_kpi': p.total_kpi_count or 0,
                    'submitted_date': str(p.submitted_date) if p.submitted_date else None,
                    'supervisor_name': p.supervisor_id.name if p.supervisor_id else '',
                    'secondary_name': p.secondary_supervisor_id.name if p.secondary_supervisor_id else '',
                    'reviewer_name': p.reviewer_id.name if p.reviewer_id else '',
                    'state_key': p.state,

                } for p in pending_plans],
                'pending_appraisal_list': [{
                    'id': a.id,
                    'appraisal_id': a.id,
                    'employee_id': a.employee_id.id,
                    'name': a.employee_id.name,
                    'department': a.employee_id.department_id.name or '-',
                    'self_score': a.total_self_score if a.total_self_score is not None else None,
                    'supervisor_score': a.total_supervisor_score if a.total_supervisor_score is not None else None,
                    'state_key': a.state,
                } for a in pending_appraisals],
                'all_plans': all_plans,
                'all_appraisals': all_appraisals_data,

                'total_pending_plans': len(all_reviewer_appraisals.filtered(
                    lambda a: a.state in ['draft', 'pending_supervisor',
                                          'pending_secondary_supervisor', 'pending_reviewer']
                )),
                'total_pending_appraisals': len(all_reviewer_appraisals.filtered(
                    lambda a: 'appraisal' in a.state and a.state != 'appraisal_approved'
                )),
            })

        return {
            'active_cycles': reviewer_cycles,
            'active_cycles_count': len(reviewer_cycles),
        }


