# -*- coding: utf-8 -*-
"""Actividades económicas (CIIU) del contribuyente, como las publica SUNAT
en la ficha RUC. El catálogo es la CIIU Rev. 4 de las Naciones Unidas
(docs/ciiu/); los códigos que lleguen de SUNAT y no estén (p. ej. CIIU
Rev. 3 de fichas antiguas) se agregan al consultar."""
from odoo import api, fields, models

from ..services import activities as activities_service

ACTIVITY_KINDS = [
    ('principal', 'Principal'),
    ('secondary', 'Secundaria'),
]


class L10nPeEconomicActivity(models.Model):
    _name = 'l10n_pe.economic.activity'
    _description = 'Actividad económica (CIIU)'
    _order = 'code'
    _rec_names_search = ('code', 'name')

    code = fields.Char(string='Código', required=True, index=True,
                       help='Clase CIIU de cuatro dígitos (Rev. 4) o cinco (Rev. 3).')
    name = fields.Char(string='Descripción', required=True)
    active = fields.Boolean(string='Activo', default=True)

    _code_unique = models.Constraint('UNIQUE(code)', 'El código de la actividad debe ser único.')

    @api.depends('code', 'name')
    @api.depends_context('l10n_pe_activity_name_only')
    def _compute_display_name(self):
        # En la lista del contacto el código va en su propia columna.
        name_only = self.env.context.get('l10n_pe_activity_name_only')
        for activity in self:
            activity.display_name = activity.name if name_only or not activity.code \
                else '%s - %s' % (activity.code, activity.name)

    @api.model
    def _l10n_pe_get_or_create(self, code, name):
        """Actividad del catálogo por código (o por descripción si no hay
        código); si no existe, la crea con lo que publica SUNAT."""
        if code:
            activity = self.with_context(active_test=False).search([('code', '=', code)], limit=1)
        else:
            activity = self.with_context(active_test=False).search(
                [('name', '=ilike', name)], limit=1)
        if activity or not code:
            return activity
        # sudo: el catálogo solo lo editan los gestores de contactos, pero
        # cualquier usuario que consulta un RUC puede recibir una actividad
        # que aún no está (p. ej. CIIU Rev. 3 de una ficha antigua).
        catalog_sudo = self.sudo()
        return catalog_sudo.create({'code': code, 'name': (name or code).capitalize()})


class L10nPePartnerEconomicActivity(models.Model):
    _name = 'l10n_pe.partner.economic.activity'
    _description = 'Actividad económica del contribuyente'
    _order = 'partner_id, kind desc, sequence, id'

    partner_id = fields.Many2one('res.partner', string='Contribuyente', required=True,
                                 index=True, ondelete='cascade')
    sequence = fields.Integer(string='Orden', default=10)
    kind = fields.Selection(ACTIVITY_KINDS, string='Tipo', required=True, default='secondary')
    activity_id = fields.Many2one('l10n_pe.economic.activity', string='Actividad',
                                  required=True, ondelete='restrict')
    code = fields.Char(related='activity_id.code', string='Código')
    label = fields.Char(string='Tipo de actividad', compute='_compute_label',
                        help='Como la publica SUNAT: Principal, Secundaria 1, Secundaria 2…')

    @api.depends('kind', 'sequence', 'partner_id')
    def _compute_label(self):
        for line in self:
            if line.kind == 'principal':
                line.label = self.env._('Principal')
                continue
            secondaries = line.partner_id.l10n_pe_economic_activity_ids.filtered(
                lambda l: l.kind == 'secondary').sorted(lambda l: (l.sequence, l.id or 0))
            position = (list(secondaries).index(line) + 1) if line in secondaries else 1
            line.label = self.env._('Secundaria %s', position)


def activity_commands(env, texts):
    """Comandos para ``l10n_pe_economic_activity_ids`` desde los textos de
    SUNAT: reemplaza las líneas por las publicadas, en su orden."""
    Activity = env['l10n_pe.economic.activity']
    commands = [fields.Command.clear()]
    for sequence, item in enumerate(activities_service.parse_all(texts), start=1):
        activity = Activity._l10n_pe_get_or_create(item['code'], item['name'])
        if not activity:
            continue
        commands.append(fields.Command.create({
            'kind': item['kind'], 'sequence': sequence, 'activity_id': activity.id,
        }))
    return commands
