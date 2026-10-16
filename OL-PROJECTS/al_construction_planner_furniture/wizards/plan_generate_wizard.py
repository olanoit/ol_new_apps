# -*- coding: utf-8 -*-
from collections import defaultdict

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.construction_furniture_model import rate_family_for


STAGE_FIELDS = {
    'production': 'stage_production',
    'assembly': 'stage_assembly',
    'installation': 'stage_installation',
    'finishing': 'stage_finishing',
}


class ConstructionPlanGenerateWizard(models.TransientModel):
    """W-01 «Generar plan»: crea las tareas de módulo y las líneas del plan
    desde las tipologías de los ambientes elegidos."""
    _name = 'construction.plan.generate.wizard'
    _description = 'Generar plan de recursos'
    _check_company_auto = True

    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', required=True, check_company=True)
    company_id = fields.Many2one(related='plan_id.company_id', string='Compañía')
    project_id = fields.Many2one(related='plan_id.project_id', string='Obra')
    currency_id = fields.Many2one(related='plan_id.currency_id', string='Moneda')
    space_task_ids = fields.Many2many(
        'project.task', string='Ambientes', check_company=True,
        domain="[('project_id', '=', project_id), ('construction_level', '=', 'space')]",
        help='Vacío: todos los ambientes de la obra.')
    create_modules = fields.Boolean(
        string='Crear módulos faltantes desde la tipología', default=True,
        help='Crea bajo cada ambiente sin módulos una tarea por módulo de la plantilla de '
             'su tipología. Si el ambiente ya tiene módulos (p. ej. del ETO), no los duplica.')
    include_material = fields.Boolean(string='Materiales', default=True)
    include_contract = fields.Boolean(string='Contratas', default=True)
    stage_production = fields.Boolean(string='Producción de piezas', default=True)
    stage_assembly = fields.Boolean(string='Armado', default=True)
    stage_installation = fields.Boolean(string='Instalación', default=True)
    stage_finishing = fields.Boolean(string='Acabado', default=True)
    mode = fields.Selection(
        [('replace', 'Reemplazar lo generado'), ('add', 'Agregar')], string='Si ya hay líneas',
        default='replace', required=True,
        help='Reemplazar borra antes las líneas generadas de esos ambientes (conserva las '
             'manuales y los costos ya escritos); agregar las suma.')
    # Ritmo de programación (v1.5, M15-17).
    schedule_mode = fields.Selection(
        [('none', 'No cambiar fechas'), ('floors_per_week', 'Pisos por semana'),
         ('weeks_per_floor', 'Semanas por piso')], string='Ritmo', default='none', required=True,
        help='Fechas escalonadas de las etapas de cada ambiente: cada piso empieza cuando le '
             'toca según el ritmo y, dentro del ambiente, las etapas van una tras otra en días '
             'hábiles (sin feriados). Las fechas se pueden cambiar después en el cronograma.')
    schedule_pace = fields.Float(
        string='Cantidad', default=1.0,
        help='Pisos que empiezan cada semana, o semanas entre un piso y el siguiente (p. ej. 1.5).')
    schedule_date_start = fields.Date(
        string='Inicio del primer piso', default=fields.Date.context_today)
    schedule_order = fields.Selection(
        [('asc', 'Del primero al último'), ('desc', 'Del último al primero')],
        string='Orden de los pisos', default='asc', required=True)
    days_production = fields.Integer(string='Días de producción', default=5)
    days_assembly = fields.Integer(string='Días de armado', default=5)
    days_installation = fields.Integer(string='Días de instalación', default=5)
    days_finishing = fields.Integer(string='Días de acabado y entrega', default=5)
    preview_html = fields.Html(string='Se creará', compute='_compute_preview', sanitize=False)
    warning_html = fields.Html(string='Advertencias', compute='_compute_preview', sanitize=False)

    # ------------------------------------------------------------------
    # Selección y recolección
    # ------------------------------------------------------------------
    def _get_spaces(self):
        self.ensure_one()
        if self.space_task_ids:
            return self.space_task_ids
        return self.env['project.task'].search([
            ('project_id', '=', self.plan_id.project_id.id),
            ('construction_level', '=', 'space')], order='construction_floor_task_id, id')

    def _selected_stages(self):
        return {stage for stage, field in STAGE_FIELDS.items() if self[field]}

    def _existing_prices(self):
        """Costos ya escritos en el plan por producto y por actividad: se
        conservan al regenerar."""
        if 'construction_price_snapshot' in self.env.context:
            return self.env.context['construction_price_snapshot']
        prices = {}
        for line in self.plan_id.line_ids.filtered('price_unit_planned'):
            key = ('product', line.product_id.id) if line.resource_type == 'material' \
                else ('activity', line.activity_id.id)
            prices.setdefault(key, (line.price_unit_planned, line.price_basis,
                                    line.price_basis_date))
        return prices

    def _collect(self, module_map=None):
        """Recorre los ambientes y devuelve lo que se generaría.

        :param module_map: ``{(space_id, template_id): task}`` con los módulos
            ya creados; sin él (vista previa), los módulos por crear se cuentan.
        :return: dict con ``modules_to_create`` [(space, template)],
            ``lines`` [vals sin task en los módulos por crear] y ``warnings``.
        """
        self.ensure_one()
        plan = self.plan_id
        project = plan.project_id
        stages = self._selected_stages()
        prices = self._existing_prices()
        analytic = {str(project.account_id.id): 100.0} if project.account_id else False
        Task = self.env['project.task']
        result = {'modules_to_create': [], 'lines': [], 'warnings': defaultdict(list),
                  'line_kinds': defaultdict(lambda: [0, 0.0])}
        spaces = self._get_spaces()
        existing_modules = Task.search([
            ('construction_space_task_id', 'in', spaces.ids), ('construction_level', '=', 'module')])
        modules_by_space = defaultdict(lambda: self.env['project.task'])
        for module in existing_modules:
            modules_by_space[module.construction_space_task_id.id] |= module

        # Tarifa: la escrita en el plan o la vigente; sin tarifa de la obra, la
        # de la lista de la familia de la tipología (v1.8, M18-19).
        family = {'value': False}

        def rate(activity):
            if ('activity', activity.id) in prices:
                return prices[('activity', activity.id)]
            return activity.with_context(construction_rate_family=family['value'])._get_rate(
                project)[0], False, False

        # Actividades que salen de las piezas del módulo (M18-20): puertas,
        # cajones, tapas y correderas.
        piece_activities = self.env['construction.labor.activity'].search([
            ('piece_types', '!=', False), ('company_id', 'in', (plan.company_id.id, False))],
            order='sequence, code, id')

        def add(kind, vals):
            result['lines'].append(vals)
            counter = result['line_kinds'][kind]
            counter[0] += 1
            counter[1] += vals['qty_planned'] * vals['price_unit_planned']

        # Actividades por metro lineal (instalación, limpieza…) de la obra:
        # las que tienen tarifa en ella o, si no hay ninguna, las de la
        # compañía. Se aplican a la tipología que no lista ninguna actividad
        # por ML (se apoya en su ML bajo y alto: especificación v1.4, hoja
        # TIPOLOGIAS del maestro, decisión de diseño 5).
        ml_activities = self.env['construction.labor.activity'].search([
            ('ml_based', '=', True), ('ml_group', 'in', ('low', 'high')),
            ('company_id', 'in', (plan.company_id.id, False))], order='code, id')
        project_ml = ml_activities.filtered(
            lambda a: any(rate.project_id == project for rate in a.rate_ids))
        ml_activities = project_ml or ml_activities
        # Con el nivel Mueble en la plantilla de la obra y muebles en la
        # tipología, las actividades por ML cuelgan de cada mueble (v1.5,
        # M15-03): sus ML son los del mueble.
        furniture_level = bool(project._construction_level_lines().get('furniture'))

        for space in spaces:
            typology = space.construction_typology_id
            if not typology:
                result['warnings']['no_typology'].append(space.display_name)
                continue
            family['value'] = rate_family_for(typology.family)
            templates = typology.module_line_ids
            existing = modules_by_space[space.id]
            # Pares (tarea de módulo o None, plantilla).
            modules = []
            if existing:
                by_code = {m.construction_module_code: m for m in existing}
                for template in templates:
                    if template.code in by_code:
                        modules.append((by_code[template.code], template))
                    else:
                        # El ambiente ya tiene módulos (p. ej. del ETO) pero no este.
                        result['warnings']['module_missing'].append(
                            '%s · %s' % (space.display_name, template.code))
            else:
                for template in templates:
                    task = (module_map or {}).get((space.id, template.id))
                    modules.append((task, template))
                    if not task:
                        if self.create_modules:
                            result['modules_to_create'].append((space, template))
                        else:
                            result['warnings']['no_modules'].append(space.display_name)
            # Ancho y grupo ML de cada módulo: los del módulo real (ETO) si los
            # tiene; si no, los de la plantilla (decisión de diseño 5).
            def width(task, template):
                return (task and task.construction_width_mm) or template.width_mm

            def ml_group(task, template):
                return (task and task.construction_width_mm and task.construction_ml_group) \
                    or template.ml_group

            has_widths = any(width(task, template) for task, template in modules)
            common = {
                'plan_id': plan.id, 'typology_id': typology.id, 'source': 'generated',
                'source_ref': typology.code, 'analytic_distribution': analytic,
            }
            # Contratas: armado por módulo.
            if self.include_contract:
                for task, template in modules:
                    # La escrita o la del catálogo por el método de unión o el
                    # tipo especial (v1.8, M18-19).
                    activity = template.effective_assembly_activity_id
                    if not activity:
                        result['warnings']['no_assembly'].append(
                            '%s · %s' % (typology.display_name, template.name or template.code))
                        continue
                    if activity.stage not in stages:
                        continue
                    price, basis, basis_date = rate(activity)
                    add('assembly_module', dict(
                        common, task_id=task.id if task else False, resource_type='contract',
                        stage=activity.stage, activity_id=activity.id,
                        product_id=activity.product_id.id, product_uom_id=activity.uom_id.id,
                        qty_planned=1.0, price_unit_planned=price, price_basis=basis,
                        price_basis_date=basis_date, _space=space, _template=template))
                # Contratas desde las piezas de cada módulo (M18-20).
                for task, template in modules:
                    if not template.piece_ids:
                        continue
                    for activity in piece_activities:
                        if activity.stage not in stages:
                            continue
                        qty = template._piece_quantity(activity)
                        if not qty:
                            continue
                        price, basis, basis_date = rate(activity)
                        add('contract_pieces', dict(
                            common, task_id=task.id if task else False,
                            resource_type='contract', stage=activity.stage,
                            activity_id=activity.id, product_id=activity.product_id.id,
                            product_uom_id=activity.uom_id.id, qty_planned=qty,
                            price_unit_planned=price, price_basis=basis,
                            price_basis_date=basis_date, _space=space, _template=template))
                # Contratas: actividades por ambiente (o por módulo si van por
                # ML con ancho). Las por ML que la tipología no lista entran
                # con su ML bajo o alto (cantidad None → la de la tipología).
                items = [(line.activity_id, line.qty) for line in typology.activity_line_ids]
                listed = typology.activity_line_ids.activity_id
                if not listed.filtered('ml_based'):
                    items += [(activity, None) for activity in ml_activities]
                for activity, listed_qty in items:
                    if activity.stage not in stages:
                        continue
                    if listed_qty is None:
                        listed_qty = typology.ml_low if activity.ml_group == 'low' \
                            else typology.ml_high
                        if not listed_qty and not has_widths:
                            continue
                    price, basis, basis_date = rate(activity)
                    base = dict(common, resource_type='contract', stage=activity.stage,
                                activity_id=activity.id, product_id=activity.product_id.id,
                                product_uom_id=activity.uom_id.id, price_unit_planned=price,
                                price_basis=basis, price_basis_date=basis_date)
                    if activity.ml_based and has_widths:
                        for task, template in modules:
                            if ml_group(task, template) == activity.ml_group \
                                    and width(task, template):
                                add('contract_module', dict(
                                    base, task_id=task.id if task else False,
                                    qty_planned=width(task, template) / 1000.0,
                                    _space=space, _template=template))
                    elif activity.ml_based and furniture_level and typology.furniture_line_ids:
                        for furniture in typology.furniture_line_ids.filtered(
                                lambda f, group=activity.ml_group: f.ml_group == group and f.ml):
                            add('contract_furniture', dict(
                                base, task_id=False, qty_planned=furniture.ml,
                                _space=space, _furniture=furniture))
                    else:
                        if activity.ml_based:
                            result['warnings']['ml_on_space'].append(typology.display_name)
                        add('contract_space', dict(base, task_id=space.id,
                                                   qty_planned=listed_qty))
            # Materiales: la receta del módulo (materiales con su sub etapa,
            # v1.8) o su BOM; si no, la BOM de la tipología.
            if self.include_material:
                for task, template in modules:
                    if template.bom_id or not template.material_ids:
                        continue
                    for material in template.material_ids:
                        if material.stage and material.stage not in stages:
                            continue
                        price, basis, basis_date = prices.get(
                            ('product', material.product_id.id), (0.0, False, False))
                        add('material_staged' if material.stage else 'material_unstaged', dict(
                            common, resource_type='material', stage=material.stage or False,
                            product_id=material.product_id.id,
                            product_uom_id=(material.uom_id or material.product_id.uom_id).id,
                            qty_planned=material.qty, price_unit_planned=price,
                            price_basis=basis, price_basis_date=basis_date,
                            task_id=task.id if task else False, _space=space,
                            _template=template))
                recipe_modules = {template for _task, template in modules
                                  if not template.bom_id and template.material_ids}
                module_boms = [(task, template) for task, template in modules if template.bom_id]
                sources = module_boms and [(task, template, template.bom_id)
                                           for task, template in module_boms] \
                    or ([] if recipe_modules else [(space, None, typology.bom_id)])
                if not module_boms and not recipe_modules and not typology.bom_id:
                    result['warnings']['no_bom'].append(typology.display_name)
                overrides = space._construction_overrides()
                for task, template, bom in sources:
                    if not bom:
                        continue
                    factor = 1.0 / (bom.product_qty or 1.0)
                    for bom_line in bom.bom_line_ids:
                        stage = bom_line.construction_consumption_stage
                        if stage and stage not in stages:
                            continue
                        product = bom_line.product_id
                        line_qty = bom_line.product_qty * factor
                        if overrides:
                            # Variantes de la unidad (M15-04): otro color, sin el
                            # componente o con otro metrado.
                            applied = overrides._apply_to_material(product, line_qty)
                            if applied is None:
                                continue
                            product, line_qty = applied
                        price, basis, basis_date = prices.get(('product', product.id),
                                                              (0.0, False, False))
                        vals = dict(
                            common, resource_type='material', stage=stage or False,
                            product_id=product.id, product_uom_id=bom_line.product_uom_id.id,
                            qty_planned=line_qty,
                            price_unit_planned=price, price_basis=basis,
                            price_basis_date=basis_date)
                        if template:
                            vals.update(task_id=task.id if task else False,
                                        _space=space, _template=template)
                        else:
                            vals['task_id'] = space.id
                        add('material_staged' if stage else 'material_unstaged', vals)
        return result

    # ------------------------------------------------------------------
    # Vista previa
    # ------------------------------------------------------------------
    @api.depends('plan_id', 'space_task_ids', 'create_modules', 'include_material',
                 'include_contract', 'stage_production', 'stage_assembly',
                 'stage_installation', 'stage_finishing', 'mode')
    def _compute_preview(self):
        labels = [
            ('assembly_module', self.env._('Líneas de armado por módulo'), self.env._('Módulo')),
            ('contract_module', self.env._('Líneas de contrata por ML del módulo'),
             self.env._('Módulo')),
            ('contract_pieces', self.env._('Líneas de contrata desde las piezas del módulo'),
             self.env._('Módulo')),
            ('contract_space', self.env._('Líneas de contrata por ambiente'),
             self.env._('Ambiente')),
            ('contract_furniture', self.env._('Líneas de contrata por ML del mueble'),
             self.env._('Mueble')),
            ('material_staged', self.env._('Líneas de material con etapa'), ''),
            ('material_unstaged', self.env._('Líneas de material sin etapa'), ''),
        ]
        for wizard in self:
            if not wizard.plan_id:
                wizard.preview_html = wizard.warning_html = False
                continue
            data = wizard._collect()
            currency = wizard.currency_id
            fmt = lambda amount: '{:,.2f}'.format(currency.round(amount) if currency else amount)
            rows = [Markup('<tr><td>%s</td><td>%s</td><td class="text-end">%s</td>'
                           '<td class="text-end">—</td></tr>') % (
                self.env._('Tareas de módulo'), self.env._('Módulo'),
                len(data['modules_to_create']))]
            total_count, total_amount = 0, 0.0
            for key, label, level in labels:
                count, amount = data['line_kinds'].get(key, (0, 0.0))
                if not count:
                    continue
                total_count += count
                total_amount += amount
                rows.append(Markup('<tr><td>%s</td><td>%s</td><td class="text-end">%s</td>'
                                   '<td class="text-end">%s</td></tr>') % (
                    label, level or self.env._('Ambiente o módulo'), count, fmt(amount)))
            rows.append(Markup('<tr class="fw-bold"><td>%s</td><td></td>'
                               '<td class="text-end">%s</td><td class="text-end">%s</td></tr>') % (
                self.env._('Total de líneas'), total_count, fmt(total_amount)))
            wizard.preview_html = Markup(
                '<table class="table table-sm o_main_table"><thead><tr><th>%s</th><th>%s</th>'
                '<th class="text-end">%s</th><th class="text-end">%s</th></tr></thead>'
                '<tbody>%s</tbody></table>') % (
                self.env._('Se creará'), self.env._('Nivel'), self.env._('Cantidad'),
                self.env._('Monto'), Markup('').join(rows))
            wizard.warning_html = wizard._warnings_html(data)

    def _warnings_html(self, data):
        warnings = data['warnings']
        items = []
        unstaged = data['line_kinds'].get('material_unstaged', (0, 0.0))
        if unstaged[0]:
            items.append(self.env._(
                '%(count)s líneas de material sin etapa: impiden aprobar el plan hasta que la '
                'BOM de la tipología indique su etapa de consumo.', count=unstaged[0]))
        unpriced = sum(1 for vals in data['lines'] if not vals['price_unit_planned'])
        if unpriced:
            items.append(self.env._(
                '%(count)s líneas sin costo: el planificador debe escribirlo (Aplicar costo) '
                'antes de enviar el plan a aprobación.', count=unpriced))
        messages = {
            'no_typology': self.env._('Ambientes sin tipología (no se generan)'),
            'no_modules': self.env._('Ambientes sin módulos (marque «Crear módulos faltantes»)'),
            'no_bom': self.env._('Tipologías sin lista de materiales'),
            'no_assembly': self.env._(
                'Módulos sin actividad de armado: escríbala o complete su método de unión o su '
                'tipo especial (no se genera su armado)'),
            'module_missing': self.env._(
                'Módulos de la plantilla que no existen en el ambiente (no se generan)'),
            'ml_on_space': self.env._(
                'Tipologías sin anchos por módulo: la instalación y la limpieza por ML quedan '
                'en el ambiente (se resuelve cargando los anchos del ETO)'),
        }
        for key, message in messages.items():
            names = sorted(set(warnings.get(key, [])))
            if names:
                items.append('%s: %s' % (message, ', '.join(names[:8]) + (' …' if len(names) > 8 else '')))
        if not items:
            return False
        return Markup('<ul class="mb-0">%s</ul>') % Markup('').join(
            Markup('<li>%s</li>') % escape(item) for item in items)

    # ------------------------------------------------------------------
    # Generación
    # ------------------------------------------------------------------
    def _module_parents(self, modules_to_create):
        """Padre de cada módulo por crear: el ambiente o, si la plantilla de
        niveles de la obra tiene Mueble, el mueble del ambiente que le toca
        (lo crea si falta). Ver ``project.task._construction_furniture_for``."""
        project = self.plan_id.project_id
        has_furniture = bool(project._construction_level_lines().get('furniture'))
        result = {}
        for space, template in modules_to_create:
            if not has_furniture:
                result[(space.id, template.id)] = space
            elif template.furniture_id:
                result[(space.id, template.id)] = space._construction_furniture_named(
                    template.furniture_id.name, template.furniture_id.ml)
            else:
                result[(space.id, template.id)] = space._construction_furniture_for(
                    template.ml_group, template.module_type)
        return result

    def action_generate(self):
        self.ensure_one()
        plan = self.plan_id
        plan._check_draft()
        if not self._selected_stages():
            raise UserError(self.env._('Elija al menos una etapa.'))
        spaces = self._get_spaces()
        if self.mode == 'replace':
            # Los costos escritos se leen antes de borrar (ver _existing_prices).
            prices_snapshot = self._existing_prices()
            old = plan.line_ids.filtered(
                lambda l: l.source == 'generated' and l.space_task_id in spaces)
            old.unlink()
            self = self.with_context(construction_price_snapshot=prices_snapshot)
        data = self._collect()
        module_map = {}
        if data['modules_to_create']:
            Task = self.env['project.task']
            module_vals = plan.project_id._construction_level_vals('module')
            parents = self._module_parents(data['modules_to_create'])
            created = Task.with_context(mail_create_nolog=True, tracking_disable=True).create([dict(
                module_vals,
                name=template.name or template.code,
                project_id=space.project_id.id,
                parent_id=parents[(space.id, template.id)].id,
                construction_module_code=template.code,
                construction_module_type=template.module_type,
                construction_module_class=template.module_class,
                construction_special_kind=template.special_kind,
                construction_join_method=template.join_method,
                construction_width_mm=template.width_mm,
                construction_ml_group=template.ml_group,
                construction_unit_state='planned',
                user_ids=False,
            ) for space, template in data['modules_to_create']])
            for (space, template), task in zip(data['modules_to_create'], created):
                module_map[(space.id, template.id)] = task
            data = self._collect(module_map=module_map)
        vals_list = []
        for vals in data['lines']:
            vals = dict(vals)
            space, template = vals.pop('_space', None), vals.pop('_template', None)
            furniture = vals.pop('_furniture', None)
            if furniture and space:
                vals['task_id'] = space._construction_furniture_named(furniture.name, furniture.ml).id
            elif not vals.get('task_id') and space and template:
                vals['task_id'] = module_map[(space.id, template.id)].id
            vals_list.append(vals)
        # Validación de compañía por lotes (todas las relaciones salen de la obra).
        lines = self.env['construction.resource.plan.line'].with_context(
            construction_plan_generating=True).create(vals_list)
        # Etapa, partida y área de cada línea (v1.5, M15-12).
        lines._apply_analytic_rules()
        # Las barras del cronograma (P-15): una por ambiente y etapa con líneas.
        stages = self.env['construction.space.stage']._sync_from_plan(plan)
        if self.schedule_mode != 'none':
            self.env['construction.space.stage']._schedule_by_pace(
                plan, spaces, self.schedule_date_start, self.schedule_mode, self.schedule_pace,
                self.schedule_order, {
                    'production': self.days_production, 'assembly': self.days_assembly,
                    'installation': self.days_installation, 'finishing': self.days_finishing,
                })
        plan.message_post(body=self.env._(
            'Plan generado: %(modules)s tareas de módulo, %(lines)s líneas y %(stages)s etapas '
            'en el cronograma.', modules=len(module_map), lines=len(lines), stages=len(stages)))
        return plan.action_view_lines()

    @api.model
    def _get_stage_label(self, stage):
        return dict(self.env['construction.stage']._get_selection()).get(
            stage, self.env._('Sin etapa'))
