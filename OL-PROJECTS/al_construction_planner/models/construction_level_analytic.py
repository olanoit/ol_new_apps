# -*- coding: utf-8 -*-
"""Analítica nativa por nivel del árbol (paquete 1.16, M116-05).

El planificador comanda la analítica de Odoo: cada nivel de la plantilla
puede llevar un plan analítico y la cuenta de cada tarea de ese nivel sale de
un catálogo compartido por todas las obras, se crea por obra o es mixta. La
distribución de la línea del plan suma las cuentas de los niveles de su ruta;
todo lo que hereda esa distribución (requerimiento, compra, consumo, factura
de contrata, presupuesto nativo) las recibe sin cambios propios. Sin plan en
ningún nivel no cambia nada."""
import re

from odoo import api, fields, models

ANALYTIC_MODES = [
    ('catalog', 'Catálogo'),
    ('mixed', 'Mixto'),
    ('project', 'Por obra'),
]

# Código de la tarea: el número de partida al inicio del nombre (13.0102).
TASK_CODE = re.compile(r'^\s*(\d[\d.]*)')


class ConstructionLevelTemplateLine(models.Model):
    _inherit = 'construction.level.template.line'

    analytic_plan_id = fields.Many2one(
        'account.analytic.plan', string='Plan analítico',
        help='Vacío: el nivel no va a la analítica.')
    analytic_mode = fields.Selection(
        ANALYTIC_MODES, string='Modo de la cuenta', default='project',
        help='Catálogo: una cuenta del plan, compartida por todas las obras, que elige la '
             'columna de catálogo de la hoja; nunca se crea desde el título. Mixto: la del '
             'catálogo si la fila la trae; si no, una por obra. Por obra: una cuenta por tarea '
             'con código «obra-código de la tarea».')


class ConstructionLevelTemplate(models.Model):
    _inherit = 'construction.level.template'

    def action_construction_apply_analytics(self):
        """Aplica la analítica por nivel a las obras ya cargadas con estas
        plantillas (M116-05, punto 7): crea las cuentas de las tareas de los
        niveles con plan, recalcula la distribución de las líneas de los planes
        abiertos y regenera el presupuesto nativo de los aprobados o en
        ejecución. No toca apuntes contabilizados."""
        from .construction_resource_plan import OPEN_STATES
        projects = self.env['project.project'].search(
            [('construction_level_template_id', 'in', self.ids)])
        tasks = self.env['project.task'].search([
            ('project_id', 'in', projects.ids),
            ('construction_level_line_id.analytic_plan_id', '!=', False),
            ('construction_analytic_account_id', '=', False)])
        tasks._construction_ensure_level_account()
        plans = self.env['construction.resource.plan'].search([
            ('project_id', 'in', projects.ids), ('state', 'in', ('draft',) + tuple(OPEN_STATES))])
        plans.line_ids.with_context(construction_plan_force=True)._apply_analytic_rules()
        plans.filtered(lambda p: p.state in OPEN_STATES)._construction_refresh_budget()
        for plan in plans:
            plan.message_post(body=self.env._(
                'Analítica por nivel aplicada: distribución de las líneas recalculada.'))
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'success', 'message': self.env._(
                '%(tasks)s cuentas creadas; %(plans)s planes recalculados en %(projects)s obras.',
                tasks=len(tasks), plans=len(plans), projects=len(projects))},
        }


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Cuenta analítica del nivel', index='btree_not_null',
        copy=False, ondelete='restrict',
        help='La cuenta del plan analítico de su nivel (paquete 1.16, M116-05).')
    construction_analytic_own = fields.Boolean(
        string='Cuenta propia del nivel', copy=False, readonly=True,
        help='La cuenta la creó el planificador para esta tarea: sigue su nombre y se archiva '
             'con ella.')

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        tasks._construction_ensure_level_account()
        return tasks

    def write(self, vals):
        res = super().write(vals)
        if 'construction_level_line_id' in vals:
            self._construction_ensure_level_account()
        if 'name' in vals:
            # En modo «Por obra», la cuenta sigue el nombre de la tarea.
            for task in self.filtered('construction_analytic_own'):
                task.construction_analytic_account_id.sudo().name = task.name
        if 'active' in vals and not vals['active']:
            self._construction_archive_level_accounts()
        return res

    def _construction_level_account_code(self):
        self.ensure_one()
        project = self.project_id
        site = project.account_id.code or (project.name or '').split(' ')[0] or str(project.id)
        match = TASK_CODE.match(self.name or '')
        return '%s-%s' % (site, match.group(1).rstrip('.') if match else self.id)

    def _construction_ensure_level_account(self):
        """Crea la cuenta de las tareas de un nivel con plan analítico en modo
        «Por obra» o «Mixto» que aún no la tienen."""
        Account_sudo = self.env['account.analytic.account'].sudo()
        for task in self:
            level = task.construction_level_line_id
            if not level.analytic_plan_id or task.construction_analytic_account_id \
                    or level.analytic_mode == 'catalog':
                continue
            # La cuenta es configuración contable: la crea el sistema por quien
            # arma el árbol de la obra (Oficina Técnica).
            account_sudo = Account_sudo.create({
                'name': task.name,
                'code': task._construction_level_account_code(),
                'plan_id': level.analytic_plan_id.id,
                'company_id': task.project_id.company_id.id or False,
            })
            task.write({'construction_analytic_account_id': account_sudo.id,
                        'construction_analytic_own': True})

    def _construction_archive_level_accounts(self):
        """La cuenta propia se archiva solo si ninguna otra tarea activa la usa."""
        accounts = self.filtered('construction_analytic_own').construction_analytic_account_id
        if not accounts:
            return
        used = self.search([('construction_analytic_account_id', 'in', accounts.ids)])
        (accounts - used.construction_analytic_account_id).sudo().active = False

    def _construction_path_accounts(self):
        """Cuentas analíticas de los niveles de la ruta de la tarea (ella y
        sus ancestros)."""
        accounts = self.env['account.analytic.account']
        node = self
        while node:
            accounts |= node.construction_analytic_account_id
            node = node.parent_id
        return accounts

    def _construction_rubro_account(self):
        """Cuenta «Rubro» del ambiente (gancho del puente de mobiliario)."""
        self.ensure_one()
        return self.env['account.analytic.account']

    @api.model
    def _construction_catalog_account(self, level, value):
        """Cuenta del catálogo del plan del nivel por su código o su nombre."""
        Account = self.env['account.analytic.account'].with_context(active_test=False)
        if not value or not level.analytic_plan_id:
            return Account
        domain = [('plan_id', 'child_of', level.analytic_plan_id.id)]
        text = value.strip()
        return Account.search(domain + [('code', '=ilike', text)], limit=1) \
            or Account.search(domain + [('name', '=ilike', text)], limit=1)
