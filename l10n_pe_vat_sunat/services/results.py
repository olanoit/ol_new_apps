# -*- coding: utf-8 -*-
"""Resultados normalizados de los scrapers de SUNAT.

Los scrapers (``sunat_oficial``) devuelven estas dataclasses; el motor
(``l10n_pe.api.connection``) las convierte a ``dict`` con
``dataclasses.asdict`` y les aplica el mismo mapeo genérico que a una
respuesta JSON. Las claves de la dataclass son las 'rutas' que se
configuran en el mapeo de una conexión de tipo scraper.
"""
from dataclasses import dataclass, field


@dataclass
class RucResult:
    ruc: str = ''
    name: str = ''
    commercial_name: str = ''
    state: str = ''           # ACTIVO / BAJA DE OFICIO / ...
    condition: str = ''       # HABIDO / NO HABIDO / ...
    address: str = ''
    ubigeo: str = ''
    district: str = ''
    province: str = ''
    department: str = ''
    legal_representatives: list = field(default_factory=list)
    annexed_locals: list = field(default_factory=list)


@dataclass
class DniResult:
    dni: str = ''
    first_name: str = ''
    paternal_surname: str = ''
    maternal_surname: str = ''

    @property
    def full_name(self):
        parts = [self.first_name, self.paternal_surname, self.maternal_surname]
        return ' '.join(p for p in parts if p)
