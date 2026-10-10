# -*- coding: utf-8 -*-
"""Valorización con el cliente (P-20, fase 10): las entregas semanales
confirmadas hasta un corte, valorizadas por partida; se envía al cliente,
recibe sus observaciones y su conformidad (fecha, nombre, cargo y documento)
y se factura lo confirmado desde la orden de venta del contrato. Lo no
confirmado queda por valorizar para la siguiente."""
from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round

VALUATION_STATES = [
    ('draft', 'Borrador'),
    ('sent', 'Enviada'),
    ('observed', 'Observada'),
    ('confirmed', 'Confirmada'),
    ('invoiced', 'Facturada'),
    ('cancel', 'Anulada'),
]
# Valorizaciones cuyo monto confirmado ya cuenta («% anterior» de la siguiente).
DONE_STATES = ('confirmed', 'invoiced')


class ConstructionValuation(models.Model):
    _name = 'construction.valuation'
    _description = 'Valorización de obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'cutoff_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', required=True, readonly=True, copy=False, default='/')
    sequence_number = fields.Integer(
        string='Nº en la obra', readonly=True, copy=False,
        help='Valorización 1, 2… de la obra.')
    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, index=True, check_company=True,
        domain=[('is_construction_site', '=', True)], tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True, store=True,
        compute='_compute_company_id', precompute=True, readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda', store=True)
    sale_order_id = fields.Many2one(
        'sale.order', string='Contrato', required=True, check_company=True, readonly=True)
    partner_id = fields.Many2one(related='sale_order_id.partner_id', string='Cliente', store=True)
    delivery_ids = fields.One2many(
        'construction.weekly.delivery', 'valuation_id', string='Entregas incluidas',
        readonly=True)
    delivery_count = fields.Integer(string='Nº de entregas', compute='_compute_delivery_count')
    cutoff_date = fields.Date(string='Corte', required=True, tracking=True)
    planned_submit_date = fields.Date(
        string='Presentación prevista', compute='_compute_planned_dates', store=True)
    planned_confirm_date = fields.Date(
        string='Confirmación prevista', compute='_compute_planned_dates', store=True)
    planned_invoice_date = fields.Date(
        string='Facturación prevista', compute='_compute_planned_dates', store=True)
    planned_collection_date = fields.Date(
        string='Cobro previsto', compute='_compute_planned_dates', store=True)
    submit_date = fields.Date(string='Enviada al cliente', readonly=True, copy=False,
                              tracking=True)
    state = fields.Selection(
        VALUATION_STATES, string='Estado', required=True, default='draft', tracking=True,
        copy=False)
    confirm_date = fields.Date(string='Fecha de conformidad', readonly=True, copy=False,
                               tracking=True)
    confirm_name = fields.Char(string='Confirmado por', readonly=True, copy=False,
                               tracking=True, help='Quién confirma por el cliente.')
    confirm_role = fields.Char(string='Cargo', readonly=True, copy=False, tracking=True)
    confirm_attachment_ids = fields.Many2many(
        'ir.attachment', 'construction_valuation_confirm_attachment_rel', 'valuation_id',
        'attachment_id', string='Documento de conformidad', readonly=True, copy=False)
    observation_ids = fields.One2many(
        'mail.message', 'res_id', string='Observaciones del cliente', readonly=True,
        domain=lambda self: [
            ('model', '=', self._name),
            ('subtype_id', '=', self.env.ref(
                'al_construction_planner.mt_valuation_observation').id)])
    line_ids = fields.One2many(
        'construction.valuation.line', 'valuation_id', string='Líneas por partida')
    guarantee_pct = fields.Float(
        string='Fondo de garantía (%)', readonly=True,
        help='El de la obra al preparar la valorización.')
    advance_amortization_pct = fields.Float(
        string='Amortización del adelanto (%)', readonly=True,
        help='La previsión de la obra al preparar la valorización; el cliente la decide en la '
             'conformidad.')
    amount_delivered = fields.Monetary(
        string='Entregado', compute='_compute_amounts', store=True)
    amount_confirmed = fields.Monetary(
        string='Confirmado', compute='_compute_amounts', store=True)
    amount_pending = fields.Monetary(
        string='Por valorizar', compute='_compute_amounts', store=True,
        help='Entregado y no confirmado: entra en la siguiente valorización.')
    amount_amortization = fields.Monetary(
        string='Amortización del adelanto', compute='_compute_amounts', store=True)
    amount_guarantee = fields.Monetary(
        string='Fondo de garantía', compute='_compute_amounts', store=True)
    amount_net = fields.Monetary(string='Neto a cobrar', compute='_compute_amounts', store=True)
    invoice_id = fields.Many2one(
        'account.move', string='Factura', readonly=True, copy=False, check_company=True)
    invoice_state = fields.Selection(related='invoice_id.state', string='Estado de la factura')
    invoice_payment_state = fields.Selection(
        related='invoice_id.payment_state', string='Estado del cobro')

    _number_unique = models.UniqueIndex(
        '(project_id, sequence_number) WHERE state != \'cancel\'',
        'La obra ya tiene una valorización con ese número.')

    @api.depends('project_id')
    def _compute_company_id(self):
        for valuation in self:
            valuation.company_id = valuation.project_id.company_id or valuation.company_id \
                or self.env.company

    def _compute_delivery_count(self):
        for valuation in self:
            valuation.delivery_count = len(valuation.delivery_ids)

    @api.depends('cutoff_date', 'project_id.construction_valuation_submit_days',
                 'project_id.construction_client_confirm_days',
                 'project_id.construction_invoice_days',
                 'project_id.construction_collection_days')
    def _compute_planned_dates(self):
        for valuation in self:
            if not valuation.cutoff_date or not valuation.project_id:
                valuation.planned_submit_date = valuation.planned_confirm_date = False
                valuation.planned_invoice_date = valuation.planned_collection_date = False
                continue
            dates = valuation.project_id._construction_income_dates(valuation.cutoff_date)
            valuation.planned_submit_date = dates['submit']
            valuation.planned_confirm_date = dates['confirm']
            valuation.planned_invoice_date = dates['invoice']
            valuation.planned_collection_date = dates['collection']

    @api.depends('line_ids.amount_delivered', 'line_ids.amount_confirmed',
                 'line_ids.amount_amortization', 'line_ids.amount_guarantee')
    def _compute_amounts(self):
        for valuation in self:
            lines = valuation.line_ids
            valuation.amount_delivered = sum(lines.mapped('amount_delivered'))
            valuation.amount_confirmed = sum(lines.mapped('amount_confirmed'))
            valuation.amount_pending = sum(lines.mapped('amount_pending'))
            valuation.amount_amortization = sum(lines.mapped('amount_amortization'))
            valuation.amount_guarantee = sum(lines.mapped('amount_guarantee'))
            valuation.amount_net = sum(lines.mapped('amount_net'))

    @api.depends('name', 'sequence_number')
    def _compute_display_name(self):
        for valuation in self:
            if valuation.name == '/':
                valuation.display_name = self.env._('Valorización nueva')
            else:
                valuation.display_name = self.env._(
                    '%(name)s · Valorización %(number)s', name=valuation.name,
                    number=valuation.sequence_number)

    @api.constrains('state', 'confirm_date', 'confirm_name', 'confirm_role',
                    'confirm_attachment_ids')
    def _check_confirmation(self):
        """Sin fecha, nombre, cargo y documento del cliente no pasa a
        Confirmada (especificación, P-20)."""
        for valuation in self:
            if valuation.state in DONE_STATES and not (
                    valuation.confirm_date and valuation.confirm_name
                    and valuation.confirm_role and valuation.confirm_attachment_ids):
                raise ValidationError(self.env._(
                    'La valorización %s necesita la fecha, el nombre, el cargo y el documento '
                    'de conformidad del cliente para quedar confirmada.', valuation.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'construction.valuation') or '/'
            if vals.get('project_id') and not vals.get('sequence_number'):
                last = self.search([('project_id', '=', vals['project_id']),
                                    ('state', '!=', 'cancel')],
                                   order='sequence_number desc', limit=1)
                vals['sequence_number'] = last.sequence_number + 1
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if self.filtered(lambda v: v.state not in ('draft', 'cancel')):
            raise UserError(self.env._('Solo se borran valorizaciones en borrador o anuladas.'))

    def unlink(self):
        # sudo: ídem al borrar una valorización en borrador.
        self.delivery_ids.sudo().write({'valuation_id': False})
        return super().unlink()

    # ------------------------------------------------------------------
    # Preparación (W-13)
    # ------------------------------------------------------------------
    @api.model
    def _get_pending_deliveries(self, project, cutoff):
        """Entregas confirmadas de la obra hasta el corte que no están en una
        valorización vigente."""
        return self.env['construction.weekly.delivery'].search([
            ('project_id', '=', project.id), ('state', '=', 'confirmed'),
            ('period_end', '<=', cutoff),
            '|', ('valuation_id', '=', False), ('valuation_id.state', '=', 'cancel'),
        ], order='period_start')

    @api.model
    def _get_line_values(self, project, deliveries, cutoff, exclude=None):
        """Valores de las líneas por partida: el avance entregado es el de la
        última entrega incluida y el «% anterior», lo confirmado antes. Lo
        entregado del periodo es precio × avance entregado − confirmado antes,
        de modo que lo no confirmado vuelve en la siguiente."""
        previous = self.env['construction.valuation.line'].search([
            ('valuation_id.project_id', '=', project.id),
            ('valuation_id.state', 'in', DONE_STATES),
            ('valuation_id', 'not in', (exclude or self).ids)])
        delivered = {}
        for line in deliveries.sorted('period_start').line_ids:
            delivered[line.sale_line_id] = line.progress_end
        currency = project.company_id.currency_id or self.env.company.currency_id
        values = []
        for sale_line in project._construction_partida_lines():
            if sale_line not in delivered:
                continue
            price = sale_line._construction_price(cutoff)
            before = previous.filtered(lambda l, s=sale_line: l.sale_line_id == s)
            confirmed_before = sum(before.mapped('amount_confirmed'))
            amount = currency.round(price * delivered[sale_line] - confirmed_before)
            values.append({
                'sale_line_id': sale_line.id,
                'price': price,
                'progress_delivered': delivered[sale_line],
                'confirmed_before': confirmed_before,
                'amortization_before': sum(before.mapped('amount_amortization')),
                'amount_delivered': amount,
                'amount_confirmed': amount,
            })
        return values

    @api.model
    def _create_from_deliveries(self, project, cutoff, deliveries):
        if not deliveries:
            raise UserError(self.env._(
                'La obra %s no tiene entregas semanales confirmadas sin valorizar hasta el '
                'corte.', project.display_name))
        valuation = self.create({
            'project_id': project.id,
            'sale_order_id': project.construction_sale_order_id.id,
            'cutoff_date': cutoff,
            'guarantee_pct': project.construction_guarantee_pct,
            'advance_amortization_pct': project.construction_advance_amortization_pct,
            'line_ids': [Command.create(vals) for vals in self._get_line_values(
                project, deliveries, cutoff)],
        })
        # sudo: incluir la entrega en la valorización es efecto del sistema;
        # Proyectos prepara la valorización sin poder editar las entregas.
        deliveries_sudo = deliveries.sudo()
        deliveries_sudo.write({'valuation_id': valuation.id})
        return valuation

    @api.model
    def _prepare_valuations(self, today=None, projects=None):
        """Corte de valorización según la obra (F-11): con entregas
        confirmadas sin valorizar hasta el último corte y sin otra
        valorización en borrador, la prepara en borrador."""
        today = today or fields.Date.context_today(self)
        if projects is None:
            projects = self.env['project.project'].search([
                ('is_construction_site', '=', True), ('construction_sale_order_id', '!=', False)])
        created = self.browse()
        for project in projects:
            cutoffs = [c for c in project._construction_valuation_cutoffs() if c < today]
            if not cutoffs or self.search_count([('project_id', '=', project.id),
                                                 ('state', '=', 'draft')], limit=1):
                continue
            deliveries = self._get_pending_deliveries(project, cutoffs[-1])
            if deliveries:
                created |= self._create_from_deliveries(project, cutoffs[-1], deliveries)
        return created

    def action_refresh(self):
        """Vuelve a tomar las entregas confirmadas hasta el corte."""
        for valuation in self:
            if valuation.state != 'draft':
                raise UserError(self.env._('Solo se actualizan valorizaciones en borrador.'))
            deliveries = valuation.delivery_ids | self._get_pending_deliveries(
                valuation.project_id, valuation.cutoff_date)
            deliveries = deliveries.filtered(lambda d: d.state == 'confirmed')
            # sudo: ídem, el enlace de las entregas lo mantiene el sistema.
            valuation.delivery_ids.sudo().write({'valuation_id': False})
            deliveries.sudo().write({'valuation_id': valuation.id})
            valuation.line_ids = [Command.clear()] + [
                Command.create(vals) for vals in self._get_line_values(
                    valuation.project_id, deliveries, valuation.cutoff_date, exclude=valuation)]

    # ------------------------------------------------------------------
    # Estados
    # ------------------------------------------------------------------
    def _check_state(self, states):
        labels = dict(VALUATION_STATES)
        for valuation in self:
            if valuation.state not in states:
                raise UserError(self.env._(
                    'La valorización %(name)s está %(state)s: no admite esta acción.',
                    name=valuation.display_name, state=labels[valuation.state].lower()))

    def _check_group(self, group, label):
        if not self.env.user.has_group(group):
            raise UserError(label)

    def action_send(self):
        """Enviar al cliente (o reenviar con la observación levantada): fecha
        de envío y el PDF de la valorización en el historial."""
        self._check_state(('draft', 'observed'))
        for valuation in self:
            if not valuation.delivery_ids:
                raise UserError(self.env._(
                    'La valorización %s no tiene entregas confirmadas.', valuation.display_name))
            resend = valuation.state == 'observed'
            valuation.write({'state': 'sent', 'submit_date': fields.Date.context_today(self)})
            # sudo: el PDF se adjunta al historial aunque quien envía no
            # administre los reportes.
            report_sudo = self.env.ref(
                'al_construction_planner.action_report_construction_valuation').sudo()
            content, _type = report_sudo._render_qweb_pdf(report_sudo.id, valuation.ids)
            valuation.message_post(
                body=self.env._('Observación levantada y valorización reenviada al cliente.')
                if resend else self.env._('Valorización enviada al cliente.'),
                attachments=[('%s.pdf' % valuation.name.replace('/', '-'), content)])

    def action_open_observe_wizard(self):
        self._check_state(('sent',))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Observación del cliente'),
            'res_model': 'construction.reason.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_model': self._name, 'active_ids': self.ids,
                        'construction_reason_action': 'observe'},
        }

    def _action_observe(self, reason):
        """El cliente observa: queda en el historial con fecha y autor, con el
        subtipo «Observación del cliente»."""
        self._check_state(('sent',))
        for valuation in self:
            valuation.state = 'observed'
            valuation.message_post(
                body=reason, message_type='comment',
                subtype_xmlid='al_construction_planner.mt_valuation_observation')

    def action_open_confirm_wizard(self):
        """Confirmar valorización (W-14)."""
        self.ensure_one()
        self._check_state(('sent',))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Confirmar valorización'),
            'res_model': 'construction.valuation.confirm.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_valuation_id': self.id},
        }

    def _action_confirm(self, values, confirmed):
        """Conformidad del cliente: ``values`` con fecha, nombre, cargo y
        adjuntos; ``confirmed`` {línea: monto}. Las entregas pasan a
        Valorizada."""
        self.ensure_one()
        self._check_state(('sent',))
        for line, amount in confirmed.items():
            line.amount_confirmed = amount
        self.write(dict(values, state='confirmed'))
        # sudo: la conformidad la registra Proyectos o Finanzas, que no
        # editan entregas; el paso a Valorizada es efecto del sistema.
        self.delivery_ids.sudo().write({'state': 'valued'})

    def action_cancel(self):
        """Anular (Jefatura): sin factura; las entregas vuelven a Confirmada."""
        self._check_group('al_construction_planner.group_planner_manager', self.env._(
            'Anula la valorización la Jefatura de Proyectos (grupo Administrador).'))
        self._check_state(('draft', 'sent', 'observed'))
        if self.filtered(lambda v: v.invoice_id and v.invoice_id.state != 'cancel'):
            raise UserError(self.env._('Una valorización con factura no se anula.'))
        # sudo: las entregas vuelven a Confirmada como efecto de la anulación.
        self.delivery_ids.sudo().write({'valuation_id': False, 'state': 'confirmed'})
        self.write({'state': 'cancel'})

    # ------------------------------------------------------------------
    # Factura
    # ------------------------------------------------------------------
    def _construction_check_invoice_balance(self):
        """La factura de la valorización no puede superar lo confirmado por
        el cliente en ninguna partida (gancho de la fase 7, §6.4)."""
        for valuation in self:
            company = valuation.company_id
            moves = self.env['account.move'].search([
                ('construction_valuation_id', '=', valuation.id), ('state', '!=', 'cancel')])
            errors = []
            for line in valuation.line_ids:
                invoiced = 0.0
                for move_line in moves.invoice_line_ids.filtered(
                        lambda ml, s=line.sale_line_id: s in ml.sale_line_ids):
                    move = move_line.move_id
                    sign = -1 if move.move_type == 'out_refund' else 1
                    invoiced += sign * move.currency_id._convert(
                        move_line.price_subtotal, company.currency_id, company,
                        move.invoice_date or move.date or fields.Date.context_today(self))
                if valuation.currency_id.compare_amounts(invoiced, line.amount_confirmed) > 0:
                    errors.append(self.env._(
                        '%(partida)s: facturado %(invoiced)s, confirmado %(confirmed)s',
                        partida=line.sale_line_id.name.splitlines()[0],
                        invoiced=round(invoiced, 2), confirmed=round(line.amount_confirmed, 2)))
            if errors:
                raise UserError(self.env._(
                    'La factura de %(valuation)s supera lo confirmado por el cliente:\n%(lines)s',
                    valuation=valuation.display_name, lines='\n'.join(errors)))

    def _construction_sync_invoiced(self):
        """Confirmada ↔ Facturada según la factura publicada."""
        for valuation in self:
            posted = valuation.invoice_id.state == 'posted'
            if valuation.state == 'confirmed' and posted:
                valuation.state = 'invoiced'
            elif valuation.state == 'invoiced' and not posted:
                valuation.state = 'confirmed'

    def _prepare_invoice_lines(self, invoice_date):
        """Una línea por partida con la cantidad entregada de la OV al %
        acumulado confirmado (OV por partida con cantidad 1, D23) menos lo ya
        facturado, por el monto confirmado. Con la precisión de la unidad (2
        decimales en la base del cliente) la cantidad se redondea y, si
        cantidad × precio no da lo confirmado, el precio unitario se ajusta
        hacia abajo para no superarlo."""
        self.ensure_one()
        order = self.sale_order_id
        company = self.company_id
        vals_list = []
        delivered = {}
        for line in self.line_ids.filtered(lambda l: l.amount_confirmed > 0):
            sale_line = line.sale_line_id
            uom = sale_line.product_uom_id
            cumulative = uom.round(sale_line.product_uom_qty * line.progress_confirmed)
            quantity = uom.round(cumulative - sale_line.qty_invoiced)
            if quantity <= 0:
                raise UserError(self.env._(
                    '%(partida)s: el %% acumulado confirmado (%(pct)s %%) no alcanza una unidad '
                    'facturable con la precisión de la cantidad. Suba la precisión de «Product '
                    'Unit» o facture junto con la siguiente valorización.',
                    partida=sale_line.name.splitlines()[0],
                    pct=round(line.progress_confirmed * 100, 2)))
            amount = company.currency_id._convert(
                line.amount_confirmed, order.currency_id, company, invoice_date)
            vals = sale_line._prepare_invoice_line(quantity=quantity)
            price = sale_line.price_unit * (1 - (sale_line.discount or 0.0) / 100.0)
            if order.currency_id.compare_amounts(price * quantity, amount):
                digits = self.env['decimal.precision'].precision_get('Product Price')
                vals.update({
                    'price_unit': float_round(amount / quantity, precision_digits=digits,
                                              rounding_method='DOWN'),
                    'discount': 0.0,
                })
            vals['name'] = self.env._(
                '%(name)s\nValorización %(number)s: %(period)s %% del periodo, %(cumulative)s %% '
                'acumulado', name=sale_line.name, number=self.sequence_number,
                period=round(line.progress_period * 100, 2),
                cumulative=round(line.progress_confirmed * 100, 2))
            vals_list.append(vals)
            delivered[sale_line] = cumulative
        for field, account, label in (
                ('amount_guarantee', company.construction_guarantee_account_id,
                 self.env._('Fondo de garantía retenido (%s %%)', round(self.guarantee_pct, 2))),
                ('amount_amortization', company.construction_advance_account_id,
                 self.env._('Amortización del adelanto'))):
            if account and not self.currency_id.is_zero(self[field]):
                vals_list.append({
                    'display_type': 'product',
                    'name': '%s · %s' % (label, self.name),
                    'account_id': account.id,
                    'quantity': 1.0,
                    'price_unit': -company.currency_id._convert(
                        self[field], order.currency_id, company, invoice_date),
                    'tax_ids': [Command.clear()],
                })
        return vals_list, delivered

    def action_create_invoice(self):
        """Factura lo confirmado desde la OV del contrato (Administración y
        Finanzas): la factura guarda la valorización y la línea de la OV
        queda con la cantidad entregada al % acumulado confirmado."""
        self._check_group('al_construction_planner.group_planner_revenue', self.env._(
            'Factura la valorización Administración y Finanzas (grupo Planificación de obra: '
            'ingresos).'))
        self.ensure_one()
        self._check_state(('confirmed',))
        if self.invoice_id and self.invoice_id.state != 'cancel':
            raise UserError(self.env._('La valorización %s ya tiene factura.', self.display_name))
        self._construction_check_invoice_balance()
        order = self.sale_order_id.with_company(self.company_id)
        today = fields.Date.context_today(self)
        lines, delivered = self._prepare_invoice_lines(today)
        if not lines:
            raise UserError(self.env._('No hay montos confirmados que facturar.'))
        vals = order._prepare_invoice()
        vals.update({
            'construction_valuation_id': self.id,
            'ref': self.name,
            'invoice_origin': '%s, %s' % (order.name, self.name),
            'invoice_line_ids': [Command.create(line) for line in lines],
        })
        invoice = self.env['account.move'].with_company(self.company_id).with_context(
            default_move_type='out_invoice').create(vals)
        for sale_line, qty in delivered.items():
            if sale_line.qty_delivered_method == 'manual':
                sale_line.qty_delivered = qty
        self.invoice_id = invoice
        self._construction_check_invoice_balance()
        self.message_post(body=Markup(self.env._('Factura creada: %s')) % invoice._get_html_link())
        return self.action_view_invoice()

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def action_view_deliveries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Entregas de %s', self.display_name),
            'res_model': 'construction.weekly.delivery',
            'view_mode': 'list,form',
            'domain': [('valuation_id', '=', self.id)],
            'context': {'create': False},
        }


