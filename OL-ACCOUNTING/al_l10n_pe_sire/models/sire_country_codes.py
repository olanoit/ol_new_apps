"""Tabla 16 del anexo 1 de la R.S. 112-2021/SUNAT (incorporada por la R.S.
040-2022): código SUNAT de cada país en el registro de no domiciliados.

Odoo 20 trae el código en ``res.country.l10n_pe_code`` (``l10n_pe_reports``).
Aquí quedan solo los países en que difiere del anexo oficial
(``docs/sire/oficial/anexo-040-2022.pdf``) o que no lo traen:
ISO 3166-1 → (código del anexo, código que trae Odoo o '' si no lo trae).
"""

SIRE_COUNTRY_CODE_FIXES = {
    'CD': ('9888', ''),
    'CI': ('9002', '9193'),
    'ID': ('9365', ''),
    'MC': ('9498', '9497'),
    'SH': ('9710', ''),
    'TN': ('9646', '9820'),
}
