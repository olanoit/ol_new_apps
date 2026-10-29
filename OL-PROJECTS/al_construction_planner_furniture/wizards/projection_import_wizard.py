# -*- coding: utf-8 -*-
"""Importador de la proyección de materiales (v1.8, M17-18) con validación
de códigos de producto (M17-19).

Lee las hojas de proyección en su formato actual (``projection_layout``) y
carga la receta planificada de cada módulo: sus piezas y sus consumos por
material con la sub etapa de consumo, el tipo de mueble (bajo o alto) y el
método de unión propuesto. La receta del mueble es la suma de sus módulos en
cocinas y el bloque mismo en los demás rubros. Del resumen toma qué
tipología lleva cada unidad y arma el árbol de la obra.

Antes de escribir muestra la vista previa con sus avisos y una fila por
columna de material: el código de las pestañas, el del resumen y el producto
de Odoo que les corresponde. Toda columna sin código, con un código que no
existe en Odoo, con códigos que llevan a productos distintos o con un nombre
que no coincide queda marcada; sin resolverlas (eligiendo el producto) la
receta no se guarda como planificada.
"""
import logging
from collections import defaultdict
from io import BytesIO

from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import TYPOLOGY_FAMILIES, norm

from . import projection_layout as layout

_logger = logging.getLogger(__name__)

COLUMN_STATES = [
    ('ok', 'Correcto'),
    ('resolved', 'Resuelto a mano'),
    ('no_code', 'Sin código'),
    ('unknown', 'Código inexistente en Odoo'),
    ('conflict', 'Códigos de productos distintos'),
    ('name', 'El nombre no coincide'),
]
FAMILY_SPACE_NAMES = {'kitchen': 'Cocina', 'closet': 'Closet', 'bathroom': 'Baño',
                      'laundry': 'Lavandería', 'duct': 'Ducto', 'common': 'Área común'}


