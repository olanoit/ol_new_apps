"""Crea o actualiza la demo de farmacia en una base instalada SIN datos de demostración.

Odoo solo carga los ``demo/*.xml`` al instalar un módulo en una base con demo.
Las bases de desarrollo de clientes (farmacia-dev) no la tienen, así que este
guion carga esos mismos archivos con el registro completo:

* **Empareja** lo que ya existe sin xmlid por su clave natural (producto por
  nombre, contacto por nombre, lote por nombre y producto…) y le asigna el
  xmlid de la demo: se actualiza en vez de duplicarse.
* **Actualiza** el catálogo (productos, presentaciones, principios activos,
  contactos, personal): fotos, indicaciones, códigos y categorías nuevos.
  Las recetas, compras y demás documentos que ya existen no se tocan.
* Ejecuta a mano las funciones de la demo (aplicar inventario solo a las
  existencias nuevas, confirmar compras en borrador, vencer recetas…).

Cómo: cada archivo se filtra en memoria (sin los documentos que ya existen,
sin las existencias de lotes que ya existían y sin las ``<function>``) y se
carga en modo ``init``. En modo ``update`` Odoo salta todo registro existente
de un bloque noupdate, aunque se le quite la marca, y no actualizaría nada.
También sirve para bases con demo: ``-u`` carga la demo con el registro a
medio cargar y los contactos nuevos fallan por columnas obligatorias de
módulos que aún no cargó (``group_rfq`` de Compras).

Uso (odoo shell, todo o nada: si algo falla no se guarda nada)::

    odoo-bin shell -c <cfg> -d <base> --no-http < docs/farmacia/cargar_demo.py
"""
import io
import logging
import re

from lxml import etree

from odoo.tools import file_open
from odoo.tools.convert import convert_xml_import

_logger = logging.getLogger('cargar_demo')

# Archivos de demo en orden de dependencias (los de módulos no instalados se saltan).
# al_pharmacy_loyalty no está: su programa no es noupdate y se duplicaría.
FILES = [
    ('al_pharmacy_base', 'demo/pharmacy_demo.xml'),
    ('al_pharmacy_stock', 'demo/pharmacy_stock_demo.xml'),
    ('al_pharmacy_prescription', 'demo/pharmacy_prescription_demo.xml'),
    ('al_pharmacy_pos', 'demo/pharmacy_pos_demo.xml'),
    ('al_l10n_pe_pharmacy_edi', 'demo/pharmacy_edi_demo.xml'),
    ('al_l10n_pe_prescriber_cmp', 'demo/prescriber_cmp_demo.xml'),
    ('al_l10n_pe_pharmacy_controlled', 'demo/controlled_demo.xml'),
    ('al_l10n_pe_pharmacy_digemid', 'demo/digemid_demo.xml'),
    ('al_pharmacy_care', 'demo/pharmacy_care_demo.xml'),
    ('al_pharmacy_replenishment', 'demo/pharmacy_replenishment_demo.xml'),
    ('al_pharmacy_website', 'demo/website_demo.xml'),
    ('al_pharmacy_insurance', 'demo/pharmacy_insurance_demo.xml'),
    ('al_industry_pharmacy', 'demo/pharmacy_demo.xml'),
]
SUITE = {module for module, _path in FILES} | {'al_pharmacy_loyalty'}
# Modelos del catálogo: se reescriben en cada carga (sin líneas One2many que se dupliquen,
# salvo los principios activos del producto, que se borran antes).
CATALOG = {'product.template', 'res.partner', 'pharmacy.ingredient', 'pharmacy.presentation', 'hr.employee',
           'pharmacy.environment.point'}
REF_IN_EVAL = re.compile(r"env\.ref\('([\w.]+)'\)")


def full_xmlid(module, xmlid):
    return xmlid if '.' in xmlid else f'{module}.{xmlid}'


def field_nodes(record):
    return {node.get('name'): node for node in record.iter('field')}


def resolve(env, module, node):
    """Registro al que apunta un <field ref=…> o un eval con env.ref(…)."""
    if node is None:
        return None
    if node.get('ref'):
        return env.ref(full_xmlid(module, node.get('ref')), raise_if_not_found=False)
    match = REF_IN_EVAL.search(node.get('eval') or '')
    return env.ref(match.group(1), raise_if_not_found=False) if match else None


