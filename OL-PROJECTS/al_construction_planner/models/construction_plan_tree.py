# -*- coding: utf-8 -*-
"""Árbol de recursos (P-02): nodos con lo acumulado de cada nivel y resumen
de la selección. La acumulación se resuelve con _read_group sobre los
ancestros almacenados de las líneas (floor/apartment/space/module_task_id),
sin recorrer el árbol en Python."""
from odoo import api, models

from .common import DRIVER_TYPES, LEVELS, RESOURCE_TYPES, UNIT_STATES, can_see_amounts, mask_amounts

# Campo de la línea del plan que agrupa por cada nivel (el nodo incluido).
LINE_FIELD = {
    'floor': 'floor_task_id', 'apartment': 'apartment_task_id',
    'space': 'space_task_id', 'furniture': 'furniture_task_id', 'module': 'module_task_id',
}
# Campo de project.task con el ancestro de cada nivel (también incluye al
# propio nodo: el piso es su propio construction_floor_task_id).
TASK_FIELD = {
    'floor': 'construction_floor_task_id', 'apartment': 'construction_apartment_task_id',
    'space': 'construction_space_task_id', 'furniture': 'construction_furniture_task_id',
}
# Los agrupadores (torre, etapa) suman lo de los pisos que tienen debajo:
# no llevan un ancestro propio en las líneas.
GROUP_LEVEL = 'group'
ROOT_KEY = 'p'
TREE_ACTION_FEATURES = {
    'al_construction_planner.action_plan_progress_wizard':
        'al_construction_planner.group_planner_feature_progress',
}

