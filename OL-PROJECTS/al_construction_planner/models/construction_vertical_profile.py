# -*- coding: utf-8 -*-
"""Perfiles de vertical (v1.7, M17-05).

Un perfil reúne lo que deja el planificador listo para un rubro: la plantilla
de niveles, las etapas, los tipos de recurso, las funciones y los puentes que
se activan, los parámetros de la compañía y los planes analíticos. Es un
registro de datos, no código: se elige en Ajustes, se aplica (crea lo que
falta sin borrar nada y se puede volver a aplicar), muestra en qué se aparta
la compañía de su definición y se exporta e importa entre bases como JSON.
"""
import base64
import json

from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

FEATURE_FIELDS = {
    'control': 'group_construction_control',
    'progress': 'group_construction_progress',
}


class ConstructionVerticalProfile(models.Model):
    _name = 'construction.vertical.profile'
    _description = 'Perfil de vertical del planificador'
    _order = 'sequence, name'

    name = fields.Char(string='Perfil', required=True, translate=True)
    code = fields.Char(string='Código', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Para quién es', translate=True)
    level_template_id = fields.Many2one(
        'construction.level.template', string='Plantilla de niveles', required=True,
        help='La que reciben las obras nuevas.')
    stage_ids = fields.Many2many(
        'construction.stage', 'construction_profile_stage_rel', 'profile_id', 'stage_id',
        string='Etapas', help='Las del catálogo que usa el rubro.')
    resource_type_ids = fields.Many2many(
        'construction.resource.type', 'construction_profile_resource_type_rel', 'profile_id',
        'type_id', string='Tipos de recurso')
    module_ids = fields.Many2many(
        'ir.module.module', 'construction_profile_module_rel', 'profile_id', 'module_id',
        string='Puentes', domain=[('name', '=like', 'al_construction_planner\\_%')],
        help='Se instalan al aplicar el perfil.')
    feature_control = fields.Boolean(string='Control', default=True)
    feature_progress = fields.Boolean(string='Avance y metrados', default=True)
    parameter_ids = fields.One2many(
        'construction.vertical.profile.parameter', 'profile_id', string='Parámetros', copy=True,
        help='Valores de la compañía que fija el perfil (semana de contratas, '
             'valorización…).')
    analytic_plan_names = fields.Char(
        string='Planes analíticos',
        help='Separados por comas (p. ej. «Disciplina, Subpartida, Partida»): se crean los '
             'que no existen.')
    note = fields.Text(string='Por decidir', translate=True,
                       help='Lo que aún se valida con los clientes del rubro.')
    deviation_html = fields.Html(
        string='Desvíos de la compañía', compute='_compute_deviation_html', sanitize=False)

    _code_unique = models.Constraint('UNIQUE(code)', 'Ya hay un perfil con ese código.')

    # ------------------------------------------------------------------
    # Lo que fija el perfil
    # ------------------------------------------------------------------
    def _parameter_values(self):
        self.ensure_one()
        return {param.name: param._value() for param in self.parameter_ids}

    def _modules_to_install(self):
        self.ensure_one()
        return self.module_ids.filtered(lambda m: m.state not in ('installed', 'to upgrade'))

    def _get_deviations(self, company=None):
        """[(qué, en el perfil, en la compañía)] de lo que la compañía tiene
        distinto de la definición del perfil."""
        self.ensure_one()
        company = company or self.env.company
        rows = []
        for module in self._modules_to_install():
            rows.append((self.env._('Puente %s', module.shortdesc or module.name),
                         self.env._('Instalado'), self.env._('No instalado')))
        groups = {'control': 'al_construction_planner.group_planner_feature_control',
                  'progress': 'al_construction_planner.group_planner_feature_progress'}
        internal = self.env.ref('base.group_user')
        labels = {'control': self.env._('Control'), 'progress': self.env._('Avance y metrados')}
        for feature, xmlid in groups.items():
            active = self.env.ref(xmlid) in internal.implied_ids
            if self['feature_%s' % feature] != active:
                yes, no = self.env._('Activo'), self.env._('Apagado')
                rows.append((labels[feature], yes if self['feature_%s' % feature] else no,
                             yes if active else no))
        for name, value in self._parameter_values().items():
            if name not in company._fields:
                continue
            current = company[name]
            current = current.id if isinstance(current, models.BaseModel) else current
            if current != value:
                rows.append((company._fields[name].string, str(value), str(current)))
        if company.construction_level_template_id != self.level_template_id:
            rows.append((self.env._('Plantilla de niveles'), self.level_template_id.name,
                         company.construction_level_template_id.name or '—'))
        for stage in self.stage_ids.filtered(lambda s: not s.active):
            rows.append((self.env._('Etapa %s', stage.name), self.env._('Activa'),
                         self.env._('Archivada')))
        return rows

    @api.depends_context('company')
    def _compute_deviation_html(self):
        for profile in self:
            rows = profile._get_deviations() if profile.id else []
            if not rows:
                profile.deviation_html = Markup('<p class="text-success">%s</p>') % self.env._(
                    'La compañía tiene la configuración del perfil.')
                continue
            body = Markup('').join(
                Markup('<tr><td>%s</td><td>%s</td><td>%s</td></tr>') % row for row in rows)
            profile.deviation_html = Markup(
                '<table class="table table-sm"><thead><tr><th>%s</th><th>%s</th><th>%s</th>'
                '</tr></thead><tbody>%s</tbody></table>') % (
                self.env._('Qué'), self.env._('Perfil'), self.env._('Compañía'), body)

    # ------------------------------------------------------------------
    # Aplicar
    # ------------------------------------------------------------------
    def _apply_configuration(self, company):
        """Lo que no instala módulos: etapas y tipos activos, parámetros de la
        compañía, planes analíticos y plantilla por defecto. No borra nada."""
        self.ensure_one()
        self.stage_ids.filtered(lambda r: not r.active).active = True
        self.resource_type_ids.filtered(lambda r: not r.active).active = True
        values = {}
        for name, value in self._parameter_values().items():
            if name in company._fields:
                values[name] = value
        values.update(construction_profile_id=self.id,
                      construction_level_template_id=self.level_template_id.id)
        company.write(values)
        Plan = self.env['account.analytic.plan']
        for plan_name in filter(None, (n.strip() for n in (self.analytic_plan_names or '').split(','))):
            if not Plan.search_count([('name', '=ilike', plan_name)]):
                Plan.create({'name': plan_name})

    def action_apply(self):
        """Aplica el perfil a la compañía activa: la configuración y, por los
        Ajustes de Odoo, las funciones y los puentes (instalar un puente
        recarga la aplicación)."""
        self.ensure_one()
        if not self.env.user.has_group('al_construction_planner.group_planner_manager'):
            raise UserError(self.env._('Solo el administrador del planificador aplica perfiles.'))
        self._apply_configuration(self.env.company)
        settings_vals = {field: self['feature_%s' % feature]
                         for feature, field in FEATURE_FIELDS.items()}
        for module in self.module_ids:
            field = 'module_%s' % module.name
            if field in self.env['res.config.settings']._fields:
                settings_vals[field] = True
        if self.env.context.get('construction_profile_no_install'):
            settings_vals = {k: v for k, v in settings_vals.items() if not k.startswith('module_')}
        settings = self.env['res.config.settings'].create(settings_vals)
        return settings.execute()

    @api.model
    def _assign_legacy_companies(self):
        """Actualización a la v1.7 (migración de Allcenter): antes del paquete
        el planificador solo servía para mobiliario, así que una compañía sin
        perfil que ya tiene obras o tipologías pasa al perfil Mobiliario, y sus
        obras con ella. No toca su plantilla, sus parámetros ni los módulos (los
        puentes ya se instalaron en la v30): lo que usaba sigue igual, y una
        obra sin plantilla conserva el árbol clásico. Devuelve las compañías."""
        profile = self.env.ref('al_construction_planner.profile_furniture',
                               raise_if_not_found=False)
        if not profile:
            return self.env['res.company']
        Project = self.env['project.project'].with_context(active_test=False)
        Typology = self.env['construction.typology'].with_context(active_test=False)
        companies = self.env['res.company'].with_context(active_test=False).search(
            [('construction_profile_id', '=', False)]).filtered(
            lambda company: Project.search_count(
                [('company_id', '=', company.id), ('is_construction_site', '=', True)], limit=1)
            or Typology.search_count([('company_id', '=', company.id)], limit=1))
        if not companies:
            return companies
        profile.stage_ids.filtered(lambda r: not r.active).active = True
        profile.resource_type_ids.filtered(lambda r: not r.active).active = True
        companies.construction_profile_id = profile
        # Por SQL: con el ORM, el perfil recalcularía la plantilla de las obras
        # que no tienen una y les cambiaría el árbol.
        self.env.cr.execute(SQL("""
            UPDATE project_project SET construction_profile_id = %s
             WHERE construction_profile_id IS NULL AND is_construction_site
               AND company_id = ANY(%s)
        """, profile.id, companies.ids))
        # Las obras sin compañía, si todas las compañías quedan con este perfil
        # (Allcenter es una sola compañía); con perfiles distintos no hay a
        # cuál atribuirlas.
        all_companies = self.env['res.company'].with_context(active_test=False).search([])
        if all(company.construction_profile_id == profile for company in all_companies):
            self.env.cr.execute(SQL("""
                UPDATE project_project SET construction_profile_id = %s
                 WHERE construction_profile_id IS NULL AND is_construction_site
                   AND company_id IS NULL
            """, profile.id))
        Project.invalidate_model(['construction_profile_id'])
        return companies

    # ------------------------------------------------------------------
    # Exportar e importar
    # ------------------------------------------------------------------
    def _export_data(self):
        self.ensure_one()
        template = self.level_template_id
        return {
            'format': 'al_construction_planner.profile/1',
            'code': self.code, 'name': self.name, 'description': self.description or '',
            'note': self.note or '',
            'level_template': {
                'name': template.name,
                'purchase_destination': template.purchase_destination,
                'lines': [{
                    'sequence': line.sequence, 'name': line.name, 'role': line.role,
                    'has_recipe': line.has_recipe, 'is_measured': line.is_measured,
                    'is_billable': line.is_billable, 'receives_progress': line.receives_progress,
                    'measure_uom': line.measure_uom_id.get_external_id().get(
                        line.measure_uom_id.id) if line.measure_uom_id else False,
                    'stages': line.stage_ids.mapped('code'),
                } for line in template.line_ids.sorted('sequence')],
            },
            'stages': [{
                'code': stage.code, 'name': stage.name, 'sequence': stage.sequence,
                'kind': stage.kind, 'production_consumption': stage.production_consumption,
                'previous': stage.previous_stage_id.code or False,
                'duration_days': stage.duration_days, 'color': stage.color or False,
            } for stage in self.stage_ids],
            'resource_types': [{
                'code': rtype.code, 'name': rtype.name, 'sequence': rtype.sequence,
                'behavior': rtype.behavior, 'supply_method': rtype.supply_method,
            } for rtype in self.resource_type_ids],
            'modules': self.module_ids.mapped('name'),
            'features': {'control': self.feature_control, 'progress': self.feature_progress},
            'parameters': {param.name: param.value for param in self.parameter_ids},
            'analytic_plans': self.analytic_plan_names or '',
        }

    def action_export(self):
        self.ensure_one()
        content = json.dumps(self._export_data(), ensure_ascii=False, indent=2)
        attachment = self.env['ir.attachment'].create({
            'name': 'perfil_%s.json' % self.code,
            'datas': base64.b64encode(content.encode()),
            'mimetype': 'application/json',
            'res_model': self._name, 'res_id': self.id,
        })
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/web/content/%s?download=true' % attachment.id}

    @api.model
    def _import_data(self, data):
        """Crea o actualiza el perfil (por su código) con su plantilla, sus
        etapas y sus tipos de recurso (por su código)."""
        if data.get('format') != 'al_construction_planner.profile/1':
            raise UserError(self.env._('El archivo no es un perfil del planificador.'))
        Stage = self.env['construction.stage'].with_context(active_test=False)
        Type = self.env['construction.resource.type'].with_context(active_test=False)
        stages = Stage
        for vals in data.get('stages', []):
            stage = Stage.search([('code', '=', vals['code'])], limit=1)
            values = {key: vals[key] for key in ('name', 'sequence', 'kind',
                                                 'production_consumption', 'duration_days')
                      if key in vals}
            if vals.get('color'):
                values['color'] = vals['color']
            stage = stage.write(values) and stage if stage else Stage.create(
                dict(values, code=vals['code']))
            stages |= stage
        for vals in data.get('stages', []):
            if vals.get('previous'):
                Stage.search([('code', '=', vals['code'])]).previous_stage_id = Stage.search(
                    [('code', '=', vals['previous'])], limit=1)
        types = Type
        for vals in data.get('resource_types', []):
            rtype = Type.search([('code', '=', vals['code'])], limit=1)
            values = {key: vals[key] for key in ('name', 'sequence', 'behavior', 'supply_method')}
            rtype = rtype.write(values) and rtype if rtype else Type.create(
                dict(values, code=vals['code']))
            types |= rtype
        template_data = data['level_template']
        Template = self.env['construction.level.template'].with_context(active_test=False)
        template = Template.search([('name', '=', template_data['name'])], limit=1)
        lines = [Command.create({
            'sequence': line['sequence'], 'name': line['name'], 'role': line['role'],
            'has_recipe': line['has_recipe'], 'is_measured': line['is_measured'],
            'is_billable': line['is_billable'], 'receives_progress': line['receives_progress'],
            'measure_uom_id': self.env.ref(line['measure_uom']).id if line.get('measure_uom')
            else False,
            'stage_ids': [Command.set(Stage.search([('code', 'in', line.get('stages', []))]).ids)],
        }) for line in template_data['lines']]
        if not template:
            template = Template.create({
                'name': template_data['name'], 'line_ids': lines,
                'purchase_destination': template_data.get('purchase_destination', 'general')})
        elif not template.line_ids:
            template.write({'line_ids': lines})
        modules = self.env['ir.module.module'].search([('name', 'in', data.get('modules', []))])
        values = {
            'name': data['name'], 'description': data.get('description') or False,
            'note': data.get('note') or False,
            'level_template_id': template.id,
            'stage_ids': [Command.set(stages.ids)],
            'resource_type_ids': [Command.set(types.ids)],
            'module_ids': [Command.set(modules.ids)],
            'feature_control': data.get('features', {}).get('control', True),
            'feature_progress': data.get('features', {}).get('progress', True),
            'analytic_plan_names': data.get('analytic_plans') or False,
            'parameter_ids': [Command.clear()] + [
                Command.create({'name': name, 'value': value})
                for name, value in data.get('parameters', {}).items()],
        }
        profile = self.with_context(active_test=False).search([('code', '=', data['code'])])
        if profile:
            profile.write(values)
        else:
            profile = self.create(dict(values, code=data['code']))
        return profile


class ConstructionVerticalProfileParameter(models.Model):
    _name = 'construction.vertical.profile.parameter'
    _description = 'Parámetro del perfil de vertical'
    _order = 'profile_id, name'

    profile_id = fields.Many2one(
        'construction.vertical.profile', string='Perfil', required=True, ondelete='cascade',
        index=True)
    name = fields.Char(string='Campo de la compañía', required=True,
                       help='Nombre técnico (p. ej. construction_week_start_day).')
    value = fields.Char(string='Valor', required=True,
                        help='Tal como se guarda: «3», «week», «5.0». Un registro, por su '
                             'xmlid.')
    label = fields.Char(string='Parámetro', compute='_compute_label')

    @api.depends('name')
    def _compute_label(self):
        company_fields = self.env['res.company']._fields
        for param in self:
            field = company_fields.get(param.name)
            param.label = field.string if field else self.env._('(no instalado)')

    def _value(self):
        """El valor con el tipo del campo de la compañía."""
        self.ensure_one()
        field = self.env['res.company']._fields.get(self.name)
        if not field:
            return self.value
        if field.type in ('integer',):
            return int(self.value)
        if field.type in ('float', 'monetary'):
            return float(self.value)
        if field.type == 'boolean':
            return self.value.lower() in ('1', 'true', 'sí', 'si')
        if field.type == 'many2one':
            return self.env.ref(self.value).id if '.' in self.value else int(self.value)
        return self.value


class ConstructionProfileImportWizard(models.TransientModel):
    _name = 'construction.profile.import.wizard'
    _description = 'Importar perfil de vertical'

    file = fields.Binary(string='Perfil (JSON)', required=True)
    filename = fields.Char(string='Nombre del archivo')

    def action_import(self):
        self.ensure_one()
        try:
            data = json.loads(base64.b64decode(self.with_context(bin_size=False).file))
        except ValueError as exc:
            raise UserError(self.env._('El archivo no es un JSON válido.')) from exc
        profile = self.env['construction.vertical.profile']._import_data(data)
        return {'type': 'ir.actions.act_window', 'res_model': profile._name,
                'res_id': profile.id, 'view_mode': 'form'}
