from odoo import _, api, fields, models
from odoo.exceptions import UserError

#: Acciones del asistente: (clave, etiqueta, libros en que existe).
WIZARD_ACTIONS = [
    ('fiscal_rcf', 'Reintegro del crédito fiscal', ('rce',)),
    ('fiscal_cfe', 'Crédito fiscal especial', ('rce',)),
    ('fiscal_prorrata', 'Coeficiente de prorrata', ('rce',)),
    ('delete_replacement', 'Eliminar el reemplazo de la propuesta', ('rvie',)),
    ('delete_registered', 'Eliminar el preliminar registrado', ('rvie', 'rce')),
    ('delete_registered_nd', 'Eliminar solo los no domiciliados del preliminar', ('rce',)),
    ('adjust_previous', 'Ajustes de periodos anteriores al SIRE', ('rvie', 'rce')),
]
FISCAL_FIELDS = {'fiscal_rcf': 'valorRCF', 'fiscal_cfe': 'valorCFE',
                 'fiscal_prorrata': 'factProrrata'}


class L10nPeSireActionWizard(models.TransientModel):
    """Acciones del SIRE que piden un dato o una confirmación explícita."""
    _name = 'l10n_pe.sire.action.wizard'
    _description = 'Acción SIRE'

    res_model = fields.Char(required=True, readonly=True)
    res_id = fields.Many2oneReference(model_field='res_model', required=True, readonly=True)
    book_type = fields.Char(compute='_compute_book_type')
    action = fields.Selection(
        selection='_selection_action', string='Acción', required=True)
    company_id = fields.Many2one('res.company', compute='_compute_company_id')
    value = fields.Float(string='Importe o coeficiente', digits=(16, 4))
    move_ids = fields.Many2many(
        'account.move', string='Comprobantes a ajustar',
        help='Comprobantes de periodos llevados en el PLE o el portal, antes del SIRE.')
    adjust_state = fields.Selection(
        selection=[('8', '8 - No se anotó en su periodo'), ('9', '9 - Se anotó y se corrige')],
        string='Estado del ajuste', default='9')
    confirm = fields.Boolean(
        string='Entiendo que la eliminación se hace en SUNAT y no se puede deshacer')

    @api.model
    def _selection_action(self):
        """Solo las acciones del libro desde el que se abre el asistente
        (antes el RVIE ofrecía las del RCE y fallaban al aplicar). Sin libro
        en el contexto (validación del valor guardado), todas."""
        res_model = self.env.context.get('default_res_model')
        if res_model:
            book = 'rce' if res_model == 'l10n_pe.sire.rce' else 'rvie'
            return [(key, label) for key, label, books in WIZARD_ACTIONS if book in books]
        return [(key, label) for key, label, dummy in WIZARD_ACTIONS]

    @api.depends('res_model', 'res_id')
    def _compute_company_id(self):
        for wizard in self:
            wizard.company_id = self.env[wizard.res_model].browse(wizard.res_id).company_id \
                if wizard.res_model and wizard.res_id else False

    @api.depends('res_model')
    def _compute_book_type(self):
        for wizard in self:
            wizard.book_type = 'rce' if wizard.res_model == 'l10n_pe.sire.rce' else 'rvie'

    @api.constrains('action', 'res_model')
    def _check_action_book(self):
        books = {key: book for key, dummy, book in WIZARD_ACTIONS}
        for wizard in self:
            if wizard.book_type not in books.get(wizard.action, ()):
                raise UserError(_('Esta acción no existe para este registro.'))

    def action_apply(self):
        self.ensure_one()
        period = self.env[self.res_model].browse(self.res_id)
        if self.action == 'adjust_previous':
            if not self.move_ids:
                raise UserError(_('Seleccione los comprobantes a ajustar.'))
            types = ('out_invoice', 'out_refund') if self.book_type == 'rvie' \
                else ('in_invoice', 'in_refund')
            # La compañía y sus sucursales: el registro es del RUC.
            moves = self.move_ids.filtered(
                lambda m: m.company_id.root_id == period.company_id.root_id
                and m.move_type in types)
            if not moves:
                raise UserError(_('Ninguno de los comprobantes es de este registro y compañía.'))
            # El RCE solo admite el estado 9 (anexo 13); el RVIE, 8 o 9 (anexo 5).
            if self.book_type == 'rce':
                period._sire_upload_previous_adjustment(moves)
            else:
                period._sire_upload_previous_adjustment(moves, self.adjust_state)
            return {'type': 'ir.actions.act_window_close'}
        if self.action in FISCAL_FIELDS:
            period._sire_send_fiscal_credit(FISCAL_FIELDS[self.action], self.value)
        else:
            if not self.confirm:
                raise UserError(_('Confirme que quiere eliminar la información en SUNAT.'))
            if self.action == 'delete_replacement':
                period.action_sire_delete_replacement()
            elif self.action == 'delete_registered':
                period.action_sire_delete_registered_preliminary()
            elif self.action == 'delete_registered_nd':
                period.action_sire_delete_registered_preliminary(only_non_domiciled=True)
        return {'type': 'ir.actions.act_window_close'}
