from odoo import fields, models


class L10nPeSireCompareField(models.Model):
    """Campo a incluir en la comparación SIRE vs Sistema.

    La secuencia define el orden en que se listan las diferencias; desactivar
    un registro lo excluye de la comparación (p. ej. razón social, cuyo texto
    nunca coincide literalmente entre SUNAT y Odoo).
    """
    _name = 'l10n_pe.sire.compare.field'
    _description = 'Campo de comparación SIRE'
    _order = 'book_type, sequence, id'

    name = fields.Char(string='Columna', required=True, translate=True)
    field_name = fields.Char(
        string='Campo técnico', required=True,
        help='Nombre del campo en las líneas SIRE/Sistema.')
    book_type = fields.Selection(
        selection=[('rce', 'RCE — Compras'), ('rvie', 'RVIE — Ventas')],
        string='Registro', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _field_book_uniq = models.Constraint(
        'unique (book_type, field_name)',
        'El campo ya está configurado para este registro.')
