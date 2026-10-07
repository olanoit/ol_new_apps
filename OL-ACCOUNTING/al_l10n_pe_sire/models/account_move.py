from odoo import api, fields, models

from .sire_country_codes import SIRE_COUNTRY_CODES

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

    l10n_pe_sire_goods_class = fields.Selection(
        selection=[
            ('1', '1 - Mercadería, materia prima, suministro, envases y embalajes'),
            ('2', '2 - Activo fijo'),
            ('3', '3 - Otros activos no considerados en 1 y 2'),
            ('4', '4 - Gastos de educación, recreación, salud, culturales y otros'),
            ('5', '5 - Otros gastos no incluidos en 4'),
        ],
        string='Clasificación de bienes y servicios',
        help='Tabla 30 SUNAT — columna "Clasif de Bss y Sss" del RCE. Obligatoria '
             'para contribuyentes con ingresos mayores a 1500 UIT.')

    # --- Registro de compras de no domiciliados (anexo 9, R.S. 040-2022).
    # Nombres propios: l10n_pe_reports (Enterprise) tiene campos parecidos
    # y este módulo funciona sin él. ---
    l10n_pe_sire_is_non_domiciled = fields.Boolean(
        string='Proveedor no domiciliado', compute='_compute_l10n_pe_sire_is_non_domiciled',
        store=True, readonly=False,
        help='Va al registro de compras de no domiciliados del SIRE (8.5) y no al RCE.')
    l10n_pe_sire_nd_credit_move_id = fields.Many2one(
        'account.move', string='Documento que sustenta el crédito fiscal',
        check_company=True,
        domain="[('move_type', 'in', ('in_invoice', 'in_refund')), ('state', '=', 'posted'),"
               " ('company_id', '=', company_id)]",
        help='DUA, liquidación de compra o formulario de pago del IGV (tipos 00, 46, 50-53).')
    l10n_pe_sire_nd_igv_withholding = fields.Monetary(
        string='Retención del IGV', currency_field='company_currency_id')
    l10n_pe_sire_nd_beneficiary_vat = fields.Char(string='Id. fiscal del beneficiario efectivo')
    l10n_pe_sire_nd_beneficiary_name = fields.Char(string='Beneficiario efectivo')
    l10n_pe_sire_nd_beneficiary_country_id = fields.Many2one(
        'res.country', string='País del beneficiario efectivo')
    l10n_pe_sire_nd_link = fields.Selection(ND_LINK_SELECTION, string='Vinculación económica')
    l10n_pe_sire_nd_gross_income = fields.Monetary(
        string='Renta bruta', currency_field='company_currency_id')
    l10n_pe_sire_nd_deduction = fields.Monetary(
        string='Deducción o costo de enajenación', currency_field='company_currency_id')
    l10n_pe_sire_nd_net_income = fields.Monetary(
        string='Renta neta', currency_field='company_currency_id',
        compute='_compute_l10n_pe_sire_nd_net_income', store=True, readonly=False)
    l10n_pe_sire_nd_withholding_rate = fields.Float(string='Tasa de retención (%)', digits=(5, 2))
    l10n_pe_sire_nd_withheld_tax = fields.Monetary(
        string='Impuesto retenido', currency_field='company_currency_id')
    l10n_pe_sire_nd_agreement = fields.Selection(
        ND_AGREEMENT_SELECTION, string='Convenio de doble imposición', default='00')
    l10n_pe_sire_nd_exemption = fields.Selection(
        ND_EXEMPTION_SELECTION, string='Exoneración aplicada')
    l10n_pe_sire_nd_income_type = fields.Selection(ND_INCOME_SELECTION, string='Tipo de renta')
    l10n_pe_sire_nd_service_modality = fields.Selection(
        ND_MODALITY_SELECTION, string='Modalidad del servicio')
    l10n_pe_sire_nd_art76 = fields.Boolean(
        string='Aplica el penúltimo párrafo del art. 76 de la LIR')

    @api.depends('partner_id.commercial_partner_id.country_id', 'l10n_latam_document_type_id',
                 'move_type')
    def _compute_l10n_pe_sire_is_non_domiciled(self):
        for move in self:
            country = move.partner_id.commercial_partner_id.country_id
            move.l10n_pe_sire_is_non_domiciled = bool(
                move.move_type in ('in_invoice', 'in_refund')
                and move.l10n_latam_document_type_id.code in ('00', '91', '97', '98')
                and country and country.code != 'PE')

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
