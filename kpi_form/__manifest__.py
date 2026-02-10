{
    'name': 'Performance Management',
    'version': '1.0',
    'summary': 'KPI Templates with KPA',
    'description': 'Create KPI templates with Key Performance Areas',
    'category': 'Human Resources',
    'depends': ['base','hr_extension'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu_views.xml',
        'views/kpi_template_views.xml',
        'views/competency_template_views.xml',
    ],
    'installable': True,
    'application': True,
}
