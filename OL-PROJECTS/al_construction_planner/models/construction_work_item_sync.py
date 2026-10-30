# -*- coding: utf-8 -*-
"""Receta sincronizada con los Work Items (v1.8, M18-13).

La receta de cada partida (APU) vive en dos lugares: el Work Item de Ventas,
con el que se cotiza, y la plantilla de ejecución del planificador, con la
que se planifica y controla. Desde la 1.8 quedan vinculadas: la receta guarda
el Work Item y cada línea su línea del Work Item, y una huella del contenido
de cada lado en la última sincronización. Un cambio en cualquiera de los dos
queda marcado como diferencia y se propone aplicarlo en el otro, con vista
previa. La sincronización nunca toca los planes: el cambio llega a los planes
nuevos o con una versión nueva del plan (mecanismo aprobado por Vicente el
16-oct-2026).

Los Work Items son modelos ``x_`` del paquete de industria Construction: no se
heredan en Python. Toda su lectura y escritura pasa por ``_work_item_read`` y
``_work_item_apply``."""
import hashlib
import json

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_round

WORK_ITEM_MODEL = 'x_work_item'
SYNC_STATES = [
    ('none', 'Sin Work Item'),
    ('synced', 'Sincronizada'),
    ('work_item', 'Cambió el Work Item'),
    ('template', 'Cambió la receta'),
    ('both', 'Cambiaron los dos'),
    ('missing', 'Work Item borrado'),
]
# Naturaleza de costo del Work Item → comportamiento del recurso (como al
# copiarlo) y al revés.
NATURE_BY_BEHAVIOR = {'material': 'material', 'equipment': 'equipment',
                      'labor': 'labour', 'contract': 'labour', 'service': 'material',
                      'production': 'material'}


def _digest(data):
    return hashlib.sha1(json.dumps(data, sort_keys=True).encode()).hexdigest()


