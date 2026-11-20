# -*- coding: utf-8 -*-
"""Alcance del requerimiento de obra (RQ-01 a RQ-07, «Requerimiento de obra —
selección de nivel y etapa»).

Quien pide indica en el mismo requerimiento para qué niveles (piso,
departamento, ambiente, mueble o los de la plantilla de la obra), etapas y
tareas del Gantt es el material, y «Traer materiales del plan» llena el
requerimiento abierto con el saldo por pedir del plan vigente: una línea por
material, nivel y etapa, enlazada a sus líneas del plan.

El material de la etapa de fabricación (Producción) va a la preproducción de
la planta que elige quien pide; lo demás, a la ubicación de la obra.
"""
from collections import Counter, defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

from odoo.addons.al_construction_planner.models.common import LEVELS, stage_selection

# Selectores de nivel del formulario: uno por nivel de la plantilla (el módulo
# el último, M114-03), hasta seis como los niveles del plan.
SCOPE_DEPTH = 6


def _scope_fields(namespace):
    """Campos de cada selector: lo elegido, su etiqueta (vacía: la obra no
    tiene ese nivel) y lo que se puede elegir según lo elegido arriba."""
    for depth in range(1, SCOPE_DEPTH + 1):
        namespace['construction_scope_%s_ids' % depth] = fields.Many2many(
            'project.task', 'construction_mat_request_scope_%s_rel' % depth,
            'request_id', 'task_id', string='Nivel %s elegido' % depth, copy=False,
            check_company=True,
            help='Vacío: todos los de este nivel bajo lo elegido arriba.')
        namespace['construction_scope_%s_label' % depth] = fields.Char(
            string='Nombre del nivel %s' % depth, compute='_compute_construction_scope')
        # Paquete 1.24, M124-03: el «?» de cada nivel.
        namespace['construction_scope_%s_hint' % depth] = fields.Char(
            string='Orientación del nivel %s' % depth, compute='_compute_construction_scope')
        namespace['construction_scope_%s_allowed_ids' % depth] = fields.Many2many(
            'project.task', string='Nivel %s permitido' % depth,
            compute='_compute_construction_scope')


# Paquete 1.24, M124-01: clave del tipo de los niveles con etapas a los que la
# vertical no les da tipo (el ambiente sin tipología).
NO_TYPE = '_none'


def _plural(count, label):
    """«3 cocinas», «11 closets», «1 ambiente». Un nombre de varias palabras
    queda como está («2 sin tipo»)."""
    word = (label or '').strip().lower()
    if count != 1 and word and ' ' not in word:
        last = word[-1]
        if last in 'aeiouáéó':
            word += 's'
        elif last == 'z':
            word = word[:-1] + 'ces'
        elif last in 'lrndj':
            word += 'es'
        elif last not in 'sx':
            word += 's'
    return '%s %s' % (count, word)


def _join(names):
    """«A», «A y B», «A, B y C»."""
    names = list(names)
    if len(names) < 2:
        return ''.join(names)
    return '%s y %s' % (', '.join(names[:-1]), names[-1])


SCOPE_FIELDS = ['construction_scope_%s_ids' % depth for depth in range(1, SCOPE_DEPTH + 1)]


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_request_production_stage = fields.Boolean(
        string='Etapa Producción en el requerimiento de obra', default=True,
        help='Mientras la orden de fabricación del planificador no esté en uso, el jefe de '
             'producción pide su material por el requerimiento de obra eligiendo la etapa '
             'Producción; se despacha a la preproducción de la planta.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_request_production_stage = fields.Boolean(
        related='company_id.construction_request_production_stage', readonly=False)


class StockLocation(models.Model):
    _inherit = 'stock.location'

    construction_preproduction = fields.Boolean(
        string='Preproducción de planta',
        help='Destino del material de la etapa Producción pedido por el requerimiento de obra '
             '(BRE/Preproducción, PPD/Preproducción).')