def _similar(name_a, name_b):
    """Coincidencia por palabras (≥ la mitad de las palabras del nombre corto)."""
    words_a = {w for w in norm(name_a).split() if len(w) > 2}
    words_b = {w for w in norm(name_b).split() if len(w) > 2}
    if not words_a or not words_b:
        return True
    shorter = min(words_a, words_b, key=len)
    return len(words_a & words_b) >= max(1, len(shorter) // 2)


class ConstructionProjectionImportWizard(models.TransientModel):
    _name = 'construction.projection.import.wizard'
    _description = 'Importar la proyección de materiales'

    project_id = fields.Many2one('project.project', string='Obra', required=True,
                                 domain=[('is_construction_site', '=', True)])
    company_id = fields.Many2one(related='project_id.company_id')
    file = fields.Binary(string='Hoja de proyección (.xlsx)', required=True)
    filename = fields.Char(string='Archivo')
    family = fields.Selection(TYPOLOGY_FAMILIES, string='Familia',
                              help='La del libro (cocinas, closet, baños…); se propone al leerlo.')
    create_tree = fields.Boolean(
        string='Crear el árbol de la obra', default=True,
        help='Pisos, unidades y ambientes del resumen con la tipología de cada uno.')
    state = fields.Selection([('upload', 'Archivo'), ('preview', 'Vista previa'),
                              ('done', 'Importado')], default='upload')
    line_ids = fields.One2many('construction.projection.import.column', 'wizard_id',
                               string='Columnas de material')
    preview_html = fields.Html(string='Se importará', sanitize=False, readonly=True)
    warning_html = fields.Html(string='Avisos', sanitize=False, readonly=True)
    unresolved_count = fields.Integer(string='Columnas sin resolver',
                                      compute='_compute_unresolved_count')

    @api.depends('line_ids.state', 'line_ids.used')
    def _compute_unresolved_count(self):
        for wizard in self:
            wizard.unresolved_count = len(wizard.line_ids.filtered(
                lambda l: l.used and l.state not in ('ok', 'resolved')))

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def _parse(self):
        self.ensure_one()
        from openpyxl import load_workbook
        try:
            workbook = load_workbook(BytesIO(self.file.content), data_only=True, read_only=False)
        except Exception as exc:  # noqa: BLE001 - archivo de usuario
            _logger.info('Hoja de proyección no válida: %s', exc)
            raise UserError(self.env._('El archivo no es un libro Excel (.xlsx) válido.')) from exc
        parsed = layout.parse_workbook(workbook)
        materials = layout.match_columns(parsed)
        return parsed, materials

    def _resolve(self, material):
        """(producto propuesto, estado, nota) de una columna de material."""
        Product = self.env['product.product'].with_context(active_test=False)
        company = self.project_id.company_id or self.env.company
        codes = sorted(material['codes'] | ({material['summary_code']}
                                            if material['summary_code'] else set()))
        if not codes:
            return Product, 'no_code', self.env._('La columna no tiene código.')
        found = {}
        for code in codes:
            found[code] = Product.search([('default_code', '=', code),
                                          ('company_id', 'in', (company.id, False))], limit=1)
        products = Product.union(*[p for p in found.values() if p])
        missing = [code for code, product in found.items() if not product]
        if not products:
            return Product, 'unknown', self.env._('No existe en Odoo: %s.', ', '.join(missing))
        if len(products) > 1 or missing:
            note = self.env._('Pestañas %(tabs)s, resumen %(summary)s.',
                              tabs=', '.join(sorted(material['codes'])) or '—',
                              summary=material['summary_code'] or '—')
            if missing:
                note += ' ' + self.env._('No existe en Odoo: %s.', ', '.join(missing))
            return products[:1], 'conflict', note
        name = material['full_name'] or material['name']
        if not _similar(name, products.name):
            return products, 'name', self.env._('En la hoja: %(sheet)s; en Odoo: %(odoo)s.',
                                                sheet=name, odoo=products.display_name)
        return products, 'ok', False

    def action_preview(self):
        self.ensure_one()
        parsed, materials = self._parse()
        if not parsed['typologies']:
            raise UserError(self.env._('El libro no tiene bloques «MODULO:» que importar.'))
        self.family = self.family or parsed['family'] or 'kitchen'
        used = defaultdict(float)
        for typology in parsed['typologies']:
            for block in typology['blocks']:
                for c, material_key in block['keys'].items():
                    used[material_key] += block['totals'].get(c, 0.0)
        commands = [Command.clear()]
        for index, (material_key, material) in enumerate(materials.items()):
            product, state, note = self._resolve(material)
            commands.append(Command.create({
                'sequence': index, 'key': '%s|%s' % material_key, 'name': material['name'],
                'full_name': material['full_name'], 'stage': material['stage'] or False,
                'tab_codes': ', '.join(sorted(material['codes'])),
                'summary_code': material['summary_code'],
                'auto_product_id': product.id, 'product_id': product.id,
                'auto_state': state, 'note': note, 'used': bool(used.get(material_key)),
                'in_summary': material['in_summary'],
            }))
        modules = sum(len(t['blocks']) for t in parsed['typologies'])
        pieces = sum(len(b['pieces']) for t in parsed['typologies'] for b in t['blocks'])
        units = parsed['summary']['units']
        rows = [
            (self.env._('Tipologías'), len(parsed['typologies'])),
            (self.env._('Módulos'), modules if parsed['typologies'][0]['kind'] == 'tabs'
             else len(parsed['typologies'])),
            (self.env._('Piezas'), pieces),
            (self.env._('Columnas de material'), len(materials)),
            (self.env._('Unidades del resumen'), len(units)),
            (self.env._('Pisos'), len({u['floor'] for u in units})),
        ]
        self.write({
            'line_ids': commands, 'state': 'preview',
            'preview_html': Markup('<table class="table table-sm w-auto"><tbody>%s</tbody>'
                                   '</table>') % Markup('').join(
                Markup('<tr><td>%s</td><td class="text-end">%s</td></tr>') % row for row in rows),
            'warning_html': Markup('<ul class="mb-0">%s</ul>') % Markup('').join(
                Markup('<li>%s</li>') % warning for warning in parsed['warnings'][:200])
            if parsed['warnings'] else False,
        })
        return self._reopen()

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new',
                'name': self.env._('Importar la proyección de materiales')}

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    def action_import(self):
        self.ensure_one()
        if self.state != 'preview':
            return self.action_preview()
        unresolved = self.line_ids.filtered(
            lambda l: l.used and l.state not in ('ok', 'resolved'))
        if unresolved:
            raise UserError(self.env._(
                'Hay columnas de material sin resolver; la receta no se guarda como '
                'planificada:\n\n%s', '\n'.join(
                    '   · %s (%s): %s' % (line.name, line.tab_codes or line.summary_code or
                                         self.env._('sin código'),
                                         dict(COLUMN_STATES)[line.state])
                    for line in unresolved)))
        parsed, materials = self._parse()
        products = {line.key: line for line in self.line_ids}
        typologies = self._import_typologies(parsed, products)
        tree = self._import_tree(parsed, typologies) if self.create_tree else 0
        self.project_id.message_post(body=self.env._(
            'Proyección de materiales importada (%(file)s): %(typologies)s tipologías y '
            '%(spaces)s ambientes.', file=self.filename or '', typologies=len(typologies),
            spaces=tree))
        self.state = 'done'
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Tipologías'),
            'res_model': 'construction.typology', 'view_mode': 'list,form',
            'domain': [('id', 'in', [t.id for t in typologies.values()])],
        }

    def _block_materials(self, block, products):
        """{(producto, etapa): cantidad} de un bloque con las columnas resueltas."""
        result = defaultdict(float)
        for c, material_key in block['keys'].items():
            qty = block['totals'].get(c, 0.0)
            if not qty:
                continue
            line = products.get('%s|%s' % material_key)
            if not line or not line.product_id:
                continue
            result[(line.product_id, line.stage or False)] += qty
        return result

    def _module_values(self, sequence, block, products, furniture=None, code=None):
        materials = self._block_materials(block, products)
        name = layout.module_name(block['name']) or block['name']
        group = block['group'] if block['group'] in ('low', 'high') else 'none'
        return {
            'sequence': sequence, 'code': code or 'M%02d' % sequence, 'name': name,
            'module_type': {'low': 'low', 'high': 'high'}.get(group, 'other'),
            'width_mm': layout.width_from_name(block['name']),
            'ml_group': group if group in ('low', 'high') else 'none',
            'furniture_id': furniture.id if furniture else False,
            'piece_ids': [Command.create(dict(piece, sequence=i))
                          for i, piece in enumerate(block['pieces'], start=1)],
            'material_ids': [Command.create({
                'sequence': i, 'product_id': product.id, 'qty': round(qty, 6),
                'stage': stage, 'source_code': product.default_code})
                for i, ((product, stage), qty) in enumerate(materials.items(), start=1)],
        }

    def _import_typologies(self, parsed, products):
        """Crea o actualiza las tipologías (por código) con sus muebles y
        módulos; lo que trae el libro de una tipología queda exactamente así."""
        Typology = self.env['construction.typology'].with_context(active_test=False)
        result = {}
        for data in parsed['typologies']:
            code = data['code'].strip()
            typology = Typology.search([('project_id', '=', self.project_id.id),
                                        ('family', '=', self.family), ('code', '=', code)],
                                       limit=1)
            if not typology:
                typology = Typology.create({'project_id': self.project_id.id,
                                            'family': self.family, 'code': code,
                                            'name': data['name']})
            typology.module_line_ids.unlink()
            typology.furniture_line_ids.unlink()
            if data['kind'] == 'tabs':
                furniture = {}
                for group, label, kind in (('low', self.env._('Mueble bajo'), 'low'),
                                           ('high', self.env._('Mueble alto'), 'high')):
                    if any(block['group'] == group for block in data['blocks']):
                        furniture[group] = self.env['construction.typology.furniture'].create({
                            'typology_id': typology.id, 'name': label, 'ml_group': group,
                            'furniture_kind': kind, 'sequence': len(furniture) + 1})
                typology.write({'module_line_ids': [Command.create(self._module_values(
                    index, block, products, furniture.get(block['group'])))
                    for index, block in enumerate(data['blocks'], start=1)]})
            else:
                block = data['blocks'][0]
                furniture = self.env['construction.typology.furniture'].create({
                    'typology_id': typology.id, 'name': data['name'], 'ml_group': 'other',
                    'furniture_kind': 'block'})
                typology.write({'module_line_ids': [Command.create(self._module_values(
                    1, block, products, furniture, code=data['code']))]})
            result[layout.typology_key(code)] = typology
        return result

    def _import_tree(self, parsed, typologies):
        """Pisos, unidades y ambientes del resumen con su tipología. Las
        agrupaciones sin unidad (ductos por piso, estacionamientos por sótano)
        cuelgan del piso. No duplica lo que ya existe."""
        Task = self.env['project.task'].with_context(mail_create_nolog=True,
                                                     tracking_disable=True)
        project = self.project_id
        cache = {}

        def node(name, level, parent=None, **vals):
            cache_key = (parent.id if parent else 0, level, name)
            if cache_key in cache:
                return cache[cache_key]
            task = Task.search([('project_id', '=', project.id), ('name', '=', name),
                                ('parent_id', '=', parent.id if parent else False),
                                ('construction_level', '=', level)], limit=1)
            if not task:
                task = Task.create(dict(project._construction_level_vals(level), name=name,
                                        project_id=project.id,
                                        parent_id=parent.id if parent else False,
                                        user_ids=False, **vals))
            elif vals:
                task.write(vals)
            cache[cache_key] = task
            return task

        label = FAMILY_SPACE_NAMES.get(self.family, self.env._('Ambiente'))
        created = 0
        for unit in parsed['summary']['units']:
            typology = typologies.get(layout.typology_key(unit['typology']))
            if not typology:
                continue
            floor = node(unit['floor'], 'floor')
            if unit['unit']:
                apartment = node(' '.join(unit['unit'].split()), 'apartment', floor)
            else:
                apartment = node(unit['floor'], 'apartment', floor)
            count = int(unit['qty']) if unit['qty'] and unit['qty'] >= 1 else 1
            for index in range(count):
                name = '%s %s' % (label, typology.code) if count == 1 else \
                    '%s %s (%s)' % (label, typology.code, index + 1)
                node(name, 'space', apartment, construction_typology_id=typology.id)
                created += 1
        return created


