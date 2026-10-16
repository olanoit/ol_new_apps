# -*- coding: utf-8 -*-
"""Control de consumo sin repetición (v1.8, M18-05 y M18-21).

* Política por defecto en la compañía (la fija el perfil) y en la obra, que
  cada plan hereda al crearlo y puede cambiar, en lugar de definirla plan por
  plan.
* Política por tipo de recurso: materiales, contratas (alcance adicional en
  la OC de servicio), mano de obra propia (jornales sobre lo planificado) y
  producción. Vacía: la general.
* Control por nivel y sub etapa: si los recursos de un nivel en una sub etapa
  ya se pidieron completos, un pedido nuevo para ese nivel y sub etapa es una
  repetición y pasa por la jefatura de proyectos aunque el producto aún tenga
  saldo.
* Registro de cada exceso autorizado (y de los pagos repetidos y re-trabajos
  de contratas): quién, cuándo, motivo y cantidad, visible en el análisis de
  control y en el plan."""
from odoo import api, fields, models

EXCEED_POLICIES = [
    ('warn', 'Solo alerta'),
    ('approval', 'Aprobación adicional'),
    ('block', 'Bloquear'),
]
#: Tipos de recurso con política propia (el comportamiento de la línea).
POLICY_TYPES = ('material', 'contract', 'labor', 'production')
EXCEED_KINDS = [
    ('excess', 'Exceso sobre el saldo'),
    ('repeat', 'Pedido repetido del nivel y sub etapa'),
    ('repeat_payment', 'Pago repetido de contrata'),
    ('rework', 'Re-trabajo'),
    ('manual_pct', 'Porcentaje manual sobre el avance'),
]
REWORK_REASONS = [
    ('change', 'Cambio'),
    ('missing', 'Faltante'),
    ('bad_assembly', 'Mal armado'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_exceed_policy = fields.Selection(
        EXCEED_POLICIES, string='Si se excede el saldo del plan', default='approval',
        help='Política por defecto de las obras nuevas; cada obra y cada plan la pueden cambiar.')
    construction_exceed_tolerance = fields.Float(
        string='Tolerancia sobre el saldo (%)', digits=(5, 2), default=0.0)
    construction_exceed_policy_material = fields.Selection(
        EXCEED_POLICIES, string='Exceso en materiales', help='Vacía: la general.')
    construction_exceed_policy_contract = fields.Selection(
        EXCEED_POLICIES, string='Exceso en contratas',
        help='Alcance adicional en la OC de servicio de la misma actividad y nivel. Vacía: la '
             'general.')
    construction_exceed_policy_labor = fields.Selection(
        EXCEED_POLICIES, string='Exceso en mano de obra propia',
        help='Jornales sobre lo planificado. Vacía: la general.')
    construction_exceed_policy_production = fields.Selection(
        EXCEED_POLICIES, string='Exceso en producción', help='Vacía: la general.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_exceed_policy = fields.Selection(
        related='company_id.construction_exceed_policy', readonly=False)
    construction_exceed_tolerance = fields.Float(
        related='company_id.construction_exceed_tolerance', readonly=False)
    construction_exceed_policy_material = fields.Selection(
        related='company_id.construction_exceed_policy_material', readonly=False)
    construction_exceed_policy_contract = fields.Selection(
        related='company_id.construction_exceed_policy_contract', readonly=False)
    construction_exceed_policy_labor = fields.Selection(
        related='company_id.construction_exceed_policy_labor', readonly=False)
    construction_exceed_policy_production = fields.Selection(
        related='company_id.construction_exceed_policy_production', readonly=False)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_exceed_policy = fields.Selection(
        EXCEED_POLICIES, string='Si se excede el saldo del plan',
        compute='_compute_construction_exceed', store=True, readonly=False,
        help='La de la compañía; la heredan los planes nuevos de la obra.')
    construction_exceed_tolerance = fields.Float(
        string='Tolerancia sobre el saldo (%)', digits=(5, 2),
        compute='_compute_construction_exceed', store=True, readonly=False)
    construction_exceed_policy_material = fields.Selection(
        EXCEED_POLICIES, string='Exceso en materiales', compute='_compute_construction_exceed',
        store=True, readonly=False)
    construction_exceed_policy_contract = fields.Selection(
        EXCEED_POLICIES, string='Exceso en contratas', compute='_compute_construction_exceed',
        store=True, readonly=False)
    construction_exceed_policy_labor = fields.Selection(
        EXCEED_POLICIES, string='Exceso en mano de obra propia',
        compute='_compute_construction_exceed', store=True, readonly=False)
    construction_exceed_policy_production = fields.Selection(
        EXCEED_POLICIES, string='Exceso en producción', compute='_compute_construction_exceed',
        store=True, readonly=False)

    @api.depends('company_id')
    def _compute_construction_exceed(self):
        for project in self:
            company = project.company_id or self.env.company
            project.construction_exceed_policy = project.construction_exceed_policy \
                or company.construction_exceed_policy or 'approval'
            project.construction_exceed_tolerance = project.construction_exceed_tolerance \
                or company.construction_exceed_tolerance
            for rtype in POLICY_TYPES:
                name = 'construction_exceed_policy_%s' % rtype
                project[name] = project[name] or company[name]


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    exceed_policy_material = fields.Selection(
        EXCEED_POLICIES, string='Exceso en materiales', tracking=True, help='Vacía: la general.')
    exceed_policy_contract = fields.Selection(
        EXCEED_POLICIES, string='Exceso en contratas', tracking=True,
        help='Alcance adicional en la OC de servicio de la misma actividad y nivel. Vacía: la '
             'general.')
    exceed_policy_labor = fields.Selection(
        EXCEED_POLICIES, string='Exceso en mano de obra propia', tracking=True,
        help='Jornales sobre lo planificado. Vacía: la general.')
    exceed_policy_production = fields.Selection(
        EXCEED_POLICIES, string='Exceso en producción', tracking=True, help='Vacía: la general.')
    exceed_log_ids = fields.One2many('construction.exceed.log', 'plan_id',
                                     string='Excesos autorizados')
    exceed_log_count = fields.Integer(string='Nº de excesos', compute='_compute_exceed_log_count')

    def _compute_exceed_log_count(self):
        counts = dict(self.env['construction.exceed.log']._read_group(
            [('plan_id', 'in', self.ids)], ['plan_id'], ['__count']))
        for plan in self:
            plan.exceed_log_count = counts.get(plan, 0)

    @api.model_create_multi
    def create(self, vals_list):
        # Heredan la política de la obra (que sale de la compañía y el perfil).
        for vals in vals_list:
            project = self.env['project.project'].browse(vals.get('project_id'))
            if not project:
                continue
            if 'exceed_policy' not in vals and project.construction_exceed_policy:
                vals['exceed_policy'] = project.construction_exceed_policy
            if 'exceed_tolerance' not in vals and project.construction_exceed_tolerance:
                vals['exceed_tolerance'] = project.construction_exceed_tolerance
            for rtype in POLICY_TYPES:
                name = 'exceed_policy_%s' % rtype
                if name not in vals and project['construction_exceed_policy_%s' % rtype]:
                    vals[name] = project['construction_exceed_policy_%s' % rtype]
        return super().create(vals_list)

    def _exceed_policy_for(self, resource_type):
        """Política del plan para un tipo de recurso (la general si no tiene una
        propia). Material, servicio y equipo siguen a la de materiales."""
        self.ensure_one()
        key = 'material' if resource_type in ('material', 'service', 'equipment') \
            else resource_type
        if key in POLICY_TYPES and self['exceed_policy_%s' % key]:
            return self['exceed_policy_%s' % key]
        return self.exceed_policy

    def action_view_exceed_logs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner.action_construction_exceed_log')
        action['domain'] = [('plan_id', '=', self.id)]
        action['context'] = {'search_default_group_kind': 1}
        return action


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    def _construction_stage_complete(self):
        """{(nivel, etapa): True} de las líneas cuyos recursos de material de
        su nivel y sub etapa ya se pidieron completos (M18-05)."""
        result = {}
        Line = self.env['construction.resource.plan.line']
        for line in self:
            key = (line.task_id, line.stage)
            if key in result or not line.task_id or not line.stage:
                continue
            group = Line.search([
                ('plan_id', '=', line.plan_id.id), ('task_id', '=', line.task_id.id),
                ('stage', '=', line.stage),
                ('resource_type', 'in', ('material', 'service', 'equipment', 'production'))])
            result[key] = bool(group) and all(
                not other.product_uom_id or other.product_uom_id.compare(
                    other.qty_requested, other.qty_planned) >= 0
                for other in group)
        return result


class ConstructionExceedLog(models.Model):
    """Exceso, repetición o re-trabajo autorizado (M18-05, M18-21)."""
    _name = 'construction.exceed.log'
    _description = 'Exceso autorizado sobre el plan'
    _order = 'date desc, id desc'
    _check_company_auto = True

    kind = fields.Selection(EXCEED_KINDS, string='Tipo', required=True, default='excess',
                            index=True)
    plan_id = fields.Many2one('construction.resource.plan', string='Plan', index=True,
                              ondelete='cascade', check_company=True)
    project_id = fields.Many2one('project.project', string='Obra', required=True, index=True,
                                 check_company=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, index=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    plan_line_id = fields.Many2one('construction.resource.plan.line', string='Línea del plan',
                                   index=True, ondelete='set null', check_company=True)
    task_id = fields.Many2one('project.task', string='Nivel', index=True)
    stage = fields.Selection(related='plan_line_id.stage', string='Etapa', store=True)
    resource_type = fields.Selection(related='plan_line_id.resource_type',
                                     string='Comportamiento', store=True)
    product_id = fields.Many2one('product.product', string='Producto')
    activity_id = fields.Many2one('construction.labor.activity', string='Actividad')
    partner_id = fields.Many2one('res.partner', string='Contrata o proveedor')
    qty = fields.Float(string='Cantidad', digits='Product Unit')
    uom_id = fields.Many2one('uom.uom', string='Unidad')
    amount = fields.Monetary(string='Monto', currency_field='currency_id')
    reason = fields.Text(string='Motivo')
    rework_reason = fields.Selection(REWORK_REASONS, string='Motivo del re-trabajo')
    user_id = fields.Many2one('res.users', string='Autorizado por', required=True,
                              default=lambda self: self.env.user)
    date = fields.Datetime(string='Fecha', required=True, default=fields.Datetime.now)
    document = fields.Char(string='Documento')
    res_model = fields.Char(string='Modelo del documento')
    res_id = fields.Many2oneReference(string='Id del documento', model_field='res_model')

    @api.model
    def _log(self, values):
        """Registra excesos con sudo: quien autoriza (la jefatura) puede no
        tener acceso de escritura al registro (solo lectura para todos)."""
        return self.sudo().create(values)

    def action_open_document(self):
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return False
        return {'type': 'ir.actions.act_window', 'res_model': self.res_model,
                'res_id': self.res_id, 'view_mode': 'form'}
