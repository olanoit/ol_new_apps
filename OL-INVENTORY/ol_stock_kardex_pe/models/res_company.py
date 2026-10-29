from datetime import datetime, time

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

PE_TZ = pytz.timezone('America/Lima')
#: Marca de «recalcular todo»: el motor borra y rehace desde el primer movimiento.
WH_COST_FULL = datetime(1900, 1, 1)


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_wh_cost = fields.Boolean(
        string='Costo promedio por almacén',
        help='El kardex calcula el costo promedio ponderado de cada almacén: las '
             'salidas y los traslados salen al costo del almacén de origen. El '
             'cierre de valorización del inventario lleva la diferencia con el '
             'costo de Odoo a la cuenta de variación (69 en el PCGE).')
    l10n_pe_wh_cost_dirty_date = fields.Datetime(
        string='Costo por almacén pendiente desde', copy=False,
        help='Fecha del movimiento más antiguo que cambió desde el último cálculo. '
             'Vacía: el costo por almacén está al día.')
    l10n_pe_stock_lock_date = fields.Date(
        string='Almacén cerrado hasta', copy=False, readonly=True,
        help='Lo fija el cierre mensual de almacén: no se pueden validar '
             'movimientos ni cambiar su valor con fecha hasta este día.')

    def _get_company_root_delegated_field_names(self):
        # El método de costo es una decisión del RUC, no de cada sucursal.
        return super()._get_company_root_delegated_field_names() + ['l10n_pe_wh_cost']

    def write(self, vals):
        enabling = self.filtered(lambda c: not c.l10n_pe_wh_cost) if vals.get('l10n_pe_wh_cost') else self.browse()
        res = super().write(vals)
        # Al activarlo, el primer cálculo recorre toda la historia.
        enabling.l10n_pe_wh_cost_dirty_date = WH_COST_FULL
        return res

    # ------------------------------------------------------------------
    # Cierre mensual de almacén
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_day_end(self, day):
        """Último instante (UTC, sin zona) de ``day`` en hora de Lima."""
        end = PE_TZ.localize(datetime.combine(fields.Date.to_date(day), time.max))
        return end.astimezone(pytz.utc).replace(tzinfo=None)

    def _l10n_pe_stock_lock_end(self):
        """Último instante (UTC) del día de cierre del almacén."""
        self.ensure_one()
        return self.l10n_pe_stock_lock_date and self._l10n_pe_day_end(self.l10n_pe_stock_lock_date)

    def _l10n_pe_check_stock_lock(self, moment, what):
        """Error si ``moment`` (datetime UTC o date) cae en un periodo cerrado."""
        self.ensure_one()
        lock_end = self._l10n_pe_stock_lock_end()
        if not lock_end or not moment:
            return
        if not isinstance(moment, datetime):
            moment = datetime.combine(moment, time.min)
            if moment.date() > self.l10n_pe_stock_lock_date:
                return
        elif moment > lock_end:
            return
        raise UserError(_(
            '%(what)s: el almacén de %(company)s está cerrado hasta el %(date)s. '
            'Reabra el cierre mensual o use una fecha posterior.',
            what=what, company=self.display_name,
            date=fields.Date.to_string(self.l10n_pe_stock_lock_date)))

    # ------------------------------------------------------------------
    # Costo por almacén
    # ------------------------------------------------------------------
    def _l10n_pe_wh_cost_mark_dirty(self, moment):
        """Anota que el costo por almacén cambió desde ``moment``."""
        for company in self.filtered('l10n_pe_wh_cost'):
            if not company.l10n_pe_wh_cost_dirty_date or moment < company.l10n_pe_wh_cost_dirty_date:
                # sudo: lo dispara cualquier usuario que valida un movimiento;
                # la marca no da acceso a nada.
                company.sudo().l10n_pe_wh_cost_dirty_date = moment

    def _l10n_pe_wh_cost_refresh(self):
        """Recalcula el costo por almacén de lo que quedó pendiente."""
        Cost = self.env['l10n_pe.kardex.wh.cost']
        for company in self.filtered(lambda c: c.l10n_pe_wh_cost and c.l10n_pe_wh_cost_dirty_date):
            date_from = company.l10n_pe_wh_cost_dirty_date
            if date_from == WH_COST_FULL:
                date_from = None
            Cost._l10n_pe_recompute(company, date_from)
            company.sudo().l10n_pe_wh_cost_dirty_date = False

    def get_inventory_value(self, at_date=None):
        """Valor del inventario con el costo por almacén.

        El cierre de valorización de Odoo lleva la cuenta de existencias a este
        valor contra la cuenta de variación: así el ajuste del costo de ventas
        entre el promedio de la compañía y el de cada almacén lo hace el propio
        cierre, sin un asiento aparte que el siguiente cierre desharía.
        """
        value_by_account = super().get_inventory_value(at_date)
        if not self.l10n_pe_wh_cost:
            return value_by_account
        self._l10n_pe_wh_cost_refresh()
        accounts_by_product = self.with_context(prefetch_fields=False)._get_accounts_by_product(at_date)
        wh_values = self.env['l10n_pe.kardex.wh.cost']._l10n_pe_values_at(self, at_date)
        for product, value in wh_values.items():
            accounts = accounts_by_product.get(product)
            if not accounts:
                continue
            odoo_value = product.with_context(to_date=at_date).total_value
            value_by_account[accounts['valuation']] += value - odoo_value
        return value_by_account