class ConstructionProjectionImportColumn(models.TransientModel):
    _name = 'construction.projection.import.column'
    _description = 'Columna de material de la proyección'
    _order = 'sequence, id'

    wizard_id = fields.Many2one('construction.projection.import.wizard', required=True,
                                ondelete='cascade')
    sequence = fields.Integer()
    key = fields.Char(required=True)
    name = fields.Char(string='Columna')
    full_name = fields.Char(string='Nombre en el resumen')
    stage = fields.Selection(lambda self: self.env['construction.stage']._get_selection(),
                             string='Sub etapa')
    tab_codes = fields.Char(string='Código en las pestañas')
    summary_code = fields.Char(string='Código en el resumen')
    in_summary = fields.Boolean(string='En el resumen')
    used = fields.Boolean(string='Con consumo')
    auto_product_id = fields.Many2one('product.product', string='Propuesto')
    product_id = fields.Many2one('product.product', string='Producto')
    auto_state = fields.Selection(COLUMN_STATES, string='Control automático')
    state = fields.Selection(COLUMN_STATES, string='Control', compute='_compute_state')
    note = fields.Char(string='Detalle')

    @api.depends('product_id', 'auto_product_id', 'auto_state')
    def _compute_state(self):
        for line in self:
            if line.auto_state == 'ok' and line.product_id == line.auto_product_id:
                line.state = 'ok'
            elif line.product_id and line.product_id != line.auto_product_id:
                line.state = 'resolved'
            else:
                line.state = line.auto_state

    def action_accept(self):
        """Acepta el producto propuesto (nombre distinto o códigos en conflicto
        revisados a mano)."""
        for line in self.filtered('product_id'):
            line.auto_state = 'ok'
            line.auto_product_id = line.product_id
        return self.wizard_id._reopen() if self.wizard_id else True
