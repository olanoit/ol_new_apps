from odoo import api, fields, models

#: Cuentas de cobranza y su valor por defecto en el PCGE de l10n_pe.
ACCOUNT_DEFAULTS = {
    # 68711 Estimación de cuentas de cobranza dudosa – comerciales terceros.
    'l10n_pe_collection_provision_expense_account_id': 'chart68711',
    # 1911 Estimación de cobranza dudosa – facturas, boletas y otros comprobantes.
    'l10n_pe_collection_provision_account_id': 'chart1911',
    # 7722 Rendimientos ganados – cuentas por cobrar comerciales (intereses moratorios).
    'l10n_pe_collection_interest_account_id': 'chart7722',
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_collection_promise_tolerance = fields.Integer(
        string='Tolerancia de compromisos (días)', default=2,
        help='Días después de la fecha del compromiso antes de evaluarlo como incumplido.')
    l10n_pe_collection_promise_reminder_days = fields.Integer(
        string='Recordar el compromiso (días antes)', default=1,
        help='Días antes de la fecha del compromiso en que se envía el recordatorio al cliente; '
             '0 para no enviar.')
    l10n_pe_collection_promise_min_percent = fields.Float(
        string='Cumplido desde (%)', default=99.0, digits=(5, 1),
        help='Porcentaje del importe prometido que debe cobrarse para darlo por cumplido; por '
             'debajo, y con algún cobro, es parcial.')
    l10n_pe_collection_digest = fields.Boolean(
        string='Resumen diario a los gestores', default=True,
        help='Correo diario a cada gestor con sus compromisos del día, gestiones pendientes, '
             'documentos por vencer y nuevos vencidos.')
    l10n_pe_collection_history_months = fields.Integer(
        string='Historial de pago (meses)', default=12,
        help='Meses de facturas pagadas que se usan para calcular el atraso promedio de cada cliente.')

    # Art. 62 del Código de Protección al Consumidor (solo consumidores).
    l10n_pe_collection_hour_from = fields.Float(
        string='Contactar desde', default=7.0,
        help='Hora desde la que se puede llamar, visitar o escribir a un consumidor (art. 62, Ley 29571).')
    l10n_pe_collection_hour_to = fields.Float(
        string='Contactar hasta', default=20.0,
        help='Hora hasta la que se puede llamar, visitar o escribir a un consumidor.')
    l10n_pe_collection_consumer_guard = fields.Boolean(
        string='Proteger a los consumidores', default=True,
        help='Impide registrar llamadas, visitas, WhatsApp o SMS a consumidores fuera del horario, '
             'en fines de semana o feriados, y no les envía recordatorios antes del vencimiento '
             'sin su consentimiento.')
    # Riesgo y bloqueo
    l10n_pe_collection_hold_days = fields.Integer(
        string='Bloquear con atraso de (días)', default=0,
        help='Bloquea las ventas al cliente cuando su deuda más antigua supera estos días; 0 para no '
             'bloquear por atraso.')
    l10n_pe_collection_hold_rating_d = fields.Boolean(
        string='Bloquear a los clientes con calificación D')
    # Intereses moratorios
    l10n_pe_collection_interest_rate = fields.Float(
        string='Interés moratorio (TEA %)', digits=(7, 4),
        help='Tasa efectiva anual pactada con los clientes; el contacto puede tener la suya. Solo '
             'corre si se pactó y no puede superar el tope del BCRP.')
    l10n_pe_collection_interest_account_id = fields.Many2one(
        'account.account', string='Ingreso por intereses moratorios',
        help='Por defecto 7722 Rendimientos ganados – cuentas por cobrar comerciales.')
    # Provisión y castigo
    l10n_pe_collection_provision_months = fields.Integer(
        string='Provisionar desde (meses vencida)', default=12,
        help='Art. 21 f) del Reglamento de la LIR: más de 12 meses vencida, salvo que haya proceso '
             'judicial o se acredite la morosidad de otro modo.')
    l10n_pe_collection_provision_min_actions = fields.Integer(
        string='Gestiones mínimas para provisionar', default=1,
        help='Gestiones de cobro registradas después del vencimiento que sustentan la provisión.')
    l10n_pe_collection_provision_journal_id = fields.Many2one(
        'account.journal', string='Diario de provisiones', domain="[('type', '=', 'general')]")
    l10n_pe_collection_provision_expense_account_id = fields.Many2one(
        'account.account', string='Gasto por cobranza dudosa', help='Por defecto 68711.')
    l10n_pe_collection_provision_account_id = fields.Many2one(
        'account.account', string='Estimación de cobranza dudosa',
        help='Por defecto 1911; no forma parte de la cartera.')
    l10n_pe_collection_uit = fields.Monetary(
        string='UIT', default=5500.0, currency_field='currency_id',
        help='Valor de la UIT del ejercicio: el castigo sin acciones judiciales exige una deuda por '
             'deudor que no supere 3 UIT.')
    # Pago en línea
    l10n_pe_collection_online_payment = fields.Boolean(
        string='Enlace de pago en los avisos', default=True,
        help='Agrega «Pagar en línea» (y un QR en el estado de cuenta) con el saldo del cliente, si la '
             'compañía tiene alguna pasarela de pago en línea activa.')
    # Centrales de riesgo
    l10n_pe_collection_bureau_wait_days = fields.Integer(
        string='Días entre el aviso y el reporte', default=7,
        help='Plazo que se da al cliente desde el aviso previo antes de reportarlo a una central de riesgo.')
    # Comisiones
    l10n_pe_collection_commission_plan_id = fields.Many2one(
        'l10n_pe.collection.commission.plan', string='Plan de comisión de los gestores',
        help='Se propone en las liquidaciones de los gestores; cada agencia tiene el suyo.')
    l10n_pe_collection_commission_product_id = fields.Many2one(
        'product.product', string='Servicio de comisión de agencias',
        help='Producto con el que se registra la factura de la agencia (cuenta de gasto e IGV).')

    def _get_company_root_delegated_field_names(self):
        return super()._get_company_root_delegated_field_names() + [
            'l10n_pe_collection_promise_tolerance', 'l10n_pe_collection_promise_reminder_days',
            'l10n_pe_collection_promise_min_percent', 'l10n_pe_collection_digest',
            'l10n_pe_collection_history_months', 'l10n_pe_collection_hour_from',
            'l10n_pe_collection_hour_to', 'l10n_pe_collection_consumer_guard',
            'l10n_pe_collection_hold_days', 'l10n_pe_collection_hold_rating_d',
            'l10n_pe_collection_interest_rate', 'l10n_pe_collection_interest_account_id',
            'l10n_pe_collection_provision_months', 'l10n_pe_collection_provision_min_actions',
            'l10n_pe_collection_provision_journal_id', 'l10n_pe_collection_provision_expense_account_id',
            'l10n_pe_collection_provision_account_id', 'l10n_pe_collection_uit',
            'l10n_pe_collection_bureau_wait_days', 'l10n_pe_collection_online_payment',
            'l10n_pe_collection_commission_plan_id', 'l10n_pe_collection_commission_product_id']

    def _l10n_pe_collection_account(self, field):
        """Cuenta configurada o, si no hay, la del PCGE de l10n_pe."""
        self.ensure_one()
        company = self.root_id
        return company[field] or self.env.ref(
            'account.%s_%s' % (company.id, ACCOUNT_DEFAULTS[field]), raise_if_not_found=False) \
            or self.env['account.account']

    def _l10n_pe_collection_excluded_accounts(self):
        """Cuentas por cobrar que no son cobranza: anticipos (se aplican a la
        factura) y detracciones por cobrar (van al Banco de la Nación)."""
        self.ensure_one()
        company = self.root_id
        accounts = self.env['account.account']
        if hasattr(company, '_l10n_pe_advance_accounts'):
            accounts |= company._l10n_pe_advance_accounts()
        if 'l10n_pe_detraction_receivable_account_id' in company._fields:
            accounts |= company.l10n_pe_detraction_receivable_account_id
        # La estimación de cobranza dudosa (19) es una cuenta por cobrar en l10n_pe.
        accounts |= company._l10n_pe_collection_account('l10n_pe_collection_provision_account_id')
        return accounts


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_collection_promise_tolerance = fields.Integer(
        related='company_id.l10n_pe_collection_promise_tolerance', readonly=False)
    l10n_pe_collection_promise_reminder_days = fields.Integer(
        related='company_id.l10n_pe_collection_promise_reminder_days', readonly=False)
    l10n_pe_collection_promise_min_percent = fields.Float(
        related='company_id.l10n_pe_collection_promise_min_percent', readonly=False)
    l10n_pe_collection_digest = fields.Boolean(related='company_id.l10n_pe_collection_digest', readonly=False)
    l10n_pe_collection_history_months = fields.Integer(
        related='company_id.l10n_pe_collection_history_months', readonly=False)

    l10n_pe_collection_hour_from = fields.Float(related='company_id.l10n_pe_collection_hour_from', readonly=False)
    l10n_pe_collection_hour_to = fields.Float(related='company_id.l10n_pe_collection_hour_to', readonly=False)
    l10n_pe_collection_consumer_guard = fields.Boolean(
        related='company_id.l10n_pe_collection_consumer_guard', readonly=False)
    l10n_pe_collection_hold_days = fields.Integer(related='company_id.l10n_pe_collection_hold_days', readonly=False)
    l10n_pe_collection_hold_rating_d = fields.Boolean(
        related='company_id.l10n_pe_collection_hold_rating_d', readonly=False)
    l10n_pe_collection_interest_rate = fields.Float(
        related='company_id.l10n_pe_collection_interest_rate', readonly=False)
    l10n_pe_collection_interest_account_id = fields.Many2one(
        related='company_id.l10n_pe_collection_interest_account_id', readonly=False)
    l10n_pe_collection_interest_warning = fields.Char(compute='_compute_l10n_pe_collection_interest_warning')

    @api.depends('l10n_pe_collection_interest_rate')
    def _compute_l10n_pe_collection_interest_warning(self):
        caps = self.env['l10n_pe.collection.rate.cap']
        for settings in self:
            settings.l10n_pe_collection_interest_warning = caps._l10n_pe_rate_warning(
                settings.l10n_pe_collection_interest_rate)
    l10n_pe_collection_provision_months = fields.Integer(
        related='company_id.l10n_pe_collection_provision_months', readonly=False)
    l10n_pe_collection_provision_min_actions = fields.Integer(
        related='company_id.l10n_pe_collection_provision_min_actions', readonly=False)
    l10n_pe_collection_provision_journal_id = fields.Many2one(
        related='company_id.l10n_pe_collection_provision_journal_id', readonly=False)
    l10n_pe_collection_provision_expense_account_id = fields.Many2one(
        related='company_id.l10n_pe_collection_provision_expense_account_id', readonly=False)
    l10n_pe_collection_provision_account_id = fields.Many2one(
        related='company_id.l10n_pe_collection_provision_account_id', readonly=False)
    l10n_pe_collection_uit = fields.Monetary(related='company_id.l10n_pe_collection_uit', readonly=False)
    l10n_pe_collection_bureau_wait_days = fields.Integer(
        related='company_id.l10n_pe_collection_bureau_wait_days', readonly=False)
    l10n_pe_collection_online_payment = fields.Boolean(
        related='company_id.l10n_pe_collection_online_payment', readonly=False)
    l10n_pe_collection_commission_plan_id = fields.Many2one(
        related='company_id.l10n_pe_collection_commission_plan_id', readonly=False)
    l10n_pe_collection_commission_product_id = fields.Many2one(
        related='company_id.l10n_pe_collection_commission_product_id', readonly=False)

    def action_l10n_pe_collection_load_followup_levels(self):
        return self.env['account_followup.followup.line']._l10n_pe_load_levels(self.company_id)