# Acciones de la barra de selección (W-02 a W-08). Las de un puente que no
# está instalado no se muestran; las de una función apagada en Ajustes,
# tampoco (TREE_ACTION_FEATURES).
TREE_ACTIONS = [
    ('al_construction_planner_purchase.action_plan_purchase_wizard', 'Compra masiva', 'shopping_cart'),
    ('al_construction_planner_purchase.action_plan_request_wizard', 'Requerimiento de obra', 'local_shipping'),
    ('al_construction_planner_mrp.action_plan_production_wizard', 'Orden de fabricación', 'factory'),
    ('al_construction_planner_subcontract.action_plan_contract_wizard', 'Asignar contrata', 'handshake'),
    ('al_construction_planner_crew.action_plan_crew_wizard', 'Asignar cuadrilla', 'groups'),
    ('al_construction_planner.action_plan_progress_wizard', 'Registrar avance', 'check_box'),
    ('al_construction_planner.action_plan_reschedule_wizard', 'Cambiar fechas', 'calendar_month'),
]


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def action_open_tree(self):
        """Abre el árbol de recursos de este plan."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'al_construction_planner.plan_tree',
            'name': self.env._('Árbol de recursos · %s', self.display_name),
            'context': {'active_id': self.id, 'active_model': self._name},
        }

    # ------------------------------------------------------------------
    # Filtros
    # ------------------------------------------------------------------
    def _tree_line_domain(self, filters=None):
        """Dominio de las líneas del plan con los filtros del árbol.

        El filtro por estado del módulo solo puede aplicarse a las líneas que
        cuelgan de un módulo: las de ambiente o superiores quedan fuera
        mientras está activo."""
        self.ensure_one()
        filters = filters or {}
        domain = [('plan_id', '=', self.id)]
        if filters.get('stages'):
            # Una etapa padre del filtro son todas sus sub etapas (M18-02).
            domain.append(('stage', 'in', self.env['construction.stage']._leaf_codes(
                filters['stages'])))
        if filters.get('resource_types'):
            domain.append(('resource_type', 'in', filters['resource_types']))
        if filters.get('unit_states'):
            domain.append(('module_task_id.construction_unit_state', 'in', filters['unit_states']))
        partners = filters.get('partner_ids') or []
        if partners:
            ids = [p for p in partners if p]
            if 0 in partners or False in partners:
                domain += ['|', ('partner_id', 'in', ids), ('partner_id', '=', False)]
            else:
                domain.append(('partner_id', 'in', ids))
        return domain

    def _tree_module_domain(self, filters=None):
        domain = [('project_id', '=', self.project_id.id), ('construction_level', '=', 'module')]
        if (filters or {}).get('unit_states'):
            domain.append(('construction_unit_state', 'in', filters['unit_states']))
        return domain

    # ------------------------------------------------------------------
    # Avance valorizado
    # ------------------------------------------------------------------
    @api.model
    def _progress_amounts(self, line_domain, group_field=None):
        """Avance de nodos por valor (especificación, «Avance de un nodo»):
        {clave: (Σ ejecutado × costo unitario, Σ monto planificado)} sobre
        las líneas de contrata y personal propio de ``line_domain``. La
        clave es el id del ancestro ``group_field`` o ``False`` sin agrupar.

        Lo ejecutado son los avances validados (valor guardado en el avance);
        el personal propio por horas suma sus horas al costo del plan."""
        Line = self.env['construction.resource.plan.line']
        Progress = self.env['construction.task.progress']
        domain = list(line_domain) + [('resource_type', 'in', DRIVER_TYPES)]
        groupby = [group_field] if group_field else []

        def key(record):
            return record.id if group_field else False

        planned = {}
        for row in Line._read_group(domain, groupby, ['amount_planned:sum']):
            planned[key(row[0]) if group_field else False] = row[-1] or 0.0
        executed = dict.fromkeys(planned, 0.0)
        for row in Progress._read_group(
                [('state', '=', 'validated'), ('is_rework', '=', False),
                 ('plan_line_id', 'any', domain)],
                groupby, ['amount:sum']):
            group = key(row[0]) if group_field else False
            executed[group] = executed.get(group, 0.0) + (row[-1] or 0.0)
        for line in Line.search(domain + [('resource_type', '=', 'labor')]):
            if line._is_hour_based():
                group = line[group_field].id if group_field else False
                executed[group] = executed.get(group, 0.0) + \
                    line.qty_executed * line.price_unit_planned
        return {group: (executed.get(group, 0.0), planned.get(group, 0.0))
                for group in set(planned) | set(executed)}

    @staticmethod
    def _progress_ratio(amounts, group):
        executed, planned = amounts.get(group, (0.0, 0.0))
        return round(executed / planned, 4) if planned else 0.0

    # ------------------------------------------------------------------
    # Nodos
    # ------------------------------------------------------------------
    @api.model
    def get_tree_filters(self):
        """Opciones de los filtros del árbol (etiquetas en el idioma del usuario)."""
        Line = self.env['construction.resource.plan.line']
        selection = lambda field: [
            [value, label] for value, label in Line._fields[field]._description_selection(self.env)]
        Task = self.env['project.task']
        return {
            'stages': selection('stage'),
            # Árbol de etapas con casillas (M18-02): las de la obra van en
            # orden, con su etapa padre y las hojas que cubre cada una.
            'stage_tree': self.env['construction.stage']._get_tree(),
            'resource_types': selection('resource_type'),
            'unit_states': [[v, l] for v, l in Task._fields[
                'construction_unit_state']._description_selection(self.env)],
            'levels': dict(LEVELS),
        }

    def get_tree_nodes(self, parent_key='root', filters=None):
        """Hijos de un nodo del árbol con lo acumulado de cada uno.

        :param parent_key: ``'root'`` (devuelve la obra), ``'p'`` (los pisos de
            la obra) o el id de una tarea de piso, departamento o ambiente.
        :returns: lista de nodos (dicts) en el orden de las tareas.
        """
        self.ensure_one()
        self.check_access('read')
        Task = self.env['project.task']
        if parent_key == 'root':
            return mask_amounts(self.env, [self._tree_root_node(filters)])
        if parent_key == ROOT_KEY:
            children = Task.search([
                ('project_id', '=', self.project_id.id), ('construction_level', '!=', False),
                ('parent_id', '=', False)], order='sequence, name, id')
        else:
            parent = Task.browse(int(parent_key)).exists()
            if not parent or parent.project_id != self.project_id \
                    or parent.construction_level == 'module':
                return []
            children = Task.search([('parent_id', '=', parent.id),
                                    ('construction_level', '!=', False)],
                                   order='sequence, name, id')
            if (filters or {}).get('unit_states'):
                children = children.filtered(
                    lambda t: t.construction_level != 'module'
                    or t.construction_unit_state in filters['unit_states'])
        # Hermanos de distinto nivel (p. ej. módulos sueltos junto a muebles):
        # cada nivel se resuelve con sus propias consultas, en el orden de las tareas.
        nodes = {}
        for level in dict.fromkeys(children.mapped('construction_level')):
            level_children = children.filtered(lambda t, level=level: t.construction_level == level)
            for node in self._tree_nodes(level_children, level, filters):
                nodes[node['task_id']] = node
        return mask_amounts(self.env, [nodes[task.id] for task in children if task.id in nodes])

    def _tree_root_node(self, filters):
        Line = self.env['construction.resource.plan.line']
        Task = self.env['project.task']
        domain = self._tree_line_domain(filters)
        amounts = self._tree_amounts(Line._read_group(
            domain, ['resource_type'], ['amount_planned:sum', 'qty_planned:sum']))
        modules = Task.search_count(self._tree_module_domain(filters))
        spaces = Task.search([('project_id', '=', self.project_id.id),
                              ('construction_level', '=', 'space')])
        has_children = bool(Task.search_count([
            ('project_id', '=', self.project_id.id), ('construction_level', '!=', False),
            ('parent_id', '=', False)]))
        return dict(amounts, **{
            'key': ROOT_KEY, 'task_id': False, 'name': self.project_id.display_name,
            'level': 'project', 'typology': '', 'modules': modules,
            'ml': round(sum(self._tree_space_ml(spaces).values()), 2),
            'progress': self._progress_ratio(self._progress_amounts(domain), False),
            'unit_state': False, 'has_children': has_children,
        })

    @staticmethod
    def _tree_amounts(groups, base=None):
        """Suma por tipo de recurso de un _read_group (resource_type, monto,
        cantidad)."""
        data = dict(base or {}, material=0.0, contract=0.0, other=0.0, total=0.0,
                    qty_material=0.0, qty_contract=0.0, qty_total=0.0)
        for rtype, amount, qty in groups:
            amount, qty = amount or 0.0, qty or 0.0
            if rtype == 'material':
                data['material'] += amount
                data['qty_material'] += qty
            elif rtype in ('contract', 'labor'):
                data['contract'] += amount
                data['qty_contract'] += qty
            else:
                data['other'] += amount
            data['total'] += amount
            data['qty_total'] += qty
        return {k: round(v, 2) if isinstance(v, float) else v for k, v in data.items()}

    @api.model
    def _tree_space_ml(self, spaces):
        """Metros lineales de cada ambiente: los calcula el rubro mobiliario."""
        return dict.fromkeys(spaces.ids, 0.0)

    @api.model
    def _tree_module_info(self, task):
        """(metros lineales, etiqueta) de un nodo de nivel de detalle: el ancho
        y el código del módulo en mobiliario."""
        return 0.0, ''

    @api.model
    def _tree_furniture_ml(self, children, task_field):
        """{subnivel: metros lineales} (los muebles en mobiliario)."""
        return {}

    @api.model
    def _tree_loose_ml(self, module_domain, spaces):
        """Metros lineales de los módulos sueltos de la selección (su ambiente
        no está entero en ella)."""
        return 0.0

    def _tree_nodes(self, children, level, filters):
        if not children:
            return []
        if level == GROUP_LEVEL:
            return self._tree_group_nodes(children, filters)
        Line = self.env['construction.resource.plan.line']
        Task = self.env['project.task']
        ids = children.ids
        line_field = LINE_FIELD[level]
        groups = {}
        for task, rtype, amount, qty in Line._read_group(
                self._tree_line_domain(filters) + [(line_field, 'in', ids)],
                [line_field, 'resource_type'], ['amount_planned:sum', 'qty_planned:sum']):
            groups.setdefault(task.id, []).append((rtype, amount, qty))

        modules, ml, typology, has_children = {}, {}, {}, {}
        if level == 'module':
            for task in children:
                modules[task.id] = 1
                ml[task.id], typology[task.id] = self._tree_module_info(task)
        else:
            task_field = TASK_FIELD[level]
            modules = {task.id: count for task, count in Task._read_group(
                self._tree_module_domain(filters) + [(task_field, 'in', ids)],
                [task_field], ['__count'])}
            if level == 'furniture':
                ml.update(self._tree_furniture_ml(children, task_field))
            spaces = Task.search([('construction_level', '=', 'space'), (task_field, 'in', ids)])
            space_ml = self._tree_space_ml(spaces)
            codes = {}
            for space in spaces:
                key = space[task_field].id
                ml[key] = ml.get(key, 0.0) + space_ml[space.id]
                if space.construction_typology_id:
                    codes.setdefault(key, set()).add(space.construction_typology_id.code)
            for key, values in codes.items():
                typology[key] = ', '.join(sorted(values)) if len(values) <= 2 else \
                    self.env._('%s tipologías', len(values))
            has_children = {task.id: count for task, count in Task._read_group(
                [('parent_id', 'in', ids), ('construction_level', '!=', False)],
                ['parent_id'], ['__count'])}

        progress = self._progress_amounts(
            self._tree_line_domain(filters) + [(line_field, 'in', ids)], line_field)
        # El nivel con etapas que tiene driver (la partida en m²) avanza por él
        # (v1.8, M18-12); sin filtros de etapa ni de recurso.
        driver_progress = {}
        if level == 'space' and not (filters or {}).get('stages') \
                and not (filters or {}).get('resource_types'):
            driver_progress = {task.id: ratio for task, (ratio, _qty) in
                               children._construction_driver_progress().items()
                               if ratio is not None}
        unit_labels = dict(UNIT_STATES)
        nodes = []
        for task in children:
            node = self._tree_amounts(groups.get(task.id, []))
            node.update({
                'key': str(task.id), 'task_id': task.id, 'name': task.name, 'level': level,
                'level_name': task.construction_level_name,
                'typology': typology.get(task.id, ''), 'modules': modules.get(task.id, 0),
                'ml': round(ml.get(task.id, 0.0), 2),
                'progress': round(driver_progress[task.id], 4) if task.id in driver_progress
                else self._progress_ratio(progress, task.id),
                'unit_state': task.construction_unit_state or False,
                'unit_state_label': unit_labels.get(task.construction_unit_state, ''),
                'has_children': bool(has_children.get(task.id)),
            })
            nodes.append(node)
        return nodes

    def _tree_group_nodes(self, groups, filters):
        """Agrupadores (torre, etapa): suman los nodos de los pisos que tienen
        debajo, con las mismas consultas por piso."""
        Task = self.env['project.task']
        floors = Task.search([('id', 'child_of', groups.ids), ('construction_level', '=', 'floor')])
        floor_nodes = {node['task_id']: node for node in self._tree_nodes(floors, 'floor', filters)}
        owner = {}
        for floor in floors:
            node = floor
            while node and node not in groups:
                node = node.parent_id
            if node:
                owner.setdefault(node.id, []).append(floor_nodes.get(floor.id))
        numeric = ('material', 'contract', 'other', 'total', 'qty_material', 'qty_contract',
                   'qty_total', 'modules', 'ml')
        has_children = {task.id for task, _count in Task._read_group(
            [('parent_id', 'in', groups.ids), ('construction_level', '!=', False)],
            ['parent_id'], ['__count'])}
        nodes = []
        for task in groups:
            parts = [node for node in owner.get(task.id, []) if node]
            node = {key: round(sum(part[key] for part in parts), 2) for key in numeric}
            total = sum(part['total'] for part in parts)
            node.update({
                'key': str(task.id), 'task_id': task.id, 'name': task.name, 'level': GROUP_LEVEL,
                'level_name': task.construction_level_name,
                'typology': '', 'unit_state': False, 'unit_state_label': '',
                'progress': sum(part['progress'] * part['total'] for part in parts) / total
                if total else 0.0,
                'has_children': task.id in has_children,
            })
            nodes.append(node)
        return nodes

    # ------------------------------------------------------------------
    # Selección
    # ------------------------------------------------------------------
    def _tree_selection_tasks(self, keys):
        """Tareas de la selección efectiva expandidas a sus descendientes con
        child_of; ``None`` si la obra entera está marcada."""
        self.ensure_one()
        keys = [str(k) for k in (keys or [])]
        if ROOT_KEY in keys:
            return None
        ids = [int(k) for k in keys if k.isdigit()]
        if not ids:
            return self.env['project.task']
        return self.env['project.task'].search([
            ('id', 'child_of', ids), ('project_id', '=', self.project_id.id)])

    def _tree_selection_line_domain(self, keys, filters=None):
        tasks = self._tree_selection_tasks(keys)
        domain = self._tree_line_domain(filters)
        if tasks is None:
            return domain
        return domain + [('task_id', 'in', tasks.ids)]

    def get_selection_summary(self, keys, filters=None):
        """Resumen de la selección efectiva (barra de selección) y recursos
        acumulados agrupados por actividad, producto o rol (panel lateral)."""
        self.ensure_one()
        self.check_access('read')
        Line = self.env['construction.resource.plan.line']
        Task = self.env['project.task']
        tasks = self._tree_selection_tasks(keys)
        if tasks is not None and not tasks:
            return {'empty': True}
        line_domain = self._tree_selection_line_domain(keys, filters)
        totals = self._tree_amounts(Line._read_group(
            line_domain, ['resource_type'], ['amount_planned:sum', 'qty_planned:sum']))
        module_domain = self._tree_module_domain(filters)
        space_domain = [('project_id', '=', self.project_id.id), ('construction_level', '=', 'space')]
        if tasks is not None:
            module_domain.append(('id', 'in', tasks.ids))
            space_domain.append(('id', 'in', tasks.ids))
        spaces = Task.search(space_domain)
        ml = sum(self._tree_space_ml(spaces).values())
        if tasks is not None:
            ml += self._tree_loose_ml(module_domain, spaces)
        totals.update({
            'empty': False,
            'modules': Task.search_count(module_domain),
            'spaces': len(spaces),
            'ml': round(ml, 2),
        })

        totals['progress'] = self._progress_ratio(self._progress_amounts(line_domain), False)
        totals.update(self._selection_resources(line_domain))
        return mask_amounts(self.env, totals)

    def _selection_resources(self, line_domain):
        """Recursos acumulados de la selección (panel lateral).

        ``resources``: una fila por actividad, producto o rol y unidad, como
        siempre. ``groups`` (v1.8, M18-03): las mismas filas agrupadas por
        tipo de recurso, en el orden del catálogo (materiales, contratas,
        mano de obra propia, equipo, servicios, producción), con subtotal en
        cantidad y en soles, y dentro de cada tipo por etapa y sub etapa."""
        Line = self.env['construction.resource.plan.line']
        type_labels = dict(RESOURCE_TYPES)
        resources, groups = {}, {}
        stage_labels = dict(self.env['construction.stage']._get_selection())
        stage_order = {code: index for index, code in enumerate(stage_labels)}
        # Las líneas de contrata y personal propio siempre tienen actividad.
        for rtype, rtype_rec, stage, activity, product, uom, partner, amount, qty in \
                Line._read_group(
                    line_domain,
                    ['resource_type', 'resource_type_id', 'stage', 'activity_id', 'product_id',
                     'product_uom_id', 'partner_id'],
                    ['amount_planned:sum', 'qty_planned:sum']):
            record = activity or product
            key = (rtype, record._name if record else '', record.id if record else 0, uom.id)
            item = resources.setdefault(key, {
                'resource_type': rtype, 'type_label': type_labels.get(rtype, ''),
                'name': record.display_name if record else self.env._('Sin recurso'),
                'uom': uom.display_name, 'qty': 0.0, 'executed': 0.0, 'amount': 0.0,
                'partners': set(), 'unassigned': False,
            })
            item['qty'] += qty or 0.0
            item['amount'] += amount or 0.0
            if partner:
                item['partners'].add(partner.display_name)
            elif rtype in ('contract', 'labor'):
                item['unassigned'] = True
            group = groups.setdefault(rtype_rec.id or 0, {
                'type_id': rtype_rec.id or False,
                'name': rtype_rec.name or type_labels.get(rtype, self.env._('Sin tipo')),
                'resource_type': rtype, 'sequence': (rtype_rec.sequence, rtype_rec.id or 0),
                'qty': 0.0, 'amount': 0.0, 'keys': {}, 'stages': {},
            })
            group['qty'] += qty or 0.0
            group['amount'] += amount or 0.0
            group['keys'][key] = True
            stage_group = group['stages'].setdefault(stage or False, {
                'stage': stage or False,
                'label': stage_labels.get(stage, self.env._('Sin etapa')),
                'qty': 0.0, 'amount': 0.0, 'items': {},
            })
            stage_group['qty'] += qty or 0.0
            stage_group['amount'] += amount or 0.0
            part = stage_group['items'].setdefault(key, {'qty': 0.0, 'amount': 0.0})
            part['qty'] += qty or 0.0
            part['amount'] += amount or 0.0
        # Acumulado de contratas y personal propio: avances validados por
        # actividad y unidad (las horas del personal propio, por línea).
        executed = {}
        for line in Line.search(line_domain + [('resource_type', 'in', DRIVER_TYPES)]):
            key = (line.resource_type, 'construction.labor.activity', line.activity_id.id,
                   line.product_uom_id.id)
            executed[key] = executed.get(key, 0.0) + line.qty_executed
        for key, qty in executed.items():
            if key in resources:
                resources[key]['executed'] = round(qty, 2)
        rows = []
        for item in sorted(resources.values(), key=lambda r: (-r['amount'], r['name'])):
            partners = sorted(item.pop('partners'))
            if item.pop('unassigned'):
                partners.append(self.env._('sin asignar'))
            item.update(qty=round(item['qty'], 2), amount=round(item['amount'], 2),
                        partners=', '.join(partners))
            rows.append(item)

        def row_of(key, values=None):
            row = dict(resources[key])
            if values:
                row.update(qty=round(values['qty'], 2), amount=round(values['amount'], 2))
            return row

        result_groups = []
        for group in sorted(groups.values(), key=lambda g: g['sequence']):
            stages = []
            for stage_group in sorted(group['stages'].values(),
                                      key=lambda g: stage_order.get(g['stage'], 9999)):
                items = [row_of(key, values) for key, values in stage_group['items'].items()]
                stages.append({
                    'stage': stage_group['stage'], 'label': stage_group['label'],
                    'qty': round(stage_group['qty'], 2), 'amount': round(stage_group['amount'], 2),
                    'resources': sorted(items, key=lambda r: (-r['amount'], r['name'])),
                })
            items = [row_of(key) for key in group['keys']]
            result_groups.append({
                'type_id': group['type_id'], 'name': group['name'],
                'resource_type': group['resource_type'],
                'qty': round(group['qty'], 2), 'amount': round(group['amount'], 2),
                'resources': sorted(items, key=lambda r: (-r['amount'], r['name'])),
                'stages': stages,
            })
        return {'resources': rows, 'groups': result_groups}

    @api.model
    def _plural(self, name):
        """Plural español sencillo de un nombre de nivel (Módulo → Módulos,
        Actividad → Actividades, Mueble → Muebles)."""
        name = (name or '').strip()
        if not name or name[-1].lower() == 's':
            return name
        return name + ('s' if name[-1].lower() in 'aeiouáéíóú' else 'es')

    def _tree_show_ml(self):
        """Columna de metros lineales: solo la vertical mobiliario."""
        self.ensure_one()
        return False

    def get_tree_terms(self):
        """Términos de la vertical para el árbol, el cronograma y sus paneles
        (v1.8, M18-01): los nombres de los niveles de la plantilla de la obra
        y qué columnas propias de mobiliario se muestran."""
        self.ensure_one()
        self.check_access('read')
        project = self.project_id
        terms = self.env['construction.level.labels.mixin']._construction_level_terms(
            project.construction_level_template_id)
        detail = terms.get('module') or self.env._('Módulo')
        space = terms.get('space') or self.env._('Ambiente')
        return {
            'detail': detail, 'details': self._plural(detail),
            'space': space, 'spaces': self._plural(space),
            'unit': terms.get('apartment') or self.env._('Departamento'),
            'show_ml': self._tree_show_ml(),
            'show_amounts': can_see_amounts(self.env),
            'show_typology': bool(self.env['construction.typology'].search_count(
                [('project_id', '=', project.id)], limit=1)),
        }

    def get_tree_partners(self):
        """Contratas y proveedores asignados en el plan (filtro del árbol)."""
        self.ensure_one()
        self.check_access('read')
        partners = self.env['construction.resource.plan.line']._read_group(
            [('plan_id', '=', self.id), ('partner_id', '!=', False)], ['partner_id'])
        return [[partner.id, partner.display_name] for (partner,) in partners]

    @api.model
    def get_tree_actions(self):
        """Botones de la barra de selección: los asistentes instalados que el
        usuario puede abrir."""
        actions = []
        user_groups = self.env.user.all_group_ids
        for xmlid, label, icon in TREE_ACTIONS:
            # sudo: los grupos de la acción solo los lee el administrador; se
            # miran para mostrar el botón a quien puede abrirla.
            action_sudo = self.env.ref(xmlid, raise_if_not_found=False)
            action_sudo = action_sudo.sudo() if action_sudo else action_sudo
            feature = TREE_ACTION_FEATURES.get(xmlid)
            if feature and not self.env.user.has_group(feature):
                continue
            if action_sudo and (not action_sudo.group_ids
                                or action_sudo.group_ids & user_groups):
                actions.append({'xmlid': xmlid, 'name': label, 'icon': icon})
        return actions
