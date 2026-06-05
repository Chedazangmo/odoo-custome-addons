from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


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

    # =========================================================================
    # CID FIELD
    # -------------------------------------------------------------------------
    # =========================================================================

    cid_number = fields.Char(
        string='CID Number',
        required=False,   # view enforces required="1"
        copy=False,
        help='Bhutan Citizen Identity Card Number',
    )

    @api.constrains('cid_number')
    def _validate_cid_number(self):
        for rec in self:
            if rec.cid_number:
                # Uniqueness check only — no length/format constraint for now
                duplicate = self.search([
                    ('cid_number', '=', rec.cid_number),
                    ('id',         '!=', rec.id),
                ], limit=1)
                if duplicate:
                    raise ValidationError(
                        'CID Number must be unique. '
                        'This CID is already assigned to employee: %s'
                        % duplicate.name
                    )

    # =========================================================================
    # EXISTING CONSTRAINTS — unchanged
    # =========================================================================

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

        affected_users = self.env['res.users']
        for emp in self:
            if emp.user_id:                        affected_users |= emp.user_id
            if emp.parent_id.user_id:              affected_users |= emp.parent_id.user_id
            if emp.secondary_manager_id.user_id:   affected_users |= emp.secondary_manager_id.user_id
            if emp.reviewer_id.user_id:            affected_users |= emp.reviewer_id.user_id

        res = super().write(vals)

        for emp in self:
            if emp.user_id:                        affected_users |= emp.user_id
            if emp.parent_id.user_id:              affected_users |= emp.parent_id.user_id
            if emp.secondary_manager_id.user_id:   affected_users |= emp.secondary_manager_id.user_id
            if emp.reviewer_id.user_id:            affected_users |= emp.reviewer_id.user_id

        if affected_users:
            self.sudo()._recalculate_pms_rights(affected_users)

        return res

    # =========================================================================
    # CORE AUTO-ASSIGNMENT LOGIC — unchanged
    # =========================================================================

    @api.model
    def _recalculate_pms_rights(self, users):
        """
        Grants or revokes PMS security groups based on each user's actual role
        in the hr.employee hierarchy.
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
            is_employee = self.search_count([
                ('user_id', '=', user.id),
                ('active',  '=', True),
            ]) > 0

            is_supervisor = self.search_count([
                '|',
                ('parent_id.user_id',          '=', user.id),
                ('secondary_manager_id.user_id','=', user.id),
            ]) > 0

            is_reviewer = self.search_count([
                ('reviewer_id.user_id', '=', user.id),
            ]) > 0

            if is_reviewer:
                user.group_ids = [(4, group_rev.id)]
            else:
                user.group_ids = [(3, group_rev.id)]

            if is_supervisor:
                user.group_ids = [(4, group_sup.id)]
            elif not is_reviewer:
                user.group_ids = [(3, group_sup.id)]

            if is_employee:
                user.group_ids = [(4, group_emp.id)]
            elif not is_supervisor and not is_reviewer:
                user.group_ids = [(3, group_emp.id)]