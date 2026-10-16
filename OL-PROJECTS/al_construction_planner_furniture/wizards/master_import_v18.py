# -*- coding: utf-8 -*-
"""Maestro de planificación de la hoja de trabajo (v1.8, M18-22).

La oficina técnica arma el presupuesto y la carga de la obra en la hoja de
cálculo de Odoo; «Enviar al planificador» la trae con este importador, que
además de las hojas de la 1.5 lee:

* MODULOS con el nombre, el tipo de módulo y el método de unión;
* PIEZAS (despiece de cada módulo) y BOM por módulo y sub etapa: la receta de
  cada módulo, de la que salen sus materiales y sus contratas;
* PRODUCTOS NUEVOS: se crean con su nombre, unidad, categoría y costo, con
  el código de la regla del maestro (familia más correlativo, P-17) en lugar
  del provisional, que se reemplaza en BOM y PIEZAS; se avisan los parecidos;
* TARIFAS de la obra (lista de tarifas de la obra), OBRA (fechas, cliente,
  condiciones), MO PROPIA (roles de cuadrilla con su jornal) y, con Ventas,
  CONTRATOS, HITOS y VENTA.

Un segundo envío no duplica nada: todo se busca por su código o su nombre.
"""
import logging
import re
from collections import defaultdict

from odoo import Command, models

from odoo.addons.al_construction_planner.models.common import norm

from ..models.construction_furniture_model import JOIN_METHODS, MODULE_CLASSES
from .master_import_wizard import _number, _text

_logger = logging.getLogger(__name__)


def _choice(selection, text):
    """Clave de una lista por su etiqueta o su clave (o False)."""
    key = norm(text)
    for value, label in selection:
        if key in (norm(value), norm(label)):
            return value
    return False


