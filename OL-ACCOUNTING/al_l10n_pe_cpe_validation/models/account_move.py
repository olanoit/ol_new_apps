# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services import sunat_cpe

_logger = logging.getLogger(__name__)

# Tipo de documento de Odoo (catálogo 01) → codComp del servicio de SUNAT.
DOC_CODES = {'01': '01', '03': '03', '04': '04', '07': '07', '08': '08', '02': 'R1'}
VALID_CP = ('1', '3')  # aceptado (electrónico) o autorizado por imprenta (físico)
RESULTS = [
    ('valid', 'Válido'),
    ('observed', 'Válido con observaciones'),
    ('invalid', 'No válido'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_cpe_result = fields.Selection(
        RESULTS, string='Validez en SUNAT', copy=False, readonly=True, tracking=True,
        help='Resultado de la consulta integrada de comprobantes de pago de SUNAT. «Con '
             'observaciones»: el comprobante existe, pero el emisor no está activo o no está '
             'habido.')
    l10n_pe_cpe_doc_state = fields.Selection(
        list(sunat_cpe.CP_STATES.items()), string='Estado del comprobante', copy=False,
        readonly=True)
    l10n_pe_cpe_ruc_state = fields.Selection(
        list(sunat_cpe.RUC_STATES.items()), string='Estado del emisor', copy=False,
        readonly=True)
    l10n_pe_cpe_domicile = fields.Selection(
        list(sunat_cpe.DOMICILE_STATES.items()), string='Domicilio del emisor', copy=False,
        readonly=True)
    l10n_pe_cpe_checked_on = fields.Datetime(string='Consultado el', copy=False, readonly=True)
    l10n_pe_cpe_message = fields.Text(string='Observaciones de SUNAT', copy=False,
                                      readonly=True)
    l10n_pe_cpe_applicable = fields.Boolean(compute='_compute_l10n_pe_cpe_applicable')

    @api.depends('move_type', 'country_code', 'l10n_latam_document_type_id')
    def _compute_l10n_pe_cpe_applicable(self):
        for move in self:
            move.l10n_pe_cpe_applicable = (
                move.country_code == 'PE' and move.move_type in ('in_invoice', 'in_refund')
                and (move.l10n_latam_document_type_id.code or '') in DOC_CODES)

    def _l10n_pe_cpe_query_values(self):
        """Datos de la consulta, o un texto con el motivo si no se puede consultar."""
        self.ensure_one()
        if not self.l10n_pe_cpe_applicable:
            return self.env._('el tipo de documento no se consulta en SUNAT')
        ruc = (self.commercial_partner_id.vat or '').strip()
        if len(ruc) != 11 or not ruc.isdigit():
            return self.env._('el proveedor no tiene RUC')
        number = (self.l10n_latam_document_number or '').strip()
        if '-' not in number:
            return self.env._('el número no tiene el formato serie-número')
        series, correlative = (part.strip() for part in number.split('-', 1))
        if not correlative.isdigit() or not self.invoice_date:
            return self.env._('falta el número o la fecha de emisión')
        values = {
            'numRuc': ruc,
            'codComp': DOC_CODES[self.l10n_latam_document_type_id.code],
            'numeroSerie': series.upper(),
            'numero': int(correlative),
            'fechaEmision': self.invoice_date.strftime('%d/%m/%Y'),
        }
        # El monto solo se envía en comprobantes electrónicos (serie con letra).
        if series[:1].isalpha():
            values['monto'] = '%.2f' % abs(self.amount_total)
        return values

    def _l10n_pe_cpe_apply(self, data):
        cp_state = str(data.get('estadoCp', '')).strip()
        ruc_state = str(data.get('estadoRuc') or '').strip()
        domicile = str(data.get('condDomiRuc') or '').strip()
        if cp_state not in VALID_CP:
            result = 'invalid'
        elif ruc_state in ('', '00') and domicile in ('', '00'):
            result = 'valid'
        else:
            result = 'observed'
        notes = data.get('observaciones') or []
        self.write({
            'l10n_pe_cpe_result': result,
            'l10n_pe_cpe_doc_state': cp_state if cp_state in sunat_cpe.CP_STATES else False,
            'l10n_pe_cpe_ruc_state': ruc_state if ruc_state in sunat_cpe.RUC_STATES else False,
            'l10n_pe_cpe_domicile': domicile if domicile in sunat_cpe.DOMICILE_STATES else False,
            'l10n_pe_cpe_checked_on': fields.Datetime.now(),
            'l10n_pe_cpe_message': '\n'.join(str(note) for note in notes) or False,
        })
        return result

    def _l10n_pe_cpe_validate(self, raise_on_error=True):
        """Consulta cada comprobante; devuelve ``{'done': moves, 'skipped':
        [(move, motivo)], 'errors': [(move, error)]}``."""
        outcome = {'done': self.browse(), 'skipped': [], 'errors': []}
        for company, moves in self.grouped('company_id').items():
            token = None
            for move in moves:
                values = move._l10n_pe_cpe_query_values()
                if isinstance(values, str):
                    outcome['skipped'].append((move, values))
                    continue
                try:
                    token = token or company._l10n_pe_cpe_get_token()
                    data = sunat_cpe.validate(token, company.root_id.vat, values)
                except (UserError, sunat_cpe.SunatCpeError) as exc:
                    if raise_on_error and len(self) == 1:
                        raise UserError(str(exc)) from exc
                    outcome['errors'].append((move, str(exc)))
                    continue
                move._l10n_pe_cpe_apply(data)
                outcome['done'] |= move
        return outcome

    def action_l10n_pe_cpe_validate(self):
        """Botón y acción de lista «Validar en SUNAT»."""
        moves = self.filtered(lambda m: m.move_type in ('in_invoice', 'in_refund'))
        if not moves:
            raise UserError(self.env._('Seleccione facturas o notas de crédito de proveedor.'))
        outcome = moves._l10n_pe_cpe_validate()
        done = outcome['done']
        lines = [self.env._('%(count)s consultados: %(valid)s válidos, %(observed)s con '
                            'observaciones y %(invalid)s no válidos.',
                            count=len(done),
                            valid=len(done.filtered(lambda m: m.l10n_pe_cpe_result == 'valid')),
                            observed=len(done.filtered(
                                lambda m: m.l10n_pe_cpe_result == 'observed')),
                            invalid=len(done.filtered(
                                lambda m: m.l10n_pe_cpe_result == 'invalid')))]
        for move, reason in outcome['skipped'][:10]:
            lines.append(self.env._('%(move)s: no se consultó (%(reason)s).',
                                    move=move.display_name, reason=reason))
        for move, error in outcome['errors'][:10]:
            lines.append('%s: %s' % (move.display_name, error))
        warning = outcome['errors'] or done.filtered(lambda m: m.l10n_pe_cpe_result != 'valid')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if warning else 'success',
                'title': self.env._('Consulta de comprobantes en SUNAT'),
                'message': '\n'.join(lines),
                'sticky': bool(warning),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def _post(self, soft=True):
        to_check = self.filtered(
            lambda m: m.l10n_pe_cpe_applicable and m.company_id.l10n_pe_cpe_post_mode != 'none')
        if to_check:
            outcome = to_check._l10n_pe_cpe_validate(raise_on_error=False)
            blocked = outcome['done'].filtered(
                lambda m: m.l10n_pe_cpe_result == 'invalid'
                and m.company_id.l10n_pe_cpe_post_mode == 'block')
            if blocked:
                raise UserError(self.env._(
                    'SUNAT no da por válidos estos comprobantes y no se pueden publicar:\n%s',
                    '\n'.join('· %s (%s)' % (
                        move.display_name,
                        dict(sunat_cpe.CP_STATES).get(move.l10n_pe_cpe_doc_state, '—'))
                        for move in blocked)))
            for move in outcome['done'].filtered(lambda m: m.l10n_pe_cpe_result != 'valid'):
                move.message_post(body=self.env._(
                    'Consulta en SUNAT: %(result)s. Comprobante: %(cp)s; emisor: %(ruc)s; '
                    'domicilio: %(dom)s.',
                    result=dict(RESULTS)[move.l10n_pe_cpe_result],
                    cp=sunat_cpe.CP_STATES.get(move.l10n_pe_cpe_doc_state or '', '—'),
                    ruc=sunat_cpe.RUC_STATES.get(move.l10n_pe_cpe_ruc_state or '', '—'),
                    dom=sunat_cpe.DOMICILE_STATES.get(move.l10n_pe_cpe_domicile or '', '—')))
            for move, error in outcome['errors']:
                # Sin respuesta de SUNAT no se bloquea: se deja constancia.
                move.message_post(body=self.env._(
                    'No se pudo consultar el comprobante en SUNAT: %s', error))
        return super()._post(soft=soft)

    @api.model
    def _cron_l10n_pe_cpe_validate(self, days=60, limit=200):
        """Consulta las compras publicadas de los últimos ``days`` días aún sin
        resultado (acción programada, desactivada por defecto)."""
        moves = self.search([
            ('move_type', 'in', ('in_invoice', 'in_refund')), ('state', '=', 'posted'),
            ('country_code', '=', 'PE'), ('l10n_pe_cpe_result', '=', False),
            ('invoice_date', '>=', fields.Date.context_today(self) - timedelta(days=days)),
        ], limit=limit, order='invoice_date desc, id desc')
        outcome = moves._l10n_pe_cpe_validate(raise_on_error=False)
        _logger.info('Consulta de comprobantes en SUNAT: %s consultados, %s errores.',
                     len(outcome['done']), len(outcome['errors']))
