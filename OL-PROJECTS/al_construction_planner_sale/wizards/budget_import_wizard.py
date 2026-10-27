# -*- coding: utf-8 -*-
"""Importación del presupuesto con secciones (requerimiento CREVAL v1.0, 6.4).

El presupuesto de la obra entra a la cotización con una sección por nivel 1 y
una subsección por nivel 2 (las partidas como líneas), y de la cotización a
los niveles del plan de la obra. Las unidades escritas de varias formas
(«UND», «Und»; «GLB»; «M», «ML») se leen con la tabla de equivalencias; los
ítems pueden tener cualquier formato, faltar o repetirse: los duplicados se
avisan antes de crear."""
import base64
import io
from collections import Counter

from markupsafe import Markup

from odoo import Command, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import norm

COLUMNS = [
    ('item', ('item', 'ítem', 'partida n', 'codigo', 'código'), False),
    ('name', ('descripcion', 'descripción', 'partida', 'nombre'), True),
    ('uom', ('unidad', 'und', 'unid', 'u.m.'), False),
    ('qty', ('metrado', 'cantidad', 'cant.'), False),
    ('price', ('precio unitario', 'precio', 'p.u.', 'costo unitario'), False),
    ('amount', ('parcial', 'importe', 'total'), False),
]


def _text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _number(value):
    if value in (None, ''):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(' ', '')
    if ',' in text and '.' in text:
        text = text.replace(',', '')
    else:
        text = text.replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return None


