{
    'name': 'Evaluation Planning',
    'version': '1.0',
    'author': 'Your Name',
    'license': 'LGPL-3',
    'depends': ['base', 'hr', 'mail','kpi_form'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/ir.rule.xml',
        'views/evaluation_planning_views.xml',
        'views/performance_plan_views.xml',
        'views/menus.xml',

    ],
    'installable': True,
    'application': True,
}