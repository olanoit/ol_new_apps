# -*- coding: utf-8 -*-
import json
import logging
import time

from odoo import api, fields, models
from odoo.modules import module as odoo_module
from odoo.exceptions import UserError
from odoo.tools.misc import format_datetime

_logger = logging.getLogger(__name__)

GENERATE_STATES = [
    ('queued', 'En cola'),
    ('running', 'Generando'),
    ('done', 'Terminado'),
    ('failed', 'Falló'),
]
# Ambientes por tanda del proceso en segundo plano (cada tanda se guarda).
GENERATE_CHUNK = 10


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    # Paquete 1.18, M118-05: «Generar plan» en segundo plano, con avance y un
    # solo proceso por plan.
    construction_generate_state = fields.Selection(
        GENERATE_STATES, string='Generación', readonly=True, copy=False)
    construction_generate_info = fields.Char(string='Avance de la generación', readonly=True,
                                             copy=False)
    construction_generate_started = fields.Datetime(string='Generación desde', readonly=True,
                                                    copy=False)
    construction_generate_params = fields.Text(readonly=True, copy=False)
    construction_generate_user_id = fields.Many2one('res.users', readonly=True, copy=False)

    def _construction_generate_busy(self):
        self.ensure_one()
        return self.construction_generate_state in ('queued', 'running')

    def _construction_check_not_generating(self):
        for plan in self.filtered(lambda p: p._construction_generate_busy()):
            raise UserError(self.env._(
                'Generación en curso desde las %s: espere a que termine.',
                format_datetime(self.env, plan.construction_generate_started, dt_format='HH:mm')))

    def action_open_generate_wizard(self):
        self.ensure_one()
        self._check_draft()
        self._construction_check_not_generating()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Generar plan'),
            'res_model': 'construction.plan.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_plan_id': self.id},
        }

    # ------------------------------------------------------------------
    # Segundo plano
    # ------------------------------------------------------------------
    def _construction_enqueue_generate(self, params, total):
        """Deja la generación en cola y dispara la acción programada
        (decisión D1 del diseño: ``ir.cron._trigger``, sin dependencias)."""
        self.ensure_one()
        self.write({
            'construction_generate_state': 'queued',
            'construction_generate_started': fields.Datetime.now(),
            'construction_generate_params': json.dumps(params),
            'construction_generate_user_id': self.env.uid,
            'construction_generate_info': self.env._('En cola: %s ambientes', total),
        })
        self.env.ref('al_construction_planner_furniture.ir_cron_construction_generate')._trigger()

    @api.model
    def _cron_construction_generate(self):
        plans = self.search([('construction_generate_state', '=', 'queued')], order='id')
        for plan in plans:
            plan._construction_run_generate()

    def _construction_commit(self):
        # En las pruebas no se confirma la transacción.
        if not odoo_module.current_test:
            self.env.cr.commit()

    def _construction_rollback(self):
        if not odoo_module.current_test:
            self.env.cr.rollback()

    def _construction_run_generate(self):
        """Corre la generación encolada por tandas de ambientes, guardando el
        avance después de cada una. Hace lo mismo que «Generar» en primer
        plano (persona-días, personal propio a jornal ÷ rendimiento, base
        anotada y rendimiento inicial, M119-01)."""
        self.ensure_one()
        params = json.loads(self.construction_generate_params or '{}')
        user = self.construction_generate_user_id or self.env.user
        plan = self.with_user(user).with_company(self.company_id)
        space_ids = params.pop('space_ids', [])
        total = len(space_ids)
        started = time.time()
        self.write({'construction_generate_state': 'running'})
        self._construction_commit()
        Wizard = plan.env['construction.plan.generate.wizard']
        modules = lines = 0
        current = None
        try:
            for start in range(0, total, GENERATE_CHUNK):
                chunk = space_ids[start:start + GENERATE_CHUNK]
                current = plan.env['project.task'].browse(chunk)
                wizard = Wizard.create(dict(
                    params, plan_id=plan.id, space_task_ids=[(6, 0, chunk)],
                    schedule_mode='none'))
                result = wizard._construction_generate_now(post=False)
                modules += result['modules']
                lines += result['lines']
                self.write({'construction_generate_info': self.env._(
                    'Generando: %(done)s de %(total)s ambientes · %(lines)s líneas · %(seconds)s s',
                    done=min(start + GENERATE_CHUNK, total), total=total, lines=lines,
                    seconds=int(time.time() - started))})
                self._construction_commit()
            # El ritmo, una sola vez con todos los ambientes.
            if params.get('schedule_mode') and params['schedule_mode'] != 'none':
                wizard = Wizard.create(dict(params, plan_id=plan.id,
                                            space_task_ids=[(6, 0, space_ids)]))
                wizard._construction_schedule(plan.env['project.task'].browse(space_ids))
        except Exception as error:  # noqa: BLE001 — se informa y se guarda el fallo
            self._construction_rollback()
            _logger.exception('Generar plan en segundo plano falló (plan %s)', self.id)
            where = current[:1].display_name if current else ''
            message = self.env._('La generación falló en %(where)s: %(error)s',
                                 where=where or '—', error=error)
            self.write({'construction_generate_state': 'failed',
                        'construction_generate_info': message[:250]})
            self.message_post(body=message, partner_ids=user.partner_id.ids)
            self._construction_commit()
            return
        seconds = int(time.time() - started)
        self.write({'construction_generate_state': 'done', 'construction_generate_info': (
            self.env._('Terminado: %(modules)s tareas de módulo y %(lines)s líneas en %(total)s '
                       'ambientes (%(seconds)s s)', modules=modules, lines=lines, total=total,
                       seconds=seconds))})
        # La notificación: un mensaje en el plan para quien lo pidió, con el
        # vínculo a las líneas.
        self.message_post(
            body=self.env._(
                'Plan generado en segundo plano: %(modules)s tareas de módulo y %(lines)s líneas '
                'en %(total)s ambientes (%(seconds)s s). Vea las líneas del plan.',
                modules=modules, lines=lines, total=total, seconds=seconds),
            partner_ids=user.partner_id.ids)
        self._construction_commit()
