from odoo import models, fields, api
from odoo.exceptions import UserError

class PMSAddEmployeeWizard(models.TransientModel):
    _name = 'pms.add.employee.wizard'
    _description = 'Add Employees to Active Cycle'

    cycle_id = fields.Many2one('pms.cycle', string='Cycle', required=True)
    
    employee_ids = fields.Many2many(
        'hr.employee', 
        string='Employees to Add',
        domain="[('active', '=', True), ('evaluation_group_id', '!=', False)]"
    )

    def action_add_employees(self):
        self.ensure_one()
        if not self.employee_ids:
            raise UserError("Please select at least one employee.")
        
        # Check if any selected employee is already in this specific cycle
        existing_appraisals = self.env['pms.appraisal'].search([
            ('cycle_id', '=', self.cycle_id.id),
            ('employee_id', 'in', self.employee_ids.ids)
        ])
        if existing_appraisals:
            names = "\n".join([f"- {a.employee_id.name}" for a in existing_appraisals])
            raise UserError(f"The following employees are already in this cycle:\n{names}")
        
        # Validate rules (Supervisors exist, Templates exist, etc.)
        self.cycle_id._validate_employees(self.employee_ids)
        
        # Create their appraisals and give them a custom planning deadline
        self.cycle_id._create_employee_appraisals(self.employee_ids, is_late=True)
        
        # Append them to the cycle's tracking list so they appear in the UI table
        self.cycle_id.with_context(skip_cycle_edit_check=True).write({
            'employee_ids': [(4, emp.id) for emp in self.employee_ids]
        })        
        return {'type': 'ir.actions.act_window_close'}