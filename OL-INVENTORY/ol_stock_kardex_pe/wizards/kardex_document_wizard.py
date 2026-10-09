from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.stock_move import split_serie_number

DOC_TYPES = [
    ('01', '01 - Factura'), ('03', '03 - Boleta de venta'), ('04', '04 - Liquidación de compra'),
    ('07', '07 - Nota de crédito'), ('08', '08 - Nota de débito'), ('09', '09 - Guía de remisión remitente'),
    ('12', '12 - Ticket o cinta de máquina registradora'), ('31', '31 - Guía de remisión transportista'),
    ('50', '50 - Declaración Única de Aduanas'), ('00', '00 - Otros'),
]


class L10nPeKardexDocumentWizard(models.TransientModel):
    """Documento del kardex para todos los movimientos de una transferencia."""
    _name = 'l10n_pe.kardex.document.wizard'
    _description = 'Documento del kardex SUNAT'

    picking_id = fields.Many2one('stock.picking', string='Transferencia', required=True)
    doc_type = fields.Selection(DOC_TYPES, string='Tipo de documento', required=True, default='01')
    document = fields.Char(string='Serie y número', required=True,
                           help='Por ejemplo F001-00000123 o T001-456.')
    overwrite_manual = fields.Boolean(string='Reemplazar corregidos a mano',
        help='Reemplazar también los datos corregidos a mano.')

    def action_apply(self):
        self.ensure_one()
        serie, number = split_serie_number(self.document)
        if not number:
            raise UserError(_('Indique un número de documento válido, p. ej. F001-00000123.'))
        moves = self.picking_id.move_ids.filtered(lambda m: m.state == 'done')
        if not self.overwrite_manual:
            moves = moves.filtered(lambda m: not m.l10n_pe_kardex_doc_manual)
        if not moves:
            raise UserError(_('La transferencia no tiene movimientos hechos que cambiar.'))
        moves.write({
            'l10n_pe_kardex_doc_type': self.doc_type,
            'l10n_pe_kardex_serie': serie or False,
            'l10n_pe_kardex_number': number,
            'l10n_pe_kardex_invoice_id': False,
            'l10n_pe_kardex_doc_manual': True,
        })
        return {'type': 'ir.actions.act_window_close'}
