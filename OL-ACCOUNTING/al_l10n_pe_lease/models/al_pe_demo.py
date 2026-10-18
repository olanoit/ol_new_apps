# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_lease(self):
        """Contratos NIIF 16 de un arrendador: oficina a 36 meses confirmada
        con sus dos primeras facturas, almacén a 12 meses exento por corto
        plazo, montacargas en borrador con su tabla y un depósito con
        subcuentas del pasivo, remedido por el reajuste anual de la renta."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_lease.demo_lease_depot'):
            return
        env = self._demo_env(company)
        lessor = self._demo_partner(env, 'al_l10n_pe_lease.demo_lessor', 'Inmobiliaria San Isidro S.A.C.',
                                    self._demo_ruc('2061234567'))
        Lease = env['l10n_pe.lease']
        month = fields.Date.context_today(self).replace(day=1)

        def lease(key, **vals):
            return self._demo_record('al_l10n_pe_lease.demo_lease_%s' % key, Lease, dict(partner_id=lessor.id, **vals))

        office = lease('office', property_description='Oficina Av. Javier Prado 450, piso 8',
                       contract_ref='ARR-%s-01' % month.year, date_start=month - relativedelta(months=3),
                       term_months=36, payment_amount=4500.0, payment_timing='advance', annual_rate=12.0,
                       initial_direct_costs=1200.0, guarantee_amount=9000.0)
        office.action_confirm()
        office.action_register_installment()
        office.action_register_installment()
        warehouse = lease('warehouse', property_description='Almacén temporal Lurín',
                          contract_ref='ARR-%s-02' % month.year, date_start=month - relativedelta(months=2),
                          term_months=12, payment_amount=2800.0, payment_timing='advance')
        warehouse.action_confirm()
        warehouse.action_register_installment()
        lease('forklift', property_description='Montacargas eléctrico 2,5 t', contract_ref='ARR-%s-03' % month.year,
              date_start=month + relativedelta(months=1), term_months=24, payment_amount=1350.0,
              payment_timing='arrears', annual_rate=10.5).action_compute()
        depot = lease('depot', property_description='Depósito Ate (reajuste anual)',
                      contract_ref='ARR-%s-05' % month.year, date_start=month.replace(month=1), term_months=36,
                      payment_amount=3000.0, payment_timing='advance', annual_rate=12.0)
        depot.action_create_liability_accounts()
        depot.action_confirm()
        if month.month > 1:
            env['l10n_pe.lease.remeasure'].with_context(default_lease_id=depot.id).create({
                'date': month, 'payment_amount': 3300.0, 'remaining_months': 36 - (month.month - 1),
                'annual_rate': 12.0, 'reason': 'Reajuste anual de la renta (10 %)'}).action_apply()
