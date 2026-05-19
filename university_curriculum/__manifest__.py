# -*- coding: utf-8 -*-
{
    'name': 'University Curriculum Module',
    'version': '18.0.1.0.0',
    'category': 'Education',
    'summary': 'Curriculum blueprints, subjects, credit hours, timetable, teacher assignment',
    'description': """
        University Curriculum & Batch Blueprint Module
        ===============================================
        
        Features:
        - Curriculum blueprint templates (one per batch - immutable once active)
        - Subject definitions with Arabic/English names
        - Credit hour calculation: lecture_hours + (practical_hours * ratio)
        - Assessment configuration per subject (must sum to 100%)
        - Timetable / schedule management
        - Teacher assignment (by department or program-specific)
        - Blueprint immutability enforcement for historical batches
        - Repeater batch transition wizard
    """,
    'author': 'University Development Team',
    'depends': [
        'university_core',
        'university_student',
        'mail',
        'website',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/curriculum_view.xml',
        'views/subject_view.xml',
        'views/program_view_inherit.xml',
        'views/student_view_inherit.xml',
        'views/timetable_view.xml',
        'views/timetable_report.xml',
        'views/timetable_portal_templates.xml',
        'views/employee_view_inherit.xml',
        'views/university_batch_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
