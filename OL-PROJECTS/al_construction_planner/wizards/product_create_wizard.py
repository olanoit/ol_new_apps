# -*- coding: utf-8 -*-
"""Crear producto desde el plan (W-11, P-17).

El código sigue la regla del maestro: los 4 dígitos de la familia más un
correlativo de 3, asignado al guardar (con la familia bloqueada) para que dos
planificadores no tomen el mismo. Antes de crear muestra los productos de
nombre parecido. El producto queda activo, marcado con el plan que lo creó y
asignado a la línea; Logística recibe una actividad para completarlo."""
import difflib
import re
import unicodedata

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

#: Coincidencia mínima para listar un producto como parecido.
SIMILARITY_MIN = 0.4
SIMILARITY_LIMIT = 8
CODE_DIGITS = 3


def normalize(text):
    """Minúsculas, sin tildes ni signos: base de la comparación de nombres."""
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(char for char in text if not unicodedata.combining(char)).lower()
    return ' '.join(re.findall(r'[a-z0-9]+', text))


def similarity(name_a, name_b):
    """Coincidencia entre dos nombres (0 a 1): la mayor entre la de las
    cadenas y la de sus palabras ordenadas, para que el orden de las palabras
    no esconda un duplicado."""
    a, b = normalize(name_a), normalize(name_b)
    if not a or not b:
        return 0.0
    plain = difflib.SequenceMatcher(None, a, b).ratio()
    tokens = difflib.SequenceMatcher(
        None, ' '.join(sorted(a.split())), ' '.join(sorted(b.split()))).ratio()
    return max(plain, tokens)


