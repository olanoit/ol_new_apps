from odoo import SUPERUSER_ID, api
from odoo.tools import convert_file


def migrate(cr, version):
    """Las plantillas de correo son noupdate: se recargan para agregar «Pagar en
    línea» (aún no se habían personalizado en ninguna base)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for filename in ('data/mail_template_data.xml', 'data/mail_template_bureau_data.xml'):
        convert_file(env, 'al_l10n_pe_collection', filename, {}, mode='init', noupdate=True)
