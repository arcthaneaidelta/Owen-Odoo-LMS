# -*- coding: utf-8 -*-
{
    'name': 'University Student Information Module',
    'version': '18.0.1.0.0',
    'category': 'Education',
    'summary': 'Student profiles, guardians, phone history, RFID cards, portal access',
    'description': """
        University Student Information Module (SIM)
        ===========================================
        Complete student profile management for Sudanese universities.
        
        Features:
        - Full student profiles with Ministry import fields (FRMNO, FAC, UNIV_ID, etc.)
        - Four-part Arabic name (N1, N2, N3, N4) as in Ministry Excel
        - Guardian management with emergency contact enforcement
        - Phone number history (never overwrite policy)
        - RFID card records
        - Academic standing tracking
        - Student portal access
        
        Import compatible with Ministry student data Excel format.
    """,
    'author': 'University Development Team',
    'depends': [
        'university_core',
        'mail',
        'portal',
        'base',
        'account',
        'sale',
    ],
    'data': [
    'security/student_security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/student_view.xml',
        'views/guardian_view.xml',
        'views/phone_history_view.xml',
        'views/rfid_card_view.xml',
        'views/university_batch_views.xml',
        'views/portal_templates.xml',
        'views/re_registration_portal_templates.xml',
        'views/menu_views.xml',
    ],

    'assets': {
        'web.assets_frontend': [
            'university_student/static/src/css/student_portal.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    
}
