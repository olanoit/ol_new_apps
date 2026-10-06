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
}
# Carpetas de primer nivel que no son áreas de módulos.
NO_AREAS = {'docs', 'scripts'}
