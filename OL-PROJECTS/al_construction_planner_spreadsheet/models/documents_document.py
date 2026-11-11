# -*- coding: utf-8 -*-
"""Hoja de trabajo de presupuesto y plan en Hojas de cálculo (requerimiento
CREVAL v1.0, 6.7).

La hoja tiene las mismas hojas y columnas del libro de carga (6.6): se valida,
se envía al planificador (destino Presupuesto o Plan) por el mismo asistente
del libro, trae el costo vigente de los insumos y los datos de Odoo, y guarda
una copia numerada en cada versión y en cada envío. Las obras de mobiliario
llenan su propio maestro con el puente al_construction_planner_spreadsheet_furniture."""
import base64
import json
from io import BytesIO

from markupsafe import Markup

from odoo import fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner_sale.wizards.budget_book_wizard import COLUMNS

from .project_project import (
    BUDGET_LAYOUT, CALCULATED_KEYS, LISTS, PLAN_COLUMNS, PRODUCT_LIST, ROW_KEYS, TEMPLATE_LABELS,
    calculated, cell_text, data_keys, presupuesto_columns, presupuesto_headers, presupuesto_row,
    sheet_digits,
)
from .sheet_keys import KEYS_SHEET, apply_keys

SHEET_KINDS = [
    ('budget', 'Presupuesto y plan'),
    ('furniture', 'Maestro de mobiliario'),
]
# Pestañas de la hoja que van al libro de carga.
BOOK_SHEETS = ('OBRA', 'INSUMOS', 'APU', 'APU_DETALLE', 'PRESUPUESTO', 'PLAN', 'LISTAS')
# Pestañas que «Traer de Odoo» escribe por clave de columna.
KEYED_SHEETS = ('INSUMOS', 'APU', 'APU_DETALLE')
# Estado de la hoja (paquete 1.13, M113-11): lo escriben «Importar Excel a la
# hoja», «Validar» y el envío; lo leen INICIO y la ficha de la obra (M113-12).
SHEET_STATES = [
    ('draft', 'Borrador'),
    ('imported', 'Importada'),
    ('validated', 'Validada'),
    ('sent', 'Enviada'),
]
CONTROL_STATES = [
    ('match', 'Coincide'),
    ('mismatch', 'No coincide'),
]


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    construction_project_id = fields.Many2one(
        'project.project', string='Obra (hoja de trabajo)', index='btree_not_null',
        ondelete='set null', readonly=True, copy=False,
        help='Obra cuya hoja de trabajo es esta.')
    construction_sale_order_id = fields.Many2one(
        'sale.order', string='Cotización (hoja de trabajo)', index='btree_not_null',
        ondelete='set null', readonly=True, copy=False)
    construction_sheet_kind = fields.Selection(
        SHEET_KINDS, string='Hoja de trabajo', readonly=True, copy=False)
    # CREVAL, paquete 5, CR-38: la hoja de presupuesto de construcción se
    # parte en venta (con la cotización) y planificación de obra (con la
    # obra). Vacío: la hoja «Presupuesto y plan» de antes, que sigue igual.
    construction_budget_role = fields.Selection(
        [('sale', 'Presupuesto de venta'), ('plan', 'Planificación de obra')],
        string='Uso de la hoja', readonly=True, copy=True)
    construction_version = fields.Integer(string='Versión de la hoja', default=1, copy=False,
                                          readonly=True)
    # Paquete 1.13, M113-04/05: filas con listas y fórmulas con que nació la
    # hoja (o a las que la amplió «Importar Excel a la hoja»); 0 en las hojas
    # anteriores, que no se amplían.
    construction_sheet_rows = fields.Integer(string='Filas de la hoja', readonly=True,
                                             copy=False)
    # Paquete 1.16, CR-22 g: orden de las columnas de la hoja de presupuesto.
    # Desde el 2 el código va al final y la receta se elige por nombre; las
    # hojas anteriores tienen 0 y conservan su orden.
    construction_sheet_layout = fields.Integer(string='Orden de columnas de la hoja',
                                               readonly=True)
    construction_source_id = fields.Many2one(
        'documents.document', string='Hoja de trabajo vigente', readonly=True, copy=False,
        ondelete='set null', help='En una copia numerada: la hoja de la que se copió.')
    construction_version_reason = fields.Char(
        string='Acción que originó la versión', readonly=True, copy=False)
    construction_sheet_state = fields.Selection(
        SHEET_STATES, string='Estado de la hoja', default='draft', readonly=True, copy=False)
    construction_state_date = fields.Datetime(string='Fecha del estado', readonly=True,
                                              copy=False)
    construction_import_filename = fields.Char(string='Última importación', readonly=True,
                                               copy=False)
    construction_import_date = fields.Datetime(string='Fecha de la importación', readonly=True,
                                               copy=False)
    construction_import_errors = fields.Integer(string='Errores al importar', readonly=True,
                                                copy=False)
    construction_validate_errors = fields.Integer(string='Errores de la última validación',
                                                  readonly=True, copy=False)
    construction_validate_warnings = fields.Integer(string='Avisos de la última validación',
                                                    readonly=True, copy=False)
    construction_send_version = fields.Integer(string='Versión enviada', readonly=True,
                                               copy=False)
    construction_send_date = fields.Datetime(string='Fecha del último envío', readonly=True,
                                             copy=False)
    construction_send_message_id = fields.Many2one(
        'mail.message', string='Mensaje del envío', readonly=True, copy=False,
        ondelete='set null')
    construction_control_state = fields.Selection(
        CONTROL_STATES, string='Control de alcance', readonly=True, copy=False)
    construction_control_date = fields.Datetime(string='Fecha del control', readonly=True,
                                                copy=False)

    def _construction_state_label(self):
        """«Enviada v3 · 01/11/2026 17:40»: el texto del estado en INICIO."""
        self.ensure_one()
        label = dict(self._fields['construction_sheet_state']._description_selection(
            self.env)).get(self.construction_sheet_state or 'draft')
        if self.construction_sheet_state == 'sent' and self.construction_send_version:
            label = '%s v%s' % (label, self.construction_send_version)
        if self.construction_state_date:
            # Paquete 1.18, M118-14, punto 4: en la zona horaria del usuario
            # (sin ella, la de la compañía y, si no, la de Lima).
            tz = self.env.context.get('tz') or self.env.user.tz or \
                self.env.company.partner_id.tz or 'America/Lima'
            label = '%s · %s' % (label, fields.Datetime.context_timestamp(
                self.with_context(tz=tz), self.construction_state_date).strftime(
                '%d/%m/%Y %H:%M'))
        return label

    def _construction_set_state(self, state, **values):
        """Pasa la hoja a ``state`` con la fecha de ahora (M113-11)."""
        self.write(dict(values, construction_sheet_state=state,
                        construction_state_date=fields.Datetime.now()))

    def construction_control_done(self, matches):
        """Semáforo de CONTROL para la ficha de la obra (M113-12)."""
        self.ensure_one()
        self.write({'construction_control_state': 'match' if matches else 'mismatch',
                    'construction_control_date': fields.Datetime.now()})
        return True

    def _get_spreadsheet_metadata(self, access_token=None):
        data = super()._get_spreadsheet_metadata(access_token)
        # sudo: solo se lee el vínculo de la hoja con su obra o cotización
        # para mostrar el menú de la vertical.
        document_sudo = self.sudo()
        data['construction_project_id'] = document_sudo.construction_project_id.id or False
        data['construction_budget_role'] = document_sudo.construction_budget_role or False
        data['construction_sheet_kind'] = document_sudo.construction_sheet_kind or (
            'furniture' if document_sudo.construction_project_id else False)
        order = document_sudo.construction_sale_order_id or \
            document_sudo.construction_project_id.construction_sale_order_id
        # D3: con la cotización confirmada no se envía el presupuesto.
        data['construction_offer_locked'] = bool(order) and order._construction_offer_locked()
        # M113-02: el envío recoge solo estas pestañas.
        data['construction_send_sheets'] = document_sudo._construction_send_sheet_names() \
            if data['construction_sheet_kind'] else []
        data['construction_sheet_rows'] = document_sudo.construction_sheet_rows
        # M113-07: INICIO muestra el estado que escribe el sistema.
        data['construction_sheet_state'] = document_sudo._construction_state_label() \
            if data['construction_sheet_kind'] else ''
        # M113-11: CONTROL se actualiza al abrir la hoja después de un envío.
        send_date = document_sudo.construction_send_date
        control_date = document_sudo.construction_control_date
        data['construction_control_pending'] = bool(
            send_date and (not control_date or control_date < send_date))
        return data

    def _construction_send_sheet_names(self):
        """Pestañas que lee el envío (M113-02): las del libro y _CLAVES."""
        return list(BOOK_SHEETS) + [KEYS_SHEET]

    # ------------------------------------------------------------------
    # Enviar al planificador
    # ------------------------------------------------------------------
    def _construction_order(self):
        self.ensure_one()
        order = self.construction_sale_order_id or \
            self.construction_project_id.construction_sale_order_id
        if not order:
            raise UserError(self.env._(
                'La hoja no tiene cotización: ábrala desde la cotización (botón «Hoja de '
                'trabajo») o indique la orden de venta del contrato de la obra.'))
        return order

    def _construction_book(self, sheets):
        """Libro de carga (6.6) con las pestañas de la hoja."""
        from openpyxl import Workbook
        workbook = Workbook()
        workbook.remove(workbook.active)
        for name, rows in (sheets or {}).items():
            if name not in BOOK_SHEETS:
                continue
            if name == 'LISTAS':
                # CR-43: el envío lee de LISTAS las listas y las unidades, no
                # la lista de productos de las columnas siguientes.
                rows = [row[:len(LISTS) * 2 + 2] for row in rows or []]
                while rows and not any(value not in ('', None, False) for value in rows[-1]):
                    rows.pop()
            worksheet = workbook.create_sheet(name)
            for row in rows or []:
                worksheet.append([None if value in ('', False) else value for value in row])
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

    def _construction_budgeter_only(self):
        """CR-47: presupuestador sin el grupo de planificador."""
        user = self.env.user
        return user.has_group('al_construction_planner_spreadsheet.group_construction_budgeter') \
            and not user.has_group('al_construction_planner.group_planner_plan_planner')

    def _construction_book_wizard(self, sheets, target='budget'):
        self.ensure_one()
        if target == 'budget' and self._construction_budgeter_only() and not self.env.su:
            # sudo: el presupuestador revisa y pasa su presupuesto; la
            # revisión lee recetas, etapas y cuentas que él no administra.
            return self.sudo()._construction_book_wizard(sheets, target)
        order = self._construction_order()
        return self.env['construction.budget.book.wizard'].create({
            'sale_order_id': order.id,
            'project_id': (self.construction_project_id or order.project_id).id,
            'target': target,
            'file': base64.b64encode(self._construction_book(sheets)),
            'filename': '%s.xlsx' % self.name,
            'spreadsheet_id': self.id,
            # CR-45, punto 4: el plan con los APU de obra, sin tocar la venta.
            'site_plan': self.construction_budget_role == 'plan',
        })

    def action_construction_send_to_planner(self, sheets, target='budget'):
        """Lleva la hoja al planificador: el maestro de mobiliario a su
        importador; la de presupuesto y plan al asistente del libro (6.6),
        con su revisión antes de escribir.

        :param sheets: ``{pestaña: [[valor, …], …]}`` con los valores
            calculados, fila por fila (la primera, los encabezados).
        :param target: ``budget`` (presupuesto) o ``plan`` (presupuesto y plan).
        """
        self.ensure_one()
        if not self.construction_project_id and not self.construction_sale_order_id:
            raise UserError(self.env._('Esta hoja no es una hoja de trabajo del planificador.'))
        # CR-38: la hoja de venta solo pasa a la cotización; la de
        # planificación solo envía el plan.
        if self.construction_budget_role == 'sale' and target != 'budget':
            raise UserError(self.env._('La hoja de venta pasa el presupuesto a la cotización; '
                                       'el plan se envía desde la hoja de planificación.'))
        if self.construction_budget_role == 'plan' and target != 'plan':
            raise UserError(self.env._('La hoja de planificación envía el plan.'))
        # Las columnas se leen por su clave interna (M116-09, CR-22 d).
        sheets = apply_keys(sheets)
        if self.construction_sheet_kind != 'budget':
            return self._construction_send_furniture(sheets)
        wizard = self._construction_book_wizard(sheets, target)
        wizard.action_preview()
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Enviar al planificador'),
            'res_model': wizard._name, 'res_id': wizard.id, 'view_mode': 'form',
            'views': [(False, 'form')], 'target': 'new',
        }

    def _construction_send_furniture(self, sheets):
        """Maestro de mobiliario: lo implementa su puente."""
        raise UserError(self.env._(
            'Esta hoja es el maestro de mobiliario: instale el planificador de mobiliario.'))

    def action_construction_validate(self, sheets):
        """«Validar»: las filas de la pestaña ERRORES común (paquete 1.16,
        M116-09): hoja, fila, columna, mensaje y tipo.

        :return: ``{'rows': [[hoja, fila, columna, mensaje, tipo]],
            'errors': n, 'warnings': m}``
        """
        self.ensure_one()
        sheets = apply_keys(sheets)
        if self.construction_sheet_kind == 'budget':
            issues = self._construction_validate_budget(sheets)
        else:
            issues = self._construction_validate_furniture(sheets)
        # Primero los errores, en el orden de la hoja.
        issues = sorted(issues, key=lambda issue: issue[4] != 'error')
        labels = {'error': self.env._('Error'), 'warning': self.env._('Aviso')}
        errors = sum(1 for issue in issues if issue[4] == 'error')
        warnings = len(issues) - errors
        # M113-11: sin errores la hoja queda validada; con errores vuelve a
        # borrador (o se queda importada).
        state = 'validated' if not errors else (
            'imported' if self.construction_sheet_state == 'imported' else 'draft')
        self._construction_set_state(state, construction_validate_errors=errors,
                                     construction_validate_warnings=warnings)
        return {
            'rows': [[sheet or '', row or '', column or '', message, labels.get(kind, kind)]
                     for sheet, row, column, message, kind in issues],
            'errors': errors,
            'warnings': warnings,
            'state': self._construction_state_label(),
        }

    def _construction_validate_budget(self, sheets):
        """Errores y avisos del libro de presupuesto: ``[(hoja, fila,
        columna, mensaje, tipo)]``."""
        # La cotización confirmada no es un error de la plantilla (D3).
        wizard = self._construction_book_wizard(sheets).with_context(
            construction_validate_only=True)
        _book, errors, warnings = wizard._parse()
        wizard.unlink()
        headers = {(name, key): aliases[0] for name, columns in COLUMNS.items()
                   for key, aliases, _required in columns}
        issues = [(sheet, row, headers.get((sheet, column), column), message, 'error')
                  for sheet, row, column, message in errors]
        issues += [('', '', '', warning, 'warning') for warning in warnings]
        return issues

    def _construction_validate_furniture(self, sheets):
        """Maestro de mobiliario: lo implementa su puente."""
        raise UserError(self.env._(
            'Esta hoja es el maestro de mobiliario: instale el planificador de mobiliario.'))

    def construction_current_costs(self, codes):
        """«Actualizar insumos»: {código: (costo vigente, unidad)} del maestro
        de productos para los códigos de la hoja INSUMOS."""
        self.ensure_one()
        company = (self.construction_project_id.company_id or
                   self.construction_sale_order_id.company_id or self.env.company)
        products = self.env['product.product'].with_company(company).search([
            ('default_code', 'in', [str(code) for code in codes or [] if code]),
            ('company_id', 'in', (company.id, False))])
        return {product.default_code: [product.standard_price, product.uom_id.name]
                for product in products}

    def construction_odoo_rows(self):
        """«Traer de Odoo»: las filas de las pestañas con lo que ya tienen la
        cotización y las recetas de la obra (sin encabezados)."""
        self.ensure_one()
        order = self.construction_sale_order_id or \
            self.construction_project_id.construction_sale_order_id
        project = self.construction_project_id or order.project_id
        rows = self.env['project.project']._construction_budget_rows(
            order, project, sold=self.construction_budget_role != 'plan')
        # Todo como texto (CR-18, a); PRESUPUESTO con sus encabezados y sus
        # fórmulas, para que una hoja anterior quede con las columnas A a W.
        keyed = {}
        for name in KEYED_SHEETS:
            # Las filas llegan en el orden de ROW_KEYS; la hoja escribe cada
            # valor en la columna de su clave (la de una hoja anterior o la de
            # la plantilla, con el código al final).
            keys = ROW_KEYS[name]
            aliases = {key: list(texts) for key, texts, _required in COLUMNS[name]}
            aliases.update({key: [label] for key, label in TEMPLATE_LABELS.items()})
            keyed[name] = {'keys': keys, 'aliases': {key: aliases.get(key, [key])
                                                     for key in keys},
                           'rows': [[cell_text(value) for value in row]
                                    for row in rows.pop(name)],
                           # Las columnas de fórmula de la plantilla de la
                           # hoja no se escriben (las demás, aunque tengan
                           # una fórmula en la fila 2).
                           'calculated': [
                               CALCULATED_KEYS[(name, header)] for header, _formula in
                               calculated(name, self.construction_sheet_layout or 0)
                               if (name, header) in CALCULATED_KEYS]}
        result = {name: [[cell_text(value) for value in row] for row in sheet_rows]
                  for name, sheet_rows in rows.items() if name != 'PRESUPUESTO'}
        # INSUMOS, APU y APU_DETALLE se escriben por la clave de cada columna
        # (paquete 1.16, M116-09): sirve para las hojas nuevas y las anteriores,
        # y no pisa las columnas de fórmula.
        result['_keyed'] = keyed
        result['PRESUPUESTO'] = [presupuesto_headers(self.construction_sheet_layout)] + [
            presupuesto_row(values, number, self.construction_sheet_layout,
                            sheet_digits(self.env, self.construction_project_id.company_id
                                         or self.construction_sale_order_id.company_id or None))
            for number, values in enumerate(rows['PRESUPUESTO'], start=2)]
        result['_from_top'] = ['OBRA', 'PRESUPUESTO']
        # CREVAL, paquete 5, CR-43: la lista de productos del maestro de LISTAS.
        result['_products'] = {
            'headers': [header for _key, header in PRODUCT_LIST],
            'rows': [[cell_text(value) for value in row] for row in
                     self.env['project.project']._construction_product_rows(
                         project.company_id or order.company_id or self.env.company)]}
        return result

    def construction_plan_bring(self):
        """CREVAL, paquete 5, CR-45, punto 2: «Traer la venta» de la hoja de
        planificación de obra, con vista previa y huella (como mobiliario,
        M117-22). PLAN compara por ítem solo lo vendido (ítem y partida): lo
        que escribe el planificador (metrado de obra, modalidad, contratista,
        fechas) no se trae. INSUMOS, APU y APU_DETALLE son los APU de obra:
        lo que cambió en la hoja desde la última vez queda desmarcado. OBRA y
        PRESUPUESTO son la copia de lo vendido y se reescriben enteras.

        :return: ``{'tabs': {pestaña: {'keys', 'match', 'headers', 'rows',
            'keep_extra'}}, 'from_top': {pestaña: filas}, 'warnings': [...]}``
        """
        self.ensure_one()
        if self.construction_budget_role != 'plan':
            raise UserError(self.env._('«Traer la venta» es de la hoja de planificación de obra.'))
        rows = self.construction_odoo_rows()
        layout = self.construction_sheet_layout
        match = {'INSUMOS': ['code'], 'APU': ['code'], 'APU_DETALLE': ['apu_pick', 'pick']}
        tabs = {}
        for name, spec in rows['_keyed'].items():
            keys = data_keys(name, layout)
            index = {key: position for position, key in enumerate(spec['keys'])}
            tabs[name] = {
                'keys': keys, 'match': match[name], 'keep_extra': True,
                'headers': {key: spec['aliases'].get(key, [key]) for key in keys},
                'rows': [[row[index[key]] if key in index and index[key] < len(row) else ''
                          for key in keys] for row in spec['rows']],
            }
        plan_rows = [[row[0], row[1]] for row in rows.get('PLAN', []) if row and row[0]]
        # CR-45, punto 2: la vista previa de PLAN es una tabla por partida con
        # el metrado vendido y el APU (se muestran; no se comparan).
        keys = [key for key, _header, _kind in presupuesto_columns(layout)]
        sold = {}
        for values in rows['PRESUPUESTO'][1:]:
            value = lambda key: values[keys.index(key)] if key in keys and \
                keys.index(key) < len(values) else ''  # noqa: E731
            if value('item'):
                sold[value('item')] = [
                    ' '.join(filter(None, [cell_text(value('qty_real')), cell_text(value('uom'))])),
                    value('apu_pick') if 'apu_pick' in keys else value('apu')]
        tabs['PLAN'] = {
            'keys': ['item', 'name'], 'match': ['item'], 'keep_extra': False,
            'headers': {'item': [PLAN_COLUMNS[0]], 'name': [PLAN_COLUMNS[1]]},
            'rows': plan_rows,
            'table': [self.env._('Ítem'), self.env._('Partida'), self.env._('Metrado vendido'),
                      self.env._('APU')],
            'info': [sold.get(row[0], ['', '']) for row in plan_rows],
        }
        warnings = []
        if not tabs['PLAN']['rows']:
            warnings.append(self.env._(
                'La cotización no tiene partidas con ítem: PLAN no cambia.'))
        return {'tabs': tabs, 'from_top': {name: rows[name] for name in rows['_from_top']},
                'products': rows['_products'], 'warnings': warnings}

    def construction_plan_control(self):
        """CREVAL, paquete 5, CR-46, punto 3: «Actualizar CONTROL» de la hoja
        de planificación de obra compara también con el plan de Odoo, como el
        CONTROL de mobiliario (M113-09). El plan es el último en preparación
        (el que dejó el envío) o, si no hay, el vigente; el costo de cada
        partida es la suma del monto planificado de sus líneas y las de sus
        sub-niveles.

        :return: ``{'plan': nombre del plan, 'items': {ítem: costo}}``
        """
        self.ensure_one()
        if self.construction_budget_role != 'plan':
            raise UserError(self.env._('CONTROL con el plan de Odoo es de la hoja de '
                                       'planificación de obra.'))
        order = self._construction_order()
        project = self.construction_project_id or order.project_id
        Plan = self.env['construction.resource.plan']
        plan = Plan.search([('project_id', '=', project.id), ('state', '=', 'draft')],
                           order='id desc', limit=1) or (
            project._construction_current_plan() if project else Plan)
        items = {}
        for line in plan.line_ids:
            task = line.task_id
            while task and not task.sale_line_id:
                task = task.parent_id
            item = task.sale_line_id.construction_budget_item if task else False
            if item:
                items[item] = items.get(item, 0.0) + line.amount_planned
        self.construction_control_date = fields.Datetime.now()
        return {'plan': plan.display_name or '',
                'items': {item: plan.currency_id.round(amount) if plan.currency_id else amount
                          for item, amount in items.items()}}

    def construction_budget_upgrade(self, sheets):
        """CREVAL, paquete 5, CR-38, punto 4 (decisión del 05-nov):
        «Actualizar a la plantilla vigente» de una hoja «Presupuesto y plan»:
        guarda una versión y la rehace como hoja de presupuesto de venta, con
        la plantilla de hoy y lo escrito en la anterior. Las fórmulas propias
        de la hoja anterior pasan como su valor. La hoja de planificación de
        obra se crea aparte, desde la obra, con «Traer la venta».

        :param sheets: ``{pestaña: [[valor, …], …]}``, los valores calculados.
        :return: la acción que abre la hoja actualizada.
        """
        self.ensure_one()
        if self.construction_sheet_kind != 'budget' or self.construction_budget_role:
            raise UserError(self.env._(
                'Solo una hoja «Presupuesto y plan» se actualiza a la hoja de venta.'))
        order = self._construction_order()
        project = self.construction_project_id or order.project_id
        Project = self.env['project.project']
        values = Project._construction_budget_rows_from_sheets(apply_keys(sheets))
        self._construction_copy_version(self.env._('Antes de actualizar a la plantilla vigente'))
        data = Project._construction_budget_spreadsheet_data(order, project, values=values)
        self.write({
            'name': self.env._('Presupuesto de venta · %(order)s · %(partner)s', order=order.name,
                               partner=order.partner_id.commercial_partner_id.name or ''),
            'datas': base64.b64encode(json.dumps(data).encode()),
            'construction_sale_order_id': order.id,
            'construction_budget_role': 'sale',
            'construction_sheet_layout': BUDGET_LAYOUT,
        })
        self._delete_collaborative_data()
        order.message_post(body=self.env._(
            'Hoja «Presupuesto y plan» actualizada a hoja de presupuesto de venta (versión '
            'anterior guardada).'))
        return self.action_open_spreadsheet()

    def action_construction_new_version(self):
        """«Nueva versión»: una copia numerada de la hoja en la misma carpeta,
        con el enlace en el historial de la cotización o del plan."""
        self.ensure_one()
        return self._construction_save_version(self.env._('Nueva versión de la hoja'))

    def _construction_sent(self, reason):
        """Envío terminado: copia numerada y estado «Enviada vN» con la fecha
        y el mensaje del historial (M113-11)."""
        self.ensure_one()
        copy, message = self._construction_copy_version(reason)
        now = fields.Datetime.now()
        self._construction_set_state(
            'sent', construction_send_version=copy.construction_version,
            construction_send_date=now, construction_send_message_id=message.id or False)
        return copy

    def construction_version_before(self, reason):
        """Guarda una copia numerada antes de que una acción de la hoja
        escriba (paquete 1.13, M113-08) y devuelve su número."""
        self.ensure_one()
        copy, _message = self._construction_copy_version(reason or self.env._(
            'Antes de una acción de planificación'))
        return copy.construction_version

    def construction_versions(self):
        """Versiones guardadas de la hoja para «Restaurar versión» (paquete
        1.17, M117-03): la más reciente primero."""
        self.ensure_one()
        versions = self.search([('construction_source_id', '=', self.id)],
                               order='construction_version desc, id desc')
        return [{
            'id': version.id, 'version': version.construction_version,
            'date': fields.Datetime.context_timestamp(self, version.create_date).strftime(
                '%d/%m/%Y %H:%M'),
            'reason': version.construction_version_reason or '',
        } for version in versions]

    def _construction_save_version(self, reason):
        copy, _message = self._construction_copy_version(reason)
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'type': 'success', 'message': self.env._('Versión %s guardada: %s',
                                                     copy.construction_version, copy.name)}}

    def _construction_copy_version(self, reason):
        """Copia numerada de la hoja y el enlace en el historial de la
        cotización y del plan (o de la obra, si no hay ninguno).

        :return: (copia, mensaje del historial)
        """
        self.ensure_one()
        version = self.construction_version
        copy = self.copy({
            'name': '%s · v%s' % (self.name, version),
            'folder_id': self.folder_id.id,
            'construction_source_id': self.id,
            'construction_version': version,
            'construction_version_reason': reason,
        })
        self.construction_version = version + 1
        body = Markup('%s: <a href="#" data-oe-model="documents.document" data-oe-id="%s">%s</a>'
                      ) % (reason, copy.id, copy.name)
        order = self.construction_sale_order_id or \
            self.construction_project_id.construction_sale_order_id
        messages = self.env['mail.message']
        if order:
            messages |= order.message_post(body=body)
        plan = self.construction_project_id._construction_current_plan() \
            if self.construction_project_id else False
        if plan:
            messages |= plan.message_post(body=body)
        if not messages and self.construction_project_id:
            # sudo: quien planifica puede no tener escritura en la obra; solo
            # se deja el enlace de la versión en su historial.
            messages = self.construction_project_id.sudo().message_post(
                body=body, author_id=self.env.user.partner_id.id)
        return copy, messages[:1]


