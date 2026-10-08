#!/usr/bin/env python3
"""Etiquetas en inglés que ve el usuario en los módulos propios (solo lectura).

Lee la base (por defecto ol_pe_v19, con la configuración cfg/my/pe.cfg) y
lista, por módulo, los textos visibles que siguen en inglés en el idioma del
usuario (es_419 si no hay traducción cae al en_US del código):

- etiquetas y ayudas de campos (``ir.model.fields``);
- valores de selección (``ir.model.fields.selection``);
- menús, acciones de ventana y acciones de servidor (incluidos los crons);
- atributos ``string``/``placeholder``/``help``/``title``/``confirm`` y textos
  de las vistas propias (``ir.ui.view``).

Uso::

    python3 docs/validacion/etiquetas_espanol.py                 # todos los propios
    python3 docs/validacion/etiquetas_espanol.py al_l10n_pe_sire  # algunos módulos
    python3 docs/validacion/etiquetas_espanol.py --area OL-PAYROLL

La detección es heurística (palabras inglesas frecuentes sin palabras
españolas); revise el resultado, no lo aplique a ciegas. No escribe nada.
"""
import argparse
import configparser
import json
import re
import sys
from pathlib import Path

import psycopg2
from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
CFG = Path('/home/och/odoo/ce19/cfg/my/pe.cfg')
LANG = 'es_419'
EXCLUDED = {'ol_licencia_perpetua'}

EN_WORDS = set('''
the of and or to for with from by is are be not this that these those it its
date dates name names type types amount amounts total totals number numbers description code codes
status state active company companies partner partners journal journals account accounts
invoice invoices payment payments bill bills report reports settings configuration create
created update updated apply applied cancel cancelled confirm confirmed draft done posted view
views open close closed add remove delete print send sent download upload import export
sequence rate rates currency currencies tax taxes line lines product products customer customers
vendor vendors supplier suppliers document documents reference notes note message messages
error errors warning warnings user users value values field fields model models enabled disabled
select search filter group groups all new other details information info start end until period
periods year years month months day days hour hours full half upcoming national religious holiday
holidays receipt receipts generate generated file files attachment attachments mode provider
key token test production environment connection connections mapping request response timeout
received manual automatic please must cannot can should will when which there here only
already missing required invalid valid wrong success failed failure done pending process
processing processed save saved submit submitted approve approved reject rejected validate
validated validation check checked balance debit credit opening closing fiscal quantity price
unit units subtotal discount label labels title description notes comment comments summary
yes no none default settings level levels rule rules employee employees contract contracts
salary wage wages leave leaves attendance attendances shift shifts worked work entry entries
'''.split())
ES_WORDS = set('''
de la el los las del y en por para con sin un una al se su sus que es son no si o u a e
fecha nombre tipo monto total número descripción código estado activo compañía cuenta factura
pago diario periodo año mes día empresa contacto proveedor cliente documento
'''.split())
ATTRS = ('string', 'placeholder', 'help', 'title', 'confirm', 'sum')


# Textos revisados que el detector marca pero están bien: español que
# coincide con palabras inglesas, siglas, marcas y valores técnicos de ejemplo.
ALLOW = {
    'Manual', 'Balance', 'Carga manual', 'Confirmar TXT manual', 'P. Unit',
    'Token Decolecta', 'Decolecta — requiere token', 'Token SIRE', 'Token / clave',
    'Token Bearer', 'X-Api-Key', 'success', 'pk_test_…', 'sk_test_…',
    # Español que coincide con palabras inglesas
    'Error', 'Token', 'Token MCP', 'Revocar token', 'Domicilio fiscal:', '3 — CAN',
    # Nombres de columna o expresiones que el usuario escribe tal cual
    'check_in', 'check_out', 'contract', 'payslip.wage', 'version.wage',
    'Authorization: Bearer <token>',
    '{"sale.order": ["name", "partner_id"], "res.partner": ["name", "email"]}',
}
# Atributos que no son texto visible (sum="campo" en una lista hija, etc.)
SKIP_VALUES = {'amount', 'amount_usd'}


def looks_english(text):
    if not text or not isinstance(text, str):
        return False
    text = text.strip()
    if text in ALLOW or text in SKIP_VALUES:
        return False
    if not text or re.search(r'[áéíóúñ¿¡ü]', text, re.I):
        return False
    words = re.findall(r"[A-Za-z]+(?:'[a-z]+)?", text)
    if not words:
        return False
    lower = [w.lower() for w in words]
    if any(w in ES_WORDS for w in lower):
        return False
    hits = sum(1 for w in lower if w in EN_WORDS)
    return hits >= 1 and hits >= len(lower) / 3


