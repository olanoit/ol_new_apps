# -*- coding: utf-8 -*-
"""Cartera de obras en el Inicio (paquete 7 de CREVAL, CR-59 y CR-65).

Los indicadores de cada obra (``_construction_indicators``, los mismos de la
ficha) se guardan en la obra para el mes en curso: con 30 obras la cartera
lee lo guardado. Se recalculan con la acción programada diaria y, al abrir el
Inicio, las obras marcadas como desactualizadas: lo marcan la confirmación de
una valorización, la publicación de un asiento con la analítica de la obra y
la aprobación de una meta. Otro mes se calcula al pedirlo."""
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import can_see_amounts

from .construction_indicators import RATIO_KEYS

_logger = logging.getLogger(__name__)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_indicators_cache = fields.Json(
        string='Indicadores guardados', copy=False, readonly=True,
        help='Indicadores de la cartera del mes en curso (paquete 7, CR-59).')
    construction_indicators_date = fields.Date(
        string='Indicadores al', copy=False, readonly=True)
    construction_indicators_stale = fields.Boolean(
        string='Indicadores por recalcular', copy=False, default=True)

    def _construction_portfolio_values(self, month=None, today=None):
        """Indicadores de la obra para la cartera, en un diccionario que se
        puede guardar (fechas en texto)."""
        self.ensure_one()
        today = today or fields.Date.context_today(self)
        plan = self._construction_portfolio_plan()
        try:
            data = self._construction_indicators(month or today, today, plan)
        except UserError as error:
            _logger.info('Indicadores de %s: %s', self.display_name, error)
            data = {}
        if not data:
            return {}
        invoices = self.construction_sale_order_id.invoice_ids.filtered(
            lambda m: m.state == 'posted' and m.move_type in ('out_invoice', 'out_refund'))
        to_string = fields.Date.to_string
        return {
            'month': to_string(data['month']),
            'budget': data['budget'],
            'executed': data['executed'],
            'cpi': data['cpi'],
            'spi': data['spi'],
            'bac': data['bac'],
            'eac': data['eac'],
            'light': data['light'],
            'lights': data['lights'],
            'days_late': data['days_late'],
            'date_estimated_end': to_string(data['date_estimated_end'])
            if data['date_estimated_end'] else False,
            'invoiced': sum(invoices.mapped('amount_untaxed_signed')),
        }

    def _construction_refresh_indicators(self):
        """Recalcula y guarda los indicadores del mes en curso."""
        today = fields.Date.context_today(self)
        for project in self.filtered('is_construction_site'):
            # sudo: la cartera guarda un resumen de documentos de otras áreas
            # (contabilidad, inventario, compras); quien abre el Inicio puede
            # no tener permiso de escribir la obra. Los montos se quitan al
            # leerlos a quien no los ve.
            project.sudo().write({
                'construction_indicators_cache': project.sudo()._construction_portfolio_values(
                    today, today),
                'construction_indicators_date': today,
                'construction_indicators_stale': False,
            })

    def _construction_mark_indicators_stale(self):
        projects = self.filtered(lambda p: p.is_construction_site
                                 and not p.construction_indicators_stale)
        if projects:
            # sudo: lo marcan documentos de otras áreas (asientos, valorizaciones).
            projects.sudo().construction_indicators_stale = True

    @api.model
    def _cron_construction_indicators(self):
        projects = self.search([('is_construction_site', '=', True), ('is_template', '=', False)])
        for project in projects:
            project._construction_refresh_indicators()
            if not self.env.context.get('construction_no_commit'):
                self.env.cr.commit()


class ConstructionPlannerHome(models.AbstractModel):
    _inherit = 'construction.planner.home'

    @api.model
    def _work_indicators(self, project, plan):
        today = fields.Date.context_today(self)
        month = self.env.context.get('construction_portfolio_month')
        month = fields.Date.to_date(month).replace(day=1) if month else today.replace(day=1)
        if month == today.replace(day=1):
            if (project.construction_indicators_stale
                    or project.construction_indicators_date != today
                    or not project.construction_indicators_cache):
                project._construction_refresh_indicators()
            values = project.construction_indicators_cache or {}
        else:
            # sudo: como al guardar (ver _construction_refresh_indicators).
            values = project.sudo()._construction_portfolio_values(month, today)
        if not values:
            return False
        return self._strip_amounts(values)

    @api.model
    def _strip_amounts(self, values):
        """Sin «Ve montos»: avances, porcentajes, índices y días; sin soles."""
        if can_see_amounts(self.env):
            return values

        def visit(value, key=None):
            if isinstance(value, dict):
                return {k: visit(v, k) for k, v in value.items()}
            if isinstance(value, (int, float)) and not isinstance(value, bool) \
                    and key not in RATIO_KEYS and key not in ('days_late', 'cpi', 'spi'):
                return False
            return value
        return visit(values)

    @api.model
    def _pending_areas(self):
        return dict(super()._pending_areas(), deliveries_to_confirm='revenue',
                    valuations_to_invoice='revenue')


class ConstructionValuation(models.Model):
    _inherit = 'construction.valuation'

    def _action_confirm(self, values, confirmed):
        res = super()._action_confirm(values, confirmed)
        self.project_id._construction_mark_indicators_stale()
        return res


class ConstructionValuationTarget(models.Model):
    _inherit = 'construction.valuation.target'

    def _construction_approve(self):
        res = super()._construction_approve()
        self.project_id._construction_mark_indicators_stale()
        return res


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        # CR-59: un asiento con la analítica de una obra cambia su costo o su
        # ingreso. sudo: lo publica contabilidad, que puede no ver las obras.
        accounts = posted.sudo().line_ids.analytic_line_ids.account_id
        if accounts:
            self.env['project.project'].sudo().search(
                [('account_id', 'in', accounts.ids), ('is_construction_site', '=', True)]
            )._construction_mark_indicators_stale()
        return posted
