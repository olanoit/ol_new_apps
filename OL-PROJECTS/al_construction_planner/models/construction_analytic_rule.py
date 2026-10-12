# -*- coding: utf-8 -*-
"""Regla analítica del plan (v1.5, M15-12).

Completa la distribución de cada línea del plan con la etapa (producción,
instalación), la partida de costo (tableros, cantos, accesorios, mano de obra
fija o variable, fletes) y el área, además de la cuenta de la obra: así el
presupuesto sale por obra › etapa › partida y los documentos que nacen del
plan (compra, requerimiento, OF, liquidación) llevan la misma analítica.

Cada regla dice a qué líneas aplica (tipo de recurso, etapa del plan,
categoría del producto: vacío = cualquiera) y qué cuentas pone. Gana la más
eespecífica (la que más condiciones cumple) y, a igualdad, la de menor
secuencia, columna por columna: la etapa puede salir de una regla por etapa y
la partida de otra por categoría.
"""
from odoo import api, fields, models

from .common import RESOURCE_TYPES, STAGES


class ConstructionAnalyticRule(models.Model):
    _name = 'construction.analytic.rule'
    _description = 'Regla analítica del plan de obra'
    _order = 'sequence, id'
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    resource_type = fields.Selection(RESOURCE_TYPES, string='Recurso')
    stage = fields.Selection(STAGES, string='Etapa del plan')
    product_categ_id = fields.Many2one(
        'product.category', string='Categoría del producto',
        help='Incluye sus subcategorías.')
    stage_account_id = fields.Many2one(
        'account.analytic.account', string='Etapa', check_company=True,
        help='Cuenta del plan Etapa: producción (PRD) o instalación (INS).')
    cost_account_id = fields.Many2one(
        'account.analytic.account', string='Partida de costo', check_company=True,
        help='Cuenta del plan Partida: tableros, cantos, accesorios, MODF, MODV, fletes…')
    area_account_id = fields.Many2one(
        'account.analytic.account', string='Área', check_company=True)

    def _score(self, resource_type, stage, categ):
        """Condiciones que cumple (``None`` si alguna no se cumple)."""
        self.ensure_one()
        score = 0
        for value, wanted in ((resource_type, self.resource_type), (stage, self.stage)):
            if wanted:
                if value != wanted:
                    return None
                score += 1
        if self.product_categ_id:
            if not categ or not categ.parent_path or \
                    not categ.parent_path.startswith(self.product_categ_id.parent_path):
                return None
            score += 1
        return score

    @api.model
    def _matching(self, company, resource_type, stage, categ):
        """Reglas que aplican, de la más específica a la menos."""
        scored = []
        for rule in self.search([('company_id', '=', company.id)]):
            score = rule._score(resource_type, stage, categ)
            if score is not None:
                scored.append((-score, rule.sequence, rule.id, rule))
        return [rule for *_key, rule in sorted(scored, key=lambda item: item[:3])]

    @api.model
    def _accounts_for(self, company, resource_type, stage, categ):
        """Cuentas de etapa, partida y área: cada una de la regla más
        específica que la define."""
        Account = self.env['account.analytic.account']
        picked = {}
        for rule in self._matching(company, resource_type, stage, categ):
            for field in ('stage_account_id', 'cost_account_id', 'area_account_id'):
                if field not in picked and rule[field]:
                    picked[field] = rule[field]
        return Account.union(*picked.values()) if picked else Account
