"""Áreas del repositorio (carpetas de primer nivel con módulos), en el orden
en que se listan en los README y en el addons_path."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AREAS = [
    'ol-accounting',
    'ol-invoicing',
    'ol-payroll',
    'ol-pos',
    'ol-inventory',
    'ol-projects',
    'ol-tools',
    'ol-third-party',
]
# Áreas con módulos de otros autores: su manifiesto no se toca.
THIRD_PARTY = {'ol-third-party'}
# Licencia de los módulos propios: OPL-1. Excepciones, con su motivo (las
# de ol-third-party/ conservan siempre la de su autor).
LICENSE_DEFAULT = 'OPL-1'
LICENSE_EXCEPTIONS = {
    # Extiende base_tier_validation (AGPL-3): no puede ser propietario.
    'al_construction_material_request': 'LGPL-3',
    # Copia de l10n_pe_city de Laxicon Solution (LGPL-3).
    'al_l10n_pe_city': 'LGPL-3',
}
# Carpetas de primer nivel que no son áreas de módulos.
NO_AREAS = {'docs', 'scripts'}
