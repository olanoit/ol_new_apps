# -*- coding: utf-8 -*-
"""Valores compartidos del planificador (especificación v1.4, «Modelo de datos»)."""
import unicodedata


def norm(text):
    """Texto comparable: sin tildes, en minúsculas y con un solo espacio."""
    text = unicodedata.normalize('NFKD', str(text or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(text.lower().split())


# Niveles de la jerarquía de la obra en project.task (la obra es el proyecto).
# Es la *función* del nivel; su nombre visible (Torre, Etapa, Sótano…) sale
# de la plantilla de niveles de la obra (v1.5, M15-01). «Agrupador» es todo
# agrupador por encima del que agrupa unidades (piso), y «Mueble» el nivel
# opcional entre el ambiente y el módulo (M15-03).
LEVELS = [
    ('group', 'Agrupador'),
    ('floor', 'Piso'),
    ('apartment', 'Departamento'),
    ('space', 'Ambiente'),
    ('furniture', 'Mueble'),
    ('module', 'Módulo'),
]

# Función de cada nivel de la plantilla (construction.level.template.line).
# Es el lugar que ocupa el nivel en el árbol del planificador, con nombres de
# cualquier rubro (v1.7, M17-01): en mobiliario, torre y piso › departamento
# › ambiente › mueble › módulo; en una constructora, disciplina y subpartida
# › partida › actividad; en tuberías, área y línea › spool.
LEVEL_ROLES = [
    ('group', 'Agrupador'),
    ('unit', 'Unidad de entrega'),
    ('space', 'Nivel con etapas'),
    ('furniture', 'Subnivel'),
    ('module', 'Nivel de detalle'),
]

# Tipo de unidad (M15-02): casuística de las 29 obras vendidas.
UNIT_TYPES = [
    ('apartment', 'Departamento'),
    ('duplex_level', 'Nivel de dúplex'),
    ('duct', 'Ducto'),
    ('parking', 'Estacionamiento'),
    ('common_area', 'Área común'),
    ('storage', 'Depósito'),
    ('commercial', 'Local'),
    ('pilot', 'Piloto'),
]

# Las etapas de ejecución son un catálogo (construction.stage, v1.7): los
# campos de etapa guardan su código y toman la lista de stage_selection.


def stage_selection(model):
    """Lista de los campos de etapa: el catálogo con sus códigos."""
    return model.env['construction.stage']._get_selection()


def stage_group_selection(model):
    """Lista de las etapas de primer nivel (las etapas padre y las etapas
    sueltas): agrupa el análisis por «1 Producción», «2 Instalación»."""
    return model.env['construction.stage']._get_group_selection()


# Destino de la compra masiva (v1.7, M17-14): stock general (mobiliario) o
# directo a la obra con su analítica (constructora).
PURCHASE_DESTINATIONS = [
    ('general', 'Stock general'),
    ('project', 'Directo a la obra con su analítica'),
]

# Comportamiento del tipo de recurso (v1.7, M17-03): el tipo visible es el del
# catálogo construction.resource.type; esto es lo que hace el planificador
# con la línea.
RESOURCE_TYPES = [
    ('material', 'Material'),
    ('service', 'Servicio'),
    ('equipment', 'Equipo'),
    ('contract', 'Contrata'),
    ('labor', 'Personal propio'),
    ('production', 'Producción'),
]

# Modalidad de ejecución (CREVAL v1.0, 6.4; en la etapa y la actividad desde
# el paquete 1.12, M112-04).
EXECUTION_MODES = [
    ('own', 'Personal propio'),
    ('labor_contract', 'Contrata solo de mano de obra'),
    ('full_contract', 'Contrata a todo costo'),
]

MODULE_TYPES = [
    ('low', 'Bajo'),
    ('high', 'Alto'),
    ('drawer', 'Cajonera'),
    ('hood', 'Campana'),
    ('shelf', 'Repisero'),
    ('other', 'Otro'),
]

ML_GROUPS = [
    ('low', 'Mueble bajo'),
    ('high', 'Mueble alto'),
    ('none', 'Sin ML'),
]

UNIT_STATES = [
    ('planned', 'Planificado'),
    ('production', 'En producción'),
    ('produced', 'Producido'),
    ('on_site', 'En obra'),
    ('installed', 'Instalado'),
    ('delivered', 'Entregado'),
]

TYPOLOGY_FAMILIES = [
    ('kitchen', 'Cocina'),
    ('closet', 'Closet'),
    ('bathroom', 'Baño'),
    ('laundry', 'Lavandería'),
    ('duct', 'Ducto'),
    ('common', 'Área común'),
    ('special', 'Especial'),
    ('other', 'Otro'),
]

# Documento de donde sale cada nombre de una tipología (v1.5, M15-04): una
# misma tipología se llama distinto en la cotización, la orden o el ETO.
TYPOLOGY_ALIAS_SOURCES = [
    ('quote', 'Cotización'),
    ('client_order', 'Orden del cliente'),
    ('itemized', 'Itemizado'),
    ('projection', 'Proyección'),
    ('eto', 'ETO'),
    ('other', 'Otro'),
]

FURNITURE_GROUPS = [
    ('low', 'Bajo'),
    ('high', 'Alto'),
    ('other', 'Otro'),
]

# Variantes de una unidad o ambiente (M15-04): «Navarra 605 en Rovere»,
# «once departamentos sin verdulero», un metrado distinto.
UNIT_OVERRIDE_KINDS = [
    ('color', 'Color o acabado'),
    ('exclude', 'Excluir componente'),
    ('qty', 'Metrado distinto'),
]

# Control del saldo del plan en requerimientos de obra y OF (P-11, W-10).
EXCEED_STATES = [
    ('ok', 'En plan'),
    ('exceeded', 'Excede el plan'),
    ('approved', 'Exceso aprobado'),
]

# Días de la semana (valor = date.weekday()): inicio de semana, liquidación y
# pago de contratas (fases 5 y 6).
WEEKDAYS = [
    ('0', 'Lunes'),
    ('1', 'Martes'),
    ('2', 'Miércoles'),
    ('3', 'Jueves'),
    ('4', 'Viernes'),
    ('5', 'Sábado'),
    ('6', 'Domingo'),
]
# Orden del avance físico del módulo: el avance validado solo lo hace subir.
UNIT_STATE_RANK = {state: rank for rank, (state, _label) in enumerate(UNIT_STATES)}
# Líneas que pagan por driver: su avance pondera el de los nodos del árbol.
DRIVER_TYPES = ('contract', 'labor')

# Ruta del ingreso (fase 10): frecuencia de valorización y cobro del fondo de
# garantía de la obra (P-21).
VALUATION_UNITS = [
    ('week', 'Semanas'),
    ('dates', 'Fechas fijas'),
]
GUARANTEE_RELEASES = [
    ('close', 'Al cierre de la obra'),
    ('date', 'En una fecha fija'),
]

# Grupos en dos ejes (CREVAL v1.0, capítulo 5). La jefatura de proyectos y el
# Planificador anterior incluyen a los grupos nuevos, así que basta con
# preguntar por estos.
PLAN_VIEWER_GROUP = 'al_construction_planner.group_planner_plan_viewer'
PLAN_PLANNER_GROUP = 'al_construction_planner.group_planner_plan_planner'
PLAN_APPROVER_GROUPS = ('al_construction_planner.group_planner_plan_approver,'
                        'al_construction_planner.group_planner_manager')
EXEC_USER_GROUP = 'al_construction_planner.group_planner_user'
EXEC_VALIDATOR_GROUP = 'al_construction_planner.group_planner_exec_validator'
# Quien aprueba en la ejecución (antes «la jefatura de proyectos», v1.6,
# M16-09): Ejecución: aprueba o el administrador del planificador.
PROJECT_HEAD_GROUPS = ('al_construction_planner.group_planner_exec_approver,'
                       'al_construction_planner.group_planner_manager')
EXEC_APPROVER_GROUPS = PROJECT_HEAD_GROUPS

# Migración de la escalera anterior a los dos ejes (tabla 5.3): grupo de
# compatibilidad → grupos nuevos y si el usuario deja el de compatibilidad.
AXIS_MIGRATION = [
    ('group_planner_planner', ('group_planner_plan_planner', 'group_planner_exec_validator'), True),
    ('group_planner_project_head', ('group_planner_plan_approver', 'group_planner_exec_approver'),
     False),
]


def migrate_axis_groups(env):
    """Pasa a los usuarios de los grupos anteriores a los nuevos (CREVAL v1.0,
    5.3) sin que pierdan permisos, y las reglas de validación por niveles que
    revisaba la jefatura a los aprobadores de cada eje."""
    from odoo import Command
    ref = 'al_construction_planner.'
    for old_xmlid, new_xmlids, leave in AXIS_MIGRATION:
        old = env.ref(ref + old_xmlid, raise_if_not_found=False)
        if not old:
            continue
        news = [env.ref(ref + xmlid) for xmlid in new_xmlids]
        users = old.with_context(active_test=False).user_ids
        for group in news:
            missing = users - group.user_ids
            if missing:
                group.user_ids = [Command.link(user.id) for user in missing]
        if leave:
            # El administrador y el superusuario lo reciben del Administrador.
            keep = env.ref('base.user_root') | env.ref('base.user_admin')
            gone = users - keep
            if gone:
                old.user_ids = [Command.unlink(user.id) for user in gone]
    # Menús, acciones y reglas que citan los grupos anteriores (también los
    # que quedaron en la base de versiones viejas o hechos a mano): reciben
    # los grupos nuevos equivalentes.
    for old_xmlid, new_xmlids, _leave in AXIS_MIGRATION:
        old = env.ref(ref + old_xmlid, raise_if_not_found=False)
        if not old:
            continue
        news = [env.ref(ref + xmlid) for xmlid in new_xmlids]
        for model, fname in (('ir.ui.menu', 'group_ids'), ('ir.actions.act_window', 'group_ids'),
                             ('ir.actions.server', 'group_ids'),
                             ('ir.actions.report', 'group_ids')):
            records = env[model].with_context(active_test=False).search([(fname, 'in', old.ids)])
            for group in news:
                records.filtered(lambda r: group not in r[fname]).write(
                    {fname: [Command.link(group.id)]})
        # En Odoo 20 cada ir.access tiene un solo grupo: se duplica por grupo nuevo.
        Access = env['ir.access'].with_context(active_test=False)
        for access in Access.search([('group_id', 'in', old.ids)]):
            for group in news:
                if not Access.search_count([
                        ('model_id', '=', access.model_id.id), ('group_id', '=', group.id),
                        ('operation', '=', access.operation), ('domain', '=', access.domain)]):
                    access.copy({'group_id': group.id, 'name': access.name})
    # Las entradas a la ejecución (capítulo 4) quedan activas, como en una
    # instalación nueva (el usuario interno está en un bloque noupdate).
    internal = env.ref('base.group_user')
    for xmlid in ('group_planner_feature_exec_planner', 'group_planner_feature_exec_project'):
        feature = env.ref(ref + xmlid, raise_if_not_found=False)
        if feature and feature not in internal.implied_ids:
            internal.implied_ids = [Command.link(feature.id)]
    head = env.ref(ref + 'group_planner_project_head', raise_if_not_found=False)
    if head:
        definitions = env['tier.definition'].with_context(active_test=False).search(
            [('reviewer_group_id', '=', head.id)])
        plan = definitions.filtered(lambda d: d.model == 'construction.resource.plan')
        plan.reviewer_group_id = env.ref(ref + 'group_planner_plan_approver')
        (definitions - plan).reviewer_group_id = env.ref(ref + 'group_planner_exec_approver')


# Visibilidad de montos (v1.8, M18-10): ver construction_amounts.py.
AMOUNTS_GROUP = 'al_construction_planner.group_planner_amounts'


def can_see_amounts(env):
    """¿El usuario ve montos? El superusuario y los procesos internos, sí."""
    return env.su or env.user.has_group(AMOUNTS_GROUP)


#: Claves de monto en los diccionarios de los paneles OWL.
PANEL_AMOUNT_KEYS = frozenset({
    'amount', 'material', 'contract', 'other', 'total', 'amount_total', 'amount_remaining',
    'price', 'price_unit', 'cost', 'cost_unit'})


def mask_amounts(env, data, keys=PANEL_AMOUNT_KEYS):
    """Quita los montos de lo que devuelve un panel a quien no los ve: las
    claves de monto quedan en ``False`` en todos los niveles."""
    if can_see_amounts(env):
        return data

    def visit(value):
        if isinstance(value, dict):
            return {key: False if key in keys and isinstance(item, (int, float))
                    and not isinstance(item, bool) else visit(item)
                    for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [visit(item) for item in value]
        return value
    return visit(data)
