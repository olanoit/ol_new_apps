# -*- coding: utf-8 -*-
"""W-10 «Exceso sobre plan»: se abre al pedir la aprobación de un
requerimiento de obra o al confirmar una OF que piden más de lo que queda en
el plan, o al confirmar una OC con analítica de la obra que pasa su
presupuesto analítico. Con la política «avisar» basta confirmar; con «pedir
aprobación» la justificación es obligatoria y el requerimiento recibe una
revisión más (la OF y la OC las confirma la jefatura del planificador).

Cada documento lo agrega su puente (v1.7): su campo, sus líneas de exceso
(_exceed_lines) y su confirmación (_confirm_document)."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from ..models.common import PROJECT_HEAD_GROUPS


class ConstructionPlanExceedWizard(models.TransientModel):
    _name = 'construction.plan.exceed.wizard'
    _description = 'Exceso sobre el plan'

    policy = fields.Selection(
        [('warn', 'Avisar'), ('approval', 'Pedir aprobación'), ('block', 'Bloquear')],
        string='Política', compute='_compute_lines', store=True)
    reason = fields.Text(string='Justificación')
    by_amount = fields.Boolean(
        string='Por montos', compute='_compute_lines', store=True,
        help='El exceso es de montos (combinaciones del presupuesto), no de productos.')
    line_ids = fields.One2many(
        'construction.plan.exceed.wizard.line', 'wizard_id', string='Exceso',
        compute='_compute_lines', store=True)

    @api.depends()
    def _compute_lines(self):
        for wizard in self:
            policy, lines = wizard._exceed_lines()
            wizard.policy = policy
            wizard.by_amount = bool(lines) and all(vals.get('name') for vals in lines)
            wizard.line_ids = [Command.clear()] + [Command.create(vals) for vals in lines]

    def _exceed_lines(self):
        """(política, [valores de línea]) del documento del asistente: cada
        puente resuelve el suyo y llama a super() para los demás."""
        self.ensure_one()
        return False, []

    def _get_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Exceso sobre el plan'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _check_head_approval(self, document):
        """La OF y la OC con exceso «pedir aprobación» las confirma la jefatura."""
        if self.policy == 'approval' and not self.env.user.has_groups(PROJECT_HEAD_GROUPS):
            raise UserError(self.env._(
                'El exceso lo aprueba la jefatura de proyectos: pídale que confirme '
                '%s.', document.name))

    def _exceed_values(self, reason):
        values = {'construction_exceed_state': (
            'approved' if self.policy == 'approval' else 'exceeded')}
        if reason:
            values['construction_exceed_reason'] = reason
        return values

    def _confirm_document(self, reason):
        """Confirma el documento con el exceso aceptado; lo da el puente."""
        raise UserError(self.env._('No hay documento que confirmar.'))

    def action_confirm(self):
        self.ensure_one()
        reason = (self.reason or '').strip()
        if self.policy == 'approval' and not reason:
            raise UserError(self.env._('Escriba la justificación del exceso.'))
        res = self._confirm_document(reason)
        return res if isinstance(res, dict) else {'type': 'ir.actions.act_window_close'}


class ConstructionPlanExceedWizardLine(models.TransientModel):
    _name = 'construction.plan.exceed.wizard.line'
    _description = 'Material que excede el plan'

    wizard_id = fields.Many2one(
        'construction.plan.exceed.wizard', string='Asistente', required=True,
        ondelete='cascade')
    name = fields.Char(string='Concepto', help='Combinación del presupuesto analítico (OC).')
    product_id = fields.Many2one('product.product', string='Producto')
    product_uom_id = fields.Many2one('uom.uom', string='Unidad')
    qty_remaining = fields.Float(string='Saldo', digits='Product Unit')
    qty_requested = fields.Float(string='Pedido', digits='Product Unit')
    qty_excess = fields.Float(string='Exceso', digits='Product Unit')