def find_existing(env, module, model, fields):
    """Registro ya existente (sin xmlid de la demo) que corresponde al del XML."""
    def text(name):
        node = fields.get(name)
        return node.text.strip() if node is not None and node.text else None

    Model = env[model].with_context(active_test=False)
    if model in ('product.template', 'res.partner', 'pharmacy.ingredient', 'hr.employee',
                 'pharmacy.environment.point') and text('name'):
        return Model.search([('name', '=', text('name'))], limit=1)
    if model == 'pharmacy.presentation':
        template = resolve(env, module, fields.get('product_tmpl_id'))
        if template and text('name'):
            return Model.search([('product_tmpl_id', '=', template.id), ('name', '=', text('name'))], limit=1)
    if model == 'stock.lot':
        template = resolve(env, module, fields.get('product_id'))
        if template and text('name'):
            return Model.search([('product_id', 'in', template.product_variant_ids.ids),
                                 ('name', '=', text('name'))], limit=1)
    if model == 'pharmacy.essential.medicine':
        ingredient = resolve(env, module, fields.get('ingredient_id'))
        if ingredient and text('strength'):
            return Model.search([('ingredient_id', '=', ingredient.id), ('strength', '=', text('strength'))],
                                limit=1)
    if model == 'pharmacy.shift':
        employee = resolve(env, module, fields.get('employee_id'))
        if employee:
            return Model.search([('employee_id', '=', employee.id), ('role', '=', text('role'))], limit=1)
    return None


def prepare(env, module, tree, stats):
    """Empareja lo existente y filtra el árbol: queda el catálogo y lo nuevo."""
    Data = env['ir.model.data']
    root = tree.getroot()
    for function in list(root.iter('function')):
        if function.getparent() is not None and function.getparent().tag != 'function':
            function.getparent().remove(function)
    for record in list(root.iter('record')):
        xmlid = full_xmlid(module, record.get('id'))
        model = record.get('model')
        fields = field_nodes(record)
        owner, name = xmlid.split('.', 1)
        existing = env.ref(xmlid, raise_if_not_found=False)
        if not existing and owner == module:
            existing = find_existing(env, module, model, fields)
            if existing:
                Data.create({'module': module, 'name': name, 'model': model, 'res_id': existing.id,
                             'noupdate': True})
                stats['emparejados'] += 1
        if model == 'stock.quant' and not existing and resolve(env, module, fields.get('lot_id')):
            # El lote ya existía con sus existencias: no se le suma otro inventario.
            existing = True
        if existing and (model not in CATALOG or owner not in SUITE):
            record.getparent().remove(record)
            continue
        if existing and model == 'product.template' and 'pharmacy_ingredient_line_ids' in fields:
            existing.pharmacy_ingredient_line_ids.unlink()


def run_functions(env, module, tree, before):
    """Funciones de la demo, solo sobre lo creado en esta carga."""
    for node in tree.iter('function'):
        name = node.get('name')
        if name == 'action_apply_inventory':
            quants = env['stock.quant']
            for record in tree.iter('record'):
                if record.get('model') == 'stock.quant':
                    quant = env.ref(full_xmlid(module, record.get('id')), raise_if_not_found=False)
                    if quant and quant.id not in before.get('stock.quant', ()):
                        quants |= quant
            quants.filtered('inventory_quantity_set').action_apply_inventory()
        elif name == 'button_confirm':
            for xmlid in re.findall(r"ref\('([\w.]+)'\)", node.get('eval') or ''):
                order = env.ref(full_xmlid(module, xmlid))
                if order.state == 'draft':
                    order.button_confirm()
        elif name == '_pharmacy_set_state':
            match = re.search(r"ref\('([\w.]+)'\)\], '(\w+)', '([^']*)'", node.get('eval') or '')
            lot = env.ref(full_xmlid(module, match.group(1)))
            if lot.pharmacy_state != match.group(2):
                lot._pharmacy_set_state(match.group(2), match.group(3))
        elif name == '_cron_expire_prescriptions':
            env['pharmacy.prescription']._cron_expire_prescriptions()
        elif name == 'action_create_pos_payment_method':
            for xmlid in re.findall(r"ref\('([\w.]+)'\)", node.get('eval') or ''):
                env.ref(full_xmlid(module, xmlid)).action_create_pos_payment_method()


def main(env):
    installed = set(env['ir.module.module'].search([('state', '=', 'installed')]).mapped('name'))
    stats = {'emparejados': 0}
    for module, path in FILES:
        if module not in installed:
            _logger.info('%s no está instalado: se salta', module)
            continue
        with file_open(f'{module}/{path}', 'rb', env=env) as handle:
            original = etree.parse(handle)
        tree = etree.ElementTree(etree.fromstring(etree.tostring(original)))
        prepare(env, module, tree, stats)
        before = {'stock.quant': set(env['stock.quant'].search([]).ids)}
        content = io.BytesIO(etree.tostring(tree))
        content.name = f'{module}/{path}'  # convert_xml_import lo usa en los mensajes
        convert_xml_import(env, module, content, idref={}, mode='init')
        run_functions(env, module, original, before)
        env.flush_all()
        _logger.info('%s: demo cargada', module)
    print('Demo de farmacia cargada; registros existentes emparejados: %s' % stats['emparejados'])


try:
    main(env)  # noqa: F821 - env lo da odoo shell
    env.cr.commit()  # noqa: F821
except Exception:
    env.cr.rollback()  # noqa: F821
    raise
