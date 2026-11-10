# -*- coding: utf-8 -*-
"""«Aplicar costo» por grupo (paquete 1.18, M118-04, punto 3).

Una fila por producto de las líneas elegidas (la selección de la lista, las
líneas sin costo, una categoría o una etapa) con su costo de referencia, el
costo que sugiere la base, la variación frente a la referencia y las compras
en 6 meses. La persona decide el costo de cada fila; el asistente de un solo
producto (W-12) sigue igual."""
from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, formatLang

from .plan_price_wizard import BASES

SCOPES = [
    ('unpriced', 'Líneas sin costo'),
    ('selection', 'Líneas seleccionadas'),
    ('category', 'Una categoría'),
    ('stage', 'Una etapa'),
]


class ConstructionPlanPriceGroupWizard(models.TransientModel):
    _name = 'construction.plan.price.group.wizard'
    _description = 'Aplicar costo por grupo de productos'
    _check_company_auto = True

    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', required=True, readonly=True,
        check_company=True)
    company_id = fields.Many2one(related='plan_id.company_id', string='Compañía')
    currency_id = fields.Many2one(related='plan_id.currency_id', string='Moneda')
    scope = fields.Selection(SCOPES, string='Líneas', required=True, default='unpriced')
    selected_line_ids = fields.Many2many(
        'construction.resource.plan.line', 'construction_plan_price_group_selected_rel',
        'wizard_id', 'line_id', string='Selección', check_company=True)
    categ_id = fields.Many2one('product.category', string='Categoría')
    stage_id = fields.Many2one('construction.stage', string='Etapa')
    basis = fields.Selection(BASES, string='Base', required=True, default='weighted_6m')
    basis_date = fields.Date(
        string='Fecha de la base', required=True, default=fields.Date.context_today,
        help='Las compras confirmadas hasta esta fecha forman la base.')
    review_pct = fields.Float(
        string='Variación que pide revisión (%)', compute='_compute_review_pct',
        help='Parámetro de la compañía: las filas que se mueven más quedan sin marcar.')
    row_ids = fields.One2many(
        'construction.plan.price.group.line', 'wizard_id', string='Productos',
        compute='_compute_row_ids', store=True, readonly=False)
    product_count = fields.Integer(string='Productos', compute='_compute_counts')
    review_count = fields.Integer(string='Para revisar', compute='_compute_counts')

    @api.depends('company_id')
    def _compute_review_pct(self):
        for wizard in self:
            company = wizard.company_id or self.env.company
            wizard.review_pct = company.construction_price_review_pct

    def _scope_lines(self):
        """Líneas del plan del alcance elegido (solo con producto)."""
        self.ensure_one()
        lines = self.plan_id.line_ids.filtered(
            lambda l: l.product_id and l.line_state != 'cancel')
        if self.scope == 'unpriced':
            lines = lines.filtered(lambda l: l.qty_planned and not l.price_unit_planned)
        elif self.scope == 'selection':
            lines = lines & self.selected_line_ids
        elif self.scope == 'category':
            lines = lines.filtered(
                lambda l: self.categ_id and l.product_id.categ_id == self.categ_id)
        elif self.scope == 'stage':
            lines = lines.filtered(lambda l: self.stage_id and l.stage == self.stage_id.code)
        return lines

    @api.depends('plan_id', 'scope', 'selected_line_ids', 'categ_id', 'stage_id', 'basis',
                 'basis_date')
    def _compute_row_ids(self):
        Report = self.env['construction.purchase.price.report']
        for wizard in self:
            commands = [Command.clear()]
            if wizard.plan_id and wizard.basis_date:
                lines = wizard._scope_lines()
                company = wizard.plan_id.company_id or self.env.company
                week_start = wizard.plan_id.project_id.construction_week_start_day or '3'
                for product, product_lines in lines.grouped('product_id').items():
                    prices = Report._get_basis_prices(product, company, wizard.basis_date,
                                                      week_start)
                    suggested = prices.get(wizard.basis) if wizard.basis != 'manual' else 0.0
                    reference = product_lines[:1].price_reference or \
                        product.with_company(company).standard_price
                    variation = (suggested - reference) / reference * 100.0 \
                        if suggested and reference else 0.0
                    review = bool(suggested) and abs(variation) > wizard.review_pct
                    commands.append(Command.create({
                        'product_id': product.id,
                        'uom_id': product_lines[:1].product_uom_id.id,
                        'line_ids': [Command.set(product_lines.ids)],
                        'qty': sum(product_lines.mapped('qty_planned')),
                        'price_reference': reference,
                        'price_suggested': suggested or 0.0,
                        'variation_pct': variation,
                        'purchase_count': prices.get('count_6m') or 0,
                        'price_unit': suggested or 0.0,
                        'needs_review': review,
                        # Punto 4: las filas que se movieron más que el umbral
                        # y las que no tienen costo quedan sin marcar.
                        'apply': bool(suggested) and not review,
                    }))
            wizard.row_ids = commands

    @api.depends('row_ids.needs_review')
    def _compute_counts(self):
        for wizard in self:
            wizard.product_count = len(wizard.row_ids)
            wizard.review_count = len(wizard.row_ids.filtered('needs_review'))

    def _basis_text(self, price):
        self.ensure_one()
        return self.env._('%(basis)s al %(date)s: %(price)s', basis=dict(BASES)[self.basis],
                          date=format_date(self.env, self.basis_date),
                          price=formatLang(self.env, price, digits=2))

    def action_apply(self):
        self.ensure_one()
        self.plan_id._check_draft()
        rows = self.row_ids.filtered('apply')
        if not rows:
            raise UserError(self.env._('Marque las filas cuyo costo se aplica.'))
        summary = []
        for row in rows:
            price = row.price_unit or (row.price_reference if row.use_reference else 0.0)
            if self.currency_id.compare_amounts(price, 0) <= 0:
                raise UserError(self.env._(
                    '%s: escriba el costo o marque «Usar la referencia».',
                    row.product_id.display_name))
            # Las líneas de la fila o, si el navegador no las mandó, las del
            # producto en el alcance (como CR-34: no se confía en la vista).
            lines = (row.line_ids or self._scope_lines().filtered(
                lambda l, p=row.product_id: l.product_id == p)).filtered(
                lambda l: l.plan_id == self.plan_id)
            before = sum(lines.mapped('amount_planned'))
            basis = self._basis_text(price) if not row.use_reference or row.price_unit else \
                self.env._('Costo de referencia del %(date)s: %(price)s',
                           date=format_date(self.env, lines[:1].price_reference_date
                                            or self.basis_date),
                           price=formatLang(self.env, price, digits=2))
            lines.write({'price_unit_planned': price, 'price_basis': basis,
                         'price_basis_date': self.basis_date})
            summary.append((row.product_id, len(lines), before, sum(lines.mapped('amount_planned'))))
        # Un solo mensaje en el plan con los productos y el monto antes y
        # después.
        total_before = sum(item[2] for item in summary)
        total_after = sum(item[3] for item in summary)
        items = Markup('').join(Markup('<li>%s</li>') % self.env._(
            '%(product)s: %(count)s líneas, %(before)s → %(after)s', product=product.display_name,
            count=count, before=formatLang(self.env, before, currency_obj=self.currency_id),
            after=formatLang(self.env, after, currency_obj=self.currency_id))
            for product, count, before, after in summary)
        self.plan_id.message_post(body=Markup('<p>%s</p><ul>%s</ul>') % (
            self.env._('Costo aplicado a %(count)s productos (%(basis)s): %(before)s → %(after)s.',
                       count=len(summary), basis=dict(BASES)[self.basis],
                       before=formatLang(self.env, total_before, currency_obj=self.currency_id),
                       after=formatLang(self.env, total_after, currency_obj=self.currency_id)),
            items))
        return {'type': 'ir.actions.act_window_close'}


