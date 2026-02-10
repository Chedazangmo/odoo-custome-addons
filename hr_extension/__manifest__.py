{
    'name': 'HR Extensions',
    'version': '1.0',
    'summary': 'Add KPI fields to Employees',
    'description': 'Adds Second Manager and Evaluation Group fields to Employee form',
    'category': 'Human Resources',
    'depends': ['hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}