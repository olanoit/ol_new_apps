import base64
import re
import unicodedata

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

def _plain(text):
    """Solo letras y dígitos en mayúsculas: el banco devuelve el documento sin
    los caracteres que no acepta (BBVA cambia «/» por espacio)."""
    text = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^A-Z0-9]', '', text.upper())


LINE_STATES = [
    ('matched', 'Identificado'),
    ('partner', 'Solo cliente'),
    ('unmatched', 'Sin identificar'),
    ('duplicate', 'Ya procesado'),
    ('done', 'Pagado'),
    ('skipped', 'Descartado'),
]


class L10nPeBankCollectionResponse(models.Model):
    """Respuesta del banco: lo cobrado por ventanilla, agentes o banca por
    internet. Cada línea se identifica por el código del depositante (cliente)
    y la información de retorno (documento); al procesar se crea el pago en el
    diario de la cuenta recaudadora y se concilia con las cuotas.

    Una operación ya procesada (fecha, número de operación, depositante e
    importe) no se vuelve a pagar aunque el archivo se importe otra vez.
    """
    _name = 'l10n_pe.bank.collection.response'
    _description = 'Respuesta de recaudación bancaria'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    agreement_id = fields.Many2one('l10n_pe.bank.collection.agreement', string='Convenio', required=True,
                                   check_company=True, tracking=True)
    company_id = fields.Many2one(related='agreement_id.company_id', store=True)
    currency_id = fields.Many2one(related='agreement_id.currency_id')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    file = fields.Binary(string='Archivo del banco', attachment=True, copy=False)
    filename = fields.Char(string='Nombre del archivo')
    line_ids = fields.One2many('l10n_pe.bank.collection.response.line', 'response_id', string='Cobros')
    amount_total = fields.Monetary(string='Total cobrado', compute='_compute_totals')
    amount_done = fields.Monetary(string='Total pagado', compute='_compute_totals')
    pending_count = fields.Integer(string='Por revisar', compute='_compute_totals')
    payment_ids = fields.Many2many('account.payment', string='Pagos', compute='_compute_totals')
    state = fields.Selection([('draft', 'Borrador'), ('imported', 'Importado'), ('done', 'Procesado')],
                             string='Estado', default='draft', required=True, readonly=True, tracking=True, copy=False)
    header_count = fields.Integer(string='Registros según el banco', readonly=True, copy=False)
    header_amount = fields.Monetary(string='Total según el banco', readonly=True, copy=False)

    @api.depends('line_ids.amount', 'line_ids.state', 'line_ids.payment_id')
    def _compute_totals(self):
        for response in self:
            lines = response.line_ids
            response.amount_total = sum(lines.filtered(lambda l: l.state != 'duplicate').mapped('amount'))
            response.amount_done = sum(lines.filtered(lambda l: l.state == 'done').mapped('amount'))
            response.pending_count = len(lines.filtered(lambda l: l.state in ('partner', 'unmatched')))
            response.payment_ids = lines.payment_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n_pe.bank.collection.response') or '/'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Importación
    # ------------------------------------------------------------------

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_('Adjunte el archivo de respuesta del banco.'))
        if self.state == 'done' or self.line_ids.filtered(lambda l: l.state == 'done'):
            raise UserError(_('La respuesta ya tiene pagos creados: importe el archivo en una respuesta nueva.'))
        layout = self.agreement_id.response_layout_id
        header, details = layout._parse_file(base64.b64decode(self.file))
        commands = [Command.clear()]
        for values in details:
            commands.append(Command.create(self._line_values(values)))
        self.write({
            'line_ids': commands, 'state': 'imported',
            'header_count': int(header.get('record_count') or 0),
            'header_amount': header.get('total_amount') or 0.0,
        })
        self.line_ids._match()
        if self.header_count and self.header_count != len(details):
            self.message_post(body=_('El banco informa %(header)s registros y el archivo trae %(lines)s.',
                                     header=self.header_count, lines=len(details)))
        return True

    def _line_values(self, values):
        amount = values.get('paid_total') or values.get('paid_amount') or 0.0
        return {
            'line_number': values.get('_line'),
            'raw': values.get('_raw'),
            'depositor_code': (values.get('depositor_code') or '').strip(),
            'return_info': (values.get('return_info') or '').strip(),
            'payment_date': values.get('payment_date') or self.date,
            'amount': amount,
            'late_amount': values.get('late_amount') or 0.0,
            'operation_number': (values.get('operation_number') or '').strip(),
            'branch': (values.get('branch') or '').strip(),
            'channel': (values.get('channel') or '').strip(),
        }

    def action_rematch(self):
        self.line_ids.filtered(lambda l: l.state in ('partner', 'unmatched', 'matched'))._match()
        return True

    # ------------------------------------------------------------------
    # Pagos
    # ------------------------------------------------------------------

    def action_process(self):
        """Crea y concilia los pagos de las líneas identificadas."""
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.state in ('matched', 'partner') and l.partner_id)
        if not lines:
            raise UserError(_('No hay cobros identificados que procesar.'))
        for line in lines:
            line._create_payment()
        if not self.line_ids.filtered(lambda l: l.state in ('matched', 'partner', 'unmatched')):
            self.state = 'done'
        self.message_post(body=_('%(count)s pagos creados por %(amount)s.', count=len(lines),
                                 amount=self.currency_id.format(sum(lines.mapped('amount')))))
        return True

    def action_open_payments(self):
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_payments')
        action.update(domain=[('id', 'in', self.payment_ids.ids)], context={'create': False})
        return action


