# -*- coding: utf-8 -*-
{
    'name': 'University Results',
    'version': '18.0.1.0.0',
    'category': 'University',
    'summary': 'Manage Student End-of-Year Results and Academic Status',
    'description': """
        University Results Management
        =============================
        Extracting Academic Status and Results into a dedicated application.
    """,
    'author': 'University Development Team',
    'depends': [
        'university_core',
        'university_student',
        'university_curriculum',
        'university_registrar',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/menu_views.xml',
        'views/academic_status_views.xml',
        'views/student_exam_score_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
