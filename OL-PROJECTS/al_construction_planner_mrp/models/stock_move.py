# -*- coding: utf-8 -*-
"""Costo analítico de los componentes de una orden de obra (paquete 1.12).

Odoo da a cada componente de una orden con proyecto la distribución del
proyecto (project_mrp_account) y crea el apunte por el valor del movimiento
(stock_account). En una cadena de etapas eso carga dos veces el material:
en la orden de corte y otra vez en la de armado, que consume el paquete de
piezas. Y el hook de apuntes del puente de presupuesto pone a todo consumo
de fabricación la primera etapa de fabricación del catálogo.

- M112-01: el componente intermedio (el paquete de piezas) no carga costo
  analítico en la orden que lo consume. El asiento contable no cambia.
- M112-02: el apunte toma la etapa de su línea de la lista o, si la orden
  tiene un motivo con «Etapa analítica», la de su motivo; la partida sale
  de las reglas analíticas, como en el hook.

Las columnas se ponen en la distribución del movimiento: así Odoo vuelve a
encontrar sus apuntes al recalcularlos y no los borra y crea otra vez."""
from collections import defaultdict

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_intermediate_no_analytic = fields.Boolean(
        string='El componente intermedio no carga costo analítico', default=True,
        help='El paquete de piezas que consume la orden de armado ya cargó su material en la '
             'orden de corte: no genera apunte analítico otra vez. Su asiento contable no '
             'cambia.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_intermediate_no_analytic = fields.Boolean(
        related='company_id.construction_intermediate_no_analytic', readonly=False)


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _get_analytic_distribution(self):
        production = self.raw_material_production_id
        # Corre en cada movimiento de stock de la base: sale enseguida si no
        # es componente de una orden con obra.
        if not production or not production.project_id.is_construction_site:
            return super()._get_analytic_distribution()
        if production.company_id.construction_intermediate_no_analytic \
                and production._construction_is_intermediate(self):
            return {}
        distribution = super()._get_analytic_distribution()
        if not distribution:
            return distribution
        return self._construction_stage_distribution(production, distribution)

    def _construction_stage_distribution(self, production, distribution):
        """Completa cada clave de la distribución con la etapa y la partida
        del componente. La etapa del motivo manda sobre la de las reglas; lo
        que ya trae el proyecto en las demás columnas se respeta."""
        self.ensure_one()
        # Las reglas y el catálogo de etapas son configuración del
        # planificador: los lee el sistema por quien confirma en planta.
        Stage = self.env['construction.stage'].sudo()
        stage = self.bom_line_id.sudo().construction_consumption_stage \
            or Stage._consumption_code('production')
        product = self.product_id
        resource_type = 'material' if product.type == 'consu' else 'service'
        rule_accounts = self.env['construction.analytic.rule'].sudo()._accounts_for(
            production.company_id, resource_type, stage, product.categ_id)
        reason_account = production.construction_reason_id.sudo().analytic_account_id
        if not rule_accounts and not reason_account:
            return distribution
        Account = self.env['account.analytic.account'].sudo()
        result = defaultdict(float)
        for key, percentage in distribution.items():
            accounts = Account.browse(int(account_id) for account_id in key.split(','))
            if reason_account:
                accounts = accounts.filtered(
                    lambda a: a.root_plan_id != reason_account.root_plan_id) | reason_account
            plans = accounts.root_plan_id
            accounts |= rule_accounts.filtered(lambda a: a.root_plan_id not in plans)
            result[','.join(str(account_id) for account_id in sorted(accounts.ids))] += percentage
        return dict(result)

    def _create_analytic_move(self):
        # La etapa y la partida del consumo de una orden de obra ya vienen en
        # la distribución: el hook de apuntes del puente de presupuesto no
        # pone la etapa de fabricación por defecto en las columnas vacías.
        return super(StockMove, self.with_context(
            construction_analytic_by_move=True))._create_analytic_move()