class ConstructionBudgetBookWizard(models.TransientModel):
    _inherit = 'construction.budget.book.wizard'

    spreadsheet_id = fields.Many2one('documents.document', string='Hoja de trabajo',
                                     readonly=True)

    def action_import(self):
        res = super().action_import()
        # Cada envío deja una copia numerada de la hoja (6.7).
        if self.spreadsheet_id and self.state == 'done':
            self.spreadsheet_id._construction_sent(self.env._(
                'Hoja enviada al planificador (%s)', dict(self._fields['target'].selection)[
                    self.target]))
        return res


def spreadsheet_json(data):
    return base64.b64encode(json.dumps(data).encode())


class ConstructionBudgetBookWizard(models.TransientModel):
    _inherit = 'construction.budget.book.wizard'

    def action_import(self):
        """CREVAL, paquete 5, CR-47: «Pasar a la cotización» del presupuestador.
        El envío crea los insumos, los APU y las líneas de la cotización con
        las reglas del libro; el presupuestador no administra recetas ni
        productos, así que, solo para el destino Presupuesto, corre como el
        sistema (no crea plan ni niveles)."""
        user = self.env.user
        if self.target == 'budget' and \
                user.has_group('al_construction_planner_spreadsheet.group_construction_budgeter') \
                and not user.has_group('al_construction_planner.group_planner_plan_planner'):
            # sudo: ver el docstring; el destino Presupuesto no toca el plan.
            return super(ConstructionBudgetBookWizard, self.sudo()).action_import()
        return super().action_import()
