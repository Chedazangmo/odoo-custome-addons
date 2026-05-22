{
    'name': "employee_pms",

    'summary': "Functions same as the Employee with an added field for Secondary Manager",

    'description': """
        A custom employee module for Druksmart Performance Management System. Same as the Employee module with an added field for Secondary Manager. 
    """,

    'author': "Druksmart",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Human Resources',
    'version': '19.0.1',

    # any module necessary for this one to work correctly
    'depends': ['hr'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/employee_pms_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'installable': True,
    'application': False,
}

