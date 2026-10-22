from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class L10nPeCollectionInterestWizard(models.TransientModel):
    """Liquida los intereses moratorios de las cuotas vencidas y emite, por cada
    factura, una nota de débito en borrador (motivo 01 del catálogo 10,
    inafecta al IGV) para que el usuario la revise y la publique."""
    _name = 'l10n_pe.collection.interest.wizard'
    _description = 'Liquidar intereses moratorios'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    partner_ids = fields.Many2many('res.partner', string='Clientes', required=True,
                                   default=lambda self: self._default_partners())
    date = fields.Date(string='Liquidar hasta', required=True, default=fields.Date.context_today)
    line_ids = fields.One2many('l10n_pe.collection.interest.wizard.line', 'wizard_id', string='Intereses',
                               compute='_compute_line_ids', store=True, readonly=False)
    cap_warning = fields.Char(string='Aviso de tope', compute='_compute_cap_warning')

    @api.depends('line_ids.capped', 'line_ids.uncovered_days')
    def _compute_cap_warning(self):
        for wizard in self:
            messages = []
            if any(wizard.line_ids.mapped('capped')):
                messages.append(_('La tasa pactada supera el interés moratorio máximo del BCRP: las cuotas '
                                  'marcadas se liquidan con el tope; el exceso no es exigible.'))
            if any(wizard.line_ids.mapped('uncovered_days')):
                messages.append(_('Hay días sin tasa máxima del BCRP registrada: se liquidan con la tasa '
                                  'pactada. Revise Cobranza ‣ Configuración ‣ Tasas máximas del BCRP.'))
            wizard.cap_warning = ' '.join(messages) or False

    @api.model
    def _default_partners(self):
        if self.env.context.get('active_model') == 'res.partner':
            return self.env['res.partner'].browse(self.env.context.get('active_ids')).commercial_partner_id
        return self.env['res.partner']

    @api.depends('partner_ids', 'date')
    def _compute_line_ids(self):
        for wizard in self:
            commands = [Command.clear()]
            for partner in wizard.partner_ids.commercial_partner_id:
                for line in partner._l10n_pe_collection_open_lines(wizard.company_id):
                    if line.move_id.move_type != 'out_invoice':
                        continue
                    detail = partner._l10n_pe_collection_interest_detail(line, wizard.date, wizard.company_id)
                    if detail['amount'] > 0:
                        commands.append(Command.create({
                            'move_line_id': line.id, 'days': detail['days'], 'amount': detail['amount'],
                            'capped': detail['capped'], 'uncovered_days': detail['uncovered'],
                            'selected': True}))
            wizard.line_ids = commands

    def action_create(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.selected and l.amount > 0)
        if not lines:
            raise UserError(_('No hay intereses que liquidar.'))
        company = self.company_id
        account = company._l10n_pe_collection_account('l10n_pe_collection_interest_account_id')
        if not account:
            raise UserError(_('Configure la cuenta de ingreso por intereses moratorios en Ajustes.'))
        tax = self.env.ref('account.%s_sale_tax_ina' % company.root_id.id, raise_if_not_found=False)
        notes = self.env['account.move']
        for wiz_line in lines:
            line = wiz_line.move_line_id
            invoice = line.move_id
            vals = {
                'move_type': 'out_invoice',
                'partner_id': invoice.partner_id.id,
                'journal_id': invoice.journal_id.id,
                'currency_id': line.currency_id.id,
                'invoice_date': self.date,
                'debit_origin_id': invoice.id,
                'ref': _('Intereses moratorios de %s', invoice.name),
                'l10n_pe_collection_interest_line_id': line.id,
                'l10n_pe_collection_interest_to': self.date,
                'invoice_line_ids': [Command.create({
                    'name': (_('Intereses moratorios de %(doc)s: %(days)s días al %(rate)s %% TEA, con el tope del BCRP',
                               doc=invoice.name, days=wiz_line.days,
                               rate=invoice.partner_id._l10n_pe_collection_interest_rate_value(company))
                             if wiz_line.capped else
                             _('Intereses moratorios de %(doc)s: %(days)s días al %(rate)s %% TEA',
                               doc=invoice.name, days=wiz_line.days,
                               rate=invoice.partner_id._l10n_pe_collection_interest_rate_value(company))),
                    'account_id': account.id,
                    'quantity': 1,
                    'price_unit': wiz_line.amount,
                    'tax_ids': [Command.set(tax.ids)],
                })],
            }
            if 'l10n_pe_edi_charge_reason' in self.env['account.move']._fields:
                vals['l10n_pe_edi_charge_reason'] = '01'
            note = self.env['account.move'].create(vals)
            note.message_post(body=_('Nota de débito por intereses moratorios de %s, generada desde Cobranza.',
                                     invoice._get_html_link()))
            notes |= note
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_out_invoice_type')
        action.update(domain=[('id', 'in', notes.ids)], context={'create': False})
        if len(notes) == 1:
            action.update(views=[(False, 'form')], res_id=notes.id)
        return action


class L10nPeCollectionInterestWizardLine(models.TransientModel):
    _name = 'l10n_pe.collection.interest.wizard.line'
    _description = 'Interés moratorio de una cuota'

    wizard_id = fields.Many2one('l10n_pe.collection.interest.wizard', required=True, ondelete='cascade')
    selected = fields.Boolean(string='Liquidar', default=True)
    move_line_id = fields.Many2one('account.move.line', string='Cuota', required=True, readonly=True)
    move_id = fields.Many2one(related='move_line_id.move_id', string='Documento')
    partner_id = fields.Many2one(related='move_line_id.partner_id', string='Cliente')
    date_maturity = fields.Date(related='move_line_id.date_maturity', string='Vencimiento')
    currency_id = fields.Many2one(related='move_line_id.currency_id', string='Moneda')
    residual = fields.Monetary(related='move_line_id.amount_residual_currency', string='Saldo')
    days = fields.Integer(string='Días', readonly=True)
    capped = fields.Boolean(string='Con tope BCRP', readonly=True,
                            help='La tasa pactada superaba el moratorio máximo del BCRP: se liquidó con el tope.')
    uncovered_days = fields.Integer(string='Días sin tope registrado', readonly=True)
    amount = fields.Monetary(string='Interés')
