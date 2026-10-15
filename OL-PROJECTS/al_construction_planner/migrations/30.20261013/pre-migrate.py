# -*- coding: utf-8 -*-
"""v1.7, M17-07: el planificador se parte en un núcleo y sus puentes.

Una base que ya tiene el planificador usa todas sus funciones: la
actualización instala todos los puentes (por el módulo que los reúne) en la
misma pasada, para que nada desaparezca del menú, y les pasa lo que ahora es
suyo sin tocar los datos:

* Los xmlid de los registros que los puentes definen en sus archivos de datos
  (acciones, menús, secuencias, reglas de aprobación, plantillas de hitos…)
  y de sus modelos y campos pasan del núcleo al puente: la carga del puente
  los actualiza en lugar de duplicarlos, y la limpieza del final de la carga
  no los borra (ni las columnas con datos).
* Las vistas del núcleo y de los puentes, con las que heredan de ellas, se
  borran y se vuelven a cargar: una vista que pasó a un puente y que aún no
  tiene sus campos en el registro haría fallar la validación de las vistas
  del núcleo al cargarlas.
"""
import ast
import logging
import os

from lxml import etree

from odoo.modules.module import get_manifest, get_module_path
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

CORE = 'al_construction_planner'
SUITE = 'al_construction_planner_suite'
BRIDGES = (
    'al_construction_planner_mrp', 'al_construction_planner_purchase',
    'al_construction_planner_subcontract', 'al_construction_planner_crew',
    'al_construction_planner_budget', 'al_construction_planner_sale',
    'al_construction_planner_furniture', 'al_construction_planner_subcontract_purchase',
)


def _data_xmlids(module):
    """Ids sin prefijo que el módulo define en sus archivos de datos."""
    path = get_module_path(module)
    names = set()
    for data_file in get_manifest(module).get('data', []):
        file_path = os.path.join(path, data_file)
        if data_file.endswith('.xml'):
            for element in etree.parse(file_path).iter():
                record_id = element.get('id') if isinstance(element.tag, str) else None
                if record_id and '.' not in record_id:
                    names.add(record_id)
        elif data_file.endswith('.csv'):
            with open(file_path, encoding='utf-8') as csv_file:
                for line in csv_file.read().splitlines()[1:]:
                    if line:
                        names.add(line.split(',')[0])
    return names


def _python_xmlids(module):
    """Xmlid generados de los modelos (``_name``) y campos que define el módulo."""
    names = set()
    for dirpath, _dirs, files in os.walk(get_module_path(module)):
        if '/tests' in dirpath or '/tools' in dirpath:
            continue
        for file_name in files:
            if not file_name.endswith('.py'):
                continue
            with open(os.path.join(dirpath, file_name), encoding='utf-8') as source:
                tree = ast.parse(source.read())
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                model = None
                fields = []
                for statement in node.body:
                    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 \
                            or not isinstance(statement.targets[0], ast.Name):
                        continue
                    target = statement.targets[0].id
                    value = statement.value
                    if target == '_name' and isinstance(value, ast.Constant):
                        model = value.value
                        names.add('model_' + model.replace('.', '_'))
                    elif target == '_inherit' and model is None and isinstance(value, ast.Constant):
                        model = value.value
                    elif isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) \
                            and isinstance(value.func.value, ast.Name) \
                            and value.func.value.id == 'fields':
                        fields.append(target)
                if model:
                    for field in fields:
                        names.add('field_%s__%s' % (model.replace('.', '_'), field))
    return names


def _drop_views(cr, modules):
    """Borra las vistas de ``modules`` y todas las que heredan de ellas (de
    cualquier módulo), con sus xmlid: se vuelven a cargar en esta pasada."""
    cr.execute(SQL("""
        WITH RECURSIVE tree AS (
            SELECT res_id AS id FROM ir_model_data
             WHERE model = 'ir.ui.view' AND module = ANY(%s)
            UNION
            SELECT view.id FROM ir_ui_view view JOIN tree ON view.inherit_id = tree.id
        )
        SELECT id FROM tree
    """, list(modules)))
    view_ids = [row[0] for row in cr.fetchall()]
    if not view_ids:
        return
    cr.execute(SQL("DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id = ANY(%s)",
                   view_ids))
    # Primero las hijas: la herencia no deja borrar la vista madre.
    cr.execute(SQL("UPDATE ir_ui_view SET inherit_id = NULL, mode = 'primary' WHERE id = ANY(%s)",
                   view_ids))
    cr.execute(SQL("DELETE FROM ir_ui_view WHERE id = ANY(%s)", view_ids))
    _logger.info('Planificador v1.7: %s vistas se vuelven a cargar.', len(view_ids))


def migrate(cr, version):
    if not version:
        return
    available = [module for module in BRIDGES + (SUITE,) if get_module_path(module)]
    for module in available:
        names = _data_xmlids(module) | _python_xmlids(module)
        if not names:
            continue
        cr.execute(SQL("""
            UPDATE ir_model_data SET module = %s
             WHERE module = %s AND name = ANY(%s)
               AND NOT EXISTS (SELECT 1 FROM ir_model_data other
                                WHERE other.module = %s AND other.name = ir_model_data.name)
        """, module, CORE, sorted(names), module))
        _logger.info('Planificador v1.7: %s xmlid pasan a %s.', cr.rowcount, module)
    _drop_views(cr, (CORE,) + tuple(available))
    # Los puentes y el módulo que los reúne se instalan en esta misma pasada
    # (sus dependencias de Odoo ya están: el planificador dependía de ellas).
    cr.execute(SQL("""
        UPDATE ir_module_module SET state = 'to install'
         WHERE name = ANY(%s) AND state = 'uninstalled'
    """, available))
