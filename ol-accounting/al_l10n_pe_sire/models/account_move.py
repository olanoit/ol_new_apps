from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_sire_goods_class = fields.Selection(
        selection=[
            ('1', '1 - Mercadería, materia prima, suministro, envases y embalajes'),
            ('2', '2 - Activo fijo'),
            ('3', '3 - Otros activos no considerados en 1 y 2'),
            ('4', '4 - Gastos de educación, recreación, salud, culturales y otros'),
            ('5', '5 - Otros gastos no incluidos en 4'),
        ],
        string='Clasificación de bienes y servicios',
        help='Tabla 30 SUNAT — columna "Clasif de Bss y Sss" del RCE. Obligatoria '
             'para contribuyentes con ingresos mayores a 1500 UIT.')
