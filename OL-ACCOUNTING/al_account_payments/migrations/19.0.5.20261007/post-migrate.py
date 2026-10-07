# -*- coding: utf-8 -*-
"""Versión 5: Tabla 10 (tipo de medio de pago) según el anexo vigente.

El 011 figuraba como «LETRAS DE CAMBIO» y SUNAT lo define como documentos
de EDPYMES y cooperativas no autorizadas a captar depósitos; 006, 007 y 010
tenían la descripción recortada. Los registros son ``noupdate``: se corrigen
aquí. El 012 y el 013, nuevos, los crea la carga de datos.
"""
from odoo import SUPERUSER_ID, api

NAMES = {
    '006': 'TARJETA DE CRÉDITO EMITIDA EN EL PAÍS POR UNA EMPRESA DEL SISTEMA FINANCIERO',
    '007': 'CHEQUES CON LA CLÁUSULA DE «NO NEGOCIABLE», «INTRANSFERIBLES», «NO A LA ORDEN» '
           'U OTRA EQUIVALENTE, A QUE SE REFIERE EL INCISO G) DEL ARTÍCULO 5° DE LA LEY',
    '010': 'MEDIOS DE PAGO USADOS EN COMERCIO EXTERIOR',
    '011': 'DOCUMENTOS EMITIDOS POR LAS EDPYMES Y LAS COOPERATIVAS DE AHORRO Y CRÉDITO NO '
           'AUTORIZADAS A CAPTAR DEPÓSITOS DEL PÚBLICO',
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for code, name in NAMES.items():
        record = env.ref('al_account_payments.pe_catalog_payment_%s' % code, raise_if_not_found=False)
        if record:
            record.name = name
