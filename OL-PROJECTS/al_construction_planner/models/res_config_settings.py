# -*- coding: utf-8 -*-
from odoo import api, fields, models
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
    # Paquete 1.20, M120-07: funciones que ocultan los menús de una vertical
    # que la compañía no usa. Apagarlas no borra ni bloquea registros.
    group_construction_milestones = fields.Boolean(
        string='Valorización por entregas e hitos',
        implied_group='al_construction_planner.group_planner_feature_milestones',
        group='base.group_user',
        help='Hitos por unidad, entregas semanales y plantillas de hitos de cobro.')
    group_construction_valuation = fields.Boolean(
        string='Valorización por avance',
        implied_group='al_construction_planner.group_planner_feature_valuation',
        group='base.group_user',
        help='Preparar valorización, valorizaciones y metas de valorización.')
    group_construction_deductions = fields.Boolean(
        string='Deductivos, intervenciones y fondo de garantía',
        implied_group='al_construction_planner.group_planner_feature_deductions',
        group='base.group_user',
        help='Deductivos e intervenciones de contrata, fondos de garantía y su configuración.')
    group_construction_daily_report = fields.Boolean(
        string='Parte diario y tareo del residente',
        implied_group='al_construction_planner.group_planner_feature_daily_report',
        group='base.group_user', help='Partes diarios y tareo de cuadrillas del residente.')
    group_construction_recipes = fields.Boolean(
        string='Recetas por partida',
        implied_group='al_construction_planner.group_planner_feature_recipes',
        group='base.group_user', help='El catálogo de recetas de partida.')
    group_construction_installation_board = fields.Boolean(
        string='Control semanal de instalación',
        implied_group='al_construction_planner.group_planner_feature_installation_board',
        group='base.group_user',
        help='El tablero de control semanal de instalación y su botón en la obra.')
    # M120-07, punto 6: lo que activa otra vertical va en un bloque plegado.
    construction_other_features = fields.Char(compute='_compute_construction_other_features')
    construction_show_other_features = fields.Boolean(string='Ver las funciones de otras verticales')
    # M120-05: los tipos de recurso del perfil de la compañía.
    construction_resource_type_codes = fields.Char(
        compute='_compute_construction_resource_type_codes')
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
    construction_name_max_width = fields.Integer(
        related='company_id.construction_name_max_width', readonly=False)
    construction_payment_day = fields.Selection(
        related='company_id.construction_payment_day', readonly=False)
    construction_plan_cancel_open = fields.Boolean(
        related='company_id.construction_plan_cancel_open', readonly=False)
    construction_plan_cancel_group_id = fields.Many2one(
        related='company_id.construction_plan_cancel_group_id', readonly=False)
    construction_categ_assembly_id = fields.Many2one(
        related='company_id.construction_categ_assembly_id', readonly=False)
    # Horario de obra (paquete 1.19, M119-03).
    construction_site_calendar_id = fields.Many2one(
        related='company_id.construction_site_calendar_id', readonly=False,
        domain="[('company_id', 'in', (False, company_id))]")
    construction_workday_hours = fields.Float(
        related='company_id.construction_workday_hours', readonly=False)
    construction_site_week_hours = fields.Float(related='company_id.construction_site_week_hours')
    construction_site_full_day_hours = fields.Float(
        related='company_id.construction_site_full_day_hours')
    construction_site_week_days = fields.Float(related='company_id.construction_site_week_days')
    construction_categ_installation_id = fields.Many2one(
        related='company_id.construction_categ_installation_id', readonly=False)

    @api.depends('company_id.construction_profile_id')
    def _compute_construction_resource_type_codes(self):
        from .construction_vertical_profile import profile_resource_type_codes
        for settings in self:
            settings.construction_resource_type_codes = profile_resource_type_codes(
                self.env, settings.company_id.construction_profile_id)

    @api.depends('company_id.construction_profile_id')
    def _compute_construction_other_features(self):
        """Interruptores de Funciones que el perfil de la compañía no usa y otro
        perfil sí (por ejemplo, «Rubro mobiliario» en una constructora). Sin
        perfil, ninguno: se ve todo como hoy."""
        from .construction_vertical_profile import FEATURES
        Profile = self.env['construction.vertical.profile']
        for settings in self:
            profile = settings.company_id.construction_profile_id
            if not profile:
                settings.construction_other_features = ''
                continue
            others = Profile.search([('id', '!=', profile.id)])
            names = []
            for feature in FEATURES:
                if not profile['feature_%s' % feature] and any(
                        other['feature_%s' % feature] for other in others):
                    names.append('group_construction_%s' % feature)
            for name, field in self._fields.items():
                if not name.startswith('module_al_construction_planner_'):
                    continue
                module = name[len('module_'):]
                if module not in profile.module_ids.mapped('name') and module in \
                        others.module_ids.mapped('name'):
                    names.append(name)
            # Con espacios a los lados: la vista pregunta por « campo ».
            settings.construction_other_features = ' %s ' % ' '.join(names) if names else ''

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
        self.env.registry.clear_cache()
