from odoo import fields, models


class Website(models.Model):
    _inherit = 'website'

    l10n_pe_complaint_show_link = fields.Boolean(
        string='Enlace al libro de reclamaciones en el pie', default=True,
        help='Enlace visible y permanente en todas las páginas (Código, art. 151; '
             'Reglamento, art. 9 y Anexo III).')

    def _l10n_pe_complaint_books(self):
        """Libros activos publicados en este sitio.

        sudo: el visitante anónimo no lee libros, pero el formulario y el enlace
        del pie los necesitan; solo se exponen nombre, código y dirección.
        """
        self.ensure_one()
        return self.env['l10n_pe.complaint.book'].sudo().search([
            ('website_ids', 'in', self.ids), ('active', '=', True)])