class L10nPeBankCollectionResponseLine(models.Model):
    _name = 'l10n_pe.bank.collection.response.line'
    _description = 'Cobro informado por el banco'
    _order = 'response_id, line_number'

    response_id = fields.Many2one('l10n_pe.bank.collection.response', required=True, ondelete='cascade', index=True)
    agreement_id = fields.Many2one(related='response_id.agreement_id', store=True)
    company_id = fields.Many2one(related='response_id.company_id', store=True)
    currency_id = fields.Many2one(related='response_id.currency_id')
    line_number = fields.Integer(string='Línea', readonly=True)
    raw = fields.Char(string='Registro', readonly=True)
    depositor_code = fields.Char(string='Código del depositante', readonly=True)
    return_info = fields.Char(string='Información de retorno', readonly=True)
    payment_date = fields.Date(string='Fecha de pago', readonly=True)
    amount = fields.Monetary(string='Importe', readonly=True)
    late_amount = fields.Monetary(string='Mora', readonly=True)
    operation_number = fields.Char(string='Operación', readonly=True)
    branch = fields.Char(string='Agencia', readonly=True)
    channel = fields.Char(string='Medio', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Cliente',
                                 help='Se identifica por el código; si no, elíjalo y vuelva a identificar.')
    move_line_ids = fields.Many2many('account.move.line', string='Cuotas',
                                     domain="[('partner_id', 'child_of', partner_id), ('reconciled', '=', False),"
                                            " ('account_id.account_type', '=', 'asset_receivable'),"
                                            " ('parent_state', '=', 'posted')]")
    state = fields.Selection(LINE_STATES, string='Estado', default='unmatched', required=True)
    payment_id = fields.Many2one('account.payment', string='Pago', readonly=True, copy=False)
    operation_key = fields.Char(string='Clave de la operación', compute='_compute_operation_key', store=True,
                                index=True)

    @api.depends('response_id.agreement_id', 'payment_date', 'operation_number', 'depositor_code', 'amount')
    def _compute_operation_key(self):
        for line in self:
            line.operation_key = '%s|%s|%s|%s|%.2f' % (
                line.response_id.agreement_id.id, line.payment_date or '', line.operation_number or '',
                line.depositor_code or '', line.amount or 0.0)

    def _match(self):
        """Cliente por el código; cuota por la información de retorno (número
        del documento) o, si no viene, las cuotas abiertas más antiguas."""
        for line in self:
            agreement = line.agreement_id
            done = self.search_count([('operation_key', '=', line.operation_key), ('state', '=', 'done'),
                                      ('id', '!=', line.id)], limit=1)
            if done:
                line.write({'state': 'duplicate'})
                continue
            partner = line.partner_id or agreement._partner_by_code(line.depositor_code)
            if len(partner) != 1:
                line.write({'partner_id': False, 'move_line_ids': [Command.clear()], 'state': 'unmatched'})
                continue
            open_lines = agreement._open_lines(with_disputed=True).filtered(
                lambda l: l.partner_id.commercial_partner_id == partner)
            info = _plain(line.return_info)
            target = open_lines.filtered(lambda l: info and info in {
                _plain(l.move_id.name), _plain(l.move_id.ref), _plain(l.move_id.payment_reference)})
            state = 'matched' if target else 'partner'
            if not target:
                target = open_lines._l10n_pe_bank_collection_fifo(line.amount, agreement)
            line.write({'partner_id': partner.id, 'move_line_ids': [Command.set(target.ids)], 'state': state})

    def _create_payment(self):
        """Pago en el diario del convenio conciliado con las cuotas; sin cuotas
        abiertas, queda como anticipo del cliente."""
        self.ensure_one()
        agreement = self.agreement_id
        memo = (agreement.payment_memo or '') % {
            'bank': agreement.bank_id.name or agreement.journal_id.name, 'operation': self.operation_number or '-'}
        lines = self.move_line_ids.filtered(lambda l: not l.reconciled)
        if lines:
            wizard = self.env['account.payment.register'].with_context(
                active_model='account.move.line', active_ids=lines.ids,
            ).create({
                'journal_id': agreement.journal_id.id,
                'payment_date': self.payment_date,
                'amount': self.amount,
                'currency_id': agreement.currency_id.id,
                'communication': memo,
                'group_payment': True,
                'payment_difference_handling': 'open',
            })
            payment = wizard._create_payments()
        else:
            payment = self.env['account.payment'].create({
                'payment_type': 'inbound', 'partner_type': 'customer', 'partner_id': self.partner_id.id,
                'journal_id': agreement.journal_id.id, 'amount': self.amount, 'date': self.payment_date,
                'currency_id': agreement.currency_id.id, 'memo': memo,
            })
            payment.action_post()
        payment.message_post(body=_('Cobro de recaudación %(response)s, línea %(line)s (operación %(op)s).',
                                    response=self.response_id._get_html_link(), line=self.line_number,
                                    op=self.operation_number or '-'))
        self.write({'payment_id': payment.id, 'state': 'done'})
        return payment

    def action_skip(self):
        self.filtered(lambda l: l.state != 'done').write({'state': 'skipped'})
        return True

    def action_rematch(self):
        self._match()
        return True


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _l10n_pe_bank_collection_fifo(self, amount, agreement):
        """Cuotas más antiguas que cubren ``amount``."""
        selected = self.browse()
        covered = 0.0
        for line in self.sorted(lambda l: (l.date_maturity or l.date, l.id)):
            if agreement.currency_id.compare_amounts(covered, amount) >= 0:
                break
            selected |= line
            covered += agreement._line_amount(line)
        return selected
