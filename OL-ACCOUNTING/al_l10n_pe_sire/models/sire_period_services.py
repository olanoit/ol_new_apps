"""Servicios SIRE del periodo además de la propuesta y su envío.

Endpoints, parámetros y códigos de proceso tomados de los manuales
oficiales de servicios web API SIRE v22 (``docs/sire/SERVICIOS_RVIE.md`` y
``docs/sire/SERVICIOS_RCE.md``). Lo que el manual deja ambiguo se marca
en cada método.
"""
import base64
import io
import zipfile

from odoo import _, fields, models
from odoo.exceptions import UserError

from .sire_api import (
    SIRE_UPLOAD_ADJUSTMENT_ENDPOINT, SIRE_UPLOAD_ENDPOINT, SIRE_UPLOAD_PRELIMINARY_ENDPOINT,
)

#: Tipos de resumen de inconsistencias (5.21 / 5.36): el manual solo dice
#: «1, 2, 3 ó 4», sin describirlos, así que se piden y adjuntan los cuatro.
INCONSISTENCY_SUMMARY_TYPES = ('1', '2', '3', '4')


class L10nPeSirePeriodServices(models.AbstractModel):
    _inherit = 'l10n_pe.sire.mixin'

    receipt_name = fields.Char(
        string='Nombre de la constancia', copy=False,
        help='Nombre del PDF de la constancia de recepción en SUNAT. Se deduce '
             'del registro; indíquelo solo si la descarga no la encuentra.')

    # ------------------------------------------------------------------
    # A definir por cada libro
    # ------------------------------------------------------------------

    def _sire_inconsistency_summary_request(self, token, summary_type):
        """Respuesta JSON del resumen de inconsistencias (5.21 RVIE / 5.36 RCE)."""
        raise NotImplementedError()

    def _sire_receipt_request(self, token, name):
        """Respuesta de la constancia de recepción (5.26 RVIE / 5.49 RCE)."""
        raise NotImplementedError()

    def _sire_preliminary_inconsistencies_path(self):
        """Ruta del reporte de inconsistencias del preliminar registrado (5.24 / 5.42)."""
        raise NotImplementedError()

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _sire_next_correlative(self, kind):
        """Correlativo de dos dígitos de los archivos de un mismo tipo en el periodo."""
        count = self.env['l10n_pe.sire.operation'].search_count([
            ('res_model', '=', self._name), ('res_id', '=', self.id), ('kind', '=', kind)])
        return '%02d' % (count + 1)

    def _sire_le_name(self, book_code, opportunity, correlative='', has_data=True):
        """Nombre de libro electrónico (tabla 6 RVIE / tabla 13.1 RCE).

        ``LE`` + RUC + AAAAMM + ``00`` + libro + oportunidad + operaciones
        (1, empresa operativa) + contenido + moneda + ``2`` (SIRE) + correlativo.
        """
        ruc = self._sire_check_ruc(self.company_id)
        currency = '2' if self.company_id.currency_id.name == 'USD' else '1'
        return 'LE%s%s00%s%s1%s%s2%s.txt' % (
            ruc, self._sire_period(), book_code, opportunity,
            '1' if has_data else '0', currency, correlative)

    def _sire_complement_name(self, identifier, correlative):
        """Nombre de los archivos de complemento: RUC-ID-AAAAMM-NN.txt (tablas 6 y 13.2-13.3)."""
        ruc = self._sire_check_ruc(self.company_id)
        return '%s-%s-%s-%s.txt' % (ruc, identifier, self._sire_period(), correlative)

    @staticmethod
    def _sire_text(value, size=None):
        """Texto libre: la norma prohíbe «|», «/» y «\\» entre palotes."""
        text = ' '.join(str(value or '').replace('|', ' ').replace('/', ' ')
                        .replace('\\', ' ').split())
        return text[:size] if size else text

    def _sire_optional_amount(self, value):
        return self._sire_fmt_amount(value) if value else ''

    def _sire_move_period_record(self, move):
        """Periodo virtual del asiento: para calcular sus columnas como en su mes.

        Es el periodo del registro: en compras el de anotación (fecha
        contable), como el RCE; en ventas el de emisión. Antes el anexo 13
        tomaba la emisión también en compras y una factura de enero anotada
        en febrero salía con periodo de enero.
        """
        if move.is_purchase_document(include_receipts=True):
            date = move.date or move.invoice_date
        else:
            date = move.invoice_date or move.date
        return self.new({'year': date.year, 'month': '%02d' % date.month,
                         'company_id': move.company_id.id})

    def _sire_zip_txt(self, txt_name, lines):
        """ZIP con un TXT separado por barras: lo que exigen todas las cargas TUS."""
        content = '\n'.join('|'.join(str(col) for col in row) for row in lines)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(txt_name, content.encode('utf-8'))
        return buffer.getvalue()

    def _sire_tus_upload(self, kind, txt_name, rows, process_code, endpoint,
                         ticket_required=True):
        """Sube ``rows`` como TXT en ZIP por TUS y registra la operación."""
        self.ensure_one()
        self._sire_check_can_submit()
        if not rows:
            raise UserError(_('No hay comprobantes que enviar.'))
        zip_name = txt_name.rsplit('.', 1)[0] + '.zip'
        payload = self._sire_zip_txt(txt_name, rows)
        token = self._sire_get_token(self.company_id)
        ticket = self._sire_upload(token, zip_name, payload, {
            'filename': zip_name,
            'filetype': 'application/zip',
            'numRuc': self._sire_check_ruc(self.company_id.root_id),
            'perTributario': self._sire_period(),
            'codOrigenEnvio': '2',
            'codProceso': process_code,
            'codTipoCorrelativo': '01',
            'nomArchivoImportacion': zip_name,
            'codLibro': self._sire_upload_book_code(),
        }, endpoint=endpoint, ticket_required=ticket_required)
        return self._sire_new_operation(
            kind, ticket=ticket, filename=zip_name, content=payload,
            detail=_('%s comprobantes enviados.', len(rows)))

    def _sire_json_call(self, kind, method, endpoint, payload=None, params=None, detail=None):
        """Llamada síncrona (SUNAT responde «OK»), registrada como operación."""
        self.ensure_one()
        self._sire_check_can_submit()
        token = self._sire_get_token(self.company_id)
        response = self._sire_send_json(method, token, endpoint, payload, params=params)
        ticket = self._sire_ticket_from(response)
        return self._sire_new_operation(kind, ticket=ticket, detail=detail)

    def _sire_call_per_line(self, lines, call, label):
        """Una llamada a SUNAT por comprobante, cada una por su cuenta.

        Si falla la tercera, las dos primeras ya están hechas en SUNAT (la
        exclusión, por ejemplo, es irreversible). Antes el error deshacía en
        Odoo su registro y el historial no decía que se habían enviado. Ahora
        se queda lo hecho, se detiene en el primer error y se avisa.
        """
        self.ensure_one()
        done = 0
        for line in lines:
            try:
                with self.env.cr.savepoint():
                    call(line)
            except Exception as error:  # noqa: BLE001 — lo hecho en SUNAT no se deshace
                message = _(
                    '%(label)s: %(done)s de %(total)s comprobantes hechos en SUNAT. '
                    'Falló %(doc)s: %(error)s. Los siguientes no se enviaron.',
                    label=label, done=done, total=len(lines),
                    doc='%s %s-%s' % (line.tipo_cp, line.serie_cp, line.nro_cp),
                    error=str(error))
                self._sire_warn(message)
                return {
                    'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'title': label, 'message': message,
                               'type': 'warning', 'sticky': True},
                }
            done += 1
        return True

    @staticmethod
    def _sire_lines_cp(lines):
        """Comprobantes en el formato de los servicios de eliminación (5.13–5.16)."""
        return [{
            'codCar': line.car_sunat or '',
            'codTipoCDP': line.tipo_cp or '',
            'numSerieCDP': line.serie_cp or '',
            'numCDP': line.nro_cp or '',
        } for line in lines]

    def _sire_lines_of(self, lines):
        """Comprueba que las líneas son de este periodo."""
        self.ensure_one()
        if not lines:
            raise UserError(_('Seleccione al menos una línea.'))
        if lines.sire_id != self:
            raise UserError(_('Las líneas seleccionadas son de otro periodo.'))
        return lines

    # ------------------------------------------------------------------
    # Fase 1: reportes, inconsistencias y constancia
    # ------------------------------------------------------------------

    def action_sire_inconsistency_summary(self):
        """Resumen de inconsistencias de los cuatro tipos, en el historial."""
        self.ensure_one()
        self._sire_check_can_submit()
        token = self._sire_get_token(self.company_id)
        rows = []
        for summary_type in INCONSISTENCY_SUMMARY_TYPES:
            data = self._sire_json(self._sire_inconsistency_summary_request(token, summary_type))
            quantity, amount = data.get('cantidad') or {}, data.get('monto') or {}
            rows.append(_(
                'Tipo %(type)s: %(total)s CP (S/ %(amount)s) · con relevancia fiscal '
                '%(rel)s %% · sin relevancia %(norel)s %% · sin validar %(none)s %%',
                type=summary_type, total=quantity.get('total', 0),
                amount=amount.get('total', 0),
                rel=quantity.get('porcentajeRelFiscal', 0),
                norel=quantity.get('porcentajeNoRelFiscal', 0),
                none=quantity.get('porcentajeSinValidaciones', 0)))
        return self._sire_new_operation('inconsistencies', detail='\n'.join(rows))

    def _sire_receipt_names(self):
        """Nombres posibles de la constancia de recepción.

        El manual no dice de dónde sale el nombre: los ejemplos son el del
        registro generado con extensión PDF (``LE…140400011112.pdf`` en el
        RVIE, ``LE…080400011022.pdf`` en el RCE). Se prueban las
        combinaciones de indicadores (operaciones, contenido y moneda) que
        admite la nomenclatura de los libros electrónicos.
        """
        ruc = self._sire_check_ruc(self.company_id)
        base = 'LE%s%s00%s01' % (ruc, self._sire_period(), self._sire_ple_book_code())
        if self.receipt_name:
            return [self.receipt_name]
        return ['%s%s%s%s2.pdf' % (base, operations, content, currency)
                for operations in '10' for content in '10' for currency in '12']

    def action_sire_receipt(self):
        """Descarga la constancia de recepción y la adjunta al periodo."""
        self.ensure_one()
        self._sire_check_can_submit()
        token = self._sire_get_token(self.company_id)
        errors = []
        for name in self._sire_receipt_names():
            try:
                pdf = self._sire_receipt_pdf(self._sire_receipt_request(token, name))
            except UserError as error:
                errors.append(str(error))
                continue
            if not pdf:
                continue
            attachment = self.env['ir.attachment'].create({
                'name': name, 'raw': pdf, 'res_model': self._name, 'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            self.receipt_name = name
            operation = self._sire_new_operation('receipt', detail=name)
            operation.report_ids = attachment
            self.message_post(body=_('Constancia de recepción.'), attachment_ids=attachment.ids)
            return operation
        raise UserError(_(
            'SUNAT no entregó la constancia de recepción. ¿Ya generó el registro en '
            'el portal? Si conoce el nombre exacto del archivo, indíquelo en «Nombre de '
            'la constancia».\n%s', errors[-1] if errors else ''))

    @staticmethod
    def _sire_receipt_pdf(response):
        """PDF de la respuesta: base64 (v21), lista de bytes (v22) o el PDF sin envolver."""
        if response.content[:4] == b'%PDF':
            return response.content
        try:
            data = response.json()
        except ValueError:
            return b''
        pdf = data.get('archivoPdf') if isinstance(data, dict) else None
        if isinstance(pdf, list):
            return bytes(byte % 256 for byte in pdf)
        if isinstance(pdf, str):
            return base64.b64decode(pdf)
        return b''

    def action_sire_preliminary_inconsistencies(self):
        """Reporte de inconsistencias del preliminar registrado, adjunto al periodo."""
        self.ensure_one()
        self._sire_check_can_submit()
        token = self._sire_get_token(self.company_id)
        response = self._sire_get(token, self._sire_preliminary_inconsistencies_path(),
                                  params={'cntlimite': '1000'})
        name = 'Inconsistencias_preliminar_%s_%s.txt' % (
            self._sire_book_label(), self._sire_period())
        attachment = self.env['ir.attachment'].create({
            'name': name, 'raw': response.content,
            'res_model': self._name, 'res_id': self.id,
        })
        operation = self._sire_new_operation('inconsistencies', detail=name)
        operation.report_ids = attachment
        return operation

    # ------------------------------------------------------------------
    # Fase 2: tipo de cambio
    # ------------------------------------------------------------------

    def _sire_exchange_rates(self):
        """``[(fecha, moneda, tipo de cambio)]`` de los comprobantes en moneda extranjera.

        El tipo es el del propio comprobante (el que usó la contabilidad),
        no el del día: es el que tiene que coincidir con el registro.
        """
        self.ensure_one()
        rates = {}
        for line in self.system_line_ids:
            if line.moneda in (False, '', 'PEN') or not line.tipo_cambio or not line.fecha_emision:
                continue
            rates.setdefault((line.fecha_emision, line.moneda), line.tipo_cambio)
        return sorted((date, currency, rate) for (date, currency), rate in rates.items())

    def action_sire_send_exchange_rates(self):
        """Completa en la propuesta los tipos de cambio que SUNAT no encontró."""
        self.ensure_one()
        if not self.system_line_ids:
            raise UserError(_('Despliegue primero las líneas del sistema.'))
        rates = self._sire_exchange_rates()
        if not rates:
            raise UserError(_('No hay comprobantes en moneda extranjera en el periodo.'))
        return self._sire_send_exchange_rates(rates)

    def _sire_send_exchange_rates(self, rates):
        raise NotImplementedError()

    def action_sire_open_lines(self):
        """Lista de líneas del periodo con las acciones por comprobante."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Comprobantes de %s', self.name),
            'res_model': self.sire_line_ids._name,
            'view_mode': 'list',
            'domain': [('sire_id', '=', self.id)],
            'context': {'search_default_group_type_line': 1, 'create': False},
        }

    def action_sire_open_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Otras acciones en SUNAT'),
            'res_model': 'l10n_pe.sire.action.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_res_model': self._name, 'default_res_id': self.id},
        }

    # ------------------------------------------------------------------
    # Nuevos comprobantes y ajustes posteriores (comunes a RVIE y RCE)
    # ------------------------------------------------------------------

    def _sire_new_cp_identifier(self):
        """Identificador del archivo de nuevos CP en la propuesta (CPF / CP)."""
        raise NotImplementedError()

    def _sire_adjustment_row(self, line, car_orig):
        """Fila de ajuste posterior del periodo (anexo 4 RVIE / anexo 12 RCE)."""
        raise NotImplementedError()

    def _sire_adjustment_ticket_required(self):
        return True

    def _sire_valid_system_lines(self, lines):
        """Líneas del sistema de este periodo sin observaciones de validación."""
        lines = self._sire_lines_of(lines)
        self._sire_validate_system_lines()
        invalid = lines.filtered('check_detail')
        if invalid:
            raise UserError(_(
                'Hay %(count)s comprobantes con observaciones (%(docs)s); corríjalos '
                'antes de enviarlos.', count=len(invalid),
                docs=', '.join('%s-%s' % (l.serie_cp, l.nro_cp) for l in invalid[:5])))
        return lines

    def _sire_upload_new_proposal(self, lines):
        """Agrega a la propuesta comprobantes que SUNAT no propuso (5.4 RVIE / 5.9 RCE)."""
        self.ensure_one()
        lines = self._sire_valid_system_lines(lines)
        name = self._sire_complement_name(
            self._sire_new_cp_identifier(), self._sire_next_correlative('new_proposal'))
        return self._sire_tus_upload(
            'new_proposal', name, [self._sire_replacement_row(l) for l in lines],
            '1', SIRE_UPLOAD_ENDPOINT)

    def _sire_upload_new_preliminary(self, lines):
        """Agrega comprobantes al preliminar ya reemplazado (5.5 RVIE / 5.7 RCE)."""
        self.ensure_one()
        if self.submission_type != 'replace':
            raise UserError(_('SUNAT solo admite nuevos comprobantes en el preliminar '
                              'después de reemplazar la propuesta.'))
        lines = self._sire_valid_system_lines(lines)
        return self._sire_tus_upload(
            'new_preliminary', self._sire_le_name(self._sire_ple_book_code(), '02'),
            [self._sire_replacement_row(l) for l in lines],
            '4', SIRE_UPLOAD_PRELIMINARY_ENDPOINT)

    def _sire_car_orig(self, line):
        """CAR con que SUNAT anotó el comprobante (vacío si es nuevo)."""
        anotado = self.sire_line_ids.filtered(lambda l: l.car_sunat == line.car_sunat)[:1]
        return anotado.car_sunat or ''

    def _sire_upload_adjustment(self, lines):
        """Ajustes posteriores de un periodo generado en el SIRE (5.6 RVIE / 5.18 RCE).

        Tabla 8 / tabla 15: el comprobante va completo y correcto con el CAR
        del anotado; si no estaba anotado, sin CAR, y SUNAT le asigna uno.
        """
        self.ensure_one()
        if self.state != 'done' and not self.preliminary_registered:
            raise UserError(_('Los ajustes posteriores son para un periodo ya generado '
                              'en SUNAT (márquelo como realizado al generarlo).'))
        lines = self._sire_valid_system_lines(lines)
        correlative = self._sire_next_correlative('adjustment')
        operation = self._sire_tus_upload(
            'adjustment', self._sire_le_name(self._sire_ple_book_code(), '03', correlative),
            [self._sire_adjustment_row(l, self._sire_car_orig(l)) for l in lines],
            '6', SIRE_UPLOAD_ADJUSTMENT_ENDPOINT,
            ticket_required=self._sire_adjustment_ticket_required())
        operation.adjustment_kind = 'adjustment'
        return operation

    # ------------------------------------------------------------------
    # Fase 6: eliminaciones
    # ------------------------------------------------------------------

    def _sire_check_dangerous(self):
        """Las eliminaciones en SUNAT solo las hace un gestor contable."""
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('Solo un responsable de contabilidad puede eliminar '
                              'información registrada en SUNAT.'))


class L10nPeSireLineServices(models.AbstractModel):
    _inherit = 'l10n_pe.sire.line.mixin'

    def _sire_period_record(self):
        if len(self.sire_id) != 1:
            raise UserError(_('Seleccione líneas de un único periodo.'))
        return self.sire_id

    def _sire_proposal_lines(self):
        """Solo las líneas de la propuesta tienen CAR de SUNAT."""
        lines = self.filtered(lambda l: l.type_line == 'sire')
        if not lines:
            raise UserError(_('Seleccione líneas de la propuesta de SUNAT (origen «SIRE»).'))
        return lines

    def _sire_system_lines(self):
        lines = self.filtered(lambda l: l.type_line == 'system')
        if not lines:
            raise UserError(_('Seleccione líneas del sistema (origen «Sistema»).'))
        return lines

    def action_sire_add_to_proposal(self):
        lines = self._sire_system_lines()
        return lines._sire_period_record()._sire_upload_new_proposal(lines)

    def action_sire_add_to_preliminary(self):
        lines = self._sire_system_lines()
        return lines._sire_period_record()._sire_upload_new_preliminary(lines)

    def action_sire_send_adjustment(self):
        lines = self._sire_system_lines()
        return lines._sire_period_record()._sire_upload_adjustment(lines)

    def action_sire_delete_from_proposal(self):
        lines = self._sire_proposal_lines()
        return lines._sire_period_record()._sire_delete_proposal_lines(lines)

    def action_sire_delete_from_preliminary(self):
        lines = self._sire_proposal_lines()
        return lines._sire_period_record()._sire_delete_preliminary_lines(lines)
