# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.tools import SQL


class L10nPeMrpCostAnalysis(models.Model):
    """Costo de las órdenes terminadas por elemento (vista SQL).

    * Material: valor de los componentes consumidos.
    * Máquina: horas de cada operación × costo hora del centro de producción.
    * Mano de obra: horas de cada registro de tiempo × costo hora del empleado.
    * Ajuste de mano de obra y CIF: los cargos de los cierres de costos
      validados.
    """
    _name = 'l10n_pe.mrp.cost.analysis'
    _description = 'Costo de fabricación por elemento'
    _auto = False
    _order = 'date desc, production_id'
    # La vista lee estas tablas: el ORM las guarda en la base antes de buscar.
    _depends = {
        'mrp.production': ['product_id', 'company_id', 'date_finished', 'state'],
        'stock.move': ['raw_material_production_id', 'state', 'value'],
        'mrp.workorder': ['production_id', 'workcenter_id', 'duration', 'costs_hour'],
        'mrp.workcenter': ['costs_hour'],
        'mrp.workcenter.productivity': ['workorder_id', 'workcenter_id', 'employee_id',
                                        'duration', 'employee_cost'],
        'l10n_pe.mrp.cost.close': ['state'],
        'l10n_pe.mrp.cost.close.line': ['close_id', 'production_id', 'element', 'pool_id', 'amount'],
    }

    production_id = fields.Many2one('mrp.production', string='Orden', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date = fields.Datetime(string='Terminada', readonly=True)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Centro de producción', readonly=True)
    element = fields.Selection(
        [('material', 'Material'),
         ('machine', 'Máquina'),
         ('labor', 'Mano de obra'),
         ('labor_adjustment', 'Ajuste de mano de obra'),
         ('overhead', 'CIF')],
        string='Elemento', readonly=True)
    pool_id = fields.Many2one('l10n_pe.mrp.cost.pool', string='Bolsa de CIF', readonly=True)
    hours = fields.Float(string='Horas', readonly=True)
    amount = fields.Monetary(string='Costo', readonly=True)

    @property
    def _table_query(self):
        return SQL("""
            SELECT ROW_NUMBER() OVER (ORDER BY c.production_id, c.element, c.workcenter_id, c.pool_id) AS id, c.*
              FROM (
                SELECT mp.id AS production_id, mp.product_id, mp.company_id,
                       mp.date_finished AS date, NULL::integer AS workcenter_id,
                       'material' AS element, NULL::integer AS pool_id,
                       0.0 AS hours, SUM(sm.value) AS amount
                  FROM mrp_production mp
                  JOIN stock_move sm ON sm.raw_material_production_id = mp.id AND sm.state = 'done'
                 WHERE mp.state = 'done'
              GROUP BY mp.id
                UNION ALL
                SELECT mp.id, mp.product_id, mp.company_id, mp.date_finished, wo.workcenter_id,
                       'machine', NULL, SUM(wo.duration) / 60.0,
                       SUM(wo.duration / 60.0 * COALESCE(NULLIF(wo.costs_hour, 0), wc.costs_hour, 0))
                  FROM mrp_production mp
                  JOIN mrp_workorder wo ON wo.production_id = mp.id
                  JOIN mrp_workcenter wc ON wc.id = wo.workcenter_id
                 WHERE mp.state = 'done'
              GROUP BY mp.id, wo.workcenter_id
                UNION ALL
                SELECT mp.id, mp.product_id, mp.company_id, mp.date_finished, t.workcenter_id,
                       'labor', NULL, SUM(t.duration) / 60.0,
                       SUM(t.duration / 60.0 * COALESCE(t.employee_cost, 0))
                  FROM mrp_production mp
                  JOIN mrp_workorder wo ON wo.production_id = mp.id
                  JOIN mrp_workcenter_productivity t ON t.workorder_id = wo.id AND t.employee_id IS NOT NULL
                 WHERE mp.state = 'done'
              GROUP BY mp.id, t.workcenter_id
                UNION ALL
                SELECT mp.id, mp.product_id, mp.company_id, mp.date_finished, NULL,
                       CASE WHEN l.element = 'labor' THEN 'labor_adjustment' ELSE 'overhead' END,
                       l.pool_id, 0.0, l.amount
                  FROM l10n_pe_mrp_cost_close_line l
                  JOIN l10n_pe_mrp_cost_close cl ON cl.id = l.close_id AND cl.state = 'done'
                  JOIN mrp_production mp ON mp.id = l.production_id
              ) c
        """)
