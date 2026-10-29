from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nPeStockCostClose(models.Model):
    """Cierre mensual de almacén.

    Al cerrar un mes:

    1. se pone al día el costo por almacén (si la compañía lo usa);
    2. se publica el cierre de valorización de Odoo a fin de mes, que lleva la
       cuenta de existencias al valor del kardex contra la cuenta de variación
       (69 en el PCGE);
    3. se bloquean los movimientos y los cambios de valor con fecha hasta ese
       día (``res.company.l10n_pe_stock_lock_date``).

    Solo se reabre el último cierre: su asiento se anula y el bloqueo vuelve
    al cierre anterior.
    """
    _name = 'l10n_pe.stock.cost.close'
    _description = 'Cierre mensual de almacén'
    _inherit = ['mail.thread']
    _order = 'company_id, date desc'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    date = fields.Date(
        string='Cerrar hasta', required=True, readonly=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1) - relativedelta(days=1),
        help='Último día del periodo que se cierra (normalmente fin de mes).')
    state = fields.Selection(
        [('draft', 'Borrador'), ('closed', 'Cerrado'), ('reopened', 'Reabierto')],
        string='Estado', default='draft', required=True, readonly=True, tracking=True)
    account_move_id = fields.Many2one(
        'account.move', string='Asiento de cierre', readonly=True, copy=False,
        check_company=True,
        help='Cierre de valorización del inventario: ajuste de la cuenta de '
             'existencias al valor del kardex. Vacío si no hubo diferencia.')
    user_id = fields.Many2one('res.users', string='Cerrado por', readonly=True, copy=False)

    _company_date_uniq = models.Constraint(
        'UNIQUE(company_id, date)', 'Ya hay un cierre de almacén para esa fecha.')

    @api.depends('company_id', 'date')
    def _compute_display_name(self):
        for close in self:
            close.display_name = _('Cierre de almacén al %s', fields.Date.to_string(close.date)) if close.date else ''

    def action_close(self):
        for close in self:
            if close.state == 'closed':
                continue
            company = close.company_id
            if company.l10n_pe_stock_lock_date and close.date <= company.l10n_pe_stock_lock_date:
                raise UserError(_(
                    'El almacén ya está cerrado hasta el %s: elija una fecha posterior.',
                    fields.Date.to_string(company.l10n_pe_stock_lock_date)))
            if close.date > fields.Date.context_today(close):
                raise UserError(_('No se puede cerrar un periodo que aún no termina.'))
            company._l10n_pe_wh_cost_refresh()
            account_move = close._l10n_pe_post_valuation_closing()
            # sudo: el bloqueo es de solo lectura en la ficha de la compañía; lo
            # fija este cierre, que solo puede ejecutar el administrador de
            # inventario (permiso del modelo).
            company.sudo().l10n_pe_stock_lock_date = close.date
            close.write({
                'state': 'closed',
                'account_move_id': account_move.id,
                'user_id': self.env.user.id,
            })

    def _l10n_pe_post_valuation_closing(self):
        """Publica el cierre de valorización de Odoo a la fecha del cierre."""
        self.ensure_one()
        company = self.company_id.with_context(allowed_company_ids=self.company_id.ids)
        if not company._action_close_stock_valuation(at_date=self.date):
            return self.env['account.move']
        action = company.action_close_stock_valuation(at_date=self.date, auto_post=True)
        return self.env['account.move'].browse(action and action.get('res_id'))

    def action_reopen(self):
        for close in self:
            if close.state != 'closed':
                continue
            later = self.search([
                ('company_id', '=', close.company_id.id), ('state', '=', 'closed'),
                ('date', '>', close.date)], limit=1)
            if later:
                raise UserError(_('Reabra primero el cierre al %s.', fields.Date.to_string(later.date)))
            if close.account_move_id.state == 'posted':
                close.account_move_id.button_draft()
                close.account_move_id.button_cancel()
            previous = self.search([
                ('company_id', '=', close.company_id.id), ('state', '=', 'closed'),
                ('date', '<', close.date)], limit=1, order='date desc')
            # sudo: ver action_close.
            close.company_id.sudo().l10n_pe_stock_lock_date = previous.date
            close.state = 'reopened'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_closed(self):
        if any(close.state == 'closed' for close in self):
            raise UserError(_('Reabra el cierre de almacén antes de borrarlo.'))