class ConstructionExecutionTemplate(models.Model):
    _inherit = 'construction.execution.template'

    work_item_id = fields.Integer(
        string='Work Item', copy=False, index=True,
        help='Id del Work Item de Ventas vinculado (paquete Construction).')
    work_item_name = fields.Char(string='Nombre del Work Item', copy=False, readonly=True)
    work_item_hash = fields.Char(copy=False, readonly=True)
    template_hash = fields.Char(copy=False, readonly=True)
    sync_state = fields.Selection(
        SYNC_STATES, string='Sincronización', default='none', required=True, copy=False,
        readonly=True, tracking=True,
        help='Si la receta y su Work Item siguen iguales desde la última sincronización. Una '
             'diferencia se revisa con «Sincronizar» antes de generar planes nuevos.')
    sync_checked_on = fields.Datetime(string='Revisado el', copy=False, readonly=True)

    # ------------------------------------------------------------------
    # Lado del Work Item
    # ------------------------------------------------------------------
    @api.model
    def _work_item_available(self):
        return WORK_ITEM_MODEL in self.env

    @api.model
    def _work_item_read(self, item_ids):
        """{id: {'name', 'product_id', 'uom_id', 'lines': [{'id', 'product_id',
        'qty', 'cost', 'nature'}]}} de los Work Items que existen."""
        if not self._work_item_available() or not item_ids:
            return {}
        result = {}
        # sudo: los Work Items son de Ventas; la oficina técnica solo lee su
        # contenido para compararlo con la receta.
        for item in self.env[WORK_ITEM_MODEL].sudo().browse(item_ids).exists():
            product = item.x_product_id
            result[item.id] = {
                'name': item.x_name, 'product_id': product.id,
                'uom_id': (item.x_unit_custom_id or product.uom_id).id,
                'lines': [{'id': line.id, 'product_id': line.x_product_id.id,
                           'qty': line.x_quantity, 'cost': line.x_unit_cost,
                           'nature': line.x_cost_nature}
                          for line in item.x_work_item_line_ids],
            }
        return result

    @api.model
    def _work_item_apply(self, item_id, changes):
        """Escribe en el Work Item ``changes``: ``{'update': {línea: {'qty',
        'cost'}}, 'create': [{'product_id', 'qty', 'cost', 'nature'}],
        'unlink': [líneas]}``. Devuelve {índice de 'create': id nuevo}."""
        if not self._work_item_available():
            raise UserError(self.env._(
                'Esta base no tiene los Work Items del paquete Construction de Odoo.'))
        # sudo: la oficina técnica propone el cambio y lo confirma aquí; los
        # Work Items son de Ventas.
        WorkItem = self.env[WORK_ITEM_MODEL].sudo()
        item = WorkItem.browse(item_id).exists()
        if not item:
            raise UserError(self.env._('El Work Item vinculado ya no existe.'))
        line_field = WorkItem._fields['x_work_item_line_ids']
        Line = self.env[line_field.comodel_name].sudo()
        for line_id, vals in changes.get('update', {}).items():
            Line.browse(line_id).write({'x_quantity': vals['qty'], 'x_unit_cost': vals['cost']})
        created = {}
        for index, vals in enumerate(changes.get('create', [])):
            line = Line.create({
                line_field.inverse_name: item.id, 'x_product_id': vals['product_id'],
                'x_quantity': vals['qty'], 'x_unit_cost': vals['cost'],
                'x_cost_nature': vals['nature']})
            created[index] = line.id
        Line.browse(changes.get('unlink', [])).unlink()
        return created

    # ------------------------------------------------------------------
    # Contenido comparable
    # ------------------------------------------------------------------
    @staticmethod
    def _sync_number(value, digits):
        return float_round(value or 0.0, precision_digits=digits)

    def _template_sync_data(self):
        """Contenido de la receta que se sincroniza: {línea del Work Item o
        'n<id>' si es nueva: (producto, cantidad, costo)}."""
        self.ensure_one()
        data = {}
        for line in self.line_ids:
            product = line.product_id or line.activity_id.product_id
            key = str(line.work_item_line_id) if line.work_item_line_id else 'n%s' % line.id
            data[key] = (product.id, self._sync_number(line.qty, 6),
                         self._sync_number(line.price_unit, 2))
        return data

    @classmethod
    def _work_item_sync_data(cls, item):
        return {str(line['id']): (line['product_id'], cls._sync_number(line['qty'], 6),
                                  cls._sync_number(line['cost'], 2))
                for line in item['lines']}

    def _check_work_item_sync(self, items=None):
        """Marca la diferencia de cada receta vinculada con su Work Item desde
        la última sincronización. No cambia nada más."""
        linked = self.filtered('work_item_id')
        (self - linked).filtered(lambda t: t.sync_state != 'none').sync_state = 'none'
        if not linked:
            return
        items = items if items is not None else self._work_item_read(linked.mapped('work_item_id'))
        now = fields.Datetime.now()
        for template in linked:
            item = items.get(template.work_item_id)
            if item is None:
                state = 'missing' if self._work_item_available() else template.sync_state
            else:
                item_changed = _digest(self._work_item_sync_data(item)) != template.work_item_hash
                template_changed = _digest(template._template_sync_data()) != template.template_hash
                state = 'both' if item_changed and template_changed else \
                    'work_item' if item_changed else 'template' if template_changed else 'synced'
            vals = {'sync_checked_on': now}
            if state != template.sync_state:
                vals['sync_state'] = state
            template.with_context(construction_sync_writing=True).write(vals)

    def _mark_synced(self, item):
        self.ensure_one()
        self.with_context(construction_sync_writing=True).write({
            'work_item_hash': _digest(self._work_item_sync_data(item)),
            'template_hash': _digest(self._template_sync_data()),
            'work_item_name': item['name'], 'sync_state': 'synced',
            'sync_checked_on': fields.Datetime.now()})

    def _link_work_item(self, item_id):
        """Vincula la receta recién copiada de un Work Item: cada línea con
        la línea del Work Item de su posición y las huellas de hoy."""
        self.ensure_one()
        item = self._work_item_read([item_id]).get(item_id)
        if not item:
            return
        lines = self.line_ids.sorted(lambda l: (l.sequence, l.id))
        for line, item_line in zip(lines, item['lines']):
            line.with_context(construction_sync_writing=True).work_item_line_id = item_line['id']
        self.with_context(construction_sync_writing=True).work_item_id = item_id
        self._mark_synced(item)

    # ------------------------------------------------------------------
    # Diferencias
    # ------------------------------------------------------------------
    def _sync_differences(self, item):
        """[{key, resource, field, work_item, template}] de lo que difiere: la
        cantidad o el costo de un recurso, un recurso que solo está en un lado."""
        self.ensure_one()
        Product = self.env['product.product']
        template_lines = {str(line.work_item_line_id): line
                          for line in self.line_ids if line.work_item_line_id}
        rows = []
        for item_line in item['lines']:
            line = template_lines.pop(str(item_line['id']), None)
            name = Product.browse(item_line['product_id']).display_name
            if not line:
                rows.append({'key': 'wi%s' % item_line['id'], 'kind': 'only_work_item',
                             'resource': name, 'work_item': item_line['qty'], 'template': None,
                             'field': self.env._('Recurso')})
                continue
            for field, wi_value, tpl_value, digits in (
                    (self.env._('Cantidad por unidad'), item_line['qty'], line.qty, 6),
                    (self.env._('Costo unitario'), item_line['cost'], line.price_unit, 2)):
                if float_compare(wi_value or 0.0, tpl_value or 0.0, precision_digits=digits):
                    rows.append({'key': 'l%s' % line.id, 'kind': 'value', 'resource': name,
                                 'field': field, 'work_item': wi_value, 'template': tpl_value})
        for line in self.line_ids.filtered(lambda l: not l.work_item_line_id) + \
                self.env['construction.execution.template.line'].union(template_lines.values()):
            product = line.product_id or line.activity_id.product_id
            rows.append({'key': 'n%s' % line.id, 'kind': 'only_template',
                         'resource': (product or line.activity_id).display_name,
                         'field': self.env._('Recurso'), 'work_item': None,
                         'template': line.qty})
        return rows

    def action_check_work_items(self):
        """«Revisar Work Items»: marca las recetas que cambiaron."""
        templates = self or self.search([('work_item_id', '!=', 0)])
        templates._check_work_item_sync()
        return True

    @api.model
    def _cron_check_work_items(self):
        if self._work_item_available():
            self.search([('work_item_id', '!=', 0)])._check_work_item_sync()

    def action_open_sync_wizard(self):
        self.ensure_one()
        if not self.work_item_id:
            raise UserError(self.env._('La receta %s no está vinculada a un Work Item.',
                                       self.display_name))
        self._check_work_item_sync()
        direction = 'to_work_item' if self.sync_state == 'template' else 'to_template'
        wizard = self.env['construction.work.item.sync.wizard'].create({
            'template_id': self.id, 'direction': direction})
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Sincronizar con el Work Item'),
            'res_model': wizard._name, 'res_id': wizard.id, 'view_mode': 'form',
            'target': 'new',
        }

    # ------------------------------------------------------------------
    # Aplicar
    # ------------------------------------------------------------------
    def _apply_work_item_to_template(self, item):
        """La receta queda igual al Work Item: cantidades y costos, recursos
        nuevos y quitados. No toca los planes."""
        self.ensure_one()
        Wizard = self.env['construction.recipe.import.wizard']
        Type = self.env['construction.resource.type']
        Product = self.env['product.product']
        by_item_line = {line.work_item_line_id: line for line in self.line_ids
                        if line.work_item_line_id}
        writer = self.with_context(construction_sync_writing=True)
        stage = self.line_ids[:1].stage or False
        keep = self.env['construction.execution.template.line']
        for item_line in item['lines']:
            line = by_item_line.get(item_line['id'])
            if line:
                line.with_context(construction_sync_writing=True).write({
                    'qty': item_line['qty'], 'price_unit': item_line['cost']})
                keep |= line
                continue
            product = Product.browse(item_line['product_id'])
            behavior = {'material': 'material', 'equipment': 'equipment',
                        'labour': 'labor'}.get(item_line['nature'], 'material')
            vals = {'template_id': self.id, 'resource_type': behavior,
                    'resource_type_id': Type._default_for(behavior).id,
                    'qty': item_line['qty'], 'price_unit': item_line['cost'], 'stage': stage,
                    'product_uom_id': product.uom_id.id, 'work_item_line_id': item_line['id']}
            if behavior == 'labor':
                wizard = Wizard.new({'company_id': self.company_id.id})
                vals['activity_id'] = wizard._activity_for(product, product.uom_id, stage).id
            else:
                vals['product_id'] = product.id
            keep |= self.env['construction.execution.template.line'].with_context(
                construction_sync_writing=True).create(vals)
        (writer.line_ids - keep).with_context(construction_sync_writing=True).unlink()
        self.message_post(body=self.env._(
            'Receta actualizada desde el Work Item %s. Los planes aprobados no cambian: el '
            'cambio llega a los planes nuevos o con una versión nueva del plan.', item['name']))

    def _apply_template_to_work_item(self, item):
        """El Work Item queda igual a la receta."""
        self.ensure_one()
        lines_by_id = {line['id']: line for line in item['lines']}
        changes = {'update': {}, 'create': [], 'unlink': []}
        new_lines = []
        seen = set()
        for line in self.line_ids:
            product = line.product_id or line.activity_id.product_id
            if line.work_item_line_id and line.work_item_line_id in lines_by_id:
                seen.add(line.work_item_line_id)
                changes['update'][line.work_item_line_id] = {'qty': line.qty,
                                                             'cost': line.price_unit}
                continue
            if not product:
                raise UserError(self.env._(
                    'El recurso %s no tiene producto: el Work Item solo lleva productos.',
                    line.activity_id.display_name))
            changes['create'].append({
                'product_id': product.id, 'qty': line.qty, 'cost': line.price_unit,
                'nature': NATURE_BY_BEHAVIOR.get(line.resource_type, 'material')})
            new_lines.append(line)
        changes['unlink'] = [line_id for line_id in lines_by_id if line_id not in seen]
        created = self._work_item_apply(self.work_item_id, changes)
        for index, line in enumerate(new_lines):
            if index in created:
                line.with_context(construction_sync_writing=True).work_item_line_id = created[index]
        self.message_post(body=self.env._(
            'Work Item %s actualizado desde la receta.', item['name']))


    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('construction_sync_writing') and \
                {'uom_id', 'product_id'} & set(vals):
            self.filtered('work_item_id')._check_work_item_sync()
        return res


