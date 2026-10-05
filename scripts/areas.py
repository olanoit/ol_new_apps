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
# Carpetas de primer nivel que no son áreas de módulos.
NO_AREAS = {'docs', 'scripts'}
