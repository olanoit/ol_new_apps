# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    is_construction_site = fields.Boolean(
        string='Es obra',
        help='Habilita los requerimientos de materiales y la ubicación de obra.')
    construction_location_id = fields.Many2one(
        'stock.location', string='Ubicación de obra', copy=False,
        check_company=True,
        domain="[('usage', '=', 'internal')]",
        help='Destino de los despachos del almacén central. Se crea bajo OBRAS '
             'al marcar el proyecto como obra.')
    construction_request_ids = fields.One2many(
        'construction.material.request', 'project_id',
        string='Requerimientos de obra')
    construction_request_count = fields.Integer(
        string='Nº de requerimientos de obra', compute='_compute_construction_request_count')

    @api.depends('construction_request_ids')
    def _compute_construction_request_count(self):
        groups = self.env['construction.material.request']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count'])
        counts = {project.id: count for project, count in groups}
        for project in self:
            project.construction_request_count = counts.get(project.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        projects._al_construction_create_locations()
        return projects

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_construction_site'):
            self._al_construction_create_locations()
        return res

    def _al_construction_create_locations(self):
        """Crea ``OBRAS/<proyecto>`` a las obras que aún no tienen ubicación."""
        for project in self.filtered(
                lambda p: p.is_construction_site and not p.construction_location_id):
            # El jefe de proyecto no suele tener permisos de inventario: la
            # configuración y la ubicación de obra se crean como superusuario.
            company_sudo = (project.company_id or self.env.company).sudo()
            company_sudo._al_construction_ensure_setup()
            parent = company_sudo.construction_sites_location_id
            if not parent:
                raise UserError(_(
                    'La compañía %s no tiene almacén: configure la ubicación '
                    'padre de las obras en Ajustes ▸ Inventario.', company_sudo.name))
            location_sudo = self.env['stock.location'].sudo().create({
                'name': project.name,
                'usage': 'internal',
                'location_id': parent.id,
                'company_id': company_sudo.id,
            })
            project.construction_location_id = location_sudo.id

    def action_view_construction_requests(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_material_request.action_construction_material_request')
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action
