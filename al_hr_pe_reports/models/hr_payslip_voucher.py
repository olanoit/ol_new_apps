# -*- coding: utf-8 -*-
"""Boleta de pago legal peruana (D.S. 001-98-TR) y su envío por correo.

Port v18 → v19 de ``al_hr_payroll/hr_voucher`` con tres cambios de fondo
(plan Fase 7):

* La boleta reportlab (3 formatos en disco) se rehace como **un** reporte
  QWeb-PDF adicional con el contenido mínimo del D.S. 001-98-TR (datos de
  empleador y trabajador, periodo, días/horas, conceptos por columna con
  su código SUNAT, totales, neto en letras y firmas). El PDF nativo de
  v19 (``payslip_generate_pdf``) no se toca: conviven ambos reportes.
* El correo pasa de un ``mail.mail`` armado a mano a una ``mail.template``
  con el PDF adjunto vía ``report_template_ids`` (render automático al
  enviar) y encolado por el cron de correo en el envío masivo.
* El enlace de confirmación de recepción ya no expone el id pelado
  (``/payslip_line/<id>`` en v18, falsificable por enumeración): ahora
  viaja firmado con HMAC-SHA256 derivado de ``database.secret``
  (``odoo.tools.hmac``), verificado con ``consteq``.
"""
import logging
from itertools import zip_longest

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import hmac as hmac_sign

from odoo.addons.al_hr_pe.tools import custom_round

_logger = logging.getLogger(__name__)