class ConstructionProductCreateWizard(models.TransientModel):
    _name = 'construction.product.create.wizard'
    _description = 'Crear producto desde el plan'
    _check_company_auto = True

    plan_line_id = fields.Many2one(
        'construction.resource.plan.line', string='Línea del plan', check_company=True)
    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', required=True, check_company=True,
        compute='_compute_plan_id', store=True, readonly=False, precompute=True,
        help='Plan que crea el producto: queda marcado en el producto.')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    categ_id = fields.Many2one(
        'product.category', string='Familia', required=True,
        domain="[('construction_family_code', '!=', False)]")
    name = fields.Char(string='Nombre', required=True)
    code_proposed = fields.Char(
        string='Código propuesto', compute='_compute_code_proposed',
        help='Familia más correlativo. El número definitivo se asigna al crear, para que dos '
             'planificadores no tomen el mismo.')
    uom_id = fields.Many2one(
        'uom.uom', string='Unidad de consumo', required=True,
        compute='_compute_uom_id', store=True, readonly=False, precompute=True,
        help='Unidad del producto: en la que se planifica y se consume.')
    purchase_uom_id = fields.Many2one(
        'uom.uom', string='Unidad de compra',
        compute='_compute_purchase_uom_id', store=True, readonly=False, precompute=True,
        help='Se guarda en el proveedor del producto; la compra masiva redondea en esta '
             'unidad.')
    partner_id = fields.Many2one(
        'res.partner', string='Proveedor', check_company=True,
        help='Proveedor habitual. Sin proveedor, Logística lo completa.')
    price_reference = fields.Monetary(
        string='Precio de referencia', currency_field='currency_id',
        help='Precio del proveedor en la unidad de compra. No es el costo del plan: ese se '
             'fija con «Aplicar costo» (W-12).')
    similar_ids = fields.One2many(
        'construction.product.create.wizard.similar', 'wizard_id', string='Productos parecidos',
        compute='_compute_similar_ids', store=True, readonly=False)
    similar_count = fields.Integer(string='Parecidos', compute='_compute_similar_count')

    @api.depends('plan_line_id')
    def _compute_plan_id(self):
        for wizard in self:
            if wizard.plan_line_id:
                wizard.plan_id = wizard.plan_line_id.plan_id

    @api.depends('plan_line_id')
    def _compute_uom_id(self):
        for wizard in self:
            wizard.uom_id = wizard.plan_line_id.product_uom_id or wizard.uom_id or \
                self.env.ref('uom.product_uom_unit', raise_if_not_found=False)

    @api.depends('uom_id')
    def _compute_purchase_uom_id(self):
        for wizard in self:
            wizard.purchase_uom_id = wizard.uom_id

    @api.depends('categ_id')
    def _compute_code_proposed(self):
        for wizard in self:
            wizard.code_proposed = wizard.categ_id and wizard._next_code(wizard.categ_id) or False

    @api.depends('name', 'company_id')
    def _compute_similar_ids(self):
        for wizard in self:
            commands = [Command.clear()]
            for product, score, last_price in wizard._find_similar():
                commands.append(Command.create({
                    'product_id': product.id,
                    'score': score,
                    'price_last': last_price,
                }))
            wizard.similar_ids = commands

    @api.depends('similar_ids')
    def _compute_similar_count(self):
        for wizard in self:
            wizard.similar_count = len(wizard.similar_ids)

    # ------------------------------------------------------------------
    # Código y parecidos
    # ------------------------------------------------------------------
    @api.model
    def _next_code(self, category):
        """Siguiente código libre de la familia: el mayor correlativo usado
        más uno. Se mira todo el maestro (archivados y de otras compañías),
        porque el código no se repite en ningún caso."""
        prefix = category.construction_family_code
        if not prefix:
            return False
        # sudo: el correlativo cuenta los productos de todas las compañías y
        # los archivados, que el planificador no ve.
        products_sudo = self.env['product.product'].sudo().with_context(active_test=False)
        codes = products_sudo.search_read(
            [('default_code', '=like', prefix + '_' * CODE_DIGITS)], ['default_code'])
        used = [int(code['default_code'][len(prefix):]) for code in codes
                if code['default_code'][len(prefix):].isdigit()]
        number = max(used, default=0) + 1
        if number >= 10 ** CODE_DIGITS:
            raise UserError(self.env._(
                'La familia %(family)s ya usó sus %(count)s códigos.',
                family=category.display_name, count=10 ** CODE_DIGITS - 1))
        return '%s%0*d' % (prefix, CODE_DIGITS, number)

    def _find_similar(self):
        """[(producto, coincidencia, último precio)] de los productos cuyo
        nombre se parece al escrito: candidatos por cada palabra de 3 letras o
        más y orden por la coincidencia del nombre completo."""
        self.ensure_one()
        words = [word for word in normalize(self.name).split() if len(word) >= 3]
        if not words:
            return []
        Product = self.env['product.product']
        domain = [('company_id', 'in', [False, self.company_id.id])]
        domain += ['|'] * (len(words) - 1) + [('name', 'ilike', word) for word in words]
        candidates = Product.search(domain, limit=200)
        scored = sorted(
            ((product, similarity(self.name, product.name)) for product in candidates),
            key=lambda item: -item[1])
        scored = [(product, score) for product, score in scored
                  if score >= SIMILARITY_MIN][:SIMILARITY_LIMIT]
        last_prices = self.env['construction.purchase.price.report']._get_last_prices(
            Product.concat(*[product for product, _score in scored]), self.company_id)
        return [(product, score, last_prices.get(product, (False, 0.0))[1])
                for product, score in scored]

    # ------------------------------------------------------------------
    # Crear
    # ------------------------------------------------------------------
    def _check_line(self):
        line = self.plan_line_id
        if not line:
            return
        if line.plan_id.state != 'draft':
            raise UserError(self.env._(
                'La línea es de %s, que ya no está en borrador.', line.plan_id.display_name))
        if line.resource_type not in ('material', 'service'):
            raise UserError(self.env._(
                'Solo las líneas de material o servicio llevan un producto comprado.'))

    def action_create(self):
        self.ensure_one()
        self._check_line()
        if not self.name.strip():
            raise UserError(self.env._('Escriba el nombre del producto.'))
        if self.purchase_uom_id and not self.purchase_uom_id._has_common_reference(self.uom_id):
            raise UserError(self.env._(
                'La unidad de compra %(purchase)s no se convierte a %(uom)s.',
                purchase=self.purchase_uom_id.name, uom=self.uom_id.name))
        if self.purchase_uom_id and self.purchase_uom_id != self.uom_id and not self.partner_id:
            raise UserError(self.env._(
                'La unidad de compra se guarda en el proveedor: indique el proveedor o use la '
                'unidad de consumo.'))
        # La familia queda bloqueada hasta el fin de la transacción: otro
        # planificador que cree en la misma familia espera y toma el número
        # siguiente.
        self.env.cr.execute(SQL(
            'SELECT id FROM product_category WHERE id = %s FOR UPDATE', self.categ_id.id))
        code = self._next_code(self.categ_id)
        vals = {
            'name': self.name.strip(),
            'default_code': code,
            'categ_id': self.categ_id.id,
            'type': 'consu',
            'uom_id': self.uom_id.id,
            'purchase_ok': True,
            'active': True,
            'construction_created_from_plan_id': self.plan_id.id,
        }
        if self.partner_id:
            vals['seller_ids'] = [Command.create({
                'partner_id': self.partner_id.id,
                'price': self.price_reference,
                'currency_id': self.currency_id.id,
                'product_uom_id': (self.purchase_uom_id or self.uom_id).id,
                'company_id': self.company_id.id,
            })]
        # sudo: el planificador crea el producto desde el plan sin administrar
        # el maestro (decisión del 10-oct: «se crea desde el plan y queda
        # activo en el acto»); Logística lo completa con la actividad.
        product_sudo = self.env['product.product'].sudo().with_company(self.company_id).create(vals)
        product = product_sudo.sudo(False)
        line = self.plan_line_id
        if line:
            line.write({'product_id': product.id, 'product_uom_id': self.uom_id.id})
        self._schedule_logistics_activity(product)
        self.plan_id.message_post(body=self.env._(
            'Producto creado desde el plan: %(product)s%(line)s.',
            product=product.display_name,
            line=self.env._(' (línea de %s)', line.task_id.display_name or
                            line.project_id.display_name) if line else ''))
        if line:
            return {'type': 'ir.actions.act_window_close'}
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'res_id': product.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }

    def _schedule_logistics_activity(self, product):
        """Actividad para Logística en el producto: completar marca,
        proveedor y cuentas (P-17)."""
        user = self.env['construction.resource.plan']._get_logistics_user(self.company_id)
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        # sudo: el planificador crea el producto pero no administra el
        # maestro; la actividad es el aviso a Logística.
        product_tmpl_sudo = product.product_tmpl_id.sudo()
        product_tmpl_sudo.activity_schedule(
            activity_type_id=activity_type.id if activity_type else False,
            summary=self.env._('Completar producto creado desde el plan'),
            note=self.env._(
                'Creado desde el plan %(plan)s por %(user)s con el código %(code)s. Complete '
                'marca, proveedor, cuentas y demás datos del maestro.',
                plan=self.plan_id.display_name, user=self.env.user.name,
                code=product.default_code),
            user_id=user.id, date_deadline=fields.Date.context_today(self))


class ConstructionProductCreateWizardSimilar(models.TransientModel):
    _name = 'construction.product.create.wizard.similar'
    _description = 'Producto parecido'
    _order = 'score desc, id'

    wizard_id = fields.Many2one(
        'construction.product.create.wizard', string='Asistente', required=True,
        ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    uom_id = fields.Many2one(
        related='product_id.uom_id', string='Unidad', help='Unidad del producto parecido.')
    score = fields.Float(string='Coincidencia', help='Parecido del nombre, de 0 a 100 %.')
    currency_id = fields.Many2one(related='wizard_id.currency_id', string='Moneda')
    price_last = fields.Monetary(string='Último precio', currency_field='currency_id')

    def action_use_product(self):
        """Usar el producto existente en la línea en lugar de crear uno."""
        self.ensure_one()
        wizard = self.wizard_id
        wizard._check_line()
        if not wizard.plan_line_id:
            raise UserError(self.env._('No hay línea del plan a la que asignar el producto.'))
        wizard.plan_line_id.write({
            'product_id': self.product_id.id,
            'product_uom_id': self.product_id.uom_id.id,
        })
        return {'type': 'ir.actions.act_window_close'}
