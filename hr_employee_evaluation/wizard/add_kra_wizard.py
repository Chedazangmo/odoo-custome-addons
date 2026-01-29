from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AddKraWizard(models.TransientModel):
    _name = 'add.kra.wizard'
    _description = 'Add KRA Wizard'

    template_id = fields.Many2one(
        'appraisal.template',
        string='Template',
        required=True,
        readonly=True
    )
    kra_name = fields.Char(
        string='KRA Name',
        required=True,
        help='Name of the Key Result Area'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=1,
        help='Order in which this KRA will appear'
    )

    @api.constrains('kra_name')
    def _check_kra_name(self):
        for wizard in self:
            if wizard.kra_name:
                # Check for duplicate KRA names in the same template
                existing = self.env['appraisal.kra'].search([
                    ('template_id', '=', wizard.template_id.id),
                    ('name', '=ilike', wizard.kra_name.strip())
                ])
                if existing:
                    raise ValidationError(
                        f'A KRA with the name "{wizard.kra_name}" already exists in this template. '
                        'Please use a different name.'
                    )

    def action_add_kra(self):
        """Create the KRA and close the wizard"""
        self.ensure_one()
        
        # Get the highest sequence number for existing KRAs
        existing_kras = self.env['appraisal.kra'].search([
            ('template_id', '=', self.template_id.id)
        ], order='sequence desc', limit=1)
        
        next_sequence = (existing_kras.sequence + 10) if existing_kras else 10
        
        # Create the KRA
        new_kra = self.env['appraisal.kra'].create({
            'name': self.kra_name.strip(),
            'template_id': self.template_id.id,
            'sequence': self.sequence if self.sequence else next_sequence,
        })

        # Return action to reload the form view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'appraisal.template',
            'res_id': self.template_id.id,
            'view_mode': 'form',
            'target': 'current',
        }