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
        string='Avance',
        implied_group='al_construction_planner.group_planner_feature_progress',
        group='base.group_user', help='Avance por driver con fotos y su validación.')
    # Metrado (v1.8, M18-01): concepto de la vertical Mobiliario (medida del
    # espacio, diseño y despiece del mueble), separado del avance.
    group_construction_measurement = fields.Boolean(
        string='Metrado',
        implied_group='al_construction_planner.group_planner_feature_measurement',
        group='base.group_user', help='Metrado del nivel frente a lo planificado (mobiliario).')
    # Entradas a la ejecución (CREVAL v1.0, capítulo 4): se construyen las
    # dos y cada una se activa por separado; apagarla no borra datos.
    group_construction_exec_planner = fields.Boolean(
        string='Ejecución en Planificación de obra',
        implied_group='al_construction_planner.group_planner_feature_exec_planner',
        group='base.group_user',
        help='Menús por momento, tablero de obra y tarea de obra con su menú Ejecutar.')
    group_construction_exec_project = fields.Boolean(
        string='Ejecución desde Proyectos',
        implied_group='al_construction_planner.group_planner_feature_exec_project',
        group='base.group_user',
        help='Sección Obra en el tablero del proyecto y menú Ejecutar en la tarea de Proyectos.')
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
    construction_plan_cancel_open = fields.Boolean(
        related='company_id.construction_plan_cancel_open', readonly=False)
    construction_plan_cancel_group_id = fields.Many2one(
        related='company_id.construction_plan_cancel_group_id', readonly=False)
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
        return profile.action_open_apply_wizard()

    def set_values(self):
        super().set_values()
        # El menú por momento se arma al cargar el menú (ir.ui.menu.load_menus,
        # en caché): un cambio del ajuste se ve en la siguiente carga.
        self.env.transaction.invalidate_ormcache()