class ConstructionStage(models.Model):
    _inherit = 'construction.stage'

    @api.model
    def _construction_production_codes(self):
        """Códigos de las etapas de fabricación (taller): su material va a la
        preproducción de la planta."""
        return set(self.with_context(active_test=False).search(
            [('kind', '=', 'production')]).mapped('code'))

    @api.model
    def _construction_request_stages(self, company, project=None):
        """Etapas que se pueden elegir en el requerimiento: las que llevan
        recursos, sin las de fabricación si el ajuste de la compañía lo apaga.
        Con obra, solo las de su perfil de vertical (y sus sub etapas) más las
        que use su plan vigente (H-24)."""
        stages = self.search([])
        # sudo: quien pide no lee los perfiles de vertical (configuración del
        # planificador); solo se toman las etapas del perfil de su obra.
        profile_sudo = project and project.sudo().construction_profile_id
        if profile_sudo and profile_sudo.stage_ids:
            allowed = self.search([('id', 'child_of', profile_sudo.stage_ids.ids)])
            # sudo: quien pide no ve el plan; solo se leen las etapas que usan
            # las líneas del plan vigente de su obra.
            plan_sudo = project.sudo()._construction_current_plan()
            if plan_sudo:
                codes = {stage for stage, in self.env['construction.resource.plan.line'].sudo()
                         ._read_group([('plan_id', '=', plan_sudo.id)], ['stage'])} - {False}
                allowed |= stages.filtered(lambda stage: stage.code in codes)
            stages &= allowed
        if 'is_group' in self._fields:
            stages = stages.filtered(lambda stage: not stage.is_group)
        if not company.construction_request_production_stage:
            stages = stages.filtered(lambda stage: stage.kind != 'production')
        return stages