def shown(value):
    """Texto que ve el usuario: la traducción es_419 o, si falta, el en_US."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return value
    if isinstance(value, dict):
        return value.get(LANG) or value.get('en_US')
    return value


def own_modules(cr, wanted, area):
    names = []
    for manifest in ROOT.glob('OL-*/*/__manifest__.py'):
        module = manifest.parent.name
        if manifest.parent.parent.name == 'OL-THIRD-PARTY' or module in EXCLUDED:
            continue
        if area and manifest.parent.parent.name != area:
            continue
        if wanted and module not in wanted:
            continue
        names.append(module)
    cr.execute("SELECT name FROM ir_module_module WHERE state = 'installed' AND name = ANY(%s)", (names,))
    return sorted(r[0] for r in cr.fetchall())


def owned(cr, module, model):
    cr.execute("SELECT res_id FROM ir_model_data WHERE module = %s AND model = %s", (module, model))
    return [r[0] for r in cr.fetchall()]


def check_module(cr, module):
    found = []
    ids = owned(cr, module, 'ir.model.fields')
    if ids:
        cr.execute("SELECT model, name, field_description, help FROM ir_model_fields WHERE id = ANY(%s)", (ids,))
        for model, name, desc, help_ in cr.fetchall():
            for kind, value in (('campo', desc), ('ayuda', help_)):
                text = shown(value)
                if looks_english(text):
                    found.append((kind, '%s.%s' % (model, name), text))
    ids = owned(cr, module, 'ir.model.fields.selection')
    if ids:
        cr.execute("""SELECT f.model, f.name, s.value, s.name FROM ir_model_fields_selection s
                      JOIN ir_model_fields f ON f.id = s.field_id WHERE s.id = ANY(%s)""", (ids,))
        for model, fname, value, label in cr.fetchall():
            text = shown(label)
            if looks_english(text):
                found.append(('selección', '%s.%s=%s' % (model, fname, value), text))
    for model, table in (('ir.ui.menu', 'ir_ui_menu'), ('ir.actions.act_window', 'ir_act_window'),
                         ('ir.actions.server', 'ir_act_server')):
        ids = owned(cr, module, model)
        if ids:
            cr.execute("SELECT id, name FROM %s WHERE id = ANY(%%s)" % table, (ids,))
            for rid, name in cr.fetchall():
                text = shown(name)
                if looks_english(text):
                    found.append((model.split('.')[-1], '%s,%s' % (model, rid), text))
    ids = owned(cr, module, 'ir.ui.view')
    if ids:
        cr.execute("SELECT id, name, arch_db FROM ir_ui_view WHERE id = ANY(%s)", (ids,))
        for vid, vname, arch in cr.fetchall():
            text = shown(arch)
            if not text:
                continue
            try:
                tree = etree.fromstring(text.encode())
            except etree.XMLSyntaxError:
                continue
            for node in tree.iter():
                if not isinstance(node.tag, str):
                    continue
                for attr in ATTRS:
                    if looks_english(node.get(attr)):
                        found.append(('vista', '%s [%s@%s]' % (vname, node.tag, attr), node.get(attr)))
                for chunk in (node.text, node.tail):
                    if chunk and looks_english(chunk) and node.tag not in ('field', 'xpath', 'attribute'):
                        found.append(('vista', '%s [texto]' % vname, chunk.strip()))
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('modules', nargs='*')
    parser.add_argument('--area')
    parser.add_argument('--db', default='ol_pe_v19')
    args = parser.parse_args()
    config = configparser.ConfigParser()
    config.read(CFG)
    options = config['options']
    conn = psycopg2.connect(dbname=args.db, host=options.get('db_host', 'localhost'),
                            port=options.get('db_port', '5432'), user=options.get('db_user', 'odoo'),
                            password=options.get('db_password'))
    total = 0
    with conn, conn.cursor() as cr:
        for module in own_modules(cr, set(args.modules), args.area):
            found = check_module(cr, module)
            if not found:
                continue
            print('\n## %s (%d)' % (module, len(found)))
            for kind, where, text in found:
                print('  [%s] %s: %s' % (kind, where, ' '.join(text.split())[:120]))
            total += len(found)
    print('\nTotal: %d etiquetas en inglés' % total)
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())
