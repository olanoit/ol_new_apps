"""Afectación 37 (inafecto - transferencia gratuita) como operación gratuita.

``l10n_pe_edi`` decide si un ítem es gratuito con la lista
``FREE_AFFECTATION_REASONS`` (11-16, 21 y 31-36) y deja fuera el 37, que el
catálogo 07 y las reglas 3110/2993 de SUNAT tratan como gratuito: el ítem
salía con su precio y código de precio 01 (rechazo 3234). La lista se lee en
cada llamada, así que basta con completarla.
"""
from odoo.addons.l10n_pe_edi.models import account_edi_xml_ubl_pe as ubl_pe

if '37' not in ubl_pe.FREE_AFFECTATION_REASONS:
    ubl_pe.FREE_AFFECTATION_REASONS.append('37')

FREE_AFFECTATION_REASONS = ubl_pe.FREE_AFFECTATION_REASONS
#: Retiros gravados: el IGV se calcula sobre el valor referencial (3111).
FREE_TAXED_REASONS = ('11', '12', '13', '14', '15', '16')
#: Gratuitas exoneradas o inafectas: sin IGV (3110).
FREE_EXEMPT_REASONS = ('21', '31', '32', '33', '34', '35', '36', '37')
