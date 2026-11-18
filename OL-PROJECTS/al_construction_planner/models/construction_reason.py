# -*- coding: utf-8 -*-
"""Catálogo de motivos de la obra (paquete 1.22, M122-03).

El motivo del re-trabajo deja de ser una lista fija (Cambio, Faltante, Mal
armado): cada compañía tiene los suyos y cada perfil de vertical trae una
lista inicial. El modelo conserva el nombre con el que nació en el portal de
obra (paquete 6), que le agrega sus usos (rechazo de un avance, corrección de
su cantidad y rechazo de un requerimiento) y sus pantallas."""
from odoo import api, fields, models

#: Valores de la selección anterior, para los registros y los celulares que
#: todavía los envían.
LEGACY_REWORK = [
    ('change', 'Cambio'),
    ('missing', 'Faltante'),
    ('bad_assembly', 'Mal armado'),
]


class ConstructionPortalReason(models.Model):
    _name = 'construction.portal.reason'
    _description = 'Motivo de la obra'
    _order = 'kind, sequence, id'
    _check_company_auto = True

    name = fields.Char(string='Motivo', required=True, translate=True)
    kind = fields.Selection([('rework', 'Re-trabajo')], string='Para', required=True,
                            default='rework')
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', string='Compañía', index=True,
                                 help='Vacío: para todas las compañías.')
    active = fields.Boolean(default=True)

    @api.model
    def _rework_for(self, company):
        """Motivos de re-trabajo que se ofrecen en la compañía."""
        return self.sudo().search([('kind', '=', 'rework'),
                                   ('company_id', 'in', (company.id, False))])

    @api.model
    def _rework_from_legacy(self, code, company):
        """El motivo del catálogo que corresponde a un valor de la selección
        anterior: el del mismo nombre en la compañía (también archivado); si
        no existe, se crea."""
        name = dict(LEGACY_REWORK).get(code)
        if not name:
            return self.browse()
        # sudo: quien reporta un avance no administra el catálogo.
        Reason = self.sudo().with_context(active_test=False)
        reason = Reason.search([('kind', '=', 'rework'), ('name', '=ilike', name),
                                ('company_id', 'in', (company.id, False))],
                               order='company_id, id', limit=1)
        return reason or Reason.create({'name': name, 'kind': 'rework',
                                        'company_id': company.id})

    @api.model
    def _seed_rework(self, company, names):
        """Motivos iniciales de re-trabajo de una compañía que no tiene
        ninguno propio activo (los trae su perfil de vertical)."""
        names = [name.strip() for name in names or [] if name and name.strip()]
        if not names or self.sudo().search_count(
                [('kind', '=', 'rework'), ('company_id', '=', company.id)], limit=1):
            return self.browse()
        return self.sudo().create([
            {'name': name, 'kind': 'rework', 'company_id': company.id, 'sequence': 10 * index}
            for index, name in enumerate(names, start=1)])
