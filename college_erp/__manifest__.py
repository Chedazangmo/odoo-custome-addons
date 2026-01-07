{
    'name': "college_erp",

    'summary': "Trying out custom modules",

    'description': """
                Hello it's me.. 
            """,
    'author': "Karma Tashi Phuntshok",
    'website': "https://www.google.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Educational',
    'version': '19.0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'security/college_erp_security.xml',
        'security/ir.model.access.csv',
        'views/erp_views.xml',
        'views/erp_menus.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'sequence': 1,
    'installable': True,
    'application': True,
}

