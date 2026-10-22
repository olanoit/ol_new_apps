import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class L10nPeBankCollectionAgreement(models.Model):
    """Convenio de recaudación con un banco: la cuenta recaudadora, los
    formatos de sus archivos y cómo se identifica a cada cliente."""
    _name = 'l10n_pe.bank.collection.agreement'
    _description = 'Convenio de recaudación bancaria'
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Convenio', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    journal_id = fields.Many2one(
        'account.journal', string='Diario del banco', required=True, check_company=True,
        domain="[('type', '=', 'bank')]", help='Cuenta recaudadora donde el banco abona lo cobrado.')
    bank_id = fields.Many2one(related='journal_id.bank_id', string='Banco')
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.company.currency_id,
                                  help='Un convenio por moneda: solo se envían las cuotas en esta moneda.')
    account_branch = fields.Char(string='Sucursal', size=3, help='Tres dígitos de la sucursal de la cuenta (BCP).')
    account_number = fields.Char(string='Cuenta', help='Número de la cuenta recaudadora, sin la sucursal ni la moneda.')
    service_code = fields.Char(string='Código de servicio', default='000000',
                               help='Código del servicio o convenio que asigna el banco, si lo pide el formato.')
    company_name = fields.Char(string='Nombre en el archivo',
                               default=lambda self: self.env.company.name,
                               help='Razón social como la registró el banco (máximo 40 caracteres en el BCP).')
    debtors_layout_id = fields.Many2one('l10n_pe.bank.collection.layout', string='Formato del archivo de deudores',
                                        required=True, domain="[('file_type', '=', 'debtors')]")
    response_layout_id = fields.Many2one('l10n_pe.bank.collection.layout', string='Formato de la respuesta',
                                         required=True, domain="[('file_type', '=', 'response')]")
    code_source = fields.Selection(
        [('vat', 'Número de documento (RUC o DNI)'), ('ref', 'Referencia del cliente'),
         ('code', 'Código de recaudación del cliente')],
        string='Código del depositante', required=True, default='vat',
        help='Con qué código paga el cliente en ventanilla, agentes o banca por internet.')
    validation = fields.Selection(
        [('full', 'Completa: cada cuota con su importe'),
         ('partial', 'Parcial: solo el código del cliente, importe libre'),
         ('amounts', 'Importes: tipos de pago con importe fijo'),
         ('none', 'Sin validación: cualquier importe')],
        string='Validación', required=True, default='full',
        help='Modalidad contratada con el banco. Completa: una línea por cuota. Parcial: una línea por '
             'cliente y el pago se aplica a sus cuotas más antiguas. Importes: el archivo lleva el catálogo '
             'de tipos de pago (derechos, servicios) y quien paga se identifica con su documento. Sin '
             'validación: no hace falta enviar archivo.')
    payment_type_ids = fields.One2many('l10n_pe.bank.collection.payment.type', 'agreement_id',
                                       string='Tipos de pago', copy=True)
    days_ahead = fields.Integer(
        string='Enviar lo que vence en (días)', default=30,
        help='Además de lo vencido, las cuotas que vencen dentro de estos días; 0 solo lo vencido.')
    block_days = fields.Integer(
        string='Cobrar hasta (días después del vencimiento)', default=90,
        help='Fecha de bloqueo que piden algunos bancos (BBVA): último día en que el banco acepta el pago.')
    include_disputed = fields.Boolean(string='Incluir documentos en reclamo')
    payment_memo = fields.Char(string='Memo de los pagos', default='Recaudación %(bank)s op. %(operation)s')

    _name_company_uniq = models.Constraint('unique(company_id, name)', 'Ya existe un convenio con ese nombre.')

    @api.constrains('journal_id', 'currency_id')
    def _check_currency(self):
        for agreement in self:
            journal_currency = agreement.journal_id.currency_id or agreement.company_id.currency_id
            if journal_currency != agreement.currency_id:
                raise ValidationError(_('El diario %(journal)s es en %(currency)s: el convenio debe usar esa moneda.',
                                        journal=agreement.journal_id.name, currency=journal_currency.name))

    # ------------------------------------------------------------------
    # Código del depositante
    # ------------------------------------------------------------------

    def _depositor_code(self, partner):
        """Código con el que el cliente paga en el banco."""
        self.ensure_one()
        partner = partner.commercial_partner_id
        if self.code_source == 'vat':
            return re.sub(r'\W', '', partner.vat or '')
        if self.code_source == 'ref':
            return (partner.ref or '').strip()
        return (partner.l10n_pe_bank_collection_code or '').strip()

    def _partner_by_code(self, code):
        """Cliente de un código del depositante (sin ceros a la izquierda si el
        banco los añadió)."""
        self.ensure_one()
        code = (code or '').strip()
        if not code:
            return self.env['res.partner']
        candidates = {code, code.lstrip('0')}
        field = {'vat': 'vat', 'ref': 'ref', 'code': 'l10n_pe_bank_collection_code'}[self.code_source]
        Partner = self.env['res.partner'].with_context(active_test=False)
        partners = Partner.search([(field, 'in', list(candidates))])
        if not partners and self.code_source == 'vat':
            # El RUC o DNI puede estar guardado con guiones o prefijos.
            partners = Partner.search([('vat', 'ilike', code.lstrip('0'))]).filtered(
                lambda p: re.sub(r'\W', '', p.vat or '').lstrip('0') == code.lstrip('0'))
        return partners.commercial_partner_id

    # ------------------------------------------------------------------
    # Cuotas que se envían
    # ------------------------------------------------------------------

    def _open_lines(self, date=None, with_disputed=False):
        """Cuotas por cobrar abiertas en la moneda del convenio; con ``date``,
        solo las vencidas o que vencen dentro de ``days_ahead``. Las que están
        en reclamo no se envían al banco, pero sí se concilian si el cliente
        las paga (``with_disputed``)."""
        self.ensure_one()
        company = self.company_id
        domain = [
            ('company_id', 'child_of', company.root_id.id),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('account_id', 'not in', company._l10n_pe_collection_excluded_accounts().ids),
            ('reconciled', '=', False),
            ('amount_residual', '>', 0),
            ('partner_id', '!=', False),
        ]
        if date:
            domain.append(('date_maturity', '<=', fields.Date.add(date, days=self.days_ahead)))
        if self.currency_id == company.currency_id:
            domain.append(('currency_id', 'in', (False, self.currency_id.id)))
        else:
            domain.append(('currency_id', '=', self.currency_id.id))
        if not (self.include_disputed or with_disputed):
            domain.append(('l10n_pe_collection_in_dispute', '=', False))
        return self.env['account.move.line'].search(domain, order='partner_id, date_maturity, id')

    def _line_amount(self, line):
        """Saldo de la cuota en la moneda del convenio."""
        return line.amount_residual if self.currency_id == self.company_id.currency_id \
            else line.amount_residual_currency