#: Ámbito de la firma HMAC del enlace de confirmación (no reutilizar).
VOUCHER_TOKEN_SCOPE = 'al_hr_pe_reports-boleta-confirm'


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # --- Seguimiento del envío por correo (port de v18 hr_voucher) ---
    date_send = fields.Datetime(
        string='Fecha de envío de boleta', readonly=True, copy=False,
        help='Última vez que la boleta se envió al correo del trabajador.')
    is_verified = fields.Boolean(
        string='Recepción confirmada', readonly=True, copy=False,
        help='El trabajador confirmó la recepción de su boleta desde el '
             'enlace del correo.')
    date_confirmation = fields.Datetime(
        string='Fecha de confirmación', readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Enlace de confirmación firmado
    # ------------------------------------------------------------------
    def _get_voucher_confirm_token(self):
        """Token HMAC-SHA256 del enlace de confirmación.

        Mejora vs v18: el controller público de v18 aceptaba el id del
        payslip sin más (cualquiera podía confirmar boletas ajenas por
        enumeración). El token se deriva de ``database.secret``
        (``ir.config_parameter``) vía ``odoo.tools.hmac``, como los
        enlaces públicos del core (digest, mail_group…).
        """
        self.ensure_one()
        return hmac_sign(self.env(su=True), VOUCHER_TOKEN_SCOPE,
                         str(self.id))

    def _get_voucher_confirm_url(self):
        """URL absoluta del enlace «Confirmar recepción» del correo."""
        self.ensure_one()
        return '%s/boleta/confirmar/%s/%s' % (
            self.get_base_url(), self.id, self._get_voucher_confirm_token())

    # ------------------------------------------------------------------
    # Datos del reporte QWeb
    # ------------------------------------------------------------------
    @api.model
    def _voucher_fallback(self, param_value, xmlids):
        """Config del parámetro si existe; si no, los xml ids de al_hr_pe
        (así la boleta funciona recién instalado el módulo, sin códigos
        hardcodeados: todo es configurable en Parámetros Principales)."""
        if param_value:
            return param_value
        found = self.env['hr.salary.rule.category']
        for xmlid in xmlids:
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec:
                found |= rec
        return found

    def _voucher_lines(self, categories):
        """Líneas de la boleta cuyas categorías caen en ``categories``,
        con importe distinto de cero, como dicts listos para el QWeb
        (importes en valor absoluto: la columna ya dice el signo)."""
        self.ensure_one()
        result = []
        for line in self.line_ids:
            if line.category_id not in categories or not line.total:
                continue
            result.append({
                'codigo': line.salary_rule_id.sunat_code or '',
                'nombre': line.name or line.salary_rule_id.name or '',
                'importe': custom_round(abs(line.total)),
            })
        return result

    @api.model
    def _voucher_split_hours(self, hours):
        """(horas, minutos) enteros a partir de horas decimales."""
        total_minutes = int(custom_round((hours or 0.0) * 60, 0))
        return total_minutes // 60, total_minutes % 60

    def _get_voucher_report_data(self):
        """Diccionario con todo lo que pinta el QWeb de la boleta.

        Contenido mínimo del D.S. 001-98-TR, art. 1 (remite al registro
        de planillas, D.S. 001-98-TR arts. 13-14): datos del empleador y
        del trabajador, días y horas trabajados, conceptos percibidos y
        descontados con sus códigos, aportes del empleador, neto y
        firmas.
        """
        self.ensure_one()
        Param = self.env['hr.main.parameter']
        param = Param.get_main_parameter(self.company_id)
        version = self.version_id
        employee = self.employee_id

        # --- Días y horas (work entry types clasificados en parámetros,
        # con fallback a los conceptos PE de al_hr_pe) ---
        WdType = self.env['hr.work.entry.type']

        def wd_types(param_value, xmlids):
            if param_value:
                return param_value
            types = WdType.browse()
            for xmlid in xmlids:
                rec = self.env.ref(xmlid, raise_if_not_found=False)
                if rec:
                    types |= rec
            return types

        # v18 sumaba DOM (descanso semanal) dentro de días laborados
        # (get_dlabs): se conserva en el fallback.
        wd_dlab = wd_types(param.wd_dlab,
                           ['al_hr_pe.wd_DLAB', 'al_hr_pe.wd_DOM'])
        wd_dnlab = wd_types(param.wd_dnlab, ['al_hr_pe.wd_FAL'])
        wd_dsub = wd_types(param.wd_dsub,
                           ['al_hr_pe.wd_SENF', 'al_hr_pe.wd_SMAR'])
        wd_ext = wd_types(param.wd_ext, [
            'al_hr_pe.wd_HE25', 'al_hr_pe.wd_HE35', 'al_hr_pe.wd_HE100'])
        wd_dvac = wd_types(param.wd_dvac, ['al_hr_pe.wd_DVAC'])

        def wd_sum(types, field='number_of_days'):
            lines = self.worked_days_line_ids.filtered(
                lambda wd: wd.work_entry_type_id in types)
            return sum(lines.mapped(field))

        dias_laborados = wd_sum(wd_dlab)
        dias_subsidiados = wd_sum(wd_dsub)
        dias_vacaciones = wd_sum(wd_dvac)
        # Convención v18: «no laborados» agrupa faltas + vacaciones +
        # subsidios (todo lo que no fue jornada efectiva).
        dias_no_laborados = (wd_sum(wd_dnlab) + dias_vacaciones
                             + dias_subsidiados)
        h_ord, m_ord = self._voucher_split_hours(
            wd_sum(wd_dlab, 'number_of_hours'))
        h_ext, m_ext = self._voucher_split_hours(
            wd_sum(wd_ext, 'number_of_hours'))

        # --- Conceptos por categoría (parámetros o xml ids de al_hr_pe;
        # plan §5.2: nada de códigos de regla hardcodeados) ---
        ingresos = self._voucher_lines(self._voucher_fallback(
            param.income_categories, ['al_hr_pe.ING']))
        # Columna «Descuentos» de la boleta legal: aportes del trabajador
        # (ONP/AFP, 5ta…) primero y luego descuentos al neto (orden v18).
        aportes_trabajador = self._voucher_lines(self._voucher_fallback(
            param.contributions_categories, ['al_hr_pe.APOR_TRA']))
        descuentos_neto = self._voucher_lines(self._voucher_fallback(
            param.discounts_categories, ['al_hr_pe.DES_NET']))
        descuentos = aportes_trabajador + descuentos_neto
        aportes_empleador = self._voucher_lines(self._voucher_fallback(
            param.contributions_emp_categories, ['al_hr_pe.APOR_EMP']))

        total_ingresos = custom_round(
            sum(l['importe'] for l in ingresos))
        total_descuentos = custom_round(
            sum(l['importe'] for l in descuentos))
        total_aportes = custom_round(
            sum(l['importe'] for l in aportes_empleador))

        # --- Neto: regla configurada en parámetros o el net_wage nativo ---
        neto = 0.0
        if param.net_to_pay_sr_id:
            net_lines = self.line_ids.filtered(
                lambda l: l.salary_rule_id == param.net_to_pay_sr_id)
            neto = sum(net_lines.mapped('total'))
        if not neto:
            neto = self.net_wage
        neto = custom_round(neto)
        neto_letras = 'SON: %s SOLES' % param.number_to_letter(neto)

        # --- Situación / cese (port de la lógica v18: la boleta marca
        # BAJA solo si el cese cae dentro del periodo) ---
        fecha_cese = False
        cese = version.contract_date_end
        if cese and self.date_from <= cese <= self.date_to:
            fecha_cese = cese
        # TODO(fase7-revisar): v18 comparaba situation_id.name == 'BAJA'
        # (frágil); aquí la situación mostrada es el catálogo T15 y la
        # condición de baja se deduce de la fecha de cese del periodo.
        situacion = 'BAJA' if fecha_cese else (
            version.situation_id.name or 'ACTIVO O SUBSIDIADO')

        # --- Suspensiones de labores del periodo (T21), agrupadas ---
        suspensiones = []
        if self.periodo_id:
            grouped = self.env['hr.work.suspension']._read_group(
                domain=[('periodo_id', '=', self.periodo_id.id),
                        ('employee_id', '=', employee.id)],
                groupby=['suspension_type_id'],
                aggregates=['days:sum'])
            suspensiones = [{
                'codigo': stype.code or '',
                'motivo': stype.name or '',
                'dias': days,
            } for stype, days in grouped]

        # Filas del cuadro de 3 columnas (ingresos | descuentos |
        # aportes del empleador), alineadas con zip_longest.
        filas = list(zip_longest(ingresos, descuentos, aportes_empleador,
                                 fillvalue=None))

        # Etiquetas de selección (el QWeb no resuelve selections crudas)
        regimen_laboral = dict(
            version._fields['l10n_pe_labor_regime'].selection).get(
            version.l10n_pe_labor_regime, '')
        condicion = dict(employee._fields['condition'].selection).get(
            employee.condition, '')

        return {
            'param': param,
            'regimen_laboral': regimen_laboral,
            'condicion': condicion,
            'fecha_ingreso': employee._get_first_contract_date()
            or version.contract_date_start,
            'fecha_cese': fecha_cese,
            'situacion': situacion,
            'dias_laborados': dias_laborados,
            'dias_no_laborados': dias_no_laborados,
            'dias_subsidiados': dias_subsidiados,
            'dias_vacaciones': dias_vacaciones,
            'horas_ordinarias': '%02d:%02d' % (h_ord, m_ord),
            'horas_sobretiempo': '%02d:%02d' % (h_ext, m_ext),
            'filas': filas,
            'total_ingresos': total_ingresos,
            'total_descuentos': total_descuentos,
            'total_aportes': total_aportes,
            'neto': neto,
            'neto_letras': neto_letras,
            'suspensiones': suspensiones,
        }

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_print_voucher(self):
        """Imprime la boleta de pago PE (reporte adicional al nativo)."""
        return self.env.ref(
            'al_hr_pe_reports.action_report_boleta_pago').report_action(self)

    def action_send_voucher_by_email(self):
        """Envía la boleta por correo al trabajador (individual o masivo).

        La plantilla adjunta el PDF vía ``report_template_ids``; el
        correo se encola (``force_send=False``) para que el envío masivo
        de un lote no bloquee la transacción (mejora vs v18, que enviaba
        síncrono uno a uno).

        TODO(fase7-revisar): v18 cifraba el PDF con el DNI del trabajador
        (reportlab ``encrypt=``). QWeb-PDF no cifra; si el cliente lo
        exige, post-procesar el adjunto con pypdf en un override de
        ``_render_qweb_pdf``.
        """
        template = self.env.ref('al_hr_pe_reports.email_template_boleta_pago')
        issues, sent = [], 0
        for slip in self:
            if slip.state not in ('validated', 'paid'):
                issues.append(self.env._(
                    '%(employee)s: la boleta no está confirmada.',
                    employee=slip.employee_id.name))
                continue
            if not slip.employee_id.work_email:
                issues.append(self.env._(
                    '%(employee)s: sin correo laboral.',
                    employee=slip.employee_id.name))
                continue
            try:
                template.send_mail(
                    slip.id, force_send=False,
                    email_layout_xmlid='mail.mail_notification_light')
                slip.date_send = fields.Datetime.now()
                sent += 1
            except Exception:
                _logger.exception(
                    'Falló el envío de la boleta %s', slip.display_name)
                issues.append(self.env._(
                    '%(employee)s: error al generar o encolar el correo.',
                    employee=slip.employee_id.name))
        if not sent and not issues:
            raise UserError(self.env._('No hay boletas para enviar.'))
        if issues:
            message = self.env._(
                'Boletas encoladas: %(sent)s. No se pudieron enviar:\n%(issues)s',
                sent=sent, issues='\n'.join(issues))
            notif_type = 'warning'
        else:
            message = self.env._(
                'Se encolaron %(sent)s boletas; saldrán con el correo '
                'programado.', sent=sent)
            notif_type = 'success'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Envío de boletas'),
                'message': message,
                'type': notif_type,
                'sticky': bool(issues),
            },
        }


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def _get_voucher_slips(self):
        self.ensure_one()
        slips = self.slip_ids.filtered(
            lambda s: s.state in ('validated', 'paid'))
        if not slips:
            raise UserError(self.env._(
                'El lote no tiene boletas confirmadas o pagadas.'))
        return slips

    def action_print_vouchers(self):
        """Imprime en un solo PDF las boletas PE del lote."""
        slips = self._get_voucher_slips()
        return self.env.ref(
            'al_hr_pe_reports.action_report_boleta_pago').report_action(slips)

    def action_send_vouchers_by_email(self):
        """Envía por correo las boletas PE de todo el lote."""
        return self._get_voucher_slips().action_send_voucher_by_email()
