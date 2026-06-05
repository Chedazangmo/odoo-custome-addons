
{
    'name': 'Bhutan NDI Login',
    'version': '19.0.1.0.0',
    'summary': 'Login with Bhutan National Digital Identity via QR Code',
    'category': 'Authentication',
    'license': 'LGPL-3',
    'author': 'DS',
    'depends': ['web', 'base'],
    'data': [
        'views/login_template.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'ndi_login/static/src/css/ndi_login.css',
        ],
    },
    'installable': True,
    'auto_install': False,
}