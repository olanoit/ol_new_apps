# -*- coding: utf-8 -*-
"""Contraste del catálogo de detracciones con la página de SUNAT.

Solo compara: la página de SUNAT no trae el porcentaje por código, sino
tablas de modificaciones que hay que cruzar por nombre (ver
``tools/sunat_spot_page``). Un porcentaje mal leído cambiaría la detracción
de las facturas, así que los cambios los aplica una persona, línea a línea.
"""
import hashlib
import logging

import requests
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..tools import sunat_spot_page

_logger = logging.getLogger(__name__)

URL_PARAM = 'al_l10n_pe_detraction.sunat_spot_url'
DEFAULT_URL = 'https://orientacion.sunat.gob.pe/apendices-del-sistema-de-detracciones'
DEFAULT_MIN_AMOUNT = 700.0
# Diferencias que piden una decisión; las demás son informativas.
ACTIONABLE = ('rate_diff', 'new')

STATUS = [
    ('match', 'Coincide'),
    ('rate_diff', 'Porcentaje distinto'),
    ('new', 'Nuevo en SUNAT'),
    ('no_rate', 'Sin porcentaje en SUNAT'),
    ('missing', 'No figura en SUNAT'),
]


class L10nPeDetractionCheck(models.Model):
    _name = 'l10n_pe.detraction.check'
    _description = 'Contraste de detracciones con SUNAT'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Contraste', required=True)
    date = fields.Datetime(string='Fecha', required=True, default=fields.Datetime.now)
    source_url = fields.Char(string='Fuente', required=True)
    line_ids = fields.One2many(
        'l10n_pe.detraction.check.line', 'check_id', string='Códigos')
    difference_count = fields.Integer(
        string='Diferencias', compute='_compute_counts', store=True,
        help='Porcentajes distintos y códigos nuevos con porcentaje publicado.')
    pending_count = fields.Integer(
        string='Por aplicar', compute='_compute_counts', store=True)
    fingerprint = fields.Char(
        help='Resumen de las diferencias: la acción planificada no repite '
             'un contraste con las mismas.')

    @api.depends('line_ids.status', 'line_ids.applied')
    def _compute_counts(self):
        for check in self:
            actionable = check.line_ids.filtered(lambda l: l.status in ACTIONABLE)
            check.difference_count = len(actionable)
            check.pending_count = len(actionable.filtered(lambda l: not l.applied))

    # ------------------------------------------------------------------
    # Fuente
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_source_url(self):
        return (self.env['ir.config_parameter'].sudo().get_param(URL_PARAM)
                or DEFAULT_URL)

    @api.model
    def _l10n_pe_download(self, url):
        try:
            response = requests.get(url, timeout=60, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; Odoo)'})
            response.raise_for_status()
        except requests.RequestException as error:
            raise UserError(_('No se pudo descargar %(url)s: %(error)s',
                              url=url, error=error)) from error
        return response.content

    # ------------------------------------------------------------------
    # Comparación
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_compare(self, data):
        """Valores de las líneas del contraste, una por código."""
        Type = self.env['l10n_pe.detraction.type'].with_context(active_test=False)
        types = {dtype.code: dtype for dtype in Type.search([])}
        lines = []
        for code in sorted(set(types) | set(data['codes'])):
            dtype = types.get(code)
            name, annex1 = data['codes'].get(code, ('', False))
            rate, since = data['rates'].get(code, (0.0, False))
            if code not in data['codes']:
                status = 'missing'
            elif code not in data['rates']:
                status = 'no_rate'
            elif not dtype:
                status = 'new'
            elif abs(dtype.percentage - rate) > 0.001:
                status = 'rate_diff'
            else:
                status = 'match'
            lines.append({
                'code': code,
                'type_id': dtype.id if dtype else False,
                'sunat_name': name,
                'annex1': annex1,
                'odoo_percentage': dtype.percentage if dtype else 0.0,
                'sunat_percentage': rate,
                'sunat_since': since or False,
                'status': status,
            })
        return lines

    @staticmethod
    def _l10n_pe_fingerprint(lines):
        key = ';'.join('%s:%s:%s' % (line['code'], line['status'], line['sunat_percentage'])
                       for line in lines if line['status'] in ACTIONABLE)
        return hashlib.sha1(key.encode()).hexdigest()

    @api.model
    def _l10n_pe_check(self, only_if_changed=False):
        """Contrasta con SUNAT y guarda el resultado.

        Con ``only_if_changed`` (la acción planificada) no guarda nada si las
        diferencias son las mismas que las del último contraste.
        """
        url = self._l10n_pe_source_url()
        try:
            data = sunat_spot_page.parse_html(self._l10n_pe_download(url))
        except sunat_spot_page.SpotPageError as error:
            raise UserError(_('La página %(url)s no trae el catálogo de '
                              'detracciones reconocible: %(error)s',
                              url=url, error=error)) from error
        lines = self._l10n_pe_compare(data)
        fingerprint = self._l10n_pe_fingerprint(lines)
        if only_if_changed:
            last = self.search([], limit=1)
            if last.fingerprint == fingerprint:
                return self.browse()
        check = self.create({
            'name': _('Contraste %s', fields.Date.context_today(self)),
            'source_url': url,
            'fingerprint': fingerprint,
            'line_ids': [fields.Command.create(line) for line in lines],
        })
        check.message_post(body=_(
            '%(count)s diferencia(s) con %(url)s.',
            count=check.difference_count, url=url))
        return check

    @api.model
    def _cron_l10n_pe_check_sunat(self):
        try:
            check = self._l10n_pe_check(only_if_changed=True)
        except UserError as error:
            _logger.warning('Contraste de detracciones con SUNAT: %s', error)
            return
        if check.difference_count:
            check._l10n_pe_schedule_review()

    def _l10n_pe_schedule_review(self):
        group = self.env.ref('account.group_account_manager')
        managers = self.env['res.users'].search([
            ('all_group_ids', 'in', group.id), ('share', '=', False)])
        for check in self:
            for user in managers:
                check.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary=_('Revisar diferencias de detracciones con SUNAT'),
                    note=escape(_('%s código(s) con porcentaje distinto o nuevos '
                                  'en SUNAT.', check.difference_count)))

    @api.model
    def action_check_now(self):
        """Botón «Contrastar con SUNAT» de la lista del catálogo."""
        check = self._l10n_pe_check()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': check.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Aplicación manual
    # ------------------------------------------------------------------
    def action_apply(self):
        self.ensure_one()
        lines = self.line_ids.filtered(
            lambda l: l.to_apply and not l.applied and l.status in ACTIONABLE)
        if not lines:
            raise UserError(_('Marque las líneas que quiere aplicar.'))
        Type = self.env['l10n_pe.detraction.type']
        annex1_min = max(Type.search([('code', 'in', ('001', '003'))])
                         .mapped('min_amount') or [DEFAULT_MIN_AMOUNT])
        rows = []
        for line in lines:
            if line.status == 'rate_diff':
                old = line.type_id.percentage
                line.type_id.percentage = line.sunat_percentage
                line.type_id.action_sync_products()
                rows.append(_('%(code)s: %(old)s %% → %(new)s %% (productos actualizados)',
                              code=line.code, old=old, new=line.sunat_percentage))
            else:
                line.type_id = Type.create({
                    'code': line.code,
                    'name': line.sunat_name,
                    'percentage': line.sunat_percentage,
                    'min_amount': annex1_min if line.annex1 else DEFAULT_MIN_AMOUNT,
                    'comment': _('Creado desde el contraste con SUNAT. Revise '
                                 'el monto mínimo.'),
                })
                rows.append(_('%(code)s: creado al %(rate)s %%',
                              code=line.code, rate=line.sunat_percentage))
        lines.write({'applied': True, 'to_apply': False})
        self.message_post(body=Markup('<p>%s</p><ul>%s</ul>') % (
            _('Cambios aplicados al catálogo:'),
            Markup('').join(Markup('<li>%s</li>') % row for row in rows)))
        self.activity_ids.action_feedback(feedback=_('Diferencias aplicadas.'))
        return True


