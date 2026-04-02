{
    'name': 'PMS 360-Degree Feedback',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Appraisals',
    'summary': 'Dynamic 360-Degree Feedback System for Performance Management',
    'description': """
        360-Degree Feedback Module
        ==========================
        - HR/Admin creates feedback question templates (radio/checkbox)
        - Employees submit feedback for colleagues
        - Employees view feedback received about themselves
        - Role-based access control
    """,
    'author': 'DrukSmart / CST',
    'depends': ['hr', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/feedback_template_views.xml',
        'views/feedback_session_views.xml',
        'views/feedback_response_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pms_360_feedback/static/src/css/feedback.css',
            'pms_360_feedback/static/src/css/dashboard.css',
            'pms_360_feedback/static/src/js/feedback_dashboard.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
