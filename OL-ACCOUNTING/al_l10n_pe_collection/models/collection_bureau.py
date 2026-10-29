import io
from datetime import timedelta

import xlsxwriter
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

BUREAUS = [
    ('equifax', 'Equifax (Infocorp)'),
    ('sentinel', 'Sentinel'),
    ('experian', 'Experian'),
    ('xchange', 'Xchange'),
    ('other', 'Otra'),
]
BUREAU_STATES = [
    ('draft', 'Borrador'),
    ('notified', 'Aviso enviado'),
    ('reported', 'Reportado'),
    ('to_withdraw', 'Por retirar'),
    ('withdrawn', 'Retirado'),
    ('cancel', 'Cancelado'),
]
#: Ley 27489 art. 10 d): no se difunden deudas vencidas hace más de 5 años.
MAX_REPORT_YEARS = 5


class L10nPeCollectionBureau(models.Model):
    """Reporte de un deudor a una central de riesgo.

    Flujo: aviso previo al deudor (buena práctica que exige el proyecto de ley en
    trámite y que evita reclamos ante Indecopi) → plazo de espera → reporte →
    retiro. Solo se reportan documentos vencidos, sin reclamo abierto y con
    menos de 5 años de vencidos (Ley 27489). Un cron pasa a «por retirar» los
    reportes cuya deuda se pagó o cumplió 5 años y avisa al gestor: mantener
    reportada una deuda pagada es infracción.
    """
    _name = 'l10n_pe.collection.bureau'
    _description = 'Reporte a central de riesgo'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    partner_id = fields.Many2one(
        'res.partner', string='Deudor', required=True, tracking=True, check_company=True, index=True,
        domain="['|', ('parent_id', '=', False), ('is_company', '=', True)]")
    user_id = fields.Many2one('res.users', string='Gestor', required=True, tracking=True,
                              default=lambda self: self.env.user)
    bureau = fields.Selection(BUREAUS, string='Central de riesgo', required=True, default='equifax', tracking=True)
    line_ids = fields.Many2many(
        'account.move.line', string='Documentos', check_company=True,
        domain="[('partner_id', 'child_of', partner_id), ('reconciled', '=', False),"
               " ('parent_state', '=', 'posted'), ('account_id.account_type', '=', 'asset_receivable'),"
               " ('amount_residual', '>', 0)]")
    amount = fields.Monetary(string='Deuda actual', compute='_compute_amount')
    amount_reported = fields.Monetary(string='Monto reportado', readonly=True, copy=False)
    state = fields.Selection(BUREAU_STATES, string='Estado', default='draft', required=True, readonly=True,
                             tracking=True, copy=False)
    date_notice = fields.Date(string='Aviso enviado el', readonly=True, copy=False)
    date_eligible = fields.Date(string='Reportable desde', compute='_compute_date_eligible', store=True)
    date_reported = fields.Date(string='Reportado el', readonly=True, copy=False, tracking=True)
    date_withdrawn = fields.Date(string='Retirado el', readonly=True, copy=False, tracking=True)
    note = fields.Text(string='Notas')

    @api.depends('line_ids.amount_residual')
    def _compute_amount(self):
        for report in self:
            report.amount = sum(report.line_ids.mapped('amount_residual'))

    @api.depends('date_notice', 'company_id')
    def _compute_date_eligible(self):
        for report in self:
            report.date_eligible = report.date_notice and report.date_notice + timedelta(
                days=report.company_id.root_id.l10n_pe_collection_bureau_wait_days)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        partner = self.partner_id.commercial_partner_id
        responsible = partner.with_company(self.company_id).followup_responsible_id
        if responsible:
            self.user_id = responsible
        if partner:
            today = fields.Date.context_today(self)
            self.line_ids = partner._l10n_pe_collection_open_lines(self.company_id).filtered(
                lambda l: l.amount_residual > 0 and (l.date_maturity or l.date) < today
                and not l.l10n_pe_collection_in_dispute)

    @api.depends('name', 'partner_id', 'bureau')
    def _compute_display_name(self):
        bureaus = dict(BUREAUS)
        for report in self:
            report.display_name = '%s · %s · %s' % (report.name, report.partner_id.name or '',
                                                    bureaus.get(report.bureau, ''))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id') or self.env.company.id).next_by_code('l10n_pe.collection.bureau') or '/'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------

    def _l10n_pe_check_reportable(self, today=None):
        """Errores que impiden avisar o reportar: deuda no vencida, en disputa o
        de más de 5 años."""
        self.ensure_one()
        today = today or fields.Date.context_today(self)
        lines = self.line_ids.filtered(lambda l: l.amount_residual > 0)
        if not lines:
            raise UserError(_('%s no tiene documentos con saldo que reportar.', self.name))
        problems = []
        for line in lines:
            due = line.date_maturity or line.date
            if due >= today:
                problems.append(_('%s aún no vence', line.move_id.name))
            elif line.l10n_pe_collection_in_dispute:
                problems.append(_('%s tiene un reclamo abierto', line.move_id.name))
            elif due < today - relativedelta(years=MAX_REPORT_YEARS):
                problems.append(_('%s venció hace más de 5 años (Ley 27489)', line.move_id.name))
        if problems:
            raise UserError(_('No se puede reportar a %(partner)s: %(problems)s.',
                              partner=self.partner_id.name, problems='; '.join(problems)))

    # ------------------------------------------------------------------
    # Flujo
    # ------------------------------------------------------------------

    def action_send_notice(self):
        template = self.env.ref('al_l10n_pe_collection.mail_template_bureau_notice')
        for report in self:
            if report.state != 'draft':
                raise UserError(_('El aviso ya se envió.'))
            report._l10n_pe_check_reportable()
            if not report.partner_id.email:
                raise UserError(_('%s no tiene correo para el aviso previo.', report.partner_id.name))
            # Primero la fecha del aviso: el correo dice hasta cuándo puede regularizar.
            report.write({'state': 'notified', 'date_notice': fields.Date.context_today(self)})
            template.send_mail(report.id)
            report.partner_id._l10n_pe_collection_log(_(
                'Aviso previo de reporte a %(bureau)s enviado (%(name)s).',
                bureau=dict(BUREAUS)[report.bureau], name=report._get_html_link()))
        return True

    def action_report(self):
        today = fields.Date.context_today(self)
        for report in self:
            if report.state != 'notified':
                raise UserError(_('Primero envíe el aviso previo al deudor.'))
            if report.date_eligible and today < report.date_eligible:
                raise UserError(_('El plazo del aviso vence el %s.', report.date_eligible.strftime('%d/%m/%Y')))
            report._l10n_pe_check_reportable(today)
            report.write({'state': 'reported', 'date_reported': today, 'amount_reported': report.amount})
            report.partner_id._l10n_pe_collection_log(_('Reportado a %(bureau)s por %(amount)s.',
                                                  bureau=dict(BUREAUS)[report.bureau],
                                                  amount=report.currency_id.format(report.amount)))
        return True

    def action_withdraw(self):
        for report in self.filtered(lambda r: r.state in ('reported', 'to_withdraw')):
            report.write({'state': 'withdrawn', 'date_withdrawn': fields.Date.context_today(self)})
            report.activity_feedback(['mail.mail_activity_data_todo'])
            report.partner_id._l10n_pe_collection_log(_('Retirado de %s.', dict(BUREAUS)[report.bureau]))
        return True

    def action_cancel(self):
        if self.filtered(lambda r: r.state in ('reported', 'to_withdraw')):
            raise UserError(_('Un reporte vigente se retira, no se cancela.'))
        self.write({'state': 'cancel'})
        return True

    def action_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft', 'date_notice': False})
        return True

    @api.model
    def _cron_collection_bureau(self, today=None):
        """Pasa a «por retirar» los reportes pagados o vencidos hace 5 años."""
        today = today or fields.Date.context_today(self)
        limit = today - relativedelta(years=MAX_REPORT_YEARS)
        for report in self.search([('state', '=', 'reported')]):
            open_lines = report.line_ids.filtered(lambda l: l.amount_residual > 0)
            if open_lines and all((l.date_maturity or l.date) >= limit for l in open_lines):
                continue
            report.state = 'to_withdraw'
            reason = _('la deuda se pagó') if not open_lines else _('la deuda cumplió 5 años de vencida')
            report.activity_schedule(
                'mail.mail_activity_data_todo', user_id=report.user_id.id,
                summary=_('Retirar a %s de la central de riesgo', report.partner_id.name),
                note=_('Retírelo de %(bureau)s: %(reason)s.', bureau=dict(BUREAUS)[report.bureau], reason=reason))

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------

    def action_export_xlsx(self):
        """Archivo con los datos que piden las centrales (cada una tiene su
        formato de carga; las columnas son las comunes)."""
        reports = self or self.search([('state', 'in', ('reported', 'notified'))])
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '#,##0.00'})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        sheet = workbook.add_worksheet(_('Deudores'))
        headers = [_('Central'), _('Estado'), _('Tipo de documento'), _('Número de documento'), _('Deudor'),
                   _('Comprobante'), _('Emisión'), _('Vencimiento'), _('Días de atraso'), _('Moneda'), _('Saldo'),
                   _('Saldo en %s', self.env.company.currency_id.name)]
        for col, header in enumerate(headers):
            sheet.write(0, col, header, bold)
        today = fields.Date.context_today(self)
        bureaus, states = dict(BUREAUS), dict(BUREAU_STATES)
        row = 1
        for report in reports:
            partner = report.partner_id
            id_code = partner.l10n_pe_sunat_id_code
            for line in report.line_ids.filtered(lambda l: l.amount_residual > 0):
                due = line.date_maturity or line.date
                sheet.write(row, 0, bureaus[report.bureau])
                sheet.write(row, 1, states[report.state])
                sheet.write(row, 2, id_code or '')
                sheet.write(row, 3, partner.l10n_pe_sunat_id_value or '')
                sheet.write(row, 4, partner.name)
                sheet.write(row, 5, line.move_id.name)
                sheet.write_datetime(row, 6, fields.Datetime.to_datetime(line.move_id.invoice_date or line.date),
                                     date_fmt)
                sheet.write_datetime(row, 7, fields.Datetime.to_datetime(due), date_fmt)
                sheet.write_number(row, 8, max((today - due).days, 0))
                sheet.write(row, 9, line.currency_id.name)
                sheet.write_number(row, 10, line.amount_residual_currency, money)
                sheet.write_number(row, 11, line.amount_residual, money)
                row += 1
        sheet.set_column(0, 1, 16)
        sheet.set_column(2, 3, 14)
        sheet.set_column(4, 5, 30)
        sheet.set_column(6, 11, 13)
        workbook.close()
        attachment = self.env['ir.attachment'].create({
            'name': _('Centrales de riesgo %s.xlsx', today.strftime('%Y-%m-%d')),
            'raw': output.getvalue(),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id,
                'target': 'download'}
