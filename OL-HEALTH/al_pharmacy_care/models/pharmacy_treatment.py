# -*- coding: utf-8 -*-
"""Tratamiento crónico de un paciente: cuánto le dura cada compra, cuándo le
toca reponer y qué tan adherente es.

Cada compra del paciente (TPV o pedido de venta) del medicamento o de un
equivalente intercambiable suma días cubiertos: unidades compradas entre
unidades por día. Las compras se encadenan (si compra antes de terminar, el
saldo se suma al final del periodo cubierto). La adherencia es la
proporción de días cubiertos (PDC) de los últimos 180 días; menos de 80 % se
considera no adherente.
"""
import re
from datetime import timedelta
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

PDC_WINDOW_DAYS = 180
PDC_ADHERENT = 80.0

REFILL_STATES = [
    ('no_purchase', 'Sin compras'),
    ('ok', 'Cubierto'),
    ('due', 'Por reponer'),
    ('late', 'Atrasado'),
]


class PharmacyTreatment(models.Model):
    _name = 'pharmacy.treatment'
    _description = 'Tratamiento crónico'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'next_refill_date asc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    patient_id = fields.Many2one('res.partner', string='Paciente', required=True, index=True,
                                 tracking=True)
    product_id = fields.Many2one(
        'product.product', string='Medicamento', required=True, tracking=True,
        check_company=True, domain="[('pharmacy_ok', '=', True)]",
        help='También cuentan las compras de sus equivalentes (mismo principio activo, '
             'concentración y forma farmacéutica).')
    equivalence_key = fields.Char(related='product_id.product_tmpl_id.pharmacy_equivalence_key')
    daily_units = fields.Float(string='Unidades por día', required=True, default=1.0,
                               digits='Product Unit', tracking=True,
                               help='Unidades del producto (tabletas, cápsulas…) que toma por día.')
    posology = fields.Char(string='Posología', help='Por ejemplo «1 tableta cada 12 horas».')
    date_start = fields.Date(string='Inicio', required=True, default=fields.Date.context_today,
                             tracking=True)
    user_id = fields.Many2one('res.users', string='Responsable', default=lambda self: self.env.user,
                              tracking=True, help='Quien recibe el recordatorio de recompra.')
    state = fields.Selection([
        ('active', 'Activo'),
        ('paused', 'En pausa'),
        ('done', 'Terminado'),
    ], string='Estado', required=True, default='active', tracking=True)
    prescription_id = fields.Many2one('pharmacy.prescription', string='Receta', check_company=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Local', check_company=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    note = fields.Text(string='Notas')

    # Calculados al registrar una compra y a diario (cron).
    last_purchase_date = fields.Date(string='Última compra', readonly=True)
    covered_until = fields.Date(string='Cubierto hasta', readonly=True,
                                help='Día en que se le acaba el medicamento comprado.')
    next_refill_date = fields.Date(string='Próxima recompra', readonly=True, index=True)
    days_late = fields.Integer(string='Días de atraso', readonly=True)
    refill_state = fields.Selection(REFILL_STATES, string='Recompra', readonly=True,
                                    default='no_purchase', index=True)
    pdc = fields.Float(string='Adherencia (PDC %)', readonly=True, digits=(5, 1),
                       aggregator='avg',
                       help='Proporción de días cubiertos en los últimos 180 días (o desde el '
                            'inicio, si es más reciente).')
    adherent = fields.Boolean(string='Adherente', readonly=True,
                              help='PDC de 80 % o más.')
    whatsapp_url = fields.Char(string='WhatsApp', compute='_compute_whatsapp_url')

    _daily_units_positive = models.Constraint('CHECK(daily_units > 0)',
                                              'Las unidades por día deben ser mayores que cero.')

    @api.depends('patient_id.name', 'product_id.display_name')
    def _compute_name(self):
        for treatment in self:
            treatment.name = ' · '.join(
                filter(None, [treatment.patient_id.name, treatment.product_id.display_name]))

    @api.constrains('patient_id', 'product_id', 'state')
    def _check_unique_active(self):
        for treatment in self.filtered(lambda t: t.state == 'active'):
            duplicate = self.search_count([
                ('id', '!=', treatment.id), ('state', '=', 'active'),
                ('patient_id', '=', treatment.patient_id.id),
                ('product_id', '=', treatment.product_id.id),
                ('company_id', '=', treatment.company_id.id)])
            if duplicate:
                raise ValidationError(self.env._(
                    '%(patient)s ya tiene un tratamiento activo con %(product)s.',
                    patient=treatment.patient_id.name, product=treatment.product_id.display_name))

    # ------------------------------------------------------------------
    # Compras y cobertura
    # ------------------------------------------------------------------
    def _matching_products(self):
        """El medicamento y sus equivalentes intercambiables."""
        self.ensure_one()
        products = self.product_id
        key = self.equivalence_key
        if key:
            products |= self.env['product.product'].with_context(active_test=False).search(
                [('product_tmpl_id.pharmacy_equivalence_key', '=', key)])
        return products

    def _local_tz(self):
        """Huso del local para fechar las compras: el del responsable o el
        de la compañía, no el de quien registra la venta (la caja puede
        sincronizar con otro usuario)."""
        self.ensure_one()
        return self.user_id.tz or self.company_id.partner_id.tz or self.env.user.tz or 'UTC'

    def _get_purchases(self, date_from):
        """Compras del paciente desde ``date_from``: lista de (fecha, unidades)
        ordenada por fecha. Las devoluciones restan."""
        self.ensure_one()
        local = self.with_context(tz=self._local_tz())
        products = self._matching_products()
        purchases = []
        datetime_from = fields.Datetime.to_datetime(date_from)
        PosLine = self.env['pos.order.line']
        for line in PosLine.search([
                ('order_id.partner_id', '=', self.patient_id.id),
                ('order_id.state', 'in', ('paid', 'done')),
                ('order_id.company_id', '=', self.company_id.id),
                ('order_id.date_order', '>=', datetime_from),
                ('product_id', 'in', products.ids)]):
            purchases.append((fields.Date.context_today(local, line.order_id.date_order), line.qty))
        SaleLine = self.env['sale.order.line']
        for line in SaleLine.search([
                ('order_id.partner_id', '=', self.patient_id.id),
                ('order_id.state', '=', 'sale'),
                ('order_id.company_id', '=', self.company_id.id),
                ('order_id.date_order', '>=', datetime_from),
                ('product_id', 'in', products.ids)]):
            qty = line.product_uom_id._compute_quantity(line.product_uom_qty, line.product_id.uom_id)
            purchases.append((fields.Date.context_today(local, line.order_id.date_order), qty))
        purchases.sort(key=lambda purchase: purchase[0])
        return purchases

    @staticmethod
    def _coverage_periods(purchases, daily_units):
        """Periodos cubiertos [inicio, fin) encadenando las compras."""
        periods = []
        covered_until = None
        for date, qty in purchases:
            days = int(round(qty / daily_units)) if daily_units else 0
            if days <= 0:
                if days < 0 and covered_until:
                    # Devolución: acorta lo cubierto, sin ir antes de la compra.
                    start, end = periods[-1]
                    end = max(start, end + timedelta(days=days))
                    periods[-1] = (start, end)
                    covered_until = end
                continue
            start = max(date, covered_until) if covered_until else date
            end = start + timedelta(days=days)
            periods.append((start, end))
            covered_until = end
        return periods

    @staticmethod
    def _pdc(periods, window_start, today):
        """Días cubiertos en [window_start, today] entre los días de la ventana."""
        window_days = (today - window_start).days + 1
        if window_days <= 0:
            return 0.0
        covered = 0
        for start, end in periods:
            overlap_start = max(start, window_start)
            overlap_end = min(end, today + timedelta(days=1))
            covered += max(0, (overlap_end - overlap_start).days)
        return min(100.0, 100.0 * covered / window_days)

    def _update_coverage(self):
        for treatment in self:
            today = fields.Date.context_today(treatment.with_context(tz=treatment._local_tz()))
            window_start = max(treatment.date_start, today - timedelta(days=PDC_WINDOW_DAYS - 1))
            # Una compra anterior al inicio de la ventana puede seguir cubriendo.
            lookback = window_start - timedelta(days=PDC_WINDOW_DAYS)
            purchases = treatment._get_purchases(lookback)
            periods = self._coverage_periods(purchases, treatment.daily_units)
            reminder_days = treatment.company_id.pharmacy_care_reminder_days
            vals = {'last_purchase_date': purchases[-1][0] if purchases else False}
            if not periods:
                vals.update(covered_until=False, next_refill_date=False, days_late=0,
                            refill_state='no_purchase', pdc=0.0, adherent=False)
            else:
                covered_until = periods[-1][1]
                pdc = self._pdc(periods, window_start, today)
                days_late = max(0, (today - covered_until).days)
                if days_late:
                    refill_state = 'late'
                elif covered_until - timedelta(days=reminder_days) <= today:
                    refill_state = 'due'
                else:
                    refill_state = 'ok'
                vals.update(covered_until=covered_until,
                            next_refill_date=covered_until - timedelta(days=reminder_days),
                            days_late=days_late, refill_state=refill_state,
                            pdc=round(pdc, 1), adherent=pdc >= PDC_ADHERENT)
            treatment.write(vals)

    @api.model
    def _update_for_partners(self, partners, products, company):
        """Recalcula los tratamientos activos de ``partners`` afectados por
        una venta de ``products``."""
        if not partners or not products:
            return
        keys = [key for key in products.product_tmpl_id.mapped('pharmacy_equivalence_key') if key]
        domain = [('patient_id', 'in', partners.ids), ('state', '=', 'active'),
                  ('company_id', '=', company.id)]
        product_domain = [('product_id', 'in', products.ids)]
        if keys:
            product_domain = ['|', ('product_id.product_tmpl_id.pharmacy_equivalence_key', 'in', keys)] \
                + product_domain
        # Quien vende (cajero o vendedor) no necesariamente lee los
        # tratamientos: el recálculo es del establecimiento.
        treatments_sudo = self.sudo().search(domain + product_domain)
        treatments_sudo._update_coverage()

    @api.model_create_multi
    def create(self, vals_list):
        treatments = super().create(vals_list)
        treatments._update_coverage()
        return treatments

    def write(self, vals):
        result = super().write(vals)
        if {'product_id', 'daily_units', 'date_start', 'patient_id'} & set(vals):
            self._update_coverage()
        return result

    # ------------------------------------------------------------------
    # Recordatorios
    # ------------------------------------------------------------------
    def _refill_message(self):
        self.ensure_one()
        company = self.company_id
        date = self.covered_until and self.covered_until.strftime('%d/%m/%Y')
        if self.refill_state == 'late':
            text = self.env._(
                'Hola %(patient)s, le escribimos de %(company)s. Su %(product)s se terminó el '
                '%(date)s. ¿Desea que se lo separemos? Puede recogerlo o pedirlo por aquí.',
                patient=self.patient_id.name, company=company.name,
                product=self.product_id.name, date=date)
        else:
            text = self.env._(
                'Hola %(patient)s, le escribimos de %(company)s. Su %(product)s le alcanza hasta '
                'el %(date)s. ¿Desea que se lo separemos? Puede recogerlo o pedirlo por aquí.',
                patient=self.patient_id.name, company=company.name,
                product=self.product_id.name, date=date or '-')
        return text

    @staticmethod
    def _whatsapp_number(phone, country_code):
        digits = re.sub(r'\D', '', phone or '')
        if not digits:
            return ''
        if country_code == 'PE' and len(digits) == 9 and digits.startswith('9'):
            digits = '51' + digits
        return digits

    @api.depends('patient_id.phone', 'refill_state', 'covered_until', 'product_id')
    def _compute_whatsapp_url(self):
        for treatment in self:
            number = self._whatsapp_number(
                treatment.patient_id.phone,
                (treatment.patient_id.country_id or treatment.company_id.country_id).code)
            treatment.whatsapp_url = number and 'https://wa.me/%s?text=%s' % (
                number, quote(treatment._refill_message()))

    def action_whatsapp(self):
        self.ensure_one()
        if not self.whatsapp_url:
            raise ValidationError(self.env._('%s no tiene teléfono.', self.patient_id.name))
        self.message_post(body=self.env._('Recordatorio de recompra enviado por WhatsApp.'))
        return {'type': 'ir.actions.act_url', 'url': self.whatsapp_url, 'target': 'new'}

    def action_update_coverage(self):
        self._update_coverage()

    def action_pause(self):
        self.state = 'paused'

    def action_done(self):
        self.state = 'done'
        self.activity_unlink(['al_pharmacy_care.mail_activity_type_refill'])

    def action_activate(self):
        self.state = 'active'
        self._update_coverage()

    def action_view_purchases(self):
        """Ventas del TPV del paciente con el medicamento o sus equivalentes."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Compras de %s', self.name),
            'res_model': 'pos.order.line',
            'view_mode': 'list',
            'domain': [('order_id.partner_id', '=', self.patient_id.id),
                       ('product_id', 'in', self._matching_products().ids)],
        }

    @api.model
    def _cron_refill_reminders(self):
        """A diario: recalcula la cobertura y crea el recordatorio de los
        tratamientos por reponer o atrasados que aún no lo tienen."""
        treatments = self.search([('state', '=', 'active')])
        treatments._update_coverage()
        activity_type = self.env.ref('al_pharmacy_care.mail_activity_type_refill')
        template = self.env.ref('al_pharmacy_care.mail_template_treatment_refill',
                                raise_if_not_found=False)
        for treatment in treatments.filtered(lambda t: t.refill_state in ('due', 'late')):
            if treatment.activity_ids.filtered(lambda a: a.activity_type_id == activity_type):
                continue
            treatment.activity_schedule(
                'al_pharmacy_care.mail_activity_type_refill',
                date_deadline=max(treatment.next_refill_date, fields.Date.context_today(self)),
                summary=self.env._('Recompra: %s', treatment.product_id.display_name),
                note=treatment._refill_message(),
                user_id=(treatment.user_id or self.env.user).id)
            if template and treatment.company_id.pharmacy_care_send_email \
                    and treatment.patient_id.email:
                template.send_mail(treatment.id)
        return treatments

    # ------------------------------------------------------------------
    # TPV
    # ------------------------------------------------------------------
    @api.model
    def get_pos_due_treatments(self, partner_id, config_id):
        """Tratamientos del cliente que toca reponer, para avisar en la caja.

        Solo devuelve qué medicamento y desde cuándo: no expone datos de
        salud del paciente a quien atiende."""
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('Solo el personal del punto de venta consulta los tratamientos por reponer.'))
        config = self.env['pos.config'].browse(config_id).exists()
        if not config or not partner_id:
            return []
        if config.company_id not in self.env.companies:
            raise AccessError(_('La caja no es de una compañía permitida.'))
        # El cajero no tiene por qué leer los tratamientos; se devuelve lo
        # mínimo para el aviso.
        treatments_sudo = self.sudo().search([
            ('patient_id', '=', partner_id), ('state', '=', 'active'),
            ('company_id', '=', config.company_id.id),
            ('refill_state', 'in', ('due', 'late', 'no_purchase'))])
        treatments_sudo._update_coverage()
        result = []
        for treatment in treatments_sudo.filtered(lambda t: t.refill_state in ('due', 'late')):
            result.append({
                'id': treatment.id,
                'product_id': treatment.product_id.id,
                'product_tmpl_id': treatment.product_id.product_tmpl_id.id,
                'product_name': treatment.product_id.display_name,
                'covered_until': treatment.covered_until and fields.Date.to_string(
                    treatment.covered_until),
                'days_late': treatment.days_late,
                'refill_state': treatment.refill_state,
            })
        return result
