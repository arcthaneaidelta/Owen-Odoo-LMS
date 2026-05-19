{
    'name': 'System 18 Recurring Payment',
    'author': 'System Mates',
    'category': 'Accounting',
    'version': '1.0.0',
    'description': """System 18 Recurring Payment, Recurring Payment In System, System 18 Accounting""",
    'summary': 'Use recurring payments to handle periodically repeated payments',
    'sequence': 11,
    'website': 'https://www.odoomates.tech',
    'depends': ['account'],
    'license': 'LGPL-3',
    'data': [
        'data/sequence.xml',
        'data/recurring_cron.xml',
        'security/ir.model.access.csv',
        'views/recurring_template_view.xml',
        'views/recurring_payment_view.xml'
    ],
    'images': ['static/description/banner.png'],
}
