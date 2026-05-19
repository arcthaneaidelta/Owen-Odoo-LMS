# -*- coding: utf-8 -*-
{
    'name': 'University Core',
    'version': '18.0.1.0.0',
    'category': 'Education',
    'summary': 'University hierarchy: University, College, Program, Specialization, Department, Batch',
    'description': """
        University Core Module
        ======================
        Defines the institutional skeleton for the Sudanese University Management System.
        
        Models:
        - university.university
        - university.college
        - university.program
        - university.specialization
        - university.department
        - university.batch
        - university.academic_year
    """,
    'author': 'University Development Team',
    'depends': ['base', 'mail', 'hr'],
    'data': [
        'security/university_core_security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/department_view.xml',
        'views/program_view.xml',
        'views/college_view.xml',
        'views/university_view.xml',
        'views/specialization_view.xml',
        'views/batch_view.xml',
        'views/academic_year_view.xml',
        'views/room_view.xml',
        'views/employee_view.xml',
        'views/menu_views.xml',
        # 'i18n/ar.po',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
