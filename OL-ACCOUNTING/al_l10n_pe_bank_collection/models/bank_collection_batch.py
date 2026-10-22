import base64

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class L10nPeBankCollectionBatch(models.Model):
    """Archivo de deudores: las cuotas que el banco puede cobrar, con el código
    del depositante y el documento como información de retorno.

    El de **reemplazo** sustituye en el banco todo lo anterior; el de
    **actualización** solo agrega, modifica o elimina cuotas.
    """
    _name = 'l10n_pe.bank.collection.batch'
    _description = 'Archivo de deudores para el banco'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    agreement_id = fields.Many2one('l10n_pe.bank.collection.agreement', string='Convenio', required=True,
                                   check_company=True, tracking=True)
    company_id = fields.Many2one(related='agreement_id.company_id', store=True)
    currency_id = fields.Many2one(related='agreement_id.currency_id')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today, tracking=True)
    partner_ids = fields.Many2many('res.partner', string='Solo estos clientes',
                                   help='Vacío: todos los clientes con cuotas del convenio.')
    mode = fields.Selection([('replace', 'Reemplazo (todas las cuotas)'), ('update', 'Actualización')],
                            string='Tipo', required=True, default='replace')
    line_ids = fields.One2many('l10n_pe.bank.collection.batch.line', 'batch_id', string='Cuotas')
    line_count = fields.Integer(string='Número de cuotas', compute='_compute_totals')
    amount_total = fields.Monetary(string='Total', compute='_compute_totals')
    file = fields.Binary(string='Archivo', readonly=True, attachment=True, copy=False)
    filename = fields.Char(string='Nombre del archivo', readonly=True, copy=False)
    state = fields.Selection([('draft', 'Borrador'), ('generated', 'Generado'), ('sent', 'Enviado al banco')],
                             string='Estado', default='draft', required=True, readonly=True, tracking=True, copy=False)
    warning = fields.Text(string='Avisos', readonly=True, copy=False)

    @api.depends('line_ids.amount')
    def _compute_totals(self):
        for batch in self:
            batch.line_count = len(batch.line_ids)
            batch.amount_total = sum(batch.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n_pe.bank.collection.batch') or '/'
        return super().create(vals_list)

    def action_load(self):
        """Propone las cuotas abiertas del convenio; las de clientes sin código
        quedan fuera con un aviso."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se cargan cuotas en un archivo en borrador.'))
        agreement = self.agreement_id
        commands, missing = [Command.clear()], set()
        for line in agreement._open_lines(self.date):
            partner = line.partner_id.commercial_partner_id
            if self.partner_ids and partner not in self.partner_ids.commercial_partner_id:
                continue
            code = agreement._depositor_code(partner)
            if not code:
                missing.add(partner.name)
                continue
            commands.append(Command.create({
                'move_line_id': line.id,
                'partner_id': partner.id,
                'depositor_code': code,
                'amount': agreement._line_amount(line),
            }))
        self.write({
            'line_ids': commands,
            'warning': _('Clientes sin código del depositante (no se envían): %s', ', '.join(sorted(missing)))
            if missing else False,
        })
        return True

    def _detail_values(self, line):
        agreement = self.agreement_id
        move = line.move_id
        return {
            'account_branch': agreement.account_branch, 'account_number': agreement.account_number,
            'account_full': '%s%s' % (agreement.account_branch or '', agreement.account_number or ''),
            'currency': agreement.currency_id,
            'depositor_code': line.depositor_code,
            'depositor_name': line.partner_id.name,
            'return_info': move.name,
            'issue_date': move.invoice_date or move.date,
            'due_date': line.date_maturity,
            'amount': line.amount,
            'late_amount': 0.0,
            'min_amount': line.amount if agreement.validation == 'full' else 0.0,
            'update_type': 'A',
            'document_number': move.name,
            'depositor_vat': line.partner_id.vat,
        }

    def action_generate(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('El archivo no tiene cuotas.'))
        agreement = self.agreement_id
        layout = agreement.debtors_layout_id
        header = {
            'account_branch': agreement.account_branch, 'account_number': agreement.account_number,
            'account_full': '%s%s' % (agreement.account_branch or '', agreement.account_number or ''),
            'currency': agreement.currency_id, 'company_name': agreement.company_name or self.company_id.name,
            'company_vat': self.company_id.vat, 'file_date': self.date, 'record_count': len(self.line_ids),
            'total_amount': self.amount_total, 'file_mode': 'R' if self.mode == 'replace' else 'A',
            'service_code': agreement.service_code,
        }
        content = layout._build_file(header, [self._detail_values(line) for line in self.line_ids])
        filename = (layout.filename or 'recaudacion_%(date)s.txt') % {
            'date': self.date.strftime('%Y%m%d'), 'currency': layout._currency_code(agreement.currency_id)}
        self.write({'file': base64.b64encode(content), 'filename': filename, 'state': 'generated'})
        self.line_ids.move_line_id.write({'l10n_pe_bank_collection_batch_id': self.id})
        return True

    def action_mark_sent(self):
        self.filtered(lambda b: b.state == 'generated').write({'state': 'sent'})
        return True

    def action_draft(self):
        self.write({'state': 'draft', 'file': False, 'filename': False})
        return True

    def action_download(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'target': 'download',
                'url': '/web/content/%s/%s/file/%s?download=true' % (self._name, self.id, self.filename)}


class L10nPeBankCollectionBatchLine(models.Model):
    _name = 'l10n_pe.bank.collection.batch.line'
    _description = 'Cuota del archivo de deudores'
    _order = 'partner_id, date_maturity, id'

    batch_id = fields.Many2one('l10n_pe.bank.collection.batch', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='batch_id.company_id', store=True)
    currency_id = fields.Many2one(related='batch_id.currency_id')
    move_line_id = fields.Many2one('account.move.line', string='Cuota', required=True, readonly=True)
    move_id = fields.Many2one(related='move_line_id.move_id', string='Documento')
    date_maturity = fields.Date(related='move_line_id.date_maturity', string='Vencimiento')
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, readonly=True)
    depositor_code = fields.Char(string='Código del depositante', required=True)
    amount = fields.Monetary(string='Importe', required=True)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_bank_collection_batch_id = fields.Many2one(
        'l10n_pe.bank.collection.batch', string='Último archivo de deudores', copy=False, readonly=True,
        index='btree_not_null')
