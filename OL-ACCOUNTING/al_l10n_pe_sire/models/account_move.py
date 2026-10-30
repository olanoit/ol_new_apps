import re

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .sire_country_codes import SIRE_COUNTRY_CODES
from .sire_rce import RCE_EXCLUDED_DOC_TYPES
from .sire_rvie import RVIE_EXCLUDED_DOC_TYPES

#: Tabla 17 del anexo 1 (R.S. 040-2022): vinculación económica.
ND_LINK_SELECTION = [
    ('00', '00 - Sin vinculación'),
    ('01', '01 - Posee más del 30 % del capital de la otra'),
    ('02', '02 - Más del 30 % del capital de ambas pertenece a una misma persona'),
    ('03', '03 - Capital en manos de cónyuges o parientes hasta el 2.º grado'),
    ('04', '04 - Más del 30 % del capital pertenece a socios comunes'),
    ('05', '05 - Directores, gerentes o administradores comunes'),
    ('06', '06 - Consolidan estados financieros'),
    ('07', '07 - Contrato de colaboración con contabilidad independiente'),
    ('08', '08 - Contrato de colaboración sin contabilidad independiente'),
    ('09', '09 - Asociación en participación (más del 30 % o poder de decisión)'),
    ('10', '10 - No domiciliada con establecimientos permanentes en el país'),
    ('11', '11 - Domiciliada con establecimientos permanentes en el extranjero'),
    ('12', '12 - Influencia dominante en la administración o en las ventas'),
]
#: Tabla 18: convenios para evitar la doble imposición.
ND_AGREEMENT_SELECTION = [
    ('00', '00 - Ninguno'), ('01', '01 - Canadá'), ('02', '02 - Chile'),
    ('03', '03 - Comunidad Andina de Naciones'), ('04', '04 - Brasil'),
    ('05', '05 - Estados Unidos Mexicanos'), ('06', '06 - República de Corea'),
    ('07', '07 - Confederación Suiza'), ('08', '08 - Portugal'), ('09', '09 - Otros'),
]
#: Tabla 19: tipo de renta.
ND_INCOME_SELECTION = [
    ('00', '00 - Bienes'),
    ('01', '01 - Arrendamiento de predios'),
    ('02', '02 - Enajenación de inmuebles o derechos sobre inmuebles'),
    ('03', '03 - Bienes o derechos utilizados en el país'),
    ('04', '04 - Regalías por bienes o derechos utilizados en el país'),
    ('05', '05 - Regalías pagadas por un domiciliado'),
    ('06', '06 - Intereses, comisiones y operaciones financieras'),
    ('07', '07 - Dividendos y otras distribuciones de utilidades'),
    ('08', '08 - Rendimientos de ADR y GDR de empresas no domiciliadas'),
    ('09', '09 - Actividades civiles, comerciales o empresariales en el país'),
    ('10', '10 - Trabajo personal realizado en el país'),
    ('11', '11 - Rentas vitalicias y pensiones pagadas por un domiciliado'),
    ('12', '12 - Enajenación de acciones fuera de bolsa'),
    ('13', '13 - Enajenación de otros valores fuera de bolsa'),
    ('14', '14 - Redención o rescate de valores fuera de bolsa'),
    ('15', '15 - Enajenación de valores dentro de bolsa'),
    ('16', '16 - Redención o rescate de valores dentro de bolsa'),
    ('17', '17 - Enajenación de ADR y GDR de empresas domiciliadas'),
    ('18', '18 - Servicios digitales'),
    ('19', '19 - Asistencia técnica'),
    ('20', '20 - Intereses de obligaciones de un emisor del país'),
    ('21', '21 - Dietas de directores que actúan en el extranjero'),
    ('22', '22 - Remuneraciones del sector público por trabajos en el exterior'),
    ('23', '23 - Contratación de instrumentos financieros derivados'),
    ('24', '24 - IFD con cobertura para generar renta de fuente peruana'),
    ('25', '25 - IFD sin cobertura para generar renta de fuente peruana'),
    ('26', '26 - IFD sobre tipo de cambio a 180 días'),
    ('27', '27 - Enajenación indirecta de acciones'),
    ('28', '28 - Enajenación de ADR con subyacente de acciones domiciliadas'),
    ('29', '29 - Reducción de capital tras un aumento en 12 meses'),
    ('30', '30 - Seguros y reaseguros'),
    ('31', '31 - Alquiler de naves'),
    ('32', '32 - Alquiler de aeronaves'),
    ('33', '33 - Transporte aéreo'),
    ('34', '34 - Otros transportes'),
    ('35', '35 - Fletamento o transporte marítimo'),
    ('36', '36 - Reciprocidad en líneas extranjeras'),
    ('37', '37 - Servicios de telecomunicaciones'),
    ('38', '38 - Suministro de noticias'),
    ('39', '39 - Películas, video tape, discos y similares'),
    ('40', '40 - Suministro de contenedores'),
    ('41', '41 - Sobrestadía de contenedores'),
    ('42', '42 - Retransmisión por TV de eventos en vivo'),
    ('43', '43 - Extranjeros que ingresan a prestar servicios'),
]
#: Tabla 20: modalidad del servicio prestado.
ND_MODALITY_SELECTION = [
    ('1', '1 - Íntegramente en el Perú'),
    ('2', '2 - Parte en el Perú y parte en el extranjero'),
    ('3', '3 - Exclusivamente en el extranjero'),
]
#: Tabla 21: exoneraciones (art. 19 de la LIR).
ND_EXEMPTION_SELECTION = [
    ('1', '1 - Intereses de créditos de fomento de organismos internacionales'),
    ('2', '2 - Rentas de inmuebles sede de organismos internacionales'),
    ('3', '3 - Remuneraciones de funcionarios de gobiernos u organismos extranjeros'),
    ('4', '4 - Representaciones deportivas de países extranjeros'),
    ('5', '5 - Regalías por asesoramiento de entidades estatales u organismos'),
    ('6', '6 - Espectáculos culturales en vivo calificados por el INC'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_pe_cdr_rejected(self):
        """El comprobante tiene un CDR de rechazo de SUNAT (códigos 2000-3999).

        En Odoo 20 ``l10n_pe_edi`` deja la factura «por enviar» con el error
        en ``l10n_pe_edi_warnings``, igual que una que todavía no se envió;
        solo el código del mensaje («2800|…») los distingue. Los códigos
        0100-1999 son excepciones (no se recibió: se reenvía) y los 4000+
        observaciones (aceptado).
        """
        self.ensure_one()
        if 'l10n_pe_edi_warnings' not in self._fields or self.l10n_pe_edi_status != 'to_send':
            return False
        for warning in (self.l10n_pe_edi_warnings or {}).values():
            if warning.get('level') != 'danger':
                continue
            codes = re.findall(r'(?<!\d)(\d{4})\|', warning.get('message') or '')
            if any(2000 <= int(code) <= 3999 for code in codes):
                return True
        return False

    l10n_pe_sire_goods_class = fields.Selection(
        selection=[
            ('1', '1 - Mercadería, materia prima, suministro, envases y embalajes'),
            ('2', '2 - Activo fijo'),
            ('3', '3 - Otros activos no considerados en 1 y 2'),
            ('4', '4 - Gastos de educación, recreación, salud, culturales y otros'),
            ('5', '5 - Otros gastos no incluidos en 4'),
        ],
        string='Clase de bien o servicio',
        help='Tabla 30 SUNAT — columna "Clasif de Bss y Sss" del RCE. Obligatoria '
             'para contribuyentes con ingresos mayores a 1500 UIT. Si se deja '
             'vacía, al publicar se sugiere desde las cuentas y productos de las '
             'líneas; se puede cambiar.')

    # --- Registro de compras de no domiciliados (anexo 9, R.S. 040-2022).
    # Nombres propios: l10n_pe_reports (Enterprise) tiene campos parecidos
    # y este módulo funciona sin él. ---
    l10n_pe_sire_is_non_domiciled = fields.Boolean(
        string='Proveedor no domiciliado', compute='_compute_l10n_pe_sire_is_non_domiciled',
        store=True, readonly=False,
        help='Va al registro de compras de no domiciliados del SIRE (8.5) y no al RCE.')
    l10n_pe_sire_nd_credit_move_id = fields.Many2one(
        'account.move', string='Doc. del crédito fiscal',
        check_company=True,
        domain="[('move_type', 'in', ('in_invoice', 'in_refund')), ('state', '=', 'posted'),"
               " ('company_id', '=', company_id)]",
        help='DUA, liquidación de compra o formulario de pago del IGV (tipos 00, 46, 50-53).')
    l10n_pe_sire_nd_igv_withholding = fields.Monetary(
        string='Retención del IGV', currency_field='company_currency_id')
    l10n_pe_sire_nd_beneficiary_vat = fields.Char(string='Id. fiscal del beneficiario',
        help='Número de identificación fiscal del beneficiario efectivo.')
    l10n_pe_sire_nd_beneficiary_name = fields.Char(string='Beneficiario efectivo')
    l10n_pe_sire_nd_beneficiary_country_id = fields.Many2one(
        'res.country', string='País del beneficiario',
        help='País de residencia del beneficiario efectivo.')
    l10n_pe_sire_nd_link = fields.Selection(ND_LINK_SELECTION, string='Vinculación económica')
    l10n_pe_sire_nd_gross_income = fields.Monetary(
        string='Renta bruta', currency_field='company_currency_id')
    l10n_pe_sire_nd_deduction = fields.Monetary(
        string='Deducción o costo', currency_field='company_currency_id',
        help='Deducción o costo de enajenación.')
    l10n_pe_sire_nd_net_income = fields.Monetary(
        string='Renta neta', currency_field='company_currency_id',
        compute='_compute_l10n_pe_sire_nd_net_income', store=True, readonly=False)
    l10n_pe_sire_nd_withholding_rate = fields.Float(string='Tasa de retención (%)', digits=(5, 2))
    l10n_pe_sire_nd_withheld_tax = fields.Monetary(
        string='Impuesto retenido', currency_field='company_currency_id',
        compute='_compute_l10n_pe_sire_nd_withheld_tax', store=True, readonly=False,
        help='Renta neta por la tasa de retención; se puede corregir a mano.')
    l10n_pe_sire_nd_agreement = fields.Selection(
        ND_AGREEMENT_SELECTION, string='Convenio de doble imposición', default='00')
    l10n_pe_sire_nd_exemption = fields.Selection(
        ND_EXEMPTION_SELECTION, string='Exoneración aplicada')
    l10n_pe_sire_nd_income_type = fields.Selection(ND_INCOME_SELECTION, string='Tipo de renta')
    l10n_pe_sire_nd_service_modality = fields.Selection(
        ND_MODALITY_SELECTION, string='Modalidad del servicio')
    l10n_pe_sire_nd_art76 = fields.Boolean(
        string='Aplica art. 76 LIR',
        help='Aplica el penúltimo párrafo del art. 76 de la LIR.')

    @api.depends('partner_id.commercial_partner_id.country_id', 'l10n_latam_document_type_id',
                 'move_type')
    def _compute_l10n_pe_sire_is_non_domiciled(self):
        for move in self:
            country = move.partner_id.commercial_partner_id.country_id
            move.l10n_pe_sire_is_non_domiciled = bool(
                move.move_type in ('in_invoice', 'in_refund')
                and move.l10n_latam_document_type_id.code in ('00', '91', '97', '98')
                and country and country.code != 'PE')

    l10n_pe_sire_book_info = fields.Char(
        string='Registro SIRE', compute='_compute_l10n_pe_sire_book_info',
        help='Periodo del RVIE o RCE en que se desplegó el comprobante y su estado.')
    l10n_pe_sire_declared = fields.Boolean(
        string='Enviado en el SIRE', compute='_compute_l10n_pe_sire_book_info')

    def _l10n_pe_sire_suggest_goods_class(self):
        """Tabla 30 a partir de las líneas: activo fijo, bienes o gastos."""
        self.ensure_one()
        if self.move_type not in ('in_invoice', 'in_refund'):
            return False
        lines = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        if not lines:
            return False
        if any(line.account_id.account_type == 'asset_fixed' for line in lines):
            return '2'
        if any(line.product_id.type == 'consu' for line in lines):
            return '1'
        return '5'

    @api.depends('l10n_pe_sire_nd_net_income', 'l10n_pe_sire_nd_withholding_rate')
    def _compute_l10n_pe_sire_nd_withheld_tax(self):
        for move in self:
            move.l10n_pe_sire_nd_withheld_tax = move.company_currency_id.round(
                move.l10n_pe_sire_nd_net_income * move.l10n_pe_sire_nd_withholding_rate / 100)

    def _compute_l10n_pe_sire_book_info(self):
        self.l10n_pe_sire_book_info = False
        self.l10n_pe_sire_declared = False
        origins = self._origin.filtered('id')
        if not origins:
            return
        by_move = {}
        for model in ('l10n_pe.sire.rvie.line', 'l10n_pe.sire.rce.line'):
            # sudo: quien solo factura no lee el SIRE, pero sí ve en qué
            # periodo quedó su comprobante; solo se leen nombre y estado.
            groups = self.env[model].sudo()._read_group(
                [('move_id', 'in', origins.ids), ('type_line', '=', 'system')],
                ['move_id', 'sire_id'])
            for move, period in groups:
                by_move[move.id] = period
        for move in self:
            period = by_move.get(move._origin.id)
            if not period:
                continue
            state = dict(period._fields['state']._description_selection(self.env))[period.state]
            move.l10n_pe_sire_book_info = '%s · %s' % (period.display_name, state)
            move.l10n_pe_sire_declared = period.state in ('submitted', 'done')

    # ------------------------------------------------------------------
    # Validación al publicar
    # ------------------------------------------------------------------

    def _post(self, soft=True):
        posted = super()._post(soft)
        # Al publicar y no al crear: con las líneas ya completas, y sin pisar
        # lo que el usuario eligió.
        for move in posted.filtered(lambda m: not m.l10n_pe_sire_goods_class):
            suggestion = move._l10n_pe_sire_suggest_goods_class()
            if suggestion:
                move.l10n_pe_sire_goods_class = suggestion
        posted._l10n_pe_sire_check_on_post()
        return posted

    def _l10n_pe_sire_check_on_post(self):
        """Las reglas del registro SIRE, en el momento de publicar.

        Lo que el libro rechazaría a fin de mes (un RUC mal digitado, una
        nota sin el comprobante que modifica, una boleta de S/ 900 sin
        cliente…) se avisa o se bloquea ahora, cuando aún es fácil corregir.
        """
        blocked = []
        for move in self:
            mode = move.company_id.l10n_pe_sire_post_check
            if not mode or mode == 'none':
                continue
            errors, warnings = move._l10n_pe_sire_book_check()
            if errors and mode == 'block':
                blocked.append('%s:\n%s' % (move.display_name, '\n'.join(
                    '  · %s' % error for error in errors)))
            elif errors or warnings:
                items = Markup().join(
                    Markup('<li>%s</li>') % text for text in errors + warnings)
                move.message_post(body=Markup('<p>%s</p><ul>%s</ul>') % (
                    _('Este comprobante no pasa las reglas del registro SIRE:')
                    if errors else _('Avisos del registro SIRE:'), items))
        if blocked:
            raise UserError(_(
                'Corrija estos comprobantes antes de publicarlos; el registro '
                'SIRE los rechazaría:\n%s', '\n'.join(blocked)))

    def _l10n_pe_sire_book_check(self):
        """(errores, avisos) del comprobante como línea del RVIE o el RCE."""
        self.ensure_one()
        code = self.l10n_latam_document_type_id.code
        if self.country_code != 'PE' or not code or self.state != 'posted' \
                or self.journal_id.l10n_pe_exclude_from_books:
            return [], []
        if self.move_type in ('out_invoice', 'out_refund'):
            if code in RVIE_EXCLUDED_DOC_TYPES:
                return [], []
            book, date = 'l10n_pe.sire.rvie', self.invoice_date
        elif self.move_type in ('in_invoice', 'in_refund'):
            if code in RCE_EXCLUDED_DOC_TYPES or self.l10n_pe_sire_is_non_domiciled:
                return [], []
            book, date = 'l10n_pe.sire.rce', self.date
        else:
            return [], []
        if not date:
            return [], []
        # sudo: solo se arman registros en memoria (new) para aplicar las
        # reglas; quien factura no necesita acceso al SIRE.
        period = self.env[book].sudo().new({
            'year': date.year, 'month': '%02d' % date.month,
            'company_id': self.company_id.id})
        vals = period._sire_system_line_vals(self)
        line_model = period._fields['system_line_ids'].comodel_name
        line = self.env[line_model].sudo().new(dict(vals, type_line='system'))
        return period._sire_line_errors(line), period._sire_line_warnings(line)

    @api.depends('l10n_pe_sire_nd_gross_income', 'l10n_pe_sire_nd_deduction')
    def _compute_l10n_pe_sire_nd_net_income(self):
        for move in self:
            move.l10n_pe_sire_nd_net_income = (
                move.l10n_pe_sire_nd_gross_income - move.l10n_pe_sire_nd_deduction)


class ResCountry(models.Model):
    _inherit = 'res.country'

    l10n_pe_sire_country_code = fields.Char(
        string='Código SUNAT (SIRE)', size=4,
        help='Tabla 16 del anexo 1 de la R.S. 112-2021/SUNAT: país en el registro '
             'de compras de no domiciliados.')

    @api.model
    def _l10n_pe_sire_load_country_codes(self):
        """Asigna el código de la tabla 16 sin pisar el que se haya corregido a mano."""
        for country in self.search([('code', 'in', list(SIRE_COUNTRY_CODES))]):
            if not country.l10n_pe_sire_country_code:
                country.l10n_pe_sire_country_code = SIRE_COUNTRY_CODES[country.code]
