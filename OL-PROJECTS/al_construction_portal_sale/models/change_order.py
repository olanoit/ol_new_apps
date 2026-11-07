# -*- coding: utf-8 -*-
"""Cambio de obra registrado en el portal (paquete 6, CR-53): quién lo pidió
por el cliente, su firma en la pantalla, las fotos y lo que el residente vio
en obra (partidas afectadas, partida nueva y metrado estimado). Lo valoriza
el coordinador en el escritorio con las líneas de siempre."""
from odoo import fields, models


class ConstructionChangeOrder(models.Model):
    _inherit = 'construction.change.order'

    construction_portal_user_id = fields.Many2one(
        'res.users', string='Registrado en obra por', readonly=True, copy=False,
        help='El residente que registró el cambio en el portal de obra.')
    construction_client_rep_name = fields.Char(
        string='Lo pidió (cliente)', copy=False,
        help='Nombre del representante del cliente que pidió el cambio en obra.')
    construction_client_rep_role = fields.Char(string='Cargo de quien lo pidió', copy=False)
    construction_client_signature = fields.Binary(
        string='Firma del cliente', attachment=True, copy=False)
    construction_portal_task_ids = fields.Many2many(
        'project.task', 'construction_change_portal_task_rel', 'change_id', 'task_id',
        string='Partidas afectadas', copy=False,
        help='Las partidas que el residente marcó en obra; las líneas las arma el coordinador.')
    construction_portal_new_item = fields.Char(
        string='Partida nueva', copy=False,
        help='Lo que pide el cliente y no está en el presupuesto.')
    construction_portal_qty_estimate = fields.Char(
        string='Metrado estimado', copy=False)
    construction_portal_attachment_ids = fields.Many2many(
        'ir.attachment', 'construction_change_portal_attachment_rel', 'change_id',
        'attachment_id', string='Fotos de obra', copy=False)
    construction_record_sent_to_id = fields.Many2one(
        'res.partner', string='Constancia enviada a', readonly=True, copy=False)