class ConstructionExecutionTemplateLine(models.Model):
    _inherit = 'construction.execution.template.line'

    work_item_line_id = fields.Integer(string='Línea del Work Item', copy=False, index=True)

    # Un cambio en la receta vinculada la marca como diferencia con su Work
    # Item (se revisa al guardar; el Work Item se revisa con la acción
    # programada o con «Revisar Work Items»).
    def _check_linked_templates(self, templates=None):
        if self.env.context.get('construction_sync_writing'):
            return
        templates = (templates or self.template_id).filtered('work_item_id')
        if templates:
            templates._check_work_item_sync()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_linked_templates()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if {'qty', 'price_unit', 'product_id', 'activity_id'} & set(vals):
            self._check_linked_templates()
        return res

    def unlink(self):
        templates = self.template_id
        res = super().unlink()
        self.browse()._check_linked_templates(templates.exists())
        return res


class ConstructionWorkItemSyncWizard(models.TransientModel):
    """Vista previa y aplicación de la sincronización (M18-13)."""
    _name = 'construction.work.item.sync.wizard'
    _description = 'Sincronizar receta y Work Item'

    template_id = fields.Many2one(
        'construction.execution.template', string='Receta', required=True, ondelete='cascade')
    sync_state = fields.Selection(related='template_id.sync_state')
    direction = fields.Selection(
        [('to_template', 'Llevar el Work Item a la receta'),
         ('to_work_item', 'Llevar la receta al Work Item')],
        string='Qué hacer', required=True, default='to_template')
    preview_html = fields.Html(string='Vista previa', compute='_compute_preview_html',
                               sanitize=False)

    @api.depends('template_id', 'direction')
    def _compute_preview_html(self):
        for wizard in self:
            template = wizard.template_id
            item = template._work_item_read([template.work_item_id]).get(template.work_item_id) \
                if template.work_item_id else None
            if not item:
                wizard.preview_html = Markup('<p class="text-danger">%s</p>') % self.env._(
                    'No se encontró el Work Item vinculado.')
                continue
            rows = template._sync_differences(item)
            if not rows:
                wizard.preview_html = Markup('<p class="text-success">%s</p>') % self.env._(
                    'La receta y el Work Item ya son iguales.')
                continue

            def value(number):
                return '—' if number is None else ('%g' % number)

            to_template = wizard.direction == 'to_template'
            body = Markup('')
            for row in rows:
                if row['kind'] == 'only_work_item':
                    effect = self.env._('Se agrega a la receta') if to_template else \
                        self.env._('Se quita del Work Item')
                elif row['kind'] == 'only_template':
                    effect = self.env._('Se quita de la receta') if to_template else \
                        self.env._('Se agrega al Work Item')
                else:
                    effect = self.env._('Queda %s', value(row['work_item'] if to_template
                                                           else row['template']))
                body += Markup('<tr><td>%s</td><td>%s</td><td class="text-end">%s</td>'
                               '<td class="text-end">%s</td><td>%s</td></tr>') % (
                    row['resource'], row['field'], value(row['work_item']),
                    value(row['template']), effect)
            wizard.preview_html = Markup(
                '<table class="table table-sm o_construction_sync_preview"><thead><tr>'
                '<th>%s</th><th>%s</th><th class="text-end">%s</th><th class="text-end">%s</th>'
                '<th>%s</th></tr></thead><tbody>%s</tbody></table>') % (
                self.env._('Recurso'), self.env._('Dato'), self.env._('Work Item'),
                self.env._('Receta'), self.env._('Resultado'), body)

    def action_apply(self):
        self.ensure_one()
        template = self.template_id
        item = template._work_item_read([template.work_item_id]).get(template.work_item_id)
        if not item:
            raise UserError(self.env._('No se encontró el Work Item vinculado.'))
        if self.direction == 'to_template':
            template._apply_work_item_to_template(item)
        else:
            template._apply_template_to_work_item(item)
            item = template._work_item_read([template.work_item_id])[template.work_item_id]
        template._mark_synced(item)
        return {'type': 'ir.actions.act_window_close'}
