# -*- coding: utf-8 -*-
"""La hoja de venta nace con la cotización (paquete 1.17, M117-16)."""
import base64
import json

from odoo import api, fields, models
from odoo.exceptions import UserError

from .sale_sheet import SALE_ROWS, SaleSheetBuilder

SALE_PHASES = [
    ('in_progress', 'Venta en curso'),
    ('sent', 'Cotización enviada'),
    ('awarded', 'Adjudicada'),
    ('additional', 'Adicional en curso'),
    ('lost', 'Perdida'),
]
# Fases en las que la hoja queda como lo vendido: solo lectura.
LOCKED_PHASES = ('sent', 'awarded', 'lost')
SALE_SHEET_KIND = 'sale'
DEFAULT_SPACES = ('Cocina', 'Closet dormitorio principal', 'Closet dormitorio secundario',
                  'Baño principal', 'Baño secundario', 'Lavandería', 'Ducto')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Lo que muestra la hoja, tal como se pasó a la cotización: lo leen el PDF y
    # «Traer la venta». El servidor no puede evaluar las fórmulas de una hoja.
    construction_sale_summary = fields.Text(string='Resumen de la hoja de venta', copy=False)
    construction_copied_from_id = fields.Many2one(
        'sale.order', string='Copiada de', copy=False, readonly=True, index='btree_not_null')

    def copy_data(self, default=None):
        # El origen se recuerda para ofrecer copiar su hoja de venta.
        vals_list = super().copy_data(default=default)
        for order, vals in zip(self, vals_list):
            vals.setdefault('construction_copied_from_id', order.id)
        return vals_list

    def _construction_sale_sheet(self):
        """La hoja de venta vigente de la cotización. Quien cambia la cotización
        puede no tener acceso al documento: solo se usa para seguir su fase."""
        self.ensure_one()
        return self.env['documents.document'].sudo().search([
            ('construction_sale_order_id', '=', self.id),
            ('construction_sheet_kind', '=', SALE_SHEET_KIND),
            ('construction_source_id', '=', False)], limit=1)

    def _construction_quote_profile(self):
        """El perfil de la cotización: el de la plantilla de proyecto del producto
        de la línea; si no tiene, el de la compañía (M117-16, punto 3)."""
        self.ensure_one()
        for line in self.order_line:
            profile = line.product_id.project_template_id.construction_profile_id
            if profile:
                return profile
        return self.company_id.construction_profile_id

    def _construction_quote_sheet_kind(self):
        self.ensure_one()
        profile = self._construction_quote_profile()
        return profile.construction_spreadsheet_kind if profile else False

    def _construction_sale_obra_values(self):
        """Lo que OBRA recibe de la cotización."""
        self.ensure_one()
        partner = self.partner_id
        company_partner = partner.commercial_partner_id
        shipping = self.partner_shipping_id
        return {
            'Proyecto': self.client_order_ref or '',
            'Código de cotización': self.name or '',
            'Fecha de cotización': fields.Date.to_string(
                self.date_order.date()) if self.date_order else '',
            'Cliente': company_partner.name or '',
            'Solicitante': partner.name if partner != company_partner else '',
            'Ubicación': shipping._display_address(without_company=True).replace('\n', ', ').strip(
                ', ') if shipping else '',
        }

    def _construction_sale_sheet_overrides(self):
        """Los parámetros que no se eligen: el IGV de la compañía y la moneda."""
        self.ensure_one()
        tax = self.company_id.account_sale_tax_id
        return {'igv': str(tax.amount) if tax else False, 'moneda': self.currency_id.name}

    def _construction_sale_sheet_data(self, rows=SALE_ROWS):
        self.ensure_one()
        Parameter = self.env['construction.sheet.parameter']
        Parameter._construction_ensure(self.company_id)
        obra = dict(self._construction_sale_obra_values())
        obra['Versión de la cotización'] = 'N1'
        for key, name in (('cond_generales', 'Condiciones generales'),
                          ('forma_pago', 'Forma de pago'), ('garantia', 'Garantía'),
                          ('validez', 'Validez de la oferta')):
            text = Parameter.sudo().search([
                ('company_id', '=', self.company_id.id), ('sheet', '=', 'sale'),
                ('key', '=', key)], limit=1).value_initial
            obra[name] = text or ''
        spaces_text = Parameter.sudo().search([
            ('company_id', '=', self.company_id.id), ('sheet', '=', 'sale'),
            ('key', '=', 'ambientes')], limit=1).value_initial
        spaces = [name.strip() for name in (spaces_text or '').split(';') if name.strip()] \
            or list(DEFAULT_SPACES)
        return SaleSheetBuilder(
            Parameter, self.company_id, obra, self._construction_sale_sheet_overrides(), spaces,
            self.env._, rows=rows,
            rates=[line._sheet_row() for line in self._construction_sale_rates()]
        ).build()

    def _construction_sale_rates(self):
        """Las líneas del tarifario de esta cotización: la lee quien cotiza, que
        no administra el catálogo."""
        self.ensure_one()
        date = self.date_order.date() if self.date_order else fields.Date.context_today(self)
        return self.env['construction.sale.rate'].sudo()._construction_rates_for(
            self.company_id, self.currency_id, self.partner_id, date)

    def action_construction_open_budget_sheet(self):
        """CREVAL, paquete 5, CR-47: con un perfil de mobiliario, «Hoja de
        presupuesto» abre la hoja de venta de mobiliario."""
        self.ensure_one()
        # sudo: el presupuestador no lee los productos ni las plantillas de
        # proyecto; solo se pregunta qué hoja abre la cotización.
        if self.sudo()._construction_quote_sheet_kind() == 'furniture':
            return self.action_construction_open_spreadsheet()
        return super().action_construction_open_budget_sheet()

    def action_construction_open_spreadsheet(self):
        """Con un perfil de mobiliario, la hoja de venta; con otro, la de
        presupuesto, como hasta hoy."""
        self.ensure_one()
        if self._construction_quote_sheet_kind() != 'furniture':
            return super().action_construction_open_spreadsheet()
        document = self._construction_sale_sheet().sudo(False)
        # M117-16, punto 3: una cotización duplicada no tiene hoja; se ofrece copiar
        # la de la cotización de origen.
        origin_sheet = self.construction_copied_from_id._construction_sale_sheet() \
            if not document and self.construction_copied_from_id \
            and not self.env.context.get('construction_new_sale_sheet') \
            else self.env['documents.document']
        if origin_sheet:
            wizard = self.env['construction.sale.sheet.copy.wizard'].create({
                'order_id': self.id, 'origin_id': self.construction_copied_from_id.id})
            return {'type': 'ir.actions.act_window', 'res_model': wizard._name, 'res_id': wizard.id,
                    'name': self.env._('Hoja de venta'), 'view_mode': 'form',
                    'views': [(False, 'form')], 'target': 'new'}
        if not document:
            document = self.env['documents.document'].create({
                'name': self.env._('Hoja de venta · %s', self.name),
                'mimetype': 'application/o-spreadsheet', 'handler': 'spreadsheet',
                'datas': base64.b64encode(json.dumps(self._construction_sale_sheet_data()).encode()),
                'folder_id': self._construction_spreadsheet_folder().id,
                'construction_sale_order_id': self.id,
                'construction_sheet_kind': SALE_SHEET_KIND,
                'construction_sale_phase': self._construction_sale_phase_for_state(),
                'construction_sheet_rows': SALE_ROWS,
            })
        return document.action_open_spreadsheet()

    def _construction_sale_phase_for_state(self):
        """La fase que corresponde al estado de la cotización."""
        self.ensure_one()
        return {'draft': 'in_progress', 'sent': 'sent', 'sale': 'awarded',
                'cancel': 'lost'}.get(self.state, 'in_progress')

    @api.model
    def _construction_phase_message(self, phase):
        return dict(SALE_PHASES).get(phase, '')

    def write(self, vals):
        res = super().write(vals)
        # M117-16, punto 4: la fase la cambia el sistema, desde la cotización.
        if 'state' in vals:
            for order in self:
                document_sudo = order._construction_sale_sheet()
                if document_sudo:
                    phase = order._construction_sale_phase_for_state()
                    # Con un adicional en curso, confirmar no la devuelve:
                    # lo hace «Pasar el resumen a la cotización».
                    if document_sudo.construction_sale_phase != 'additional':
                        document_sudo.construction_sale_phase = phase
        return res

    # ------------------------------------------------------------------
    # Fase «Cotización enviada» (decisión del 04-nov)
    # ------------------------------------------------------------------
    def _construction_mark_sale_sheet_sent(self):
        for order in self:
            document_sudo = order._construction_sale_sheet()
            if document_sudo.construction_sale_phase == 'in_progress':
                document_sudo.construction_sale_phase = 'sent'

    def message_post(self, **kwargs):
        # Una versión nueva se envía con la cotización ya en «Enviada»: su estado
        # no cambia, pero la hoja sí pasa de fase.
        if self.env.context.get('mark_so_as_sent'):
            self._construction_mark_sale_sheet_sent()
        return super().message_post(**kwargs)

    def action_quotation_sent(self):
        res = super().action_quotation_sent()
        self._construction_mark_sale_sheet_sent()
        return res

    # ------------------------------------------------------------------
    # «Pasar el resumen a la cotización» (M117-21, punto 9)
    # ------------------------------------------------------------------
    def _construction_sale_summary_data(self):
        self.ensure_one()
        return json.loads(self.construction_sale_summary) if self.construction_sale_summary else {}

    def _construction_sale_version_label(self):
        self.ensure_one()
        return self._construction_sale_summary_data().get('version') or 'N1'

    def _construction_sale_partida_amounts(self, summary):
        """{partida: precio de su línea}, sin IGV y con su parte del descuento. Los
        céntimos del reparto van a la partida de mayor monto: la orden suma
        exactamente el subtotal con descuento del resumen."""
        self.ensure_one()
        currency = self.currency_id
        factor = 1.0 if summary.get('prices_without_tax', True) else 1.0 + (summary.get('igv') or 0.0)
        gross = {item['name']: (item['subtotal'] or 0.0) / factor
                 for item in summary.get('partidas', [])}
        total = sum(gross.values())
        discount = (summary.get('discount') or 0.0) / factor
        target = currency.round(total - discount)
        amounts = {name: currency.round(value - discount * value / total if total else value)
                   for name, value in gross.items()}
        if amounts:
            largest = max(amounts, key=lambda name: gross[name])
            amounts[largest] = currency.round(amounts[largest] + target - sum(amounts.values()))
        return amounts

    def _construction_sale_line_plan(self, summary, additional=False):
        """Las líneas que pide el resumen: ``[{'partida', 'name', 'price', 'kind',
        'current', 'line', 'version'}]``. Con un adicional, solo la diferencia."""
        self.ensure_one()
        amounts = self._construction_sale_partida_amounts(summary)
        typologies = summary.get('typologies', [])
        plan = []
        for item in summary.get('partidas', []):
            name = item['name']
            lines = self.order_line.filtered(lambda line: line.construction_partida == name)
            codes = ', '.join(t['code'] for t in typologies if t.get('partida') == name)
            description = '%s · %s · %s ambientes' % (name, codes, '%g' % (item.get('spaces') or 0))
            if additional:
                difference = self.currency_id.round(
                    amounts[name] - sum(lines.mapped('price_subtotal')))
                if not self.currency_id.is_zero(difference):
                    plan.append({'partida': name, 'price': difference, 'kind': 'new', 'current': 0.0,
                                 'name': 'Adicional %s · %s' % (summary.get('version'), name),
                                 'version': summary.get('version'), 'line': False})
                continue
            line = lines[:1]
            same = line and self.currency_id.compare_amounts(
                line.price_unit, amounts[name]) == 0 and line.product_uom_qty == 1
            plan.append({'partida': name, 'name': description, 'price': amounts[name],
                         'kind': 'same' if same else ('change' if line else 'new'),
                         'current': line.price_unit if line else 0.0,
                         'line': line.id if line else False, 'version': False})
        return plan

    def _construction_sale_is_additional(self):
        self.ensure_one()
        return self._construction_sale_sheet().construction_sale_phase == 'additional'

    def construction_sale_pass_preview(self, summary):
        """Vista previa: las líneas, y el total de la orden frente al de la hoja."""
        self.ensure_one()
        additional = self._construction_sale_is_additional()
        plan = self._construction_sale_line_plan(summary, additional)
        planned = {item['line'] for item in plan if item['line']}
        keep = self.order_line.filtered(lambda line: not line.display_type and (
            additional or line.id not in planned and not line.construction_partida))
        order_total = sum(keep.mapped('price_subtotal')) + sum(item['price'] for item in plan)
        warnings = []
        product = self.company_id.construction_sale_partida_product_id
        taxes = product.taxes_id.filtered(lambda tax: tax.company_id == self.company_id)
        rate = (summary.get('igv') or 0.0) * 100
        if taxes and abs(sum(taxes.mapped('amount')) - rate) > 0.001:
            warnings.append(self.env._(
                'El impuesto del producto de venta es %(tax)s %% y la hoja usa %(igv)s %%.',
                tax=sum(taxes.mapped('amount')), igv=rate))
        target = self.currency_id.round(summary.get('order_subtotal') or 0.0)
        if self.currency_id.compare_amounts(order_total, target):
            warnings.append(self.env._(
                'La orden sumaría %(order)s y la hoja dice %(sheet)s: revise sus otras líneas.',
                order=self.currency_id.format(order_total),
                sheet=self.currency_id.format(target)))
        return {'lines': [{key: item[key] for key in ('partida', 'name', 'price', 'kind', 'current')}
                          for item in plan],
                'order_total': order_total, 'sheet_total': target, 'warnings': warnings}

    def construction_sale_pass(self, summary):
        """Escribe las líneas de la cotización y guarda lo que lee el reporte."""
        self.ensure_one()
        product = self.company_id.construction_sale_partida_product_id
        if not product:
            raise UserError(self.env._(
                'Indique el «Producto de venta por partida» en Ajustes › Planificación de obra.'))
        document_sudo = self._construction_sale_sheet()
        additional = document_sudo.construction_sale_phase == 'additional'
        plan = self._construction_sale_line_plan(summary, additional)
        kept = self.env['sale.order.line']
        Line = self.env['sale.order.line']
        for item in plan:
            line = Line.browse(item['line'])
            values = {'name': item['name'], 'price_unit': item['price'], 'product_uom_qty': 1,
                      'construction_partida': item['partida'],
                      'construction_sale_version': item['version'] or False}
            if line:
                line.write(values)
                kept |= line
            else:
                kept |= Line.create(dict(values, order_id=self.id, product_id=product.id))
        if not additional:
            gone = self.order_line.filtered(
                lambda line: line.construction_partida and line not in kept)
            gone.unlink()
        self.construction_sale_summary = json.dumps(summary)
        # Paquete 1.18, M118-15, punto 1: el proyecto escrito en OBRA de la
        # hoja vuelve a la cotización.
        project_name = str((summary.get('obra') or {}).get('Proyecto') or '').strip()
        if project_name and project_name != (self.client_order_ref or ''):
            self.client_order_ref = project_name
        if additional:
            document_sudo.construction_sale_phase = 'awarded'
            self._construction_notify_planning(self.env._('Adicional adjudicado: traer la venta'))
        return True

    def _construction_notify_planning(self, summary):
        """M117-22, punto 1: la actividad para quien planifica, en la obra."""
        for order in self.filtered('construction_sale_summary'):
            project = self.env['project.project'].sudo().search([
                ('construction_sale_order_id', '=', order.id)], limit=1) or order.project_id.sudo()
            user = order.company_id.construction_planning_user_id or order.user_id
            if project and user:
                project.activity_schedule('mail.mail_activity_data_todo', user_id=user.id,
                                          summary=summary)

    def action_confirm(self):
        """M117-21, punto 10: avisa si la orden difiere de la hoja de venta vigente."""
        differences = []
        for order in self:
            summary = order._construction_sale_summary_data()
            if summary and order.currency_id.compare_amounts(
                    order.amount_untaxed, summary.get('order_subtotal') or 0.0):
                differences.append(self.env._(
                    '%(order)s: la orden suma %(amount)s y la hoja de venta %(sheet)s.',
                    order=order.name, amount=order.currency_id.format(order.amount_untaxed),
                    sheet=order.currency_id.format(summary.get('order_subtotal') or 0.0)))
        res = super().action_confirm()
        self._construction_notify_planning(self.env._(
            'Obra adjudicada: crear la hoja de planificación'))
        if differences:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'type': 'warning', 'sticky': True, 'message': '\n'.join(differences),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}}}
        return res

    def _find_mail_template(self):
        """Con hoja de venta, el correo lleva el PDF de la hoja (M117-21, punto 8)."""
        self.ensure_one()
        if self.construction_sale_summary and self.state in ('draft', 'sent'):
            template = self.env.ref(
                'al_construction_planner_spreadsheet_furniture.mail_template_sale_sheet_quotation',
                raise_if_not_found=False)
            if template:
                return template
        return super()._find_mail_template()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # La versión del adicional que creó la línea; la partida viene del puente de ventas.
    construction_sale_version = fields.Char(string='Versión del adicional', copy=False)


class ConstructionSaleSheetCopyWizard(models.TransientModel):
    _name = 'construction.sale.sheet.copy.wizard'
    _description = 'Hoja de venta de una cotización duplicada'

    order_id = fields.Many2one('sale.order', string='Cotización', required=True, ondelete='cascade')
    origin_id = fields.Many2one('sale.order', string='Cotización de origen', required=True,
                                ondelete='cascade')

    def action_copy(self):
        """Copia la hoja de la cotización de origen: al abrirla, OBRA toma los datos
        de esta cotización."""
        self.ensure_one()
        order = self.order_id
        document = self.origin_id._construction_sale_sheet().sudo(False).copy({
            'name': self.env._('Hoja de venta · %s', order.name),
            'folder_id': order._construction_spreadsheet_folder().id,
            'construction_sale_order_id': order.id, 'construction_sheet_kind': SALE_SHEET_KIND,
            'construction_sale_phase': order._construction_sale_phase_for_state(),
            'construction_sheet_rows': self.origin_id._construction_sale_sheet().construction_sheet_rows,
        })
        return document.action_open_spreadsheet()

    def action_new(self):
        self.ensure_one()
        return self.order_id.with_context(
            construction_new_sale_sheet=True).action_construction_open_spreadsheet()
