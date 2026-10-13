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
    construction_code = fields.Char(
        string='Código de obra', compute='_compute_construction_code', store=True,
        readonly=False, copy=False, index='btree_not_null',
        help='Código corto de la obra (p. ej. ROOFG-04-25). Da nombre a la ubicación '
             'de la obra y es el código de su cuenta analítica. Si la compañía usa '
             '«El nombre del proyecto empieza con el código de obra», se toma de la '
             'primera palabra del nombre.')
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

    @api.depends('name', 'company_id.construction_code_from_name')
    def _compute_construction_code(self):
        for project in self:
            company = project.company_id or self.env.company
            if company.construction_code_from_name:
                project.construction_code = (project.name or '').strip().split(' ')[0] or False
            elif not project.construction_code:
                project.construction_code = False

    def _construction_site_label(self):
        """Nombre de la obra sin el código del inicio («ROOFG-04-25 ROOF GARDEN»
        → «ROOF GARDEN»)."""
        self.ensure_one()
        name = (self.name or '').strip()
        code = self.construction_code
        if code and name.startswith(code):
            name = name[len(code):].strip()
        return name or code or ''

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        projects._al_construction_setup_sites()
        return projects

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_construction_site'):
            self._al_construction_setup_sites()
        elif {'name', 'construction_code'} & set(vals):
            self.filtered('is_construction_site')._al_construction_sync_analytic()
        return res

    def _al_construction_setup_sites(self):
        """Alta de obra: cuenta analítica con el código de obra y ubicación
        ``<padre de las obras>/<código>``."""
        sites = self.filtered('is_construction_site')
        sites._al_construction_sync_analytic()
        sites._al_construction_create_locations()

    def _al_construction_sync_analytic(self):
        """Cuenta analítica de la obra (plan de proyectos de la contabilidad
        analítica) con el código y el nombre de la obra."""
        without_account = self.filtered(lambda p: not p.account_id)
        if without_account:
            without_account._create_analytic_account()
        for project in self.filtered('construction_code'):
            account = project.account_id
            vals = {}
            if account.code != project.construction_code:
                vals['code'] = project.construction_code
            label = project._construction_site_label()
            if label and account.name != label:
                vals['name'] = label
            if project.partner_id and not account.partner_id:
                vals['partner_id'] = project.partner_id.id
            if vals:
                account.write(vals)

    def _al_construction_create_locations(self):
        """Crea ``OBRAS/<código>`` (o ``OBRAS/<proyecto>`` sin código) a las
        obras que aún no tienen ubicación; si ya existe una con ese nombre bajo
        la ubicación padre, la reutiliza."""
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
            name = project.construction_code or project.name
            # sudo: misma razón que arriba (permisos de inventario).
            Location_sudo = self.env['stock.location'].sudo()
            location_sudo = Location_sudo.search([
                ('location_id', '=', parent.id), ('name', '=', name),
                ('usage', '=', 'internal')], limit=1) or Location_sudo.create({
                    'name': name,
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