class ConstructionPlanPriceGroupLine(models.TransientModel):
    _name = 'construction.plan.price.group.line'
    _description = 'Producto de «Aplicar costo» por grupo'
    _order = 'needs_review desc, id'

    wizard_id = fields.Many2one('construction.plan.price.group.wizard', required=True,
                                ondelete='cascade')
    currency_id = fields.Many2one(related='wizard_id.currency_id')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    default_code = fields.Char(related='product_id.default_code', string='Código')
    uom_id = fields.Many2one('uom.uom', string='Unidad')
    line_ids = fields.Many2many('construction.resource.plan.line',
                                'construction_plan_price_group_line_rel', 'row_id', 'line_id',
                                string='Líneas del plan')
    qty = fields.Float(string='Cantidad del plan', digits='Product Unit')
    price_reference = fields.Float(string='Costo de referencia', digits='Product Price')
    price_suggested = fields.Float(string='Costo de la base', digits='Product Price')
    variation_pct = fields.Float(string='Variación (%)', digits=(16, 1))
    purchase_count = fields.Integer(string='Compras en 6 meses')
    price_unit = fields.Float(string='Costo que se aplica', digits='Product Price')
    use_reference = fields.Boolean(string='Usar la referencia')
    needs_review = fields.Boolean(string='Revisar')
    apply = fields.Boolean(string='Aplicar')

    @api.onchange('use_reference')
    def _onchange_use_reference(self):
        for row in self:
            if row.use_reference and not row.price_unit:
                row.price_unit = row.price_reference
                row.apply = True

    @api.onchange('price_unit')
    def _onchange_price_unit(self):
        for row in self.filtered('price_unit'):
            row.apply = True

    def action_open_purchase_prices(self):
        """«Precios de compra del producto» de la fila, con sus líneas."""
        self.ensure_one()
        return self.env['construction.purchase.price.analysis']._action_open(
            self.product_id, plan=self.wizard_id.plan_id, lines=self.line_ids)
