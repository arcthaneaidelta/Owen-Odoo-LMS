# -*- coding: utf-8 -*-
# UPDATED __manifest__.py for university_admission
# Add the new files shown below to your existing manifest
{
    'name': 'University Admission Module',
    'version': '18.0.2.0.0',
    'category': 'Education',
    'summary': '10-step admission workflow, Ministry Bank import, auto data exchange on approval',
    'author': 'University Development Team',
    'depends': [
        'university_core',
        'university_student',   # guardian model lives here
        'university_curriculum', # subject model lives here
        'mail',
        'account',
        'website',
    ],
    'data': [
        # ── Security ──────────────────────────────────────────────────────────
        'security/ir.model.access.csv',
        'security/admission_security.xml',


        # ── Data ──────────────────────────────────────────────────────────────
        'data/sequence_data.xml',
        'data/mail_template_data.xml',             # ← NEW
        'data/ir_cron_data.xml',

        # ── Views ─────────────────────────────────────────────────────────────
        'views/admission_portal_templates.xml',    # ← NEW
        'views/verification_templates.xml',
        'views/ministry_bank_views.xml',           # ← NEW  (kanban/list for batches + bank)
        'views/ministry_bank_menu.xml',            # ← NEW  (menu items)
        'views/admission_view.xml',                # UPDATED
        'views/student_view_inherit.xml',
        'views/subject_equivalency_view.xml',
        'views/menu_views.xml',

        # ── Wizards ───────────────────────────────────────────────────────────
        # wizard view is embedded in ministry_bank_views.xml already
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}