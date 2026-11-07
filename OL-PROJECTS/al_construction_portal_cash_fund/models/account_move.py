# -*- coding: utf-8 -*-
"""Comprobante registrado en el portal de obra (paquete 6, CR-55): la
factura del proveedor en borrador lleva el fondo con que se pagó, la obra, la
partida y quién lo registró."""
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    construction_portal_fund_id = fields.Many2one(
        'l10n_pe.cash.fund', string='Pagado con el fondo', copy=False, index='btree_not_null',
        readonly=True, help='Caja chica o entrega a rendir con que el residente pagó el '
                            'comprobante que registró en el portal de obra.')
    construction_portal_project_id = fields.Many2one(
        'project.project', string='Obra (portal)', copy=False, readonly=True)
    construction_portal_task_id = fields.Many2one(
        'project.task', string='Partida (portal)', copy=False, readonly=True)
    construction_portal_user_id = fields.Many2one(
        'res.users', string='Registrado en obra por', copy=False, readonly=True)
