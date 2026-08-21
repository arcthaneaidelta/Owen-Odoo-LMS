# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

{
    'name': 'Employee HR Portal',
    'version': '1.0',
    'summary': 'Employee HR Portal',
    'description': """
        Allow employees to see hr payroll related settings in portal and can manage the things.
    """,
    'category': 'Human Resources',
    'author': 'Ayyan - Dev At Eusol',
    'website': 'http://www.eusol.net',
    'depends': ['website', 'om_hr_payroll','portal','hr','hr_attendance','base','hr_holidays','web','mail','hr_contract', 'account', 'project'],
    'data': [
        
        'security/groups_security.xml',
        'security/sequence.xml',
        'security/ir.model.access.csv',
        
        'data/email_templates.xml',
        'data/ir_cron.xml',
        'views/hr_attendance_ext.xml',
        'views/portal/portal_templates.xml',
        'views/portal/payslips_portal.xml',
        'views/portal/attendances_portal.xml',
        'views/portal/absents_portal.xml',
        'views/portal/checkin_checkout.xml',
        'views/res_user_ext.xml',
        'views/portal/contracts_portal.xml',
        'views/portal/leaves_portal.xml',
        'views/portal/advances_requests_portal.xml',
        'views/account_ext.xml',
        'views/portal/loans_requests_portal.xml',
        'views/portal/punch_requests_portal.xml',
        'views/portal/hr_docs_portal.xml',
        # 'views/portal/appraisals_portal.xml',
        'views/portal/expenses_portal.xml',
        'views/portal/employee_calendar.xml',
        'views/portal/overtime_requests_portal.xml',
        
        'views/portal_ext_views.xml',
        'views/advance_requests.xml',
        'views/loan_requests.xml',
        'views/missing_punch.xml',
        'views/hr_attendance_absents.xml',
        'views/overtime_requests.xml',

    ],

    'assets': {
        'web.assets_backend': [
            'employee_hr_portal/static/src/js/calendar-app.js',
        ],
        'web.assets_frontend': [
            'employee_hr_portal/static/src/js/leaves_form.js',
            'employee_hr_portal/static/src/scss/leaves.scss',
        ],
    },


    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