class ConstructionBudgetImportWizard(models.TransientModel):
    _name = 'construction.budget.import.wizard'
    _description = 'Importar el presupuesto de la obra a la cotización'

    sale_order_id = fields.Many2one('sale.order', string='Cotización', required=True,
                                    readonly=True)
    company_id = fields.Many2one(related='sale_order_id.company_id')
    currency_id = fields.Many2one(related='sale_order_id.currency_id')
    file = fields.Binary(string='Presupuesto (Excel)', required=True)
    filename = fields.Char(string='Nombre del archivo')
    product_id = fields.Many2one(
        'product.product', string='Producto de las partidas', check_company=True,
        domain=[('sale_ok', '=', True)],
        help='Vacío: un servicio «Partida de presupuesto» (se crea si no existe).')
    state = fields.Selection([('upload', 'Archivo'), ('preview', 'Revisión'), ('done', 'Hecho')],
                             default='upload')
    preview_html = fields.Html(string='Revisión', readonly=True, sanitize=False)
    amount_file = fields.Monetary(string='Costo directo del archivo', readonly=True,
                                  currency_field='currency_id')

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def _rows(self):
        try:
            import openpyxl
        except ImportError as error:
            raise UserError(self.env._('Falta la librería openpyxl en el servidor.')) from error
        book = openpyxl.load_workbook(io.BytesIO(base64.b64decode(self.file)), data_only=True)
        sheet = book.worksheets[0]
        rows = list(sheet.iter_rows(values_only=True))
        header_index, index = None, {}
        for position, row in enumerate(rows[:20]):
            names = [norm(_text(cell)) for cell in row]
            found = {}
            for key, aliases, _required in COLUMNS:
                for alias in aliases:
                    if norm(alias) in names:
                        found[key] = names.index(norm(alias))
                        break
            if 'name' in found and ('qty' in found or 'price' in found):
                header_index, index = position, found
                break
        if header_index is None:
            raise UserError(self.env._(
                'No se encuentra la fila de encabezados (Ítem, Descripción, Unidad, Metrado, '
                'Precio unitario, Parcial).'))
        result = []
        for number, row in enumerate(rows[header_index + 1:], start=header_index + 2):
            values = {key: row[i] if i < len(row) else None for key, i in index.items()}
            if not _text(values.get('name')) and not _text(values.get('item')):
                continue
            values['_row'] = number
            result.append(values)
        return result

    def _uom(self, text):
        text = _text(text)
        if not text:
            return self.env['uom.uom']
        uom = self.env['construction.uom.alias']._find(text, self.company_id)
        return uom or self.env['uom.uom'].search([('name', '=ilike', text)], limit=1)

    def _parse(self):
        """Filas → [{kind: section|subsection|line, depth, item, name, qty,
        uom, price, amount}] y avisos."""
        entries, warnings = [], []
        for row in self._rows():
            item = _text(row.get('item'))
            name = _text(row.get('name'))
            qty = _number(row.get('qty'))
            price = _number(row.get('price'))
            amount = _number(row.get('amount'))
            depth = len([part for part in item.replace(' ', '').split('.') if part]) if item \
                else 0
            if qty is None and price is None:
                kind = 'section' if depth <= 1 else 'subsection'
                entries.append({'kind': kind, 'depth': depth or 1, 'item': item, 'name': name,
                                'row': row['_row']})
                continue
            uom = self._uom(row.get('uom'))
            if row.get('uom') and not uom:
                warnings.append(self.env._('Fila %(row)s: la unidad «%(uom)s» no tiene '
                                           'equivalencia; queda en unidades.',
                                           row=row['_row'], uom=_text(row.get('uom'))))
            qty = qty or 0.0
            price = price if price is not None else ((amount or 0.0) / qty if qty else 0.0)
            entries.append({'kind': 'line', 'depth': depth, 'item': item, 'name': name,
                            'qty': qty, 'price': price,
                            'amount': amount if amount is not None else qty * price,
                            'uom': uom, 'row': row['_row']})
        items = Counter(e['item'] for e in entries if e['item'])
        for item, count in items.items():
            if count > 1:
                warnings.append(self.env._('El ítem %(item)s aparece %(count)s veces.',
                                           item=item, count=count))
        titles = Counter(norm(e['name']) for e in entries if e['kind'] != 'line')
        for title, count in titles.items():
            if count > 1:
                warnings.append(self.env._('El título «%(title)s» se repite %(count)s veces.',
                                           title=title, count=count))
        unnumbered = [e for e in entries if e['kind'] == 'line' and not e['item']]
        if unnumbered:
            warnings.append(self.env._('%s partidas sin número de ítem.', len(unnumbered)))
        return entries, warnings

    # ------------------------------------------------------------------
    # Pasos
    # ------------------------------------------------------------------
    def action_preview(self):
        self.ensure_one()
        entries, warnings = self._parse()
        lines = [e for e in entries if e['kind'] == 'line']
        if not lines:
            raise UserError(self.env._('El archivo no tiene partidas con metrado o precio.'))
        total = sum(e['amount'] for e in lines)
        body = Markup('<p>%s</p>') % self.env._(
            '%(sections)s secciones, %(subsections)s subsecciones y %(lines)s partidas; costo '
            'directo %(amount)s.', sections=len([e for e in entries if e['kind'] == 'section']),
            subsections=len([e for e in entries if e['kind'] == 'subsection']), lines=len(lines),
            amount=self.currency_id.format(total))
        if warnings:
            body += Markup('<p class="text-warning mb-1">%s</p><ul>%s</ul>') % (
                self.env._('Revise antes de crear:'),
                Markup('').join(Markup('<li>%s</li>') % w for w in warnings))
        self.write({'state': 'preview', 'preview_html': body, 'amount_file': total})
        return self._reopen()

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}

    def _partida_product(self):
        if self.product_id:
            return self.product_id
        product = self.env['product.product'].search([
            ('default_code', '=', 'PARTIDA-PPTO'),
            ('company_id', 'in', (self.company_id.id, False))], limit=1)
        if not product:
            # sudo: quien importa el presupuesto no siempre crea productos; es
            # un servicio genérico para las líneas de la cotización.
            product = self.env['product.product'].sudo().create({
                'name': self.env._('Partida de presupuesto'), 'default_code': 'PARTIDA-PPTO',
                'type': 'service', 'sale_ok': True, 'purchase_ok': False,
                'company_id': self.company_id.id}).sudo(False)
        return product

    def action_import(self):
        self.ensure_one()
        order = self.sale_order_id
        if order.state not in ('draft', 'sent'):
            raise UserError(self.env._('El presupuesto entra a una cotización en borrador.'))
        entries, _warnings = self._parse()
        product = self._partida_product()
        sequence = max(order.order_line.mapped('sequence') or [0])
        commands = []
        for entry in entries:
            sequence += 1
            label = ' '.join(filter(None, [entry['item'], entry['name']])) or entry['name']
            if entry['kind'] in ('section', 'subsection'):
                commands.append(Command.create({
                    'display_type': 'line_section' if entry['kind'] == 'section'
                    else 'line_subsection',
                    'name': label, 'sequence': sequence}))
                continue
            values = {'product_id': product.id, 'name': label, 'sequence': sequence,
                      'product_uom_qty': entry['qty'], 'price_unit': entry['price'],
                      'construction_budget_item': entry['item'] or False}
            if entry['uom']:
                values['product_uom_id'] = entry['uom'].id
            commands.append(Command.create(values))
        order.write({'order_line': commands})
        order.message_post(body=self.env._(
            'Presupuesto importado de %(file)s: costo directo %(amount)s.',
            file=self.filename or '', amount=self.currency_id.format(self.amount_file)))
        self.state = 'done'
        return {'type': 'ir.actions.act_window', 'res_model': 'sale.order', 'res_id': order.id,
                'view_mode': 'form'}


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    construction_budget_item = fields.Char(
        string='Ítem del presupuesto', copy=True,
        help='Número de la partida en el presupuesto importado (CREVAL v1.0, 6.4).')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_construction_import_budget(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': self.env._('Importar presupuesto'),
                'res_model': 'construction.budget.import.wizard', 'view_mode': 'form',
                'target': 'new', 'context': {'default_sale_order_id': self.id}}

    def _construction_budget_groups(self):
        """[(sección, subsección, línea)] de la cotización, en su orden."""
        self.ensure_one()
        section = subsection = self.env['sale.order.line']
        result = []
        for line in self.order_line.sorted(lambda l: (l.sequence, l.id)):
            if line.display_type == 'line_section':
                section, subsection = line, self.env['sale.order.line']
            elif line.display_type == 'line_subsection':
                subsection = line
            elif not line.display_type:
                result.append((section, subsection, line))
        return result

    def action_construction_create_levels(self):
        """De la cotización al plan: sección → nivel 1, subsección → nivel 2 y
        partida → nivel 3 de la plantilla de la obra, con su metrado y la línea
        de venta."""
        self.ensure_one()
        project = self.project_id or self.project_ids[:1]
        if not project:
            raise UserError(self.env._('Indique la obra de la cotización %s.', self.name))
        template = project.construction_level_template_id
        levels = template.line_ids.sorted(lambda l: (l.sequence, l.id)) if template else []
        if len(levels) < 3:
            raise UserError(self.env._(
                'La plantilla de niveles de %s necesita al menos tres niveles (sección, '
                'subsección y partida).', project.display_name))
        Task = self.env['project.task']
        recipes = self.env['construction.execution.template']
        # Las recetas de la cotización pasan a la obra una sola vez (CR-18, D4).
        own_recipes = self._construction_copy_quote_recipes(project)
        cache = {}

        def node(name, level, parent):
            key = (parent.id, level.id, name)
            if key not in cache:
                cache[key] = Task.search([
                    ('project_id', '=', project.id), ('parent_id', '=', parent.id),
                    ('construction_level_line_id', '=', level.id), ('name', '=', name)],
                    limit=1) or Task.create({
                        'name': name, 'project_id': project.id, 'parent_id': parent.id,
                        'construction_level_line_id': level.id, 'user_ids': False})
            return cache[key]

        created = Task
        for section, subsection, line in self._construction_budget_groups():
            parent = Task
            if section:
                parent = node(section.name, levels[0], parent)
            if subsection:
                parent = node(subsection.name, levels[1], parent)
            partida = node(line.name.splitlines()[0], levels[2], parent)
            recipe = line.construction_execution_template_id
            if recipe and recipe.project_id != project:
                recipe = own_recipes.get(recipe.code) or (recipe if not recipe.project_id
                                                          else recipes)
            if not recipe and line.construction_budget_item:
                recipe = recipes.search([('code', '=', line.construction_budget_item),
                                         ('construction_sale_order_id', '=', False),
                                         ('project_id', 'in', (project.id, False))],
                                        order='project_id', limit=1)
            # El plan va con el metrado real; la cantidad de la cotización es
            # el ofertado, con su holgura (CREVAL v1.0, 6.5).
            values = {'construction_qty': line.construction_qty_real or line.product_uom_qty,
                      'sale_line_id': line.id}
            if recipe:
                values['construction_execution_template_id'] = recipe.id
            partida.write(values)
            created |= partida
        self.message_post(body=self.env._(
            '%(count)s partidas creadas o actualizadas en los niveles de %(project)s.',
            count=len(created), project=project.display_name))
        return {'type': 'ir.actions.act_window', 'res_model': 'project.task',
                'view_mode': 'list,form', 'domain': [('id', 'in', created.ids)],
                'name': self.env._('Partidas de %s', project.display_name)}

