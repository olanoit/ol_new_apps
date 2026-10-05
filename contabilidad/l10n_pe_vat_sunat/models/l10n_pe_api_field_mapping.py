# -*- coding: utf-8 -*-
"""Mapeo dinámico atributo-de-API → campo-de-Odoo.

Cada fila indica de qué **ruta** de la respuesta se toma el valor y en
qué **campo del partner** se escribe, con una transformación opcional.
Es lo que hace que el módulo sea configurable sin tocar código.
"""
from odoo import api, fields, models

TRANSFORMS = [
    ('none', 'Sin transformar'),
    ('upper', 'MAYÚSCULAS'),
    ('lower', 'minúsculas'),
    ('title', 'Título'),
    ('capitalize', 'Primera Mayúscula'),
    ('strip', 'Quitar espacios'),
]

FOR_DOCUMENT = [
    ('ruc', 'Solo RUC'),
    ('dni', 'Solo DNI'),
    ('both', 'Ambos'),
]


class L10nPeApiFieldMapping(models.Model):
    _name = 'l10n_pe.api.field.mapping'
    _description = 'Mapeo de atributo de API a campo de Odoo'
    _order = 'sequence, id'

    connection_id = fields.Many2one(
        'l10n_pe.api.connection', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    for_document = fields.Selection(
        FOR_DOCUMENT, string='Aplica a', default='both', required=True)

    source_path = fields.Char(
        string='Atributo de la API', required=True,
        help="Ruta en la respuesta, con puntos e índices de lista "
             "(p. ej. 'direccion_completa', 'ubigeo.2'). También admite "
             "plantillas con marcadores para concatenar: "
             "'{nombres} {apellido_paterno} {apellido_materno}'.")
    field_id = fields.Many2one(
        'ir.model.fields', string='Campo de Odoo', required=True,
        ondelete='cascade',
        domain="[('model', '=', 'res.partner'), ('store', '=', True), "
               "('ttype', 'in', ['char', 'text', 'boolean', 'selection'])]",
        help="Campo de res.partner donde se escribe el valor.")
    field_name = fields.Char(related='field_id.name', store=True, string='Nombre técnico')
    transform = fields.Selection(
        TRANSFORMS, string='Transformación', default='none', required=True)
    default_value = fields.Char(
        string='Valor por defecto',
        help="Se usa si la ruta no existe o viene vacía en la respuesta.")
    skip_if_empty = fields.Boolean(
        string='Omitir si vacío', default=True,
        help="Si el valor extraído es vacío y no hay valor por defecto, no "
             "sobrescribe el campo del partner.")

    _sql_source = models.Constraint(
        "CHECK (source_path <> '')",
        'La ruta del atributo no puede estar vacía.')

    @api.depends('field_id', 'source_path')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s → %s' % (
                rec.source_path or '?', rec.field_id.name or '?')
