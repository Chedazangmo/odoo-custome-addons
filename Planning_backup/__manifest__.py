{
    'name': 'Evaluation Planning',
    'version': '1.0',
    'author': 'Your Name',
    'license': 'LGPL-3',
    'depends': ['base', 'hr', 'mail','kpi_form'],
    'data': [
        'security/ir.model.access.csv',
        'views/evaluation_planning_views.xml',
    ],
    'installable': True,
    'application': True,
}