"""Áreas del repositorio (carpetas de primer nivel con módulos), en el orden
en que se listan en los README y en el addons_path."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AREAS = [
    'OL-ACCOUNTING',
    'OL-INVOICING',
    'OL-PAYROLL',
    'OL-POS',
    'OL-INVENTORY',
    'OL-PROJECTS',
    'OL-INDUSTRIES',
    'OL-HEALTH',
    'OL-TOOLS',
    'OL-THIRD-PARTY',
]
# Áreas con módulos de otros autores: su manifiesto no se toca.
THIRD_PARTY = {'OL-THIRD-PARTY'}
# Licencia de los módulos propios: OPL-1. Excepciones, con su motivo (las
# de OL-THIRD-PARTY/ conservan siempre la de su autor).
LICENSE_DEFAULT = 'OPL-1'
LICENSE_EXCEPTIONS = {
    # Extiende base_tier_validation (AGPL-3): no puede ser propietario.
    'al_construction_material_request': 'LGPL-3',
    # Depende de base_tier_validation (AGPL-3) por la aprobación del plan.
    'al_construction_planner': 'LGPL-3',
    # Extienden el planificador y, con él, base_tier_validation (AGPL-3).
    'al_construction_attendance': 'LGPL-3',
    'al_construction_planner_spreadsheet': 'LGPL-3',
    # Puentes del planificador (paquete 1.7, M17-07): extienden el núcleo.
    'al_construction_planner_mrp': 'LGPL-3',
    'al_construction_planner_purchase': 'LGPL-3',
    'al_construction_planner_subcontract': 'LGPL-3',
    'al_construction_planner_subcontract_purchase': 'LGPL-3',
    'al_construction_planner_subcontract_sale': 'LGPL-3',
    'al_construction_planner_crew': 'LGPL-3',
    'al_construction_planner_budget': 'LGPL-3',
    'al_construction_planner_sale': 'LGPL-3',
    'al_construction_planner_furniture': 'LGPL-3',
    'al_construction_planner_sale_furniture': 'LGPL-3',
    'al_construction_planner_suite': 'LGPL-3',
    # Paquete 1.9 (M19-07): aprobaciones en la aplicación Aprobaciones.
    'al_construction_planner_approvals': 'LGPL-3',
    'al_construction_planner_approvals_mrp': 'LGPL-3',
    'al_construction_planner_production': 'LGPL-3',
    # Paquetes de industria que instalan el planificador (LGPL-3 por él).
    'al_industry_construction': 'LGPL-3',
    'al_industry_furniture': 'LGPL-3',
}
# Carpetas de primer nivel que no son áreas de módulos.
NO_AREAS = {'docs', 'scripts', 'mkdocs'}
