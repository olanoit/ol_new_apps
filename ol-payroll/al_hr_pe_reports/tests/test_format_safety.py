# -*- coding: utf-8 -*-
"""Los TXT bancarios no pueden usar nombres de campo vetados por Odoo 19.

Odoo 19 parchea ``str.format`` (``odoo/_monkeypatches/_cpython.py``) para
frenar la inyección por cadena de formato. Si un campo de la plantilla
contiene ``__`` o un atributo de la lista negra de ``safe_eval``, el
parche **devuelve la plantilla sin formatear y sin avisar**: el archivo
que se manda al banco sale con los marcadores literales.

Pasó de verdad con Interbank: el campo ``benef_code`` contenía ``f_code``
y el detalle salía como ``02{doc_type}{benef_code}...`` en vez de los 380
caracteres del formato. Esta prueba recorre todas las plantillas del
generador para que no vuelva a colarse.
"""
import string

from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import _UNSAFE_ATTRIBUTES

from odoo.addons.al_hr_pe_reports.models import hr_multipayment


def _templates():
    """Plantillas de formato de todas las funciones del generador."""
    for name, func in vars(hr_multipayment).items():
        code = getattr(func, '__code__', None)
        if not code:
            continue
        for const in code.co_consts:
            if isinstance(const, str) and '{' in const and '}' in const:
                yield name, const


@tagged('post_install', '-at_install')
class TestFormatSafety(TransactionCase):

    def test_no_forbidden_field_names(self):
        """Ningún campo de plantilla colisiona con la lista negra."""
        offenders = []
        for func_name, template in _templates():
            try:
                fields = list(string.Formatter().parse(template))
            except ValueError:
                continue
            for _lit, expr, spec, _conv in fields:
                for chunk in (expr, spec):
                    if not chunk:
                        continue
                    if '__' in chunk or any(a in chunk for a in _UNSAFE_ATTRIBUTES):
                        offenders.append('%s → {%s}' % (func_name, chunk))
        self.assertFalse(
            offenders,
            'campos vetados por el parche de str.format de Odoo 19 (la '
            'plantilla se emitiría sin formatear): %s' % ', '.join(offenders))

    def test_templates_actually_format(self):
        """Comprobación de humo: las plantillas se sustituyen de verdad."""
        for func_name, template in _templates():
            try:
                fields = [expr for _l, expr, _s, _c
                          in string.Formatter().parse(template)
                          if expr is not None]
            except ValueError:
                continue
            # Solo plantillas de campos con nombre: las posicionales
            # ({} o {0}) no se pueden rellenar con kwargs.
            if not fields or not all(f and not f.isdigit() for f in fields):
                continue
            names = set(fields)
            rendered = template.format(**{name: '' for name in names})
            for name in names:
                self.assertNotIn(
                    '{%s}' % name, rendered,
                    'la plantilla de %s se emite sin formatear' % func_name)
