# -*- coding: utf-8 -*-
from . import models

# Hasta la versión 2 de al_industry_base, el modelo al.industry, su vista,
# su menú y sus accesos eran de ese módulo. Al actualizarlo, Odoo instala
# este módulo como dependencia nueva antes de seguir con al_industry_base:
# los identificadores pasan aquí antes de cargar los datos, para que la
# instalación los actualice en lugar de duplicarlos y para que al terminar
# la actualización de al_industry_base no se borren por huérfanos.
OLD_MODULE = 'al_industry_base'
NEW_MODULE = 'al_industry_core'
MOVED_MODELS = (
    'ir.model', 'ir.model.fields', 'ir.model.constraint', 'ir.access',
    'ir.ui.view', 'ir.actions.act_window', 'ir.ui.menu',
)


def pre_init_hook(env):
    cr = env.cr
    cr.execute("""
        UPDATE ir_model_data
           SET module = %s
         WHERE module = %s
           AND model IN %s
    """, (NEW_MODULE, OLD_MODULE, MOVED_MODELS))
    if not cr.rowcount:
        return  # instalación nueva: no hay nada que traspasar
    # La tabla de la relación con las compañías y la restricción de código
    # único llevan el módulo dueño en su propio registro.
    cr.execute("""
        WITH old AS (SELECT id FROM ir_module_module WHERE name = %s),
             new AS (SELECT id FROM ir_module_module WHERE name = %s)
        UPDATE ir_model_relation
           SET module = (SELECT id FROM new)
         WHERE module = (SELECT id FROM old)
    """, (OLD_MODULE, NEW_MODULE))
    cr.execute("""
        WITH old AS (SELECT id FROM ir_module_module WHERE name = %s),
             new AS (SELECT id FROM ir_module_module WHERE name = %s)
        UPDATE ir_model_constraint
           SET module = (SELECT id FROM new)
         WHERE module = (SELECT id FROM old)
    """, (OLD_MODULE, NEW_MODULE))
