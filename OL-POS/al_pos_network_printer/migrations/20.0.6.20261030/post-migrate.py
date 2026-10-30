from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Odoo 20: la ESC/POS de cada caja pasa a ser una de sus impresoras de
    recibo (pos.printer), que es lo único que el TPV sabe usar."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['pos.config'].with_context(active_test=False).search([])._al_sync_escpos_receipt_printer()
