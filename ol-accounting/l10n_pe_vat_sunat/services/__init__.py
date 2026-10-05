# -*- coding: utf-8 -*-
"""Capa de servicios del módulo ``l10n_pe_vat_sunat``.

Los modelos ORM (`res.partner`, `res.company`) sólo orquestan;
la lógica de red, parsing y resolución de ubigeos vive aquí en
módulos planos (Python sin Odoo `models`), de forma que cada pieza
puede ser testeada de forma aislada y reutilizada por otros módulos
(POS, e-commerce, integraciones externas, etc.).
"""

from . import http
from . import results
from . import sunat_oficial
from . import sunat_padron
from . import ubigeo
