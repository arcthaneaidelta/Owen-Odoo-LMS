# -*- coding: utf-8 -*-
{
    'name': "HR Salary Rules",

    'summary': "Employee Attendance",

    'description': """
    """,

    'author': "Ali Shan",
    'website': "https://www.yourcompany.com",

    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base','hr_attendance','om_hr_payroll','employee_hr_portal','hr_expense'],

    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/views.xml',
    ],
    'license': 'LGPL-3',
}