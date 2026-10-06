"""Registro de compras de no domiciliados en el SIRE (anexo 9, R.S. 040-2022).

Se carga por servicio web (manual de Compras v22, 5.5, ``codProceso`` 56)
cuando la propuesta del RCE ya se aceptó o el preliminar está registrado;
sus ajustes posteriores van con el anexo 12 (8.5, ``codProceso`` 60).
"""
from odoo import _, fields, models
from odoo.exceptions import UserError

from .sire_api import SIRE_UPLOAD_ADJUSTMENT_ENDPOINT, SIRE_UPLOAD_PRELIMINARY_ENDPOINT

ND_DOC_TYPES = ('00', '91', '97', '98')
#: Tipos del documento que sustenta el crédito fiscal (campo 10).
ND_CREDIT_DOC_TYPES = ('00', '46', '50', '51', '52', '53')


class L10nPeSireRceNdLine(models.Model):
    _name = 'l10n_pe.sire.rce.nd.line'
    _description = 'SIRE — Línea de no domiciliados'
    _order = 'fecha_emision, serie_cp, nro_cp, id'

    sire_id = fields.Many2one('l10n_pe.sire.rce', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='sire_id.company_id', store=True)
    move_id = fields.Many2one('account.move', string='Comprobante', readonly=True)
    fecha_emision = fields.Date(string='Fecha de emisión', readonly=True)
    tipo_cp = fields.Char(string='Tipo CP', readonly=True)
    serie_cp = fields.Char(string='Serie', readonly=True)
    nro_cp = fields.Char(string='Número', readonly=True)
    valor_adquisicion = fields.Float(string='Valor de la adquisición', digits=(16, 2), readonly=True)
    otros_conceptos = fields.Float(string='Otros conceptos', digits=(16, 2), readonly=True)
    total_cp = fields.Float(string='Total CP', digits=(16, 2), readonly=True)
    moneda = fields.Char(string='Moneda', readonly=True)
    tipo_cambio = fields.Float(string='Tipo de cambio', digits=(12, 3), readonly=True)
    pais = fields.Char(string='País (SUNAT)', readonly=True)
    razon_social = fields.Char(string='No domiciliado', readonly=True)
    nro_identificacion = fields.Char(string='Identificación', readonly=True)
    convenio = fields.Char(string='Convenio', readonly=True)
    tipo_renta = fields.Char(string='Tipo de renta', readonly=True)
    car_sunat = fields.Char(string='CAR SUNAT',
                            help='CAR con que SUNAT anotó el comprobante; solo para ajustes.')
    check_detail = fields.Text(string='Observaciones', readonly=True)

    def action_sire_send_nd_adjustment(self):
        if len(self.sire_id) != 1:
            raise UserError(_('Seleccione líneas de un único periodo.'))
        return self.sire_id._sire_upload_nd_adjustment(self)


class L10nPeSireRce(models.Model):
    _inherit = 'l10n_pe.sire.rce'

    nd_line_ids = fields.One2many(
        'l10n_pe.sire.rce.nd.line', 'sire_id', string='No domiciliados', copy=False)
    count_nd = fields.Integer(string='Comprobantes de no domiciliados', compute='_compute_count_nd')
    count_nd_invalid = fields.Integer(
        string='No domiciliados con observaciones', compute='_compute_count_nd')

    def _compute_count_nd(self):
        for record in self:
            record.count_nd = len(record.nd_line_ids)
            record.count_nd_invalid = len(record.nd_line_ids.filtered('check_detail'))

    def _sire_nd_moves(self):
        return self.env['account.move'].search(
            self._sire_system_domain(('in_invoice', 'in_refund'), 'date') + [
                ('l10n_pe_sire_is_non_domiciled', '=', True),
            ], order='invoice_date, name')

    def _sire_nd_amounts(self, move):
        """(valor de la adquisición, otros conceptos, total) en soles, con signo."""
        amounts = self._sire_amount_split(move)
        sign = self._sire_move_sign(move)
        if move.state == 'cancel':
            return 0.0, 0.0, 0.0
        value = sum(amounts[key] for key in (
            'taxed', 'taxed_dgng', 'taxed_dng', 'exonerated', 'unaffected', 'export',
            'ivap_base'))
        others = sum(amounts[key] for key in ('other_taxes', 'isc', 'icbper'))
        return (round(sign * value, 2), round(sign * others, 2),
                round(sign * abs(move.amount_total_signed), 2))

    def action_sire_load_nd(self):
        """Despliega los comprobantes de no domiciliados del periodo y los valida."""
        self.ensure_one()
        commands = [(5, 0, 0)]
        for move in self._sire_nd_moves():
            partner = move.commercial_partner_id
            serie, folio = self._sire_serie_folio(move)
            value, others, total = self._sire_nd_amounts(move)
            commands.append((0, 0, {
                'move_id': move.id,
                'fecha_emision': move.invoice_date,
                'tipo_cp': move.l10n_latam_document_type_id.code or '',
                'serie_cp': serie,
                'nro_cp': folio,
                'valor_adquisicion': value,
                'otros_conceptos': others,
                'total_cp': total,
                'moneda': move.currency_id.name,
                'tipo_cambio': self._sire_move_rate(move),
                'pais': partner.country_id.l10n_pe_sire_country_code or '',
                'razon_social': partner.name or '',
                'nro_identificacion': partner.vat or '',
                'convenio': move.l10n_pe_sire_nd_agreement or '',
                'tipo_renta': move.l10n_pe_sire_nd_income_type or '',
            }))
        self.nd_line_ids = commands
        self._sire_validate_nd_lines()
        return True

    def _sire_nd_line_errors(self, line):
        """Campos obligatorios y tablas del anexo 9."""
        errors = []
        if line.tipo_cp not in ND_DOC_TYPES:
            errors.append(_('El tipo %s no es de no domiciliados (00, 91, 97 o 98).', line.tipo_cp))
        if not line.nro_cp:
            errors.append(_('Falta el número del comprobante.'))
        if not line.fecha_emision:
            errors.append(_('Falta la fecha de emisión.'))
        if line.moneda != 'PEN' and not line.tipo_cambio:
            errors.append(_('Falta el tipo de cambio para %s.', line.moneda))
        if not line.pais:
            errors.append(_('El país del proveedor no tiene código SUNAT (tabla 16).'))
        if not line.razon_social:
            errors.append(_('Falta la razón social del no domiciliado.'))
        if not line.nro_identificacion:
            errors.append(_('Falta el número de identificación del no domiciliado.'))
        if not line.convenio:
            errors.append(_('Indique el convenio para evitar la doble imposición (tabla 18).'))
        if not line.tipo_renta:
            errors.append(_('Indique el tipo de renta (tabla 19).'))
        credit = line.move_id.l10n_pe_sire_nd_credit_move_id
        if credit and credit.l10n_latam_document_type_id.code not in ND_CREDIT_DOC_TYPES:
            errors.append(_('El documento que sustenta el crédito fiscal debe ser de tipo '
                            '00, 46, 50, 51, 52 o 53.'))
        return errors

    def _sire_validate_nd_lines(self):
        by_detail = {}
        for line in self.nd_line_ids:
            detail = '\n'.join(self._sire_nd_line_errors(line)) or False
            by_detail.setdefault(detail, []).append(line.id)
        for detail, ids in by_detail.items():
            self.env['l10n_pe.sire.rce.nd.line'].browse(ids).write({'check_detail': detail})
        return self.nd_line_ids.filtered('check_detail')

    def _sire_nd_row(self, line, car_orig=''):
        """Los 35 campos del anexo 9 (el 35 solo en los ajustes del anexo 12)."""
        move = line.move_id
        partner = move.commercial_partner_id
        credit = move.l10n_pe_sire_nd_credit_move_id
        credit_type = credit.l10n_latam_document_type_id.code or '' if credit else ''
        credit_serie, credit_folio = self._sire_serie_folio(credit) if credit else ('', '')
        beneficiary_country = move.l10n_pe_sire_nd_beneficiary_country_id
        optional = self._sire_optional_amount
        return [
            # El periodo va como en el resto del SIRE (AAAAMM): la norma dice
            # «AAAAMM3.», una errata, y el PLE usa los mismos seis dígitos.
            self._sire_period(),
            '',
            self._sire_fmt_date(line.fecha_emision),
            line.tipo_cp,
            line.serie_cp or '',
            line.nro_cp,
            self._sire_fmt_amount(line.valor_adquisicion),
            optional(line.otros_conceptos),
            self._sire_fmt_amount(line.total_cp),
            credit_type,
            credit_serie,
            str(credit.invoice_date.year) if credit_type in ('50', '52') and credit.invoice_date else '',
            credit_folio,
            optional(move.l10n_pe_sire_nd_igv_withholding),
            line.moneda,
            self._sire_fmt_rate(line.tipo_cambio, line.moneda),
            line.pais,
            self._sire_text(line.razon_social, 100),
            self._sire_text(partner.street, 100),
            self._sire_text(line.nro_identificacion, 15),
            self._sire_text(move.l10n_pe_sire_nd_beneficiary_vat, 15),
            self._sire_text(move.l10n_pe_sire_nd_beneficiary_name, 100),
            beneficiary_country.l10n_pe_sire_country_code or '' if beneficiary_country else '',
            move.l10n_pe_sire_nd_link or '',
            optional(move.l10n_pe_sire_nd_gross_income),
            optional(move.l10n_pe_sire_nd_deduction),
            optional(move.l10n_pe_sire_nd_net_income),
            optional(move.l10n_pe_sire_nd_withholding_rate),
            optional(move.l10n_pe_sire_nd_withheld_tax),
            line.convenio,
            move.l10n_pe_sire_nd_exemption or '',
            line.tipo_renta,
            move.l10n_pe_sire_nd_service_modality or '',
            '1' if move.l10n_pe_sire_nd_art76 else '',
            car_orig,
        ]

    def _sire_nd_check(self, lines):
        invalid = lines.filtered('check_detail')
        if invalid:
            raise UserError(_('Hay %s comprobantes de no domiciliados con observaciones; '
                              'corríjalos en la factura y vuelva a desplegarlos.', len(invalid)))

    def action_sire_send_nd(self):
        """5.5: carga del registro de no domiciliados (codProceso 56)."""
        self.ensure_one()
        if not (self.submission_ticket or self.preliminary_registered):
            raise UserError(_('SUNAT admite los no domiciliados después de aceptar la '
                              'propuesta o registrar el preliminar.'))
        if not self.nd_line_ids:
            raise UserError(_('Despliegue primero los comprobantes de no domiciliados.'))
        self._sire_validate_nd_lines()
        self._sire_nd_check(self.nd_line_ids)
        return self._sire_tus_upload(
            'non_domiciled', self._sire_le_name('080500', '00'),
            [self._sire_nd_row(line) for line in self.nd_line_ids],
            '56', SIRE_UPLOAD_PRELIMINARY_ENDPOINT)

    def action_sire_export_nd(self):
        """5.39: pide a SUNAT el preliminar de no domiciliados; llega como reporte del ticket."""
        self.ensure_one()
        self._sire_check_can_submit()
        token = self._sire_get_token(self.company_id)
        response = self._sire_get(
            token, '/libros/rce/preliminar/web/nodomiciliados/%s/exportapreliminarnd'
            % self._sire_period(), params={'codTipoArchivo': '0', 'codOrigenEnvio': '2'})
        return self._sire_new_operation('export', ticket=self._sire_ticket_from(response),
                                        detail=_('Preliminar de no domiciliados'))

    def _sire_upload_nd_adjustment(self, lines):
        """Anexo 12 (8.5): ajustes de no domiciliados con el CAR del anotado en el campo 35."""
        self.ensure_one()
        if self.state != 'done' and not self.preliminary_registered:
            raise UserError(_('Los ajustes posteriores son para un periodo ya generado.'))
        self._sire_validate_nd_lines()
        self._sire_nd_check(lines)
        correlative = self._sire_next_correlative('adjustment')
        operation = self._sire_tus_upload(
            'adjustment', self._sire_le_name('080500', '03', correlative),
            [self._sire_nd_row(line, line.car_sunat or '') for line in lines],
            '60', SIRE_UPLOAD_ADJUSTMENT_ENDPOINT)
        operation.adjustment_kind = 'adjustment_nd'
        return operation
