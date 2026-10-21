from num2words import num2words

from odoo import _, api, fields, models

#: Nombre de la moneda en el importe en letras (plural, como en los comprobantes).
CURRENCY_WORDS = {'PEN': 'SOLES', 'USD': 'DÓLARES AMERICANOS', 'EUR': 'EUROS'}
MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
          'octubre', 'noviembre', 'diciembre']
REPORT_NAME = 'al_l10n_pe_check_printing.report_check'


def amount_in_words(amount, currency):
    """«MIL DOSCIENTOS CINCUENTA Y 00/100 SOLES»."""
    integer, decimals = divmod(round(abs(amount), 2), 1)
    cents = int(round(decimals * 100))
    name = CURRENCY_WORDS.get(currency.name) or (currency.currency_unit_label or currency.name or '').upper()
    return ('%s Y %02d/100 %s' % (num2words(int(integer), lang='es'), cents, name)).upper()


class L10nPeCheckLayout(models.Model):
    """Dónde va cada dato en la hoja de la chequera de un banco.

    Las medidas son en milímetros desde la esquina superior izquierda de la
    hoja. Cada banco tiene su chequera: se parte de valores aproximados y se
    calibra con «Imprimir prueba». El desplazamiento general corrige de una vez
    lo que la impresora corre al alimentar la hoja.
    """
    _name = 'l10n_pe.check.layout'
    _description = 'Formato de cheque'
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    bank_id = fields.Many2one('res.bank', string='Banco')
    paper_width = fields.Integer(string='Ancho de la hoja (mm)', default=175, required=True)
    paper_height = fields.Integer(string='Alto de la hoja (mm)', default=80, required=True)
    offset_x = fields.Float(string='Desplazamiento horizontal (mm)', digits=(5, 1),
                            help='Suma a todas las posiciones: positivo, hacia la derecha.')
    offset_y = fields.Float(string='Desplazamiento vertical (mm)', digits=(5, 1),
                            help='Suma a todas las posiciones: positivo, hacia abajo.')
    font_size = fields.Integer(string='Tamaño de letra (pt)', default=10, required=True)
    city = fields.Char(string='Ciudad', help='Se antepone a la fecha: «Lima, 21 de octubre de 2026».')
    date_style = fields.Selection(
        [('long', '21 de octubre de 2026'), ('numeric', '21/10/2026')], string='Fecha', default='long',
        required=True)
    date_x = fields.Float(string='Fecha X', digits=(5, 1), default=105.0)
    date_y = fields.Float(string='Fecha Y', digits=(5, 1), default=12.0)
    print_due_date = fields.Boolean(
        string='Fecha de pago (diferido)', default=True,
        help='En un cheque de pago diferido, imprime la fecha desde la que se puede cobrar.')
    due_date_x = fields.Float(string='Fecha de pago X', digits=(5, 1), default=105.0)
    due_date_y = fields.Float(string='Fecha de pago Y', digits=(5, 1), default=17.0)
    payee_x = fields.Float(string='Beneficiario X', digits=(5, 1), default=32.0)
    payee_y = fields.Float(string='Beneficiario Y', digits=(5, 1), default=30.0)
    payee_width = fields.Float(string='Beneficiario ancho', digits=(5, 1), default=110.0)
    amount_x = fields.Float(string='Importe X', digits=(5, 1), default=135.0)
    amount_y = fields.Float(string='Importe Y', digits=(5, 1), default=24.0)
    amount_fill = fields.Boolean(string='Rellenar con asteriscos', default=True,
                                 help='«****1,250.00»: impide agregar cifras delante del importe.')
    words_x = fields.Float(string='Importe en letras X', digits=(5, 1), default=20.0)
    words_y = fields.Float(string='Importe en letras Y', digits=(5, 1), default=40.0)
    words_width = fields.Float(string='Importe en letras ancho', digits=(5, 1), default=145.0)
    print_not_negotiable = fields.Boolean(string='Leyenda «No negociable»')
    not_negotiable_x = fields.Float(string='«No negociable» X', digits=(5, 1), default=8.0)
    not_negotiable_y = fields.Float(string='«No negociable» Y', digits=(5, 1), default=5.0)
    paperformat_id = fields.Many2one('report.paperformat', string='Formato de papel', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        layouts = super().create(vals_list)
        layouts._l10n_pe_sync_paperformat()
        return layouts

    def write(self, vals):
        res = super().write(vals)
        if {'name', 'paper_width', 'paper_height'} & set(vals):
            self._l10n_pe_sync_paperformat()
        return res

    def _l10n_pe_sync_paperformat(self):
        """Formato de papel propio del tamaño de la hoja, sin márgenes: las
        posiciones se miden desde el borde de la hoja."""
        for layout in self:
            vals = {
                'name': _('Cheque: %s', layout.name),
                'format': 'custom',
                'page_width': layout.paper_width,
                'page_height': layout.paper_height,
                'orientation': 'Portrait',
                'margin_top': 0, 'margin_bottom': 0, 'margin_left': 0, 'margin_right': 0,
                'header_spacing': 0,
                'header_line': False,
                'disable_shrinking': True,
                'dpi': 96,
            }
            # sudo: el formato de papel es configuración técnica (ir.actions.report),
            # que el contable que define el cheque no administra.
            if layout.paperformat_id:
                layout.paperformat_id.sudo().write(vals)
            else:
                layout.paperformat_id = self.env['report.paperformat'].sudo().create(vals)

    # ------------------------------------------------------------------
    # Datos que se imprimen
    # ------------------------------------------------------------------

    def _l10n_pe_format_date(self, day, with_city=True):
        self.ensure_one()
        if not day:
            return ''
        if self.date_style == 'numeric':
            text = day.strftime('%d/%m/%Y')
        else:
            text = '%d de %s de %d' % (day.day, MONTHS[day.month - 1], day.year)
        return '%s, %s' % (self.city, text) if self.city and with_city else text

    def _l10n_pe_format_amount(self, amount, currency):
        self.ensure_one()
        text = '{:,.2f}'.format(abs(amount))
        if self.amount_fill:
            text = text.rjust(14, '*')
        return '%s %s' % (currency.symbol or currency.name, text)

    def _l10n_pe_print_values(self, issue_date, due_date, payee, amount, currency):
        """Lo que imprime la plantilla para un cheque."""
        self.ensure_one()
        deferred = bool(due_date and issue_date and due_date > issue_date)
        return {
            'layout': self,
            'date': self._l10n_pe_format_date(issue_date),
            'due_date': self._l10n_pe_format_date(due_date, with_city=False)
            if deferred and self.print_due_date else '',
            'payee': payee or '',
            'amount': self._l10n_pe_format_amount(amount, currency),
            'words': amount_in_words(amount, currency),
        }

    def action_print_test(self):
        """Hoja de prueba con datos de ejemplo, para calibrar contra la chequera."""
        self.ensure_one()
        return self.env.ref('al_l10n_pe_check_printing.action_report_check').report_action(
            None, data={'l10n_pe_test_layout_id': self.id}, config=False)
