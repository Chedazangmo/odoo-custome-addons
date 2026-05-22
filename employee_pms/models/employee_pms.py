from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    secondary_manager_id = fields.Many2one(
        'hr.employee',
        string='Secondary Manager',
        domain="[('id', '!=', id)]",
    )

    reviewer_id = fields.Many2one(
        'hr.employee',
        string='Reviewer',
        domain="[('id', '!=', id)]",
    )

    evaluation_group_id = fields.Many2one(
        'pms.evaluation.group',
        string='Evaluation Group'
    )


    @api.constrains('parent_id')
    def _check_employee_not_own_manager(self):
        for employee in self:
            if employee.parent_id == employee:
                raise ValidationError("An employee cannot be their own manager.")

    @api.constrains('secondary_manager_id', 'parent_id')
    def _check_managers_not_same(self):
        for rec in self:
            if rec.secondary_manager_id and rec.parent_id and \
               rec.secondary_manager_id == rec.parent_id:
                raise ValidationError("Primary and Secondary Manager cannot be the same person.")

    @api.constrains('reviewer_id')
    def _check_employee_not_own_reviewer(self):
        for employee in self:
            if employee.reviewer_id == employee:
                raise ValidationError("An employee cannot be their own reviewer.")

    @api.constrains('secondary_manager_id', 'reviewer_id')
    def _check_secondary_manager_and_reviewer_not_same(self):
        for employee in self:
            if employee.secondary_manager_id and employee.reviewer_id and \
               employee.secondary_manager_id == employee.reviewer_id:
                raise ValidationError("Secondary Manager and Reviewer cannot be the same person.")

    @api.constrains('parent_id', 'reviewer_id')
    def _check_reviewer_not_reporting_to_employee(self):
        for employee in self:
            if employee.reviewer_id and employee.reviewer_id.parent_id == employee:
                raise ValidationError("Reviewer cannot report to the employee.")

    # =========================================================================
    # CREATE / WRITE — trigger auto-assignment
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        affected_users = self.env['res.users']
        for emp in records:
            if emp.user_id:                        affected_users |= emp.user_id
            if emp.parent_id.user_id:              affected_users |= emp.parent_id.user_id
            if emp.secondary_manager_id.user_id:   affected_users |= emp.secondary_manager_id.user_id
            if emp.reviewer_id.user_id:            affected_users |= emp.reviewer_id.user_id

        if affected_users:
            self.sudo()._recalculate_pms_rights(affected_users)

        return records

    def write(self, vals):
        trigger_fields = {'parent_id', 'secondary_manager_id', 'reviewer_id', 'user_id'}

        if not trigger_fields.intersection(vals.keys()):
            return super().write(vals)

        # Collect users BEFORE the change (so we can clean up old roles)
        affected_users = self.env['res.users']
        for emp in self:
            if emp.user_id:                        affected_users |= emp.user_id
            if emp.parent_id.user_id:              affected_users |= emp.parent_id.user_id
            if emp.secondary_manager_id.user_id:   affected_users |= emp.secondary_manager_id.user_id
            if emp.reviewer_id.user_id:            affected_users |= emp.reviewer_id.user_id

        res = super().write(vals)

        # Collect users AFTER the change (so we catch newly assigned people)
        for emp in self:
            if emp.user_id:                        affected_users |= emp.user_id
            if emp.parent_id.user_id:              affected_users |= emp.parent_id.user_id
            if emp.secondary_manager_id.user_id:   affected_users |= emp.secondary_manager_id.user_id
            if emp.reviewer_id.user_id:            affected_users |= emp.reviewer_id.user_id

        if affected_users:
            self.sudo()._recalculate_pms_rights(affected_users)

        return res

    # =========================================================================
    # CORE AUTO-ASSIGNMENT LOGIC
    # =========================================================================

    @api.model
    def _recalculate_pms_rights(self, users):
        """
        Grants or revokes PMS security groups based on each user's actual role
        in the hr.employee hierarchy.

        Group hierarchy (from pms_security.xml implied_ids):
            group_pms_reviewer
                → group_pms_hr_manager
                    → group_pms_supervisor
                        → group_pms_employee

        CRITICAL RULE — never revoke a lower group if a higher group still
        implies it, because Odoo's implied_ids will just re-add it and you get
        inconsistent state.  Instead, only revoke a group when no higher group
        that implies it is still held.

        Revoke ladder:
            Revoke employee   → only safe if user has neither supervisor nor reviewer
            Revoke supervisor → only safe if user is not a reviewer
                                (reviewer implies supervisor via hr_manager)
            Revoke reviewer   → always safe (nothing implies reviewer)

        HR Manager is assigned manually — we never touch it here.
        """
        group_emp = self.env.ref(
            'hr_employee_evaluation.group_pms_employee', raise_if_not_found=False)
        group_sup = self.env.ref(
            'hr_employee_evaluation.group_pms_supervisor', raise_if_not_found=False)
        group_rev = self.env.ref(
            'hr_employee_evaluation.group_pms_reviewer', raise_if_not_found=False)

        if not (group_emp and group_sup and group_rev):
            return

        for user in users:
            # ── Determine roles by scanning the ENTIRE company database ──────

            # Employee: user has an employee record linked to their user account
            is_employee = self.search_count([
                ('user_id', '=', user.id),
                ('active', '=', True),
            ]) > 0

            # Supervisor: user is set as primary OR secondary manager on any employee
            is_supervisor = self.search_count([
                '|',
                ('parent_id.user_id', '=', user.id),
                ('secondary_manager_id.user_id', '=', user.id),
            ]) > 0

            # Reviewer: user is set as reviewer on any employee
            is_reviewer = self.search_count([
                ('reviewer_id.user_id', '=', user.id),
            ]) > 0

            # ── Apply reviewer group (highest — implies everything below) ────
            if is_reviewer:
                user.group_ids = [(4, group_rev.id)]
            else:
                # Safe to revoke: nothing implies reviewer
                user.group_ids = [(3, group_rev.id)]

            # ── Apply supervisor group ────────────────────────────────────────
            if is_supervisor:
                user.group_ids = [(4, group_sup.id)]
            elif not is_reviewer:
                # Only revoke supervisor if the user is NOT a reviewer.
                # If they ARE a reviewer, group_pms_reviewer implies group_pms_supervisor
                # (via hr_manager) so revoking it here would conflict with Odoo's
                # implied_ids chain and cause inconsistent state.
                user.group_ids = [(3, group_sup.id)]
            # else: is_reviewer=True → leave supervisor alone, implied chain handles it

            # ── Apply employee group ──────────────────────────────────────────
            if is_employee:
                user.group_ids = [(4, group_emp.id)]
            elif not is_supervisor and not is_reviewer:
                # Only revoke employee if the user is NEITHER supervisor NOR reviewer.
                # Both of those groups imply group_pms_employee through the chain,
                # so revoking it would conflict with implied_ids.
                user.group_ids = [(3, group_emp.id)]
            # else: higher group implies employee → leave it alone