class L10nPeDetractionCheckLine(models.Model):
    _name = 'l10n_pe.detraction.check.line'
    _description = 'Código contrastado con SUNAT'
    _order = 'code'

    check_id = fields.Many2one(
        'l10n_pe.detraction.check', required=True, ondelete='cascade', index=True)
    code = fields.Char(string='Código', required=True)
    type_id = fields.Many2one('l10n_pe.detraction.type', string='Tipo en Odoo')
    sunat_name = fields.Char(string='Nombre en SUNAT')
    annex1 = fields.Boolean(
        string='Anexo 1', help='Bienes del Anexo 1: el mínimo es media UIT.')
    odoo_percentage = fields.Float(string='% Odoo', digits=(5, 2))
    sunat_percentage = fields.Float(string='% SUNAT', digits=(5, 2))
    sunat_since = fields.Date(
        string='Vigente desde',
        help='Fecha de la tabla de SUNAT de la que sale el porcentaje.')
    status = fields.Selection(STATUS, string='Estado', required=True)
    to_apply = fields.Boolean(string='Aplicar')
    applied = fields.Boolean(string='Aplicado', readonly=True)
    actionable = fields.Boolean(compute='_compute_actionable')

    @api.depends('status', 'applied')
    def _compute_actionable(self):
        for line in self:
            line.actionable = line.status in ACTIONABLE and not line.applied