class ConstructionMaterialRequest(models.Model):
    _inherit = 'construction.material.request'

    _scope_fields(locals())

    construction_stage_ids = fields.Many2many(
        'construction.stage', 'construction_mat_request_stage_rel', 'request_id', 'stage_id',
        string='Etapas', copy=False,
        domain="[('id', 'in', construction_allowed_stage_ids)]",
        help='Etapa de la obra en la que se usará el material. Vacío: todas las de la obra.')
    construction_allowed_stage_ids = fields.Many2many(
        'construction.stage', string='Etapas permitidas',
        compute='_compute_construction_allowed_stage_ids')
    # Una sola tarea (paquete 1.11, M111-20 E): con varias, las líneas
    # agregadas a mano quedaban sin tarea.
    construction_gantt_task_id = fields.Many2one(
        'project.task', string='Tarea del Gantt', copy=False, check_company=True,
        domain="[('project_id', '=', project_id), ('construction_level', '=', False)]",
        help='Solo para material de una tarea que no está en el plan (una movilización, un '
             'trabajo adicional). "Traer materiales del plan" no la usa.')
    construction_production_location_id = fields.Many2one(
        'stock.location', string='Planta', check_company=True, tracking=True,
        domain="[('construction_preproduction', '=', True), ('usage', '=', 'internal')]",
        help='Preproducción de la planta que recibe el material de la etapa Producción. El '
             'costo sigue yendo a la obra por la analítica de la línea.')
    construction_needs_plant = fields.Boolean(
        string='Lleva material de producción', compute='_compute_construction_needs_plant')
    construction_has_levels = fields.Boolean(
        string='Obra con niveles', compute='_compute_construction_scope')
    # Paquete 1.24, M124-01: tipo del nivel con etapas (en mobiliario, «Tipo
    # de ambiente»). Los tipos los da la vertical (gancho
    # ``project.task._construction_space_types``); sin tipos, no hay selector.
    construction_scope_type_keys = fields.Json(
        string='Tipos elegidos', copy=False,
        help='Claves de los tipos elegidos. Vacío: todos.')
    construction_scope_type_options = fields.Json(
        string='Tipos que se ofrecen', compute='_compute_construction_scope')
    construction_scope_type_depth = fields.Integer(
        string='Selector al que precede el tipo', compute='_compute_construction_scope')
    construction_scope_type_label = fields.Char(
        string='Nombre del selector de tipo', compute='_compute_construction_scope')
    construction_scope_type_hint = fields.Char(
        string='Orientación del selector de tipo', compute='_compute_construction_scope')
    construction_fetch_summary = fields.Char(
        string='Lo que se va a traer', compute='_compute_construction_fetch_summary')
    # Valores por defecto de las líneas agregadas a mano.
    construction_default_stage = fields.Char(
        string='Etapa por defecto', compute='_compute_construction_line_defaults')
    construction_default_task_id = fields.Many2one(
        'project.task', string='Tarea por defecto', compute='_compute_construction_line_defaults')

    # ------------------------------------------------------------------
    # Selectores de nivel en cascada (RQ-01)
    # ------------------------------------------------------------------
    def _construction_scope_slots(self):
        """[(nombre, dominio, orientación, nivel)] de los niveles elegibles de
        la obra, de arriba abajo. Los nombres y la orientación (M124-03) salen de
        la plantilla de niveles; sin plantilla, de los niveles del
        planificador. Un nivel sin tareas en la obra no sale (la obra de
        mobiliario sin muebles: los módulos cuelgan del ambiente)."""
        self.ensure_one()
        if not self.project_id:
            return []
        Task = self.env['project.task']
        template = self.project_id.construction_level_template_id
        if template:
            # El módulo va como último selector (paquete 1.14, M114-03), solo si
            # la obra tiene módulos.
            levels = template.line_ids.sorted(lambda l: (l.sequence, l.id))
            # Solo los niveles que llevan la etapa elegida (M111-20 E): la
            # línea de la plantilla sin etapas las lleva todas.
            stages = self.construction_stage_ids._origin
            if stages:
                levels = levels.filtered(lambda l: not l.stage_ids or l.stage_ids & stages)
            slots = [(line.name, [
                '|', ('construction_level_line_id', '=', line.id),
                '&', ('construction_level_line_id', '=', False),
                ('construction_level', '=', line.level)],
                line._construction_request_hint(), line.level) for line in levels]
        else:
            hint = self.env['construction.level.template.line']._construction_request_hint_default
            slots = [(label, [('construction_level', '=', level)], hint(level), level)
                     for level, label in LEVELS]
        base = [('project_id', '=', self.project_id.id)]
        return [(name, base + domain, hint, level) for name, domain, hint, level in slots
                if Task.search_count(base + domain, limit=1)][:SCOPE_DEPTH]

    def _construction_scope_type_depth(self, slots):
        """Posición (desde 1) del selector del nivel con etapas, al que precede
        el selector de tipo; 0 si la obra no lo tiene."""
        return next((depth for depth, slot in enumerate(slots, 1) if slot[3] == 'space'), 0)

    def _construction_scope_type_noun(self, slots):
        """Nombre, en singular y minúscula, de lo que tiene tipo: el que da la
        vertical («ambiente») o, si no lo da, el del nivel con etapas."""
        type_depth = self._construction_scope_type_depth(slots)
        return self.env['project.task']._construction_space_type_noun() \
            or slots[type_depth - 1][0].lower()

    def _construction_scope_type_set(self):
        self.ensure_one()
        return set(self.construction_scope_type_keys or [])

    def _construction_scope_allowed(self, slots, depth, typed=True):
        """Tareas que se pueden elegir en el nivel ``depth``: las de ese nivel
        que cuelgan de lo elegido en el nivel más bajo de arriba. Con tipos
        elegidos (M124-01), el nivel con etapas ofrece solo los de esos tipos y
        los niveles de abajo, lo que cuelga de ellos. ``typed=False``: sin
        mirar los tipos (para contar los que se ofrecen)."""
        self.ensure_one()
        Task = self.env['project.task']
        if depth > len(slots):
            return Task
        keys = self._construction_scope_type_set() if typed else set()
        type_depth = self._construction_scope_type_depth(slots) if keys else 0
        domain = list(slots[depth - 1][1])
        for upper in range(depth - 1, 0, -1):
            chosen = self['construction_scope_%s_ids' % upper]
            if chosen:
                # En el onchange las tareas llegan como registros nuevos.
                domain.append(('id', 'child_of', chosen._origin.ids))
                break
            if upper == type_depth:
                domain.append(
                    ('id', 'child_of', self._construction_scope_allowed(slots, upper).ids))
                break
        tasks = Task.search(domain)
        if depth == type_depth:
            types = tasks._construction_space_types()
            tasks = tasks.filtered(lambda task: types.get(task.id, (NO_TYPE,))[0] in keys)
        return tasks

    def _construction_scope_type_options(self, slots):
        """[{key, label, count}] de los tipos de los niveles con etapas bajo lo
        elegido arriba, por nombre y con «Sin tipo» al final. Vacío si la
        vertical no da tipos."""
        self.ensure_one()
        type_depth = self._construction_scope_type_depth(slots)
        if not type_depth:
            return []
        spaces = self._construction_scope_allowed(slots, type_depth, typed=False)
        types = spaces._construction_space_types()
        if not types:
            return []
        none = (NO_TYPE, self.env._('Sin tipo'))
        counts = Counter(types.get(space.id, none) for space in spaces)
        return [{'key': key, 'label': label, 'count': count}
                for (key, label), count in sorted(
                    counts.items(), key=lambda item: (item[0][0] == NO_TYPE, item[0][1]))]

    @api.depends('project_id', 'construction_stage_ids', 'construction_scope_type_keys',
                 *SCOPE_FIELDS)
    def _compute_construction_scope(self):
        Task = self.env['project.task']
        for request in self:
            slots = request._construction_scope_slots()
            request.construction_has_levels = bool(slots)
            options = request._construction_scope_type_options(slots)
            type_depth = request._construction_scope_type_depth(slots) if options else 0
            request.construction_scope_type_options = options
            request.construction_scope_type_depth = type_depth
            noun = request._construction_scope_type_noun(slots) if type_depth else ''
            request.construction_scope_type_label = self.env._(
                'Tipo de %s', noun) if type_depth else False
            request.construction_scope_type_hint = (
                Task._construction_space_type_hint() or self.env._(
                    'Tipo de %s al que va el material. Puede elegir varios. Vacío: todos los '
                    'tipos de lo elegido arriba.', noun)
            ) if type_depth else False
            for depth in range(1, SCOPE_DEPTH + 1):
                request['construction_scope_%s_label' % depth] = \
                    slots[depth - 1][0] if depth <= len(slots) else False
                request['construction_scope_%s_hint' % depth] = \
                    slots[depth - 1][2] if depth <= len(slots) else False
                request['construction_scope_%s_allowed_ids' % depth] = \
                    request._construction_scope_allowed(slots, depth)

    @api.onchange('project_id')
    def _onchange_construction_scope_project(self):
        for name in SCOPE_FIELDS + ['construction_gantt_task_id']:
            self[name] = self.env['project.task']
        self.construction_scope_type_keys = False

    @api.onchange('construction_gantt_task_id', *SCOPE_FIELDS)
    def _onchange_construction_gantt_task(self):
        if self.construction_gantt_task_id and self._construction_scope_tasks() is not None:
            return {'warning': {
                'title': self.env._('Niveles y tarea del Gantt'),
                'message': self.env._(
                    'Elegiste niveles y una tarea del Gantt: los materiales del plan van a los '
                    'niveles; los que agregues a mano, a la tarea.'),
            }}
        return None

    @api.onchange('construction_scope_type_keys', *SCOPE_FIELDS)
    def _onchange_construction_scope(self):
        """Lo elegido abajo que ya no cuelga de lo elegido arriba sale, y los
        tipos que ya no tiene lo elegido arriba, también."""
        slots = self._construction_scope_slots()
        keys = self.construction_scope_type_keys or []
        if keys:
            offered = {option['key'] for option in self._construction_scope_type_options(slots)}
            kept = [key for key in keys if key in offered]
            if kept != keys:
                self.construction_scope_type_keys = kept or False
        for depth in range(1, SCOPE_DEPTH + 1):
            name = 'construction_scope_%s_ids' % depth
            if self[name]:
                allowed = set(self._construction_scope_allowed(slots, depth).ids)
                self[name] = self[name].filtered(lambda task: task._origin.id in allowed)

    def _construction_scope_tasks(self):
        """Lo elegido en el nivel más bajo; ``None`` si no se eligió nada (toda
        la obra)."""
        self.ensure_one()
        for depth in range(SCOPE_DEPTH, 0, -1):
            chosen = self['construction_scope_%s_ids' % depth]
            if chosen:
                return chosen
        return None

    def _construction_scope_spaces(self, slots):
        """Niveles con etapas del alcance elegido (M124-01); ``None`` si la
        obra no tiene ese nivel."""
        self.ensure_one()
        type_depth = self._construction_scope_type_depth(slots)
        if not type_depth:
            return None
        Task = self.env['project.task']
        for depth in range(SCOPE_DEPTH, type_depth - 1, -1):
            chosen = self['construction_scope_%s_ids' % depth]._origin
            if chosen:
                spaces = chosen if depth == type_depth \
                    else chosen.mapped('construction_space_task_id')
                if self._construction_scope_type_set():
                    spaces &= self._construction_scope_allowed(slots, type_depth)
                return spaces
        return self._construction_scope_allowed(slots, type_depth) or Task

    @api.depends('project_id', 'construction_plan_id', 'construction_stage_ids',
                 'construction_scope_type_keys', *SCOPE_FIELDS)
    def _compute_construction_fetch_summary(self):
        """M124-01, punto 4: lo que va a traer «Traer materiales del plan»,
        antes de pulsarlo."""
        for request in self:
            if not request.project_id or not request.construction_plan_id:
                request.construction_fetch_summary = False
                continue
            slots = request._construction_scope_slots()
            type_depth = request._construction_scope_type_depth(slots)
            stages = request.construction_stage_ids
            if not stages:
                stage_text = self.env._('todas las etapas')
            elif len(stages) == 1:
                stage_text = self.env._('etapa %s', stages.name)
            else:
                stage_text = self.env._('etapas %s', _join(stages.mapped('name')))
            # Dónde: lo elegido en el nivel más bajo por encima del nivel con
            # etapas (o en cualquiera, si la obra no lo tiene).
            where = self.env._('toda la obra')
            for depth in range((type_depth or SCOPE_DEPTH + 1) - 1, 0, -1):
                chosen = request['construction_scope_%s_ids' % depth]._origin
                if chosen:
                    where = _join(chosen.mapped('name')) if len(chosen) <= 3 \
                        else _plural(len(chosen), slots[depth - 1][0])
                    break
            spaces = request._construction_scope_spaces(slots)
            if spaces is None:
                request.construction_fetch_summary = self.env._(
                    'Se traerá el saldo del plan de %(where)s, %(stages)s.',
                    where=where, stages=stage_text)
                continue
            detail, noun = '', slots[type_depth - 1][0]
            if request.construction_scope_type_depth:
                noun = request._construction_scope_type_noun(slots)
                types = spaces._construction_space_types()
                none = (NO_TYPE, self.env._('Sin tipo'))
                counts = Counter(types.get(space.id, none) for space in spaces)
                detail = _join(
                    _plural(count, label) for (key, label), count in sorted(
                        counts.items(), key=lambda item: (item[0][0] == NO_TYPE, item[0][1])))
            request.construction_fetch_summary = self.env._(
                'Se traerá el saldo del plan de %(spaces)s de %(where)s%(detail)s, %(stages)s.',
                spaces=_plural(len(spaces), noun), where=where,
                detail=': %s' % detail if detail else '', stages=stage_text)

    # ------------------------------------------------------------------
    # Etapas (RQ-02) y tareas del Gantt (RQ-03)
    # ------------------------------------------------------------------
    @api.depends('company_id', 'project_id')
    def _compute_construction_allowed_stage_ids(self):
        Stage = self.env['construction.stage']
        for request in self:
            request.construction_allowed_stage_ids = Stage._construction_request_stages(
                request.company_id, request.project_id)

    def _construction_scope_stage_codes(self):
        """Códigos de las etapas elegidas (vacío: las permitidas)."""
        self.ensure_one()
        stages = self.construction_stage_ids & self.construction_allowed_stage_ids \
            or self.construction_allowed_stage_ids
        return stages.mapped('code')

    @api.depends('construction_stage_ids', 'construction_gantt_task_id', *SCOPE_FIELDS)
    def _compute_construction_line_defaults(self):
        """Nivel y etapa de las líneas agregadas a mano: los del recuadro
        cuando hay uno solo elegido (H-25). La tarea del Gantt manda sobre el
        nivel."""
        for request in self:
            stages = request.construction_stage_ids
            request.construction_default_stage = stages.code if len(stages) == 1 else False
            tasks = request.construction_gantt_task_id
            if not tasks:
                tasks = request._construction_scope_tasks() or self.env['project.task']
            # En el onchange las tareas llegan como registros nuevos.
            request.construction_default_task_id = tasks._origin if len(tasks) == 1 else False

    @api.depends('construction_stage_ids', 'line_ids.construction_stage')
    def _compute_construction_needs_plant(self):
        codes = self.env['construction.stage']._construction_production_codes()
        for request in self:
            request.construction_needs_plant = bool(
                codes & set(request.construction_stage_ids.mapped('code'))
                or request.line_ids.filtered(
                    lambda l: not l.cancelled and l.construction_stage in codes))

    # ------------------------------------------------------------------
    # Traer materiales del plan (RQ-04)
    # ------------------------------------------------------------------
    def _construction_line_analytic(self, plan_lines):
        """La analítica de las líneas del plan pasa a la línea si todas
        coinciden (como el asistente «Requerimiento de obra desde el plan»)."""
        distributions = {tuple(sorted((line.analytic_distribution or {}).items()))
                         for line in plan_lines}
        if len(distributions) == 1 and next(iter(distributions)):
            return {'analytic_distribution': dict(next(iter(distributions)))}
        return {}

    def _construction_line_analytic_common(self, plan_lines):
        """M124-01: las líneas de un mismo tipo comparten la obra y el Rubro
        aunque cada nivel tenga su cuenta. Si no coinciden enteras, pasan a la
        línea las cuentas que todas tienen (cada una con una sola combinación
        al 100 %)."""
        common = None
        for line in plan_lines:
            distribution = line.analytic_distribution or {}
            if len(distribution) != 1:
                return {}
            accounts = {int(account) for account in next(iter(distribution)).split(',')}
            common = accounts if common is None else common & accounts
        if not common:
            return {}
        # El Rubro del tipo va siempre, aunque el plan se haya generado antes
        # de configurar sus cuentas: todos los niveles con etapas de la línea
        # son del mismo tipo.
        rubros = {space._construction_rubro_account().id
                  for space in plan_lines.space_task_id}
        if len(rubros) == 1:
            common |= rubros - {False}
        return {'analytic_distribution': {
            ','.join(str(account) for account in sorted(common)): 100.0}}

    def _construction_fetch_groups(self):
        """{(nivel, producto, etapa, tipo): líneas del plan} del alcance
        elegido: el nivel es lo elegido en el nivel más bajo (la obra si no se
        eligió nada). Con tipos elegidos (M124-01) solo entran las líneas que
        cuelgan de los niveles con etapas de esos tipos, y el tipo es
        ``(clave, nombre)``; sin tipos, ``False`` y todo como antes."""
        self.ensure_one()
        # sudo: quien pide (residente, supervisor) no ve el plan; solo se leen
        # las líneas del plan vigente de su obra para traer su saldo.
        plan_sudo = self.construction_plan_id.sudo()
        domain = [('plan_id', '=', plan_sudo.id), ('resource_type', '=', 'material'),
                  ('product_id', '!=', False), ('is_client_supply', '=', False),
                  ('stage', 'in', self._construction_scope_stage_codes())]
        tasks = self._construction_scope_tasks()
        if tasks is not None:
            domain.append(('task_id', 'child_of', tasks.ids))
        types = {}
        if self._construction_scope_type_set():
            spaces = self._construction_scope_spaces(self._construction_scope_slots())
            if spaces is not None:
                domain.append(('space_task_id', 'in', spaces.ids))
                types = spaces._construction_space_types()
                types = {space.id: types.get(space.id, (NO_TYPE, self.env._('Sin tipo')))
                         for space in spaces}
        Task = self.env['project.task']
        chosen = set(tasks.ids) if tasks is not None else set()
        groups = defaultdict(lambda: self.env['construction.resource.plan.line'].sudo())
        for line in self.env['construction.resource.plan.line'].sudo().search(domain):
            if line.product_id.type != 'consu':
                continue
            level = Task
            if chosen:
                path = [int(i) for i in (line.task_path or '').split('/') if i]
                level = Task.browse(next((i for i in path if i in chosen), line.task_id.id))
            groups[(level, line.product_id, line.stage,
                    types.get(line.space_task_id.id, False))] |= line
        return groups

    def action_construction_fetch_plan(self):
        """«Traer materiales del plan»: una línea por material, nivel y etapa
        (y tipo, si se eligieron tipos: M124-01) con el saldo por pedir,
        enlazada a sus líneas del plan. Lo ya traído no se repite."""
        self.ensure_one()
        self._check_state(('draft',))
        if not self.construction_plan_id:
            raise UserError(self.env._(
                'La obra %s no tiene un plan de recursos vigente: agregue los materiales a mano.',
                self.project_id.display_name))
        existing = {(line.task_id, line.product_id, line.construction_stage,
                     line.construction_space_type_key or False)
                    for line in self.line_ids.filtered(lambda l: not l.cancelled)}
        values, shares_by_key = [], []
        for (level, product, stage, space_type), plan_lines in sorted(
                self._construction_fetch_groups().items(),
                key=lambda kv: (kv[0][0]._construction_path_name() if kv[0][0] else '',
                                kv[0][3][1] if kv[0][3] else '',
                                kv[0][2] or '', kv[0][1].display_name)):
            type_key, type_name = space_type or (False, False)
            if (level, product, stage, type_key) in existing:
                continue
            remaining = sum(line._qty_to_product_uom(line.qty_planned - line.qty_requested)
                            for line in plan_lines)
            if product.uom_id.compare(remaining, 0.0) <= 0:
                continue
            values.append(dict({
                'request_id': self.id,
                'product_id': product.id,
                'product_qty': remaining,
                'product_uom_id': product.uom_id.id,
                'task_id': level.id,
                'construction_stage': stage,
                'construction_space_type_key': type_key,
                'construction_space_type': type_name,
            }, **(self._construction_line_analytic_common(plan_lines) if type_key
                  else self._construction_line_analytic(plan_lines))))
            shares_by_key.append(plan_lines._supply_split(remaining))
        if not values:
            raise UserError(self.env._(
                'No queda saldo por pedir en el plan para esta selección de niveles, tipos y '
                'etapas.'))
        new_lines = self.env['construction.material.request.line'].create(values)
        # sudo: las asignaciones al plan son del planificador; quien pide solo
        # enlaza las líneas de su propio requerimiento (como al solicitar la
        # aprobación, _construction_sync_allocations).
        self.env['construction.resource.plan.allocation'].sudo().create([{
            'plan_line_id': plan_line.id,
            'kind': 'material_request',
            'material_request_line_id': request_line.id,
            'qty_allocated': share,
        } for request_line, shares in zip(new_lines, shares_by_key)
            for plan_line, share in shares.items() if not plan_line.product_uom_id.is_zero(share)])
        if not self.date_required:
            dates = [line.date_needed for shares in shares_by_key for line in shares
                     if line.date_needed]
            if dates:
                # Una necesidad del plan ya pasada no deja el requerimiento
                # vencido al nacer: se propone hoy (H-28).
                self.date_required = max(min(dates), fields.Date.context_today(self))
        self.construction_plan_id.sudo()._mark_in_progress()
        self.message_post(body=self.env._(
            '%(count)s materiales traídos del plan %(plan)s.',
            count=len(new_lines), plan=self.construction_plan_id.sudo().display_name))
        return True

    # ------------------------------------------------------------------
    # Material de producción (RQ-07)
    # ------------------------------------------------------------------
    def _check_ready_to_submit(self):
        super()._check_ready_to_submit()
        codes = self.env['construction.stage']._construction_production_codes()
        for request in self:
            production = request.line_ids.filtered(
                lambda l: not l.cancelled and l.construction_stage in codes)
            if not production:
                continue
            if not request.company_id.construction_request_production_stage:
                raise UserError(self.env._(
                    'El material de producción se pide con la orden de fabricación: quite la '
                    'etapa Producción de las líneas de %s.', request.name))
            if not request.construction_production_location_id:
                raise UserError(self.env._(
                    'Elija la planta que recibe el material de producción de %s.',
                    request.name))