class L10nPeBankCollectionPaymentType(models.Model):
    """Tipo de pago de la validación de importes: un concepto con importe fijo
    (derecho de trámite, matrícula…) que cualquiera paga en el banco."""
    _name = 'l10n_pe.bank.collection.payment.type'
    _description = 'Tipo de pago de recaudación'
    _order = 'agreement_id, sequence, code'

    agreement_id = fields.Many2one('l10n_pe.bank.collection.agreement', required=True, ondelete='cascade',
                                   index=True)
    company_id = fields.Many2one(related='agreement_id.company_id', store=True)
    currency_id = fields.Many2one(related='agreement_id.currency_id')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    code = fields.Char(string='Código', required=True, help='Código del tipo de pago (hasta 20 caracteres).')
    name = fields.Char(string='Nombre', required=True)
    return_info = fields.Char(string='Información de retorno')
    amount = fields.Monetary(string='Valor', required=True)
    surcharge = fields.Monetary(string='Recargo')
    total = fields.Monetary(string='Importe total', compute='_compute_total')

    _agreement_code_uniq = models.Constraint('unique(agreement_id, code)',
                                             'El código del tipo de pago se repite en el convenio.')

    @api.depends('amount', 'surcharge')
    def _compute_total(self):
        for payment_type in self:
            payment_type.total = payment_type.amount + payment_type.surcharge