class ConstructionMasterImportWizard(models.TransientModel):
    _inherit = 'construction.master.import.wizard'

    # ------------------------------------------------------------------
    # Lectura: productos nuevos con su código definitivo
    # ------------------------------------------------------------------
    def _new_product_codes(self, rows):
        """{código provisional: (código definitivo, valores)} de PRODUCTOS
        NUEVOS. Un producto que ya existe con ese nombre en la compañía (un
        envío anterior) conserva su código."""
        company = self._company()
        # sudo: el producto de un envío anterior puede estar archivado o ser de
        # otra regla de acceso; solo se busca por nombre en la compañía de la
        # obra para no duplicarlo, no se muestra ni se modifica.
        products_sudo = self.env['product.product'].sudo().with_context(active_test=False)
        Category = self.env['product.category']
        creator = self.env.get('construction.product.create.wizard')
        reserved = defaultdict(int)
        result = {}
        for row in rows:
            provisional = _text(row.get('code'))
            name = _text(row.get('name'))
            if not provisional or not name:
                continue
            existing = products_sudo.search([('name', '=', name),
                                       ('company_id', 'in', (company.id, False))], limit=1)
            categ = Category.search([('name', '=ilike', _text(row.get('categ')))], limit=1) \
                if _text(row.get('categ')) else Category
            uom = self._uom(row.get('uom')) if _text(row.get('uom')) else self.env['uom.uom']
            values = {'name': name, 'categ_id': categ.id or False,
                      'uom_id': (uom or self.env.ref('uom.product_uom_unit')).id,
                      'standard_price': _number(row.get('cost')) or 0.0}
            if existing:
                result[provisional] = (existing.default_code or provisional, values, existing)
                continue
            code = provisional
            if creator is not None and categ and 'construction_family_code' in categ._fields \
                    and categ.construction_family_code:
                base = creator._next_code(categ)
                if base:
                    prefix = categ.construction_family_code
                    number = int(base[len(prefix):]) + reserved[prefix]
                    reserved[prefix] += 1
                    code = '%s%0*d' % (prefix, len(base) - len(prefix), number)
            result[provisional] = (code, values, products_sudo.browse())
        return result

    def _read_workbook(self):
        sheets, errors = super()._read_workbook()
        new_rows = sheets.get('PRODUCTOS NUEVOS') or []
        if not new_rows:
            return sheets, errors
        mapping = self._new_product_codes(new_rows)
        for sheet in ('BOM', 'PIEZAS'):
            for row in sheets.get(sheet, []):
                code = _text(row.get('product_code'))
                if code in mapping:
                    final, values, _existing = mapping[code]
                    row['product_code'] = final
                    # El nombre sale de PRODUCTOS NUEVOS, no de la columna
                    # Producto de BOM (que trae el código entre corchetes).
                    row['product_name'] = values['name']
                    if not _number(row.get('cost')):
                        row['cost'] = values['standard_price']
        return sheets, errors

    # ------------------------------------------------------------------
    # Análisis
    # ------------------------------------------------------------------
    def _module_extra_values(self, row):
        values = super()._module_extra_values(row)
        if _text(row.get('name')):
            values['name'] = _text(row['name'])
        module_class = _choice(MODULE_CLASSES, row.get('module_class'))
        if module_class:
            values['module_class'] = module_class
        join_method = _choice(JOIN_METHODS, row.get('join_method'))
        if join_method:
            values['join_method'] = join_method
        return values

    def _analyze(self):
        result = super()._analyze()
        if not self.file or not self.project_id or not result['stats']:
            return result
        sheets, _errors = self._read_workbook()
        warn = result['warnings']
        typologies = set(result['typologies']) | set(
            self.env['construction.typology'].search(
                [('project_id', '=', self.project_id.id)]).mapped('code'))
        stage_codes = {}
        for stage in self.env['construction.stage'].search([('is_group', '=', False)]):
            for text in [stage.code, stage.name, stage._label()] + [
                    alias.strip() for alias in (stage.alias_names or '').split(',')]:
                if text:
                    stage_codes[norm(text)] = stage.code

        # Receta por módulo: BOM con módulo y PIEZAS.
        module_bom = defaultdict(list)
        for row in sheets.get('BOM', []):
            module = _text(row.get('module'))
            typology = _text(row.get('typology'))
            if module and typology in typologies:
                module_bom[(typology, module)].append({
                    'code': _text(row.get('product_code')), 'qty': _number(row.get('qty')) or 0.0,
                    'stage': stage_codes.get(norm(row.get('stage'))) or False,
                })
        pieces = defaultdict(list)
        for row in sheets.get('PIEZAS', []):
            typology = _text(row.get('typology'))
            if typology not in typologies:
                warn['unknown_typology'].append('PIEZAS · %s' % (typology or '—'))
                continue
            pieces[(typology, _text(row.get('module')))].append({
                'qty': _number(row.get('qty')) or 0.0,
                'length_mm': _number(row.get('length')) or 0.0,
                'width_mm': _number(row.get('width')) or 0.0,
                'piece_type': _text(row.get('piece_type')), 'color': _text(row.get('color')),
                'edges': _text(row.get('edges')), '_code': _text(row.get('product_code')),
            })
        result['module_bom'] = dict(module_bom)
        result['pieces'] = dict(pieces)
        # Los registros de Odoo 19 no guardan atributos: se vuelve a calcular
        # (mismos códigos, reservados con la misma búsqueda).
        new_rows = sheets.get('PRODUCTOS NUEVOS') or []
        result['new_products'] = self._new_product_codes(new_rows) if new_rows else {}
        # Parecidos de los productos nuevos (lógica de P-17).
        creator = self.env.get('construction.product.create.wizard')
        if creator is not None:
            for _provisional, (code, values, existing) in result['new_products'].items():
                if existing:
                    continue
                try:
                    wizard = creator.new({'name': values['name'],
                                          'company_id': self._company().id})
                    similar = wizard._find_similar()
                except Exception:  # noqa: BLE001 - solo es un aviso
                    _logger.debug('Sin parecidos para %s', values['name'], exc_info=True)
                    similar = []
                if similar:
                    warn['new_product_similar'].append('%s ≈ %s' % (
                        values['name'], ', '.join(p.display_name for p, _s, _l in similar[:3])))
        result['rates'] = sheets.get('TARIFAS', [])
        result['obra'] = {norm(_text(row.get('key'))): row.get('value')
                          for row in sheets.get('OBRA', [])}
        result['roles'] = sheets.get('MO PROPIA', [])
        result['contracts'] = sheets.get('CONTRATOS', [])
        result['milestones'] = sheets.get('HITOS', [])
        result['prices'] = sheets.get('VENTA', [])
        if (result['contracts'] or result['prices']) and 'construction.contract' not in self.env:
            warn['no_sale_bridge'].append('CONTRATOS, HITOS, VENTA')
        elif 'construction.contract' in self.env:
            for row in result['contracts']:
                if _text(row.get('name')) and not self._contract_partner(row):
                    warn['contract_no_partner'].append(_text(row.get('name')))
        # Aviso: el presupuesto de la obra aún no está aprobado (propuesta).
        project = self.project_id
        if 'construction_sale_order_id' in project._fields:
            # sudo: la oficina técnica puede no tener acceso a Ventas; solo se
            # lee el estado y el nombre de la venta de la obra para el aviso.
            order_sudo = project.sudo().construction_sale_order_id
            if not order_sudo or order_sudo.state != 'sale':
                warn['budget_not_approved'].append(
                    order_sudo.name if order_sudo else project.display_name)
        return result

    def _warning_messages(self):
        messages = super()._warning_messages()
        messages.update({
            'new_product_similar': self.env._(
                'Productos nuevos parecidos a otros del maestro (revise antes de crearlos)'),
            'no_sale_bridge': self.env._(
                'Hojas de contratos y venta sin el puente de Ventas instalado (se omiten)'),
            'contract_no_partner': self.env._(
                'Contratos sin cliente (ni en la hoja ni en la obra): no se crean'),
            'budget_not_approved': self.env._(
                'El presupuesto de la obra no está aprobado por el cliente'),
        })
        return messages

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    def _apply(self, data):
        summary = super()._apply(data)
        company = self._company()
        # sudo: como el importador base, que crea los productos nuevos con
        # sudo; aquí solo se buscan por código en la compañía de la obra (también
        # archivados) y se les pone la categoría del libro.
        products_sudo = self.env['product.product'].sudo().with_context(active_test=False)
        # Productos nuevos: categoría (el importador base los crea con código,
        # nombre, unidad y costo).
        for _provisional, (code, values, _existing) in data.get('new_products', {}).items():
            product = products_sudo.search([('default_code', '=', code),
                                            ('company_id', 'in', (company.id, False))], limit=1)
            if product and values.get('categ_id') and product.categ_id.id != values['categ_id']:
                product.categ_id = values['categ_id']
        typologies = {t.code: t for t in self.env['construction.typology'].search(
            [('project_id', '=', self.project_id.id)])}
        products = {}

        def product_for(code):
            if code not in products:
                products[code] = products_sudo.search(
                    [('default_code', '=', code), ('company_id', 'in', (company.id, False))],
                    limit=1)
            return products[code]

        # Receta por módulo y despiece: lo del libro reemplaza lo del módulo.
        for (typology_code, module_code), lines in data.get('module_bom', {}).items():
            module = typologies.get(typology_code) and typologies[typology_code] \
                .module_line_ids.filtered(lambda m, c=module_code: m.code == c)[:1]
            if not module:
                continue
            totals = defaultdict(float)
            for line in lines:
                product = product_for(line['code'])
                if product:
                    totals[(product, line['stage'])] += line['qty']
            module.material_ids = [Command.clear()] + [Command.create({
                'product_id': product.id, 'qty': qty, 'stage': stage,
                'source_code': product.default_code})
                for (product, stage), qty in totals.items()]
        for (typology_code, module_code), rows in data.get('pieces', {}).items():
            module = typologies.get(typology_code) and typologies[typology_code] \
                .module_line_ids.filtered(lambda m, c=module_code: m.code == c)[:1]
            if not module:
                continue
            module.piece_ids = [Command.clear()] + [Command.create(dict(
                {k: v for k, v in row.items() if not k.startswith('_')},
                sequence=index, product_id=product_for(row['_code']).id or False))
                for index, row in enumerate(rows, start=1)]
        self._apply_rates(data.get('rates', []))
        self._apply_obra(data.get('obra', {}))
        self._apply_roles(data.get('roles', []))
        if 'construction.contract' in self.env:
            self._apply_contracts(data)
        return summary

    def _apply_rates(self, rows):
        if not rows:
            return
        Activity = self.env['construction.labor.activity']
        company = self._company()
        lists = {}
        RateList = self.env['construction.rate.list']
        for row in rows:
            activity = Activity.search([('code', '=', _text(row.get('activity'))),
                                        ('company_id', 'in', (company.id, False))], limit=1)
            if not activity:
                continue
            family = 'closet_drawer' if 'closet' in norm(row.get('family')) else 'kitchen_bath'
            if family not in lists:
                rate_list = RateList.search([('project_id', '=', self.project_id.id),
                                             ('family', '=', family)], limit=1)
                lists[family] = rate_list or RateList.create({
                    'name': self.env._('Tarifas de %s', self.project_id.name), 'family': family,
                    'project_id': self.project_id.id, 'company_id': company.id})
            rate_list = lists[family]
            line = rate_list.line_ids.filtered(lambda l, a=activity: l.activity_id == a)
            values = {'price': _number(row.get('price')) or 0.0,
                      'retention_pct': _number(row.get('retention')) or 0.0}
            if line:
                line.write(values)
            else:
                rate_list.line_ids = [Command.create(dict(values, activity_id=activity.id))]

    def _apply_obra(self, values):
        if not values:
            return
        project = self.project_id
        vals = {}
        for key, field in (('inicio', 'date_start'), ('fin', 'date')):
            value = values.get(key)
            if value:
                try:
                    vals[field] = value if not isinstance(value, str) else \
                        value.strip()[:10]
                except Exception:  # noqa: BLE001
                    continue
        client = _text(values.get('cliente'))
        if client:
            partner = self.env['res.partner'].search(
                ['|', ('name', '=ilike', client), ('vat', '=', client)], limit=1)
            if partner:
                vals['partner_id'] = partner.id
        if vals:
            project.sudo().write(vals)
        for key, field in (('adelanto %', 'construction_advance_pct'),
                           ('fondo de garantia %', 'construction_guarantee_pct')):
            if key in values and field in project._fields:
                project.sudo()[field] = _number(values[key]) or 0.0

    def _apply_roles(self, rows):
        if not rows or 'planning.role' not in self.env:
            return
        Role = self.env['planning.role'].sudo()
        for row in rows:
            name = _text(row.get('role'))
            if not name:
                continue
            role = Role.search([('name', '=ilike', name)], limit=1) or Role.create({'name': name})
            vals = {}
            if 'construction_daily_cost' in role._fields and _number(row.get('daily_cost')):
                vals['construction_daily_cost'] = _number(row['daily_cost'])
            category = _text(row.get('category'))
            if category and 'construction_category_id' in role._fields:
                found = self.env['l10n_pe.hr.construction.category'].search(
                    [('name', '=ilike', category)], limit=1)
                if found:
                    vals['construction_category_id'] = found.id
            if vals:
                role.write(vals)

    def _contract_partner(self, row):
        """Cliente del contrato: la columna «Cliente», si no el de la obra o
        el de su venta."""
        name = _text(row.get('partner'))
        if name:
            partner = self.env['res.partner'].search([('name', '=ilike', name)], limit=1)
            if partner:
                return partner
        project = self.project_id
        if project.partner_id:
            return project.partner_id
        if 'construction_sale_order_id' in project._fields:
            # sudo: solo se lee el cliente de la venta de la obra; la oficina
            # técnica puede no tener acceso a Ventas.
            return project.sudo().construction_sale_order_id.partner_id.sudo(False)
        return self.env['res.partner']

    def _apply_contracts(self, data):
        """Contratos, hitos y precios de venta (con el puente de Ventas)."""
        Template = self.env['construction.milestone.template']
        Stage = self.env['construction.stage']
        rows_by_template = defaultdict(list)
        for row in data.get('milestones', []):
            name = _text(row.get('template'))
            if name and _text(row.get('name')):
                rows_by_template[name].append(row)
        templates = {}
        for name, rows in rows_by_template.items():
            template = Template.search([('name', '=', name)], limit=1)
            # Todos los hitos en una sola escritura: la plantilla exige que
            # sumen 100 % al guardar. Sin etapa, el hito es manual.
            commands = []
            for row in rows:
                stage = Stage._find_by_text(row.get('stage')) if _text(row.get('stage')) else None
                vals = {'name': _text(row.get('name')), 'pct': _number(row.get('pct')) or 0.0,
                        'trigger': 'stage_done' if stage else 'manual', 'stage': stage or False}
                line = template.line_ids.filtered(lambda l, n=vals['name']: l.name == n)[:1]
                commands.append(Command.update(line.id, vals) if line else Command.create(vals))
            if template:
                template.line_ids = commands
            else:
                template = Template.create({'name': name, 'line_ids': commands})
            templates[name] = template
        Contract = self.env['construction.contract']
        contracts = {}
        for row in data.get('contracts', []):
            name = _text(row.get('name'))
            if not name:
                continue
            contract = Contract.search([('project_id', '=', self.project_id.id),
                                        ('name', '=', name)], limit=1)
            vals = {'name': name, 'project_id': self.project_id.id,
                    'advance_pct': _number(row.get('advance')) or 0.0,
                    'guarantee_pct': _number(row.get('guarantee')) or 0.0}
            partner = self._contract_partner(row)
            if partner:
                vals['partner_id'] = partner.id
            elif not contract:
                continue  # sin cliente: avisado en el análisis
            template = templates.get(_text(row.get('milestone_template')))
            if template:
                vals['milestone_template_id'] = template.id
            if contract:
                contract.write(vals)
            else:
                contract = Contract.create(vals)
            contracts[name] = contract
        typologies = {t.code: t for t in self.env['construction.typology'].search(
            [('project_id', '=', self.project_id.id)])}
        for row in data.get('prices', []):
            contract = contracts.get(_text(row.get('contract'))) or Contract.search(
                [('project_id', '=', self.project_id.id),
                 ('name', '=', _text(row.get('contract')))], limit=1)
            typology = typologies.get(_text(row.get('typology')))
            if not contract or not typology:
                continue
            line = contract.price_line_ids.filtered(lambda l, t=typology: l.typology_id == t)
            vals = {'unit_price': _number(row.get('price')) or 0.0}
            if line:
                line.write(vals)
            else:
                contract.price_line_ids = [Command.create(dict(vals, typology_id=typology.id))]
