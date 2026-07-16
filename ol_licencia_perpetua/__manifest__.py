{
    'name': 'Perpetual License for Testing',
    'summary': 'Override enterprise subscription for testing purposes',
    'description': """
        This module overrides the enterprise subscription system
        to create a perpetual license for testing environments.
    """,
    'author': 'Extendrix eCommerce Services',
    "maintainer": "Cristóbal OCH -> Email: olanoit@gmail.com",
    'website': "https://extendrix.com/",
    "category": "Hidden",
    'version': '0.20260716',
    'depends': ['web_enterprise'],
    'assets': {
        'web.assets_backend': [
            # Reemplazar el archivo original
            ('replace', 'web_enterprise/static/src/webclient/home_menu/enterprise_subscription_service.js', 'ol_licencia_perpetua/static/src/js/subscription_manager.js'),
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
