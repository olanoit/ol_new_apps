"""Áreas del repositorio (carpetas de primer nivel con módulos), en el orden
en que se listan en los README y en el addons_path."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AREAS = [
    'accounting',
    'invoicing',
    'payroll',
    'pos',
    'inventory',
    'projects',
    'tools',
    'third_party',
]
# Carpetas de primer nivel que no son áreas de módulos.
NO_AREAS = {'docs', 'scripts'}
