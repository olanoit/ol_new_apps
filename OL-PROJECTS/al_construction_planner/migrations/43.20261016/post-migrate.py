# -*- coding: utf-8 -*-
"""CREVAL v1.0, capítulo 5: grupos en dos ejes. Cada usuario pasa a los grupos
nuevos equivalentes a los que tenía (tabla 5.3) y nadie pierde permisos:

* Planificador (anterior) → Plan: planificador y Ejecución: valida; deja de
  tener el grupo anterior, que queda solo como compatibilidad.
* Jefatura de proyectos → Plan: aprueba y Ejecución: aprueba (conserva el rol,
  que citan las rutas de aprobación).
* Reporte de avance y Usuario conservan su XMLID: son Ejecución: reporta
  avance y Ejecución: ejecuta.

Las reglas de validación por niveles que revisaba la jefatura pasan a
Plan: aprueba (planes) o Ejecución: aprueba (lo demás)."""
from odoo import SUPERUSER_ID, api

from odoo.addons.al_construction_planner.models.common import migrate_axis_groups


def migrate(cr, version):
    migrate_axis_groups(api.Environment(cr, SUPERUSER_ID, {}))