class ConstructionMaterialRequestLine(models.Model):
    _inherit = 'construction.material.request.line'

    construction_stage = fields.Selection(
        stage_selection, string='Etapa',
        help='Etapa del plan para la que es el material. La de fabricación va a la '
             'preproducción de la planta.')
    # Las etapas que se pueden elegir: las del requerimiento, que son las del
    # perfil de la obra (paquete 1.16, M116-01).
    construction_stage_codes = fields.Json(
        string='Etapas que se ofrecen', compute='_compute_construction_stage_codes')
    # Paquete 1.24, M124-01: tipo del nivel con etapas de la línea traída del
    # plan con tipos elegidos (lo escribe «Traer materiales del plan»).
    construction_space_type_key = fields.Char(string='Clave del tipo', readonly=True, copy=False)
    construction_space_type = fields.Char(
        string='Tipo de ambiente', readonly=True, copy=False,
        help='Tipo de los ambientes de los que sale el saldo de la línea (Cocina, Closet…).')
    construction_level_label = fields.Char(
        string='Nivel', compute='_compute_construction_level_label',
        help='El nivel de la línea y el de arriba, por ejemplo «Dpto 102 / Cocina».')

    @api.depends('request_id.construction_allowed_stage_ids')
    def _compute_construction_stage_codes(self):
        for line in self:
            line.construction_stage_codes = \
                line.request_id.construction_allowed_stage_ids.mapped('code')

    @api.depends('task_id.name', 'task_id.parent_id.name', 'task_id.construction_level',
                 'task_id.construction_level_line_id',
                 'task_id.project_id.construction_level_template_id.path_start_line_id')
    def _compute_construction_level_label(self):
        for line in self:
            line.construction_level_label = line._construction_level_path() or False

    def _get_report_level_label(self):
        """M117-14: en los vales, la ruta completa del nivel."""
        self.ensure_one()
        return self._construction_level_path() or super()._get_report_level_label()

    def _construction_level_path(self):
        """Ruta del nivel (paquete 1.16, M116-04): desde el primer nivel de la
        ruta de la plantilla hasta la tarea, p. ej. «Dpto 101 / Cocina /
        Mueble bajo / Bajo». Sin plantilla, el nivel de arriba y la tarea."""
        self.ensure_one()
        task = self.task_id
        if not task:
            return ''
        template = task.project_id.construction_level_template_id
        if not template or not task.construction_level_line_id:
            parent = task.parent_id
            if task.construction_level and parent.construction_level:
                return '%s / %s' % (parent.name, task.name)
            return task.name
        start = template._construction_path_start()
        start_key = (start.sequence, start.id)
        names, node = [], task
        while node and node.construction_level_line_id:
            # Paquete 1.18, M118-09: el módulo con el rótulo del plano.
            label = node.construction_eto_label \
                if 'construction_eto_label' in node._fields else False
            names.append('%s (%s)' % (node.name, label) if label else node.name)
            level_line = node.construction_level_line_id
            if (level_line.sequence, level_line.id) <= start_key:
                break
            node = node.parent_id
        return ' / '.join(reversed(names))

    @api.depends('construction_stage', 'product_id', 'task_id',
                 'task_id.construction_analytic_account_id')
    def _compute_analytic_distribution(self):
        """Paquete 1.14, M114-04: la línea de obra con etapa y material que no
        viene del plan lleva, además de la obra, las cuentas de las reglas
        analíticas del material en su etapa (lo mismo que la línea del plan).
        Lo que el usuario escriba a mano manda."""
        super()._compute_analytic_distribution()
        for line in self:
            request = line.request_id
            if request.request_type == 'internal' or not line.product_id \
                    or not line.construction_stage:
                continue
            current = line.analytic_distribution or {}
            previous = line._construction_rule_distribution(line._origin.construction_stage) \
                if line._origin.construction_stage else None
            if current and current != (request.analytic_distribution or {}) \
                    and current != previous:
                continue
            distribution = line._construction_rule_distribution(line.construction_stage)
            if distribution:
                line.analytic_distribution = distribution

    def _construction_rule_distribution(self, stage):
        """Distribución del requerimiento más las cuentas de las reglas
        analíticas para material, ``stage`` y la categoría del producto."""
        self.ensure_one()
        request = self.request_id
        base = request.analytic_distribution or {}
        if len(base) != 1:
            return {}
        Account = self.env['account.analytic.account']
        accounts = Account.browse(int(a) for a in next(iter(base)).split(','))
        accounts |= self.env['construction.analytic.rule']._accounts_for(
            request.company_id, 'material', stage, self.product_id.categ_id)
        # Paquete 1.16, M116-05: las cuentas de los niveles de su ruta y el
        # rubro de su ambiente, como la línea del plan.
        task = self.task_id or request.task_id
        if task:
            accounts |= task._construction_path_accounts() \
                | (task.construction_space_task_id or task)._construction_rubro_account()
        return {','.join(str(a) for a in sorted(accounts.ids)): 100.0}

    def _construction_scope_plan_lines(self, plan):
        """Una línea con etapa solo se compara con las líneas del plan de esa
        etapa (las ya enlazadas mandan, en ``_construction_candidate_plan_lines``)."""
        lines = super()._construction_scope_plan_lines(plan)
        if self.construction_stage:
            lines = lines.filtered(lambda l: l.stage == self.construction_stage)
        return lines

    @api.depends('construction_stage')
    def _compute_construction_plan_control(self):
        return super()._compute_construction_plan_control()

    @api.depends('construction_stage', 'request_id.construction_production_location_id')
    def _compute_location_dest_id(self):
        return super()._compute_location_dest_id()

    def _get_default_location_dest(self):
        plant = self.request_id.construction_production_location_id
        if plant and self.construction_stage and self.construction_stage in \
                self.env['construction.stage']._construction_production_codes():
            return plant
        return super()._get_default_location_dest()


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Paquete 1.24, M124-02: en los selectores de «¿Para qué es el material?»
    # cada opción se ve con su camino («Piso 19 · 1907 · Closet 2 · CL-09») y
    # la etiqueta elegida, con el nivel de arriba («1907 · Closet 2»). El
    # nombre de la tarea no cambia: solo se arma con el contexto del selector.
    construction_scope_short_name = fields.Char(
        string='Nombre en el alcance', compute='_compute_construction_scope_short_name')

    @api.depends('name', 'parent_id.name', 'construction_level')
    def _compute_construction_scope_short_name(self):
        # sudo: solo el nombre del nivel de arriba de una tarea que ya se ve.
        for task, task_sudo in zip(self, self.sudo()):
            parent_sudo = task_sudo.parent_id
            task.construction_scope_short_name = \
                '%s · %s' % (parent_sudo.name, task_sudo.name) \
                if task_sudo.construction_level and parent_sudo.construction_level \
                else task_sudo.name

    def _construction_scope_long_name(self):
        """Camino de la tarea desde el primer nivel de la obra y, si el nombre
        no la trae, el código de su tipología."""
        self.ensure_one()
        # sudo: nombres de los niveles superiores y código de la tipología de
        # una tarea que el usuario ya puede elegir (no lee las tipologías).
        task_sudo = self.sudo()
        ids = [int(i) for i in (task_sudo.construction_path or '').split('/') if i]
        names = task_sudo.browse(ids).mapped('name') or [task_sudo.name]
        code = task_sudo.construction_typology_id.code
        if code and code.lower() not in (task_sudo.name or '').lower():
            names.append(code)
        return ' · '.join(filter(None, names))

    @api.depends_context('construction_scope_path')
    @api.depends('name', 'construction_path', 'construction_typology_id.code')
    def _compute_display_name(self):
        super()._compute_display_name()
        if not self.env.context.get('construction_scope_path'):
            return
        for task in self.filtered('construction_level'):
            task.display_name = task._construction_scope_long_name()

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if self.env.context.get('construction_scope_path') and value and \
                operator in ('ilike', 'like', '=ilike', '=like', '='):
            # Busca en todo el texto de la opción: «1907» o «CL-09» filtran.
            # sudo: quien pide no lee las tipologías; solo se busca por su
            # código entre las tareas que ya puede elegir.
            typologies_sudo = self.env['construction.typology'].sudo()._search(
                [('code', operator, value)])
            domain = Domain.OR([domain, [('construction_typology_id', 'in', typologies_sudo)]] + [
                [(name, operator, value)] for name in (
                    'parent_id.name', 'construction_floor_task_id.name',
                    'construction_apartment_task_id.name', 'construction_space_task_id.name')])
        return domain
