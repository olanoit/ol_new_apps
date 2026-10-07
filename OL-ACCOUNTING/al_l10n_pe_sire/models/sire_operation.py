import logging
from datetime import timedelta


from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .sire_mixin import (
    SIRE_POLL_DELAYS, SIRE_POLL_MAX_ATTEMPTS, TICKET_FAILED_STATES,
    TICKET_FINAL_STATES, TICKET_STATES,
)

_logger = logging.getLogger(__name__)

#: Operaciones con SUNAT además de la propuesta y su envío. Cada una deja
#: aquí su ticket, el archivo enviado y los reportes que SUNAT devuelve.
OPERATION_KINDS = [
    ('exchange_rate', 'Tipo de cambio masivo'),
    ('exchange_rate_one', 'Tipo de cambio de un comprobante'),
    ('non_domiciled', 'Carga de no domiciliados'),
    ('complement', 'Datos complementarios de la propuesta'),
    ('include_exclude', 'Incluir o excluir de la propuesta'),
    ('new_proposal', 'Nuevos comprobantes en la propuesta'),
    ('new_preliminary', 'Nuevos comprobantes en el preliminar'),
    ('adjustment', 'Ajustes posteriores'),
    ('adjustment_previous', 'Ajustes posteriores de periodos anteriores'),
    ('adjustment_send', 'Envío de ajustes posteriores'),
    ('withdraw', 'Exclusión definitiva'),
    ('delete_proposal', 'Eliminar comprobantes de la propuesta'),
    ('delete_preliminary', 'Eliminar comprobantes del preliminar'),
    ('delete_replacement', 'Eliminar el reemplazo de la propuesta'),
    ('delete_registered', 'Eliminar el preliminar'),
    ('fiscal_credit', 'Crédito fiscal y prorrata'),
    ('export', 'Exportación de SUNAT'),
    ('inconsistencies', 'Resumen de inconsistencias'),
    ('receipt', 'Constancia de recepción'),
]


class L10nPeSireOperation(models.Model):
    """Una llamada a SUNAT sobre un periodo SIRE y lo que devolvió."""
    _name = 'l10n_pe.sire.operation'
    _description = 'Operación SIRE'
    _check_company_auto = True
    _order = 'id desc'

    name = fields.Char(string='Operación', compute='_compute_name', store=True)
    kind = fields.Selection(OPERATION_KINDS, string='Tipo', required=True, readonly=True)
    res_model = fields.Char(string='Modelo del periodo', required=True, readonly=True, index=True)
    res_id = fields.Many2oneReference(
        string='Periodo', model_field='res_model', required=True, readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True, index=True,
        default=lambda self: self.env.company)
    user_id = fields.Many2one(
        'res.users', string='Usuario', readonly=True, default=lambda self: self.env.user)
    date = fields.Datetime(string='Fecha', readonly=True, default=fields.Datetime.now)
    state = fields.Selection(
        selection=[('sent', 'Enviada'), ('done', 'Terminada'), ('error', 'Con errores')],
        string='Estado', default='sent', readonly=True)
    ticket = fields.Char(string='Ticket', readonly=True, index=True)
    ticket_state = fields.Selection(TICKET_STATES, string='Estado del ticket', readonly=True)
    detail = fields.Text(string='Detalle', readonly=True)
    file = fields.Binary(string='Archivo enviado', readonly=True, attachment=True)
    filename = fields.Char(string='Nombre del archivo', readonly=True)
    report_ids = fields.Many2many(
        'ir.attachment', string='Reportes de SUNAT', readonly=True,
        help='Archivos que SUNAT dejó en el ticket: inconsistencias, exportaciones…')
    poll_next_date = fields.Datetime(
        string='Próxima consulta', readonly=True, copy=False, index=True)
    poll_attempts = fields.Integer(string='Consultas', readonly=True, copy=False)
    # --- Ajustes posteriores del RCE: se cargan y luego se envían (5.19-5.28) ---
    adjustment_kind = fields.Selection(
        selection=[('adjustment', 'Del periodo'), ('adjustment_nd', 'No domiciliados'),
                   ('adjustment_previous', 'Periodos anteriores al SIRE')],
        string='Tipo de ajuste', readonly=True)
    adjustment_number = fields.Char(
        string='Número de ajuste posterior',
        help='Lo asigna SUNAT a cada carga de ajustes; se busca solo y, si no '
             'aparece, se indica aquí antes de enviar.')
    adjustment_sent = fields.Boolean(string='Ajustes enviados', readonly=True)
    can_send_adjustment = fields.Boolean(compute='_compute_can_send_adjustment')

    @api.depends('kind', 'ticket')
    def _compute_name(self):
        labels = dict(OPERATION_KINDS)
        for operation in self:
            operation.name = ' · '.join(filter(None, [labels.get(operation.kind), operation.ticket]))

    @api.depends('kind', 'res_model', 'state', 'adjustment_sent')
    def _compute_can_send_adjustment(self):
        for operation in self:
            operation.can_send_adjustment = (
                operation.res_model == 'l10n_pe.sire.rce'
                and operation.kind in ('adjustment', 'adjustment_previous')
                and operation.state == 'done' and not operation.adjustment_sent)

    #: Lo único que el contable corrige a mano: el número de ajuste que
    #: muestra SUNAT cuando la API no lo devuelve.
    USER_WRITABLE_FIELDS = {'adjustment_number'}

    def write(self, vals):
        # El historial de envíos es la prueba de lo enviado a SUNAT: solo lo
        # escribe el módulo (con sudo). Antes un contable podía cambiar por
        # RPC el estado, el ticket o el archivo enviado.
        if not self.env.su and set(vals) - self.USER_WRITABLE_FIELDS:
            raise AccessError(_('El historial de operaciones SIRE no se modifica a mano.'))
        return super().write(vals)

    def action_send_adjustment(self):
        self.ensure_one()
        # El botón se oculta, pero por RPC o doble clic se enviaba dos veces.
        if not self.can_send_adjustment:
            raise UserError(_('Este ajuste no se puede enviar (ya se envió o '
                              'su ticket no terminó bien).'))
        return self._period()._sire_send_adjustment(self)

    def _period(self):
        self.ensure_one()
        return self.env[self.res_model].browse(self.res_id)

    # ------------------------------------------------------------------
    # Consulta del ticket
    # ------------------------------------------------------------------

    def _schedule_poll(self, attempt=0):
        delay = SIRE_POLL_DELAYS[min(attempt, len(SIRE_POLL_DELAYS) - 1)]
        next_date = fields.Datetime.now() + timedelta(minutes=delay)
        # sudo: el historial solo lo escribe el módulo (ACL de solo lectura).
        self.sudo().write({'poll_next_date': next_date, 'poll_attempts': attempt})
        cron = self.env.ref('al_l10n_pe_sire.ir_cron_sire_operation_poll',
                            raise_if_not_found=False)
        if cron:
            # sudo: el contable no lee ir.cron, pero sí programa su consulta.
            cron_sudo = cron.sudo()
            cron_sudo._trigger(at=next_date)

    def _stop_poll(self):
        # sudo: ver _schedule_poll.
        self.sudo().write({'poll_next_date': False, 'poll_attempts': 0})

    def action_check(self):
        """Consulta el ticket y, si terminó, descarga sus reportes."""
        for operation in self:
            operation._period()._sire_check_can_submit()
            operation._check_once()
        return True

    def _check_once(self):
        self.ensure_one()
        if not self.ticket:
            self._stop_poll()
            return
        period = self._period()
        token = period._sire_get_token(period.company_id)
        register = period._sire_ticket_register(token, period._sire_period(), self.ticket)
        detail = register.get('detalleTicket') or {}
        code = period._sire_ticket_code(register)
        # sudo: el usuario consulta el ticket, pero el historial solo lo
        # escribe el módulo.
        operation_sudo = self.sudo()
        operation_sudo.write({
            'ticket_state': code,
            'detail': _('Filas validadas: %(rows)s · CP con error: %(errors)s · '
                        'CP informados: %(informed)s',
                        rows=detail.get('cntFilasvalidada', '—'),
                        errors=detail.get('cntCPError', '—'),
                        informed=detail.get('cntCPInformados', '—')),
        })
        if code not in TICKET_FINAL_STATES:
            self._poll_retry()
            return
        self._stop_poll()
        operation_sudo.report_ids |= period._sire_attach_reports(token, register)
        operation_sudo.state = 'error' if code in TICKET_FAILED_STATES else 'done'
        period._sire_operation_finished(self)

    def _poll_retry(self, error=None):
        attempt = self.poll_attempts + 1
        if attempt >= SIRE_POLL_MAX_ATTEMPTS:
            self._stop_poll()
            self._period()._sire_warn(_(
                'Se dejó de consultar el ticket %(ticket)s (%(kind)s) tras %(count)s '
                'intentos%(error)s.', ticket=self.ticket, count=attempt,
                kind=dict(OPERATION_KINDS).get(self.kind),
                error=(': %s' % error) if error else ''))
            return
        self._schedule_poll(attempt)

    @api.model
    def _cron_sire_poll_operations(self):
        operations = self.search([('poll_next_date', '<=', fields.Datetime.now())],
                                 order='poll_next_date')
        cron = self.env['ir.cron']
        cron._commit_progress(remaining=len(operations))
        for operation in operations:
            try:
                with self.env.cr.savepoint():
                    operation._check_once()
            except Exception as error:  # noqa: BLE001 — una operación no tumba el cron
                _logger.warning('SIRE: consulta del ticket %s fallida: %s', operation.ticket, error)
                try:
                    with self.env.cr.savepoint():
                        operation._poll_retry(error=error)
                except Exception:  # noqa: BLE001
                    # p. ej. el periodo se borró: no hay a quién avisar.
                    _logger.exception('SIRE: operación %s sin periodo; se deja de consultar',
                                      operation.id)
                    operation._stop_poll()
            if not cron._commit_progress(1):
                break

    # ------------------------------------------------------------------
    # Descargas
    # ------------------------------------------------------------------

    def action_download_file(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_('Esta operación no envió ningún archivo.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/file/%s?download=true' % (
                self._name, self.id, self.filename or 'sire.zip'),
            'target': 'new',
        }

