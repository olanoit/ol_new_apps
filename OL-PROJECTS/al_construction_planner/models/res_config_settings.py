# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Funciones del planificador (v1.7, M17-06). Siempre activos: Proyectos,
    # la planificación (árbol, plan de recursos, línea base) y el cronograma.
    # Cada puente se instala al activarlo; control y avance son del núcleo y
    # se muestran u ocultan con su grupo.
    group_construction_control = fields.Boolean(
        string='Control', implied_group='al_construction_planner.group_planner_feature_control',
        group='base.group_user',
        help='Comprometido, real, saldo y desvío por nivel, etapa y tipo de recurso.')
    group_construction_progress = fields.Boolean(
        string='Avance y metrados',
        implied_group='al_construction_planner.group_planner_feature_progress',
        group='base.group_user', help='Avance por driver, validación y metrado de los niveles.')
    module_al_construction_planner_mrp = fields.Boolean(
        string='Producción', help='Órdenes de fabricación desde el plan (instala Fabricación).')
    module_al_construction_planner_subcontract = fields.Boolean(
        string='Contratas', help='Asignar contrata con su OC de servicio, liquidación semanal y '
                                 'portal de la contrata (instala Compras).')
    module_al_construction_planner_purchase = fields.Boolean(
        string='Compras, abastecimiento y requerimientos de obra',
        help='Compra masiva, requerimientos de obra, abastecimiento, precios de compra y '
             'material extra (instala el requerimiento de compra).')
    module_al_construction_planner_crew = fields.Boolean(
        string='Cuadrillas propias',
        help='Turnos de Planificación y horas de la hoja de horas como real.')
    module_al_construction_planner_budget = fields.Boolean(
        string='Presupuesto analítico',
        help='Presupuesto analítico al aprobar el plan y control de la OC contra él.')
    module_al_construction_planner_sale = fields.Boolean(
        string='Valorización e ingresos',
        help='Calendario e ingresos, contratos con hitos, entrega semanal, valorización y '
             'cronograma valorizado (instala Ventas).')
    module_al_construction_planner_furniture = fields.Boolean(
        string='Rubro mobiliario',
        help='Tipologías de mueble con módulos, metros lineales y lista de materiales, e '
             'importación del maestro y del ETO (instala Producción).')

    construction_profile_id = fields.Many2one(
        related='company_id.construction_profile_id', readonly=False)
    construction_level_template_id = fields.Many2one(
        related='company_id.construction_level_template_id', readonly=False)
    construction_week_start_day = fields.Selection(
        related='company_id.construction_week_start_day', readonly=False)
    construction_settlement_day = fields.Selection(
        related='company_id.construction_settlement_day', readonly=False)
    construction_payment_day = fields.Selection(
        related='company_id.construction_payment_day', readonly=False)
    construction_categ_assembly_id = fields.Many2one(
        related='company_id.construction_categ_assembly_id', readonly=False)
    construction_categ_installation_id = fields.Many2one(
        related='company_id.construction_categ_installation_id', readonly=False)

    def action_construction_apply_profile(self):
        """Guarda los Ajustes y aplica el perfil elegido a la compañía."""
        self.ensure_one()
        profile = self.construction_profile_id
        if not profile:
            raise UserError(self.env._('Elija el perfil de vertical.'))
        self.execute()
        return profile.action_apply()