class ConstructionValuationLine(models.Model):
    _name = 'construction.valuation.line'
    _description = 'Línea de la valorización (partida)'
    _order = 'valuation_id, sale_line_id'
    _check_company_auto = True

    valuation_id = fields.Many2one(
        'construction.valuation', string='Valorización', required=True, ondelete='cascade',
        index=True, check_company=True)
    company_id = fields.Many2one(
        related='valuation_id.company_id', string='Compañía', store=True, index=True)
    currency_id = fields.Many2one(related='valuation_id.currency_id', string='Moneda')
    state = fields.Selection(related='valuation_id.state', string='Estado')
    sale_line_id = fields.Many2one(
        'sale.order.line', string='Partida', required=True, index=True, check_company=True)
    price = fields.Monetary(string='Precio')
    progress_delivered = fields.Float(
        string='Avance entregado', help='Avance al cierre de la última entrega incluida.')
    confirmed_before = fields.Monetary(
        string='Confirmado antes', help='Lo confirmado de la partida en las valorizaciones '
                                        'anteriores.')
    amortization_before = fields.Monetary(string='Adelanto amortizado antes')
    progress_prev = fields.Float(
        string='% anterior', compute='_compute_progress', store=True,
        help='Confirmado antes ÷ precio.')
    progress_period = fields.Float(
        string='% periodo', compute='_compute_progress', store=True,
        help='Entregado ÷ precio.')
    progress_cumulative = fields.Float(
        string='% acumulado', compute='_compute_progress', store=True)
    progress_confirmed = fields.Float(
        string='% acumulado confirmado', compute='_compute_progress', store=True,
        help='(Confirmado antes + confirmado) ÷ precio: la cantidad entregada de la OV.')
    amount_delivered = fields.Monetary(string='Entregado')
    amount_confirmed = fields.Monetary(string='Confirmado')
    amount_pending = fields.Monetary(
        string='Por valorizar', compute='_compute_amounts', store=True)
    amount_amortization = fields.Monetary(
        string='Amortización del adelanto', compute='_compute_amounts', store=True)
    amount_guarantee = fields.Monetary(
        string='Fondo de garantía', compute='_compute_amounts', store=True)
    amount_net = fields.Monetary(string='Neto', compute='_compute_amounts', store=True)

    @api.depends('price', 'confirmed_before', 'amount_delivered', 'amount_confirmed')
    def _compute_progress(self):
        for line in self:
            price = line.price
            if not price:
                line.progress_prev = line.progress_period = 0.0
                line.progress_cumulative = line.progress_confirmed = 0.0
                continue
            line.progress_prev = line.confirmed_before / price
            line.progress_period = line.amount_delivered / price
            line.progress_cumulative = (line.confirmed_before + line.amount_delivered) / price
            line.progress_confirmed = (line.confirmed_before + line.amount_confirmed) / price

    @api.depends('amount_delivered', 'amount_confirmed', 'price', 'amortization_before',
                 'valuation_id.guarantee_pct', 'valuation_id.advance_amortization_pct',
                 'valuation_id.project_id.construction_advance_pct')
    def _compute_amounts(self):
        for line in self:
            currency = line.currency_id
            valuation = line.valuation_id
            confirmed = line.amount_confirmed
            line.amount_pending = line.amount_delivered - confirmed
            guarantee = confirmed * valuation.guarantee_pct / 100.0
            advance = line.price * valuation.project_id.construction_advance_pct / 100.0
            amortization = min(confirmed * valuation.advance_amortization_pct / 100.0,
                               max(advance - line.amortization_before, 0.0))
            if currency:
                guarantee, amortization = currency.round(guarantee), currency.round(amortization)
            line.amount_guarantee = guarantee
            line.amount_amortization = amortization
            line.amount_net = confirmed - guarantee - amortization

    @api.constrains('amount_confirmed', 'amount_delivered')
    def _check_confirmed(self):
        for line in self:
            low, high = sorted((0.0, line.amount_delivered))
            currency = line.currency_id
            if currency.compare_amounts(line.amount_confirmed, low) < 0 or \
                    currency.compare_amounts(line.amount_confirmed, high) > 0:
                raise ValidationError(self.env._(
                    '%s: lo confirmado va de cero a lo entregado.',
                    line.sale_line_id.name.splitlines()[0]))
