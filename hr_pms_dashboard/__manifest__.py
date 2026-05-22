{
    'name': 'PMS Dashboard',
    'version': '19.0.1.0.0',
    'summary': 'Performance Management System Dashboard',
    'description': 'Dashboard for HR Manager, Supervisor, and Employee roles in PMS',
    'category': 'Human Resources',
    'author': 'Custom',
    'depends': ['hr_employee_evaluation', 'web'],
    'data': [
        'views/dashboard_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_pms_dashboard/static/lib/chart.umd.min.js',
'hr_pms_dashboard/static/lib/html2pdf.bundle.min.js',
            'hr_pms_dashboard/static/src/css/dashboard.css',
            'hr_pms_dashboard/static/src/xml/dashboard.xml',
            'hr_pms_dashboard/static/src/js/dashboard.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}