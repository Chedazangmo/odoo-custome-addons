{
    'name': 'Competency Template',
    'version': '19.0.1.0.0',
    'summary': 'Define HR competency templates, groups, and lines with point allocation.',
    'category': 'Human Resources',
    'author': 'DS',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
            'security/ir.model.access.csv',
            'views/competency_views.xml',
            
    ],
    'assets': {
        'web.assets_backend': [
            'competency_exact/static/src/css/competency_exact.css',
            'competency_exact/static/src/js/competency_exact.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}