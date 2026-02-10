from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class TemplateService(models.AbstractModel):
    """Service to safely find templates - NO hard dependencies"""
    _name = 'template.service'
    _description = 'Template Service'

    def get_employee_templates(self, employee):
        """
        SAFELY get templates for employee
        Returns: {'kpi': template or None, 'competency': template or None}
        """
        return {
            'kpi': self._get_template_safely('kpi.template', employee),
            'competency': self._get_template_safely('competency.template', employee),
        }

    def _get_template_safely(self, model_name, employee):
        """Get template without crashing if module missing"""
        try:
            # Check if model exists
            if model_name not in self.env:
                _logger.debug(f"Model {model_name} not available")
                return None

            # Check if employee has evaluation group
            if not employee.evaluation_group_id:
                _logger.warning(f"Employee {employee.name} has no evaluation group")
                return None

            # Find template
            template = self.env[model_name].search([
                ('evaluation_group_id', '=', employee.evaluation_group_id.id),
                ('active', '=', True),
            ], limit=1)

            return template if template else None

        except Exception as e:
            _logger.error(f"Error getting {model_name} for {employee.name}: {str(e)}")
            return None  # Graceful fallback - return None, don't crash