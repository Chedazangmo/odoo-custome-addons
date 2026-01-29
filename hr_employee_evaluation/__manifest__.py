{
    'name': 'HR Employee Evaluation',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Performance Management System for Employee Evaluation',
    'description': 'Dynamic Performance Management System (PMS)',
    'author': 'Druksmart',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/add_kra_wizard_views.xml',
        'views/appraisal_template_views.xml',
        'views/appraisal_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_employee_evaluation/static/src/components/kra_tabs/kra_tabs.js',
            'hr_employee_evaluation/static/src/components/kra_tabs/kra_tabs.xml',
            'hr_employee_evaluation/static/src/components/kra_tabs/kra_tabs.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}