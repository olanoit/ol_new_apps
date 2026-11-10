# -*- coding: utf-8 -*-
from collections import defaultdict

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.modules import module as odoo_module

from ..models.construction_furniture_model import rate_family_for


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
    # M118-05, punto 1: los pisos llenan los ambientes.
    floor_task_ids = fields.Many2many(
        'project.task', 'construction_plan_generate_wizard_floor_rel', 'wizard_id', 'task_id',
        string='Pisos', check_company=True,
        domain="[('project_id', '=', project_id), ('construction_level', '=', 'floor')]",
        help='Elegir pisos llena los ambientes de esos pisos.')
    preview_token = fields.Integer(default=0)
    preview_lines = fields.Integer(string='Líneas de la vista previa',
                                   compute='_compute_preview', store=True)
    create_modules = fields.Boolean(
        string='Crear módulos faltantes desde la tipología', default=True,
        help='Crea bajo cada ambiente sin módulos una tarea por módulo de la plantilla de '
             'su tipología. Si el ambiente ya tiene módulos (p. ej. del ETO), no los duplica.')
    include_material = fields.Boolean(string='Materiales', default=True)
    include_contract = fields.Boolean(
        string='Actividades', default=True,
        help='Armado, instalación y demás actividades de mano de obra: como contrata o como '
             'personal propio según su modalidad (la del ambiente, la de la actividad o la de su '
             'etapa).')
    # Las etapas del perfil de la obra, sin lista fija (paquete 1.16, M116-01;
    # antes cuatro casillas que dejaban fuera «2.3 Limpieza»).
    available_stage_ids = fields.Many2many(
        'construction.stage', string='Etapas del perfil', compute='_compute_available_stage_ids')
    stage_ids = fields.Many2many(
        'construction.stage', 'construction_plan_generate_wizard_stage_rel', 'wizard_id',
        'stage_id', string='Etapas', compute='_compute_stage_ids', store=True, readonly=False,
        domain="[('id', 'in', available_stage_ids)]",
        help='Las del perfil de la obra. Toda actividad o material de una etapa elegida entra '
             'al plan.')
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
    # Paquete 1.18, M118-06: días por cada sub etapa del perfil (con 2.3
    # Limpieza) y el programa de la hoja como propuesta.
    stage_day_ids = fields.One2many(
        'construction.plan.generate.stage.day', 'wizard_id', string='Días por sub etapa',
        compute='_compute_stage_day_ids', store=True, readonly=False)
    program_note = fields.Char(string='Programa', compute='_compute_program_note')
    program_changed = fields.Boolean(string='Cambiado respecto del PROGRAMA',
                                     compute='_compute_program_changed')
    schedule_reason = fields.Char(
        string='Motivo del cambio',
        help='Con el ritmo o los días cambiados respecto del PROGRAMA, el motivo queda como plazo '
             'ajustado del presupuesto de mano de obra de cada sub etapa.')
    preview_html = fields.Html(string='Se creará', compute='_compute_preview', sanitize=False,
                               store=True)
    warning_html = fields.Html(string='Advertencias', compute='_compute_preview', sanitize=False,
                               store=True)

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

    @api.model
    def default_get(self, fields_list):
        """M118-06, punto 1: con el PROGRAMA de la hoja guardado en la obra,
        el ritmo propuesto es el suyo."""
        res = super().default_get(fields_list)
        plan = self.env['construction.resource.plan'].browse(
            res.get('plan_id') or self.env.context.get('default_plan_id'))
        project = plan.project_id
        if project and project.construction_program_start and project.construction_program_pace:
            res.update({
                'schedule_mode': 'floors_per_week',
                'schedule_pace': project.construction_program_pace,
                'schedule_date_start': project.construction_program_start,
                'schedule_order': project.construction_program_order or 'asc',
            })
        return res

    def _program_days(self):
        self.ensure_one()
        return self.plan_id.project_id.construction_program_days or 0

    @api.depends('plan_id')
    def _compute_stage_day_ids(self):
        legacy = {'production': 'days_production', 'assembly': 'days_assembly',
                  'installation': 'days_installation', 'finishing': 'days_finishing'}
        Stage = self.env['construction.stage']
        for wizard in self:
            program = wizard._program_days()
            stages = Stage._offered_stages(wizard.plan_id.project_id)._leaf_stages() \
                if wizard.plan_id else Stage
            wizard.stage_day_ids = [(5, 0, 0)] + [(0, 0, {
                'stage_id': stage.id,
                'days': program or (wizard[legacy[stage.code]] if stage.code in legacy else 5),
            }) for stage in stages.sorted(lambda st: st._tree_key())]

    @api.depends('plan_id')
    def _compute_program_note(self):
        for wizard in self:
            project = wizard.plan_id.project_id
            wizard.program_note = self.env._(
                'Del PROGRAMA de la hoja «%(sheet)s», enviado el %(date)s',
                sheet=project.construction_program_source or '—',
                date=fields.Date.to_string(fields.Datetime.to_datetime(
                    project.construction_program_date).date())) \
                if project.construction_program_start else False

    @api.depends('schedule_mode', 'schedule_pace', 'schedule_date_start', 'schedule_order',
                 'stage_day_ids.days')
    def _compute_program_changed(self):
        for wizard in self:
            project = wizard.plan_id.project_id
            if not project.construction_program_start or wizard.schedule_mode == 'none':
                wizard.program_changed = False
                continue
            days = project.construction_program_days
            wizard.program_changed = (
                wizard.schedule_mode != 'floors_per_week'
                or abs(wizard.schedule_pace - project.construction_program_pace) > 1e-6
                or wizard.schedule_date_start != project.construction_program_start
                or wizard.schedule_order != (project.construction_program_order or 'asc')
                or bool(days and any(line.days != days for line in wizard.stage_day_ids)))

    def _stage_days(self):
        self.ensure_one()
        days = {line.stage_id.code: line.days for line in self.stage_day_ids if line.days}
        # Las de siempre, si el asistente se creó sin líneas.
        for code, field in (('production', 'days_production'), ('assembly', 'days_assembly'),
                            ('installation', 'days_installation'),
                            ('finishing', 'days_finishing')):
            days.setdefault(code, self[field])
        return days

    @api.onchange('floor_task_ids')
    def _onchange_floor_task_ids(self):
        if self.floor_task_ids:
            self.space_task_ids = self.env['project.task'].search([
                ('project_id', '=', self.plan_id.project_id.id),
                ('construction_level', '=', 'space'),
                ('construction_floor_task_id', 'in', self.floor_task_ids.ids)],
                order='construction_floor_task_id, id')

    def action_preview(self):
        """M118-05, punto 5: la vista previa se calcula al pedirla."""
        self.ensure_one()
        self.preview_token += 1
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new',
                'name': self.env._('Generar plan')}

    @api.depends('plan_id')
    def _compute_available_stage_ids(self):
        Stage = self.env['construction.stage']
        for wizard in self:
            wizard.available_stage_ids = Stage._offered_stages(wizard.plan_id.project_id)

    @api.depends('plan_id')
    def _compute_stage_ids(self):
        Stage = self.env['construction.stage']
        for wizard in self:
            wizard.stage_ids = Stage._offered_stages(wizard.plan_id.project_id)

    def _selected_stages(self):
        return set(self.stage_ids.mapped('code'))

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
                  'line_kinds': defaultdict(lambda: [0, 0.0]),
                  # M118-04, punto 2: monto estimado con el costo de referencia
                  # de las líneas sin costo decidido.
                  'reference': [0.0], 'reference_missing': set(),
                  'reference_products': set()}
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

        # Modalidad de cada actividad (M112-04): la del ambiente (nivel con
        # etapas), la de la actividad o la de su etapa; personal propio por
        # defecto. La contrata a todo costo no aplica al mobiliario: sale como
        # contrata solo de mano de obra y se avisa.
        stage_modes = self.env['construction.stage'].sudo()._execution_modes()

        def labor_type(activity, space):
            mode = activity._execution_mode(space, stage_modes)
            if mode == 'full_contract':
                result['warnings']['full_contract'].append(activity.display_name)
            return 'labor' if mode == 'own' else 'contract'

        # M119-01: con el presupuesto de mano de obra de la obra, el personal
        # propio cuesta jornal ÷ rendimiento exigido y toda línea de mano de
        # obra lleva sus persona-días. La contrata sigue con su tarifa.
        labor_budgets, required_cache = {}, {}

        def labor_budget(vals):
            activity = self.env['construction.labor.activity'].browse(vals.get('activity_id'))
            if not activity or vals['resource_type'] not in ('labor', 'contract'):
                return None, 0.0
            mode = 'own' if vals['resource_type'] == 'labor' else 'contract'
            key = (activity.stage, mode)
            if key not in labor_budgets:
                labor_budgets[key] = project._construction_labor_budget_for(*key)
            budget = labor_budgets[key]
            if not budget:
                return None, 0.0
            if (budget.id, activity.id) not in required_cache:
                required_cache[(budget.id, activity.id)] = budget._required_productivity(activity)
            return budget, required_cache[(budget.id, activity.id)]

        today = fields.Date.context_today(self)
        reference_cache = {}

        def reference(vals):
            """M118-04, punto 1: costo del producto en el maestro, en la
            unidad de la línea, como referencia (el costo planificado sigue
            siendo una decisión)."""
            product = self.env['product.product'].browse(vals.get('product_id'))
            if not product:
                return 0.0
            key = (product.id, vals.get('product_uom_id'))
            if key not in reference_cache:
                uom = self.env['uom.uom'].browse(vals.get('product_uom_id')) or product.uom_id
                cost = product.with_company(plan.company_id).standard_price
                reference_cache[key] = product.uom_id._compute_price(cost, uom) \
                    if uom and uom != product.uom_id else cost
            return reference_cache[key]

        def add(kind, vals):
            if vals.get('resource_type') == 'material':
                vals['price_reference'] = reference(vals)
                vals['price_reference_date'] = today
                if not vals['price_unit_planned']:
                    result['reference'][0] += vals['qty_planned'] * vals['price_reference']
                    if not vals['price_reference']:
                        result['reference_missing'].add(vals['product_id'])
                    result['reference_products'].add(vals['product_id'])
            budget, required = labor_budget(vals)
            if required:
                vals['construction_person_days'] = vals['qty_planned'] / required
                if vals['resource_type'] == 'labor' and budget.daily_wage:
                    vals['price_unit_planned'] = budget.daily_wage / required
                    vals['price_basis'] = self.env._(
                        'Presupuesto de mano de obra: jornal %(wage)s ÷ rendimiento exigido '
                        '%(required)s', wage=round(budget.daily_wage, 2),
                        required=round(required, 2))
            if vals['resource_type'] == 'labor':
                kind = 'labor'
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
            ('ml_based', '=', True), ('ml_group', 'in', ('low', 'high', 'full')),
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
                        common, task_id=task.id if task else False,
                        resource_type=labor_type(activity, space),
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
                            resource_type=labor_type(activity, space), stage=activity.stage,
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
                        listed_qty = typology._ml_of_group(activity.ml_group)
                        if not listed_qty and not has_widths:
                            continue
                    price, basis, basis_date = rate(activity)
                    base = dict(common, resource_type=labor_type(activity, space),
                                stage=activity.stage,
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
    @api.depends('plan_id', 'space_task_ids', 'preview_token')
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
            ('labor', self.env._('Líneas de personal propio'),
             self.env._('Ambiente o módulo')),
            ('material_staged', self.env._('Líneas de material con etapa'), ''),
            ('material_unstaged', self.env._('Líneas de material sin etapa'), ''),
        ]
        for wizard in self:
            if not wizard.plan_id:
                wizard.preview_html = wizard.warning_html = False
                wizard.preview_lines = 0
                continue
            # M118-05, punto 5: al abrir una obra grande (toda la obra) no se
            # calcula; se pide con «Ver vista previa» o al elegir el alcance.
            if not wizard.preview_token and not wizard.space_task_ids \
                    and len(wizard._get_spaces()) > 30:
                wizard.preview_html = Markup('<p class="text-muted">%s</p>') % self.env._(
                    'Elija pisos o ambientes, o pulse «Ver vista previa» para toda la obra.')
                wizard.warning_html = False
                wizard.preview_lines = 0
                continue
            data = wizard._collect()
            wizard.preview_lines = len(data['lines'])
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
                self.env._('Total de líneas (monto con costo decidido)'), total_count,
                fmt(total_amount)))
            # M118-04, punto 2: lo que costarían las líneas sin costo con el
            # costo de referencia del maestro.
            if data['reference_products']:
                rows.append(Markup('<tr class="text-muted"><td>%s</td><td></td><td></td>'
                                   '<td class="text-end">%s</td></tr>') % (
                    self.env._('Monto estimado con el costo de referencia (materiales sin costo '
                               'decidido)'), fmt(data['reference'][0])))
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
                '%(count)s líneas sin costo de %(products)s productos por decidir: el planificador '
                'debe escribirlo (Aplicar costo) antes de enviar el plan a aprobación.',
                count=unpriced, products=len(data['reference_products'])))
        missing = self.env['product.product'].browse(sorted(data['reference_missing']))
        if missing:
            items.append(self.env._(
                'Sin costo en el maestro: %s.', ', '.join(
                    ' · '.join(filter(None, [p.name, p.default_code])) for p in missing[:20])
                + (' …' if len(missing) > 20 else '')))
        messages = {
            'no_typology': self.env._('Ambientes sin tipología (no se generan)'),
            'no_modules': self.env._('Ambientes sin módulos (marque «Crear módulos faltantes»)'),
            'no_bom': self.env._('Tipologías sin lista de materiales'),
            'no_assembly': self.env._(
                'Módulos sin actividad de armado: escríbala o complete su método de unión o su '
                'tipo especial (no se genera su armado)'),
            'module_missing': self.env._(
                'Módulos de la plantilla que no existen en el ambiente (no se generan)'),
            'full_contract': self.env._(
                'Actividades en «Contrata a todo costo», que no aplica al mobiliario: salen como '
                'contrata solo de mano de obra'),
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

    def _background_threshold(self):
        """Líneas desde las que «Generar» va en segundo plano (D 09-nov:
        2,000); se cambia con el parámetro del sistema."""
        return int(self.env['ir.config_parameter'].sudo().get_param(
            'al_construction_planner_furniture.generate_background_lines', 2000))

    def _background_params(self, spaces):
        self.ensure_one()
        return {
            'space_ids': spaces.ids, 'create_modules': self.create_modules,
            'include_material': self.include_material, 'include_contract': self.include_contract,
            'stage_ids': [(6, 0, self.stage_ids.ids)], 'mode': self.mode,
            'schedule_mode': self.schedule_mode, 'schedule_pace': self.schedule_pace,
            'schedule_date_start': fields.Date.to_string(self.schedule_date_start)
            if self.schedule_date_start else False,
            'schedule_order': self.schedule_order,
            'days_production': self.days_production, 'days_assembly': self.days_assembly,
            'days_installation': self.days_installation, 'days_finishing': self.days_finishing,
            'stage_day_ids': [(0, 0, {'stage_id': line.stage_id.id, 'days': line.days})
                              for line in self.stage_day_ids],
            'schedule_reason': self.schedule_reason or False,
        }

    def action_generate(self):
        """M118-05: con más líneas que el umbral (o sin vista previa y una
        obra grande), la generación va en segundo plano y el asistente se
        cierra; si no, como siempre."""
        self.ensure_one()
        plan = self.plan_id
        plan._check_draft()
        plan._construction_check_not_generating()
        if not self._selected_stages():
            raise UserError(self.env._('Elija al menos una etapa.'))
        if self.program_changed and not (self.schedule_reason or '').strip():
            raise UserError(self.env._(
                'El ritmo o los días cambiaron respecto del PROGRAMA de la hoja: escriba el motivo '
                '(queda como plazo ajustado del presupuesto de mano de obra).'))
        spaces = self._get_spaces()
        computed = self.preview_token or self.space_task_ids or len(spaces) <= 30
        estimate = self.preview_lines if computed else self._background_threshold() + 1
        # En las pruebas, en primer plano salvo que lo pidan (las que ya
        # existían generan obras de demostración grandes).
        background = self.env.context.get('construction_generate_background')
        if background is None:
            background = not odoo_module.current_test and estimate > self._background_threshold()
        if background:
            plan._construction_enqueue_generate(self._background_params(spaces), len(spaces))
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'type': 'info', 'sticky': False,
                    'message': self.env._(
                        'Generación en segundo plano de %s ambientes: el plan muestra el avance '
                        'y le avisa al terminar.', len(spaces)),
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }
        self._construction_generate_now()
        return plan.action_view_lines()

    def _construction_schedule(self, spaces):
        self.ensure_one()
        if self.schedule_mode == 'none':
            return
        self.env['construction.space.stage']._schedule_by_pace(
            self.plan_id, spaces, self.schedule_date_start, self.schedule_mode,
            self.schedule_pace, self.schedule_order, self._stage_days())
        if self.program_changed and self.schedule_reason:
            self._adjust_labor_budget()

    def _adjust_labor_budget(self):
        """M118-06, punto 5: el ritmo cambiado respecto del PROGRAMA pasa como
        plazo ajustado del presupuesto de mano de obra de cada sub etapa, con
        su motivo; así presupuesto, Cronograma y tablero tienen las mismas
        fechas."""
        project = self.plan_id.project_id
        budgets = self.env['construction.labor.budget'].search([('project_id', '=', project.id)])
        if not budgets:
            return
        groups = self.env['construction.space.stage']._read_group(
            [('project_id', '=', project.id), ('stage', 'in', budgets.mapped('stage'))],
            ['stage'], ['date_start:min', 'date_end:max'])
        dates = {stage: (start, end) for stage, start, end in groups}
        for budget in budgets:
            if budget.stage in dates and all(dates[budget.stage]):
                budget.write({'date_start_adjusted': dates[budget.stage][0],
                              'date_end_adjusted': dates[budget.stage][1],
                              'adjust_reason': self.schedule_reason})

    def _construction_generate_now(self, post=True):
        """Lo que «Generar» hacía siempre, para los ambientes del asistente.

        :return: ``{'modules': n, 'lines': n}``
        """
        self.ensure_one()
        plan = self.plan_id
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
                construction_furniture_type_id=template.type_id.id,
                construction_join_method=template.join_method,
                construction_width_mm=template.width_mm,
                construction_ml_group=template.ml_group,
                construction_eto_label=template.eto_label or False,
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
        # M119-01: una actividad nueva en la obra copia el rendimiento inicial.
        plan.project_id._construction_productivity_ensure(lines.activity_id)
        # Etapa, partida y área de cada línea (v1.5, M15-12).
        lines._apply_analytic_rules()
        # Las barras del cronograma (P-15): una por ambiente y etapa con líneas.
        stages = self.env['construction.space.stage']._sync_from_plan(plan)
        self._construction_schedule(spaces)
        if post:
            plan.message_post(body=self.env._(
                'Plan generado: %(modules)s tareas de módulo, %(lines)s líneas y %(stages)s '
                'etapas en el cronograma.', modules=len(module_map), lines=len(lines),
                stages=len(stages)))
        return {'modules': len(module_map), 'lines': len(lines)}

    @api.model
    def _get_stage_label(self, stage):
        return dict(self.env['construction.stage']._get_selection()).get(
            stage, self.env._('Sin etapa'))


class ConstructionPlanGenerateStageDay(models.TransientModel):
    """Días de una sub etapa en «Generar plan» (paquete 1.18, M118-06)."""
    _name = 'construction.plan.generate.stage.day'
    _description = 'Días por sub etapa al generar el plan'

    wizard_id = fields.Many2one('construction.plan.generate.wizard', required=True,
                                ondelete='cascade')
    stage_id = fields.Many2one('construction.stage', string='Sub etapa', required=True)
    days = fields.Integer(string='Días', default=5)
