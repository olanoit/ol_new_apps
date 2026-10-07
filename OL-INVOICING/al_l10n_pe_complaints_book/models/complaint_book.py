from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class L10nPeComplaintBook(models.Model):
    """Un libro de reclamaciones: uno por establecimiento o canal (Reglamento, arts. 4 y 7).

    El código de identificación (art. 8) distingue los libros de un mismo
    proveedor; la numeración es correlativa por libro y año, con el formato
    ``000000001-AAAA`` del Anexo I.
    """
    _name = 'l10n_pe.complaint.book'
    _description = 'Libro de reclamaciones'
    _inherit = ['mail.thread']
    _order = 'company_id, sequence, id'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True, tracking=True,
                       help='Nombre del establecimiento o canal, p. ej. «Tienda virtual».')
    code = fields.Char(string='Código de identificación', required=True, tracking=True,
                       help='Código del libro (Reglamento, art. 8); aparece en la hoja.')
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, index=True,
                                 default=lambda self: self.env.company)
    address = fields.Text(
        string='Domicilio del establecimiento', required=True,
        compute='_compute_address', store=True, readonly=False, precompute=True,
        help='Domicilio donde se coloca el libro; en un libro virtual, el domicilio fiscal.')
    book_type = fields.Selection(
        selection=[('virtual', 'Virtual'), ('physical', 'Físico')],
        string='Tipo de libro', required=True, default='virtual', tracking=True,
        help='Se indica en el aviso del Anexo II.')
    is_backup = fields.Boolean(
        string='Libro de respaldo',
        help='Libro físico de respaldo del virtual (art. 4-A): lo anotado se pasa al '
             'virtual en un día calendario.')
    sequence_id = fields.Many2one(
        'ir.sequence', string='Numeración', readonly=True, copy=False,
        help='Correlativa por año, sin huecos.',
        check_company=True)
    website_ids = fields.Many2many(
        'website', string='Sitios web',
        help='Sitios donde se publica este libro. Sin sitios, el libro no se ofrece en la web.')
    user_ids = fields.Many2many(
        'res.users', string='Responsables', domain=[('share', '=', False)],
        help='Reciben el aviso de cada hoja nueva y las alertas de plazo.')
    notify_email = fields.Char(
        string='Correo de aviso adicional',
        help='Buzón que recibe una copia de cada hoja registrada.')
    sirec_site_code = fields.Char(
        string='Código de sede SIREC', size=6,
        help='Código que asigna el SIREC a esta sede (6 caracteres).')
    complaint_ids = fields.One2many('l10n_pe.complaint', 'book_id', string='Hojas')
    complaint_count = fields.Integer(string='Número de hojas', compute='_compute_complaint_count')

    _code_company_uniq = models.Constraint(
        'unique (company_id, code)',
        'El código de identificación ya existe en otro libro de la compañía.')

    @api.depends('company_id')
    def _compute_address(self):
        for book in self:
            if not book.address and book.company_id:
                partner = book.company_id.partner_id
                book.address = ', '.join(filter(None, [
                    partner.street, partner.street2, partner.city,
                    partner.state_id.name, partner.country_id.name]))

    def _compute_complaint_count(self):
        counts = dict(self.env['l10n_pe.complaint']._read_group(
            [('book_id', 'in', self.ids)], ['book_id'], ['__count']))
        for book in self:
            book.complaint_count = counts.get(book, 0)

    @api.constrains('website_ids', 'company_id')
    def _check_website_company(self):
        for book in self:
            if any(w.company_id and w.company_id != book.company_id for w in book.website_ids):
                raise ValidationError(_(
                    'El libro %s solo puede publicarse en sitios web de su compañía.', book.name))

    @api.model_create_multi
    def create(self, vals_list):
        books = super().create(vals_list)
        for book in books:
            book.sequence_id = book._create_sequence()
        return books

    def _create_sequence(self):
        """Numeración del Anexo I: nueve dígitos y el año (``000000001-2026``)."""
        self.ensure_one()
        # sudo: el responsable de reclamos no administra secuencias, pero cada
        # libro necesita la suya.
        sequence_sudo = self.env['ir.sequence'].sudo().create({
            'name': _('Libro de reclamaciones %s', self.code),
            'code': 'l10n_pe.complaint.%s' % self.id,
            'implementation': 'no_gap',
            'padding': 9,
            'suffix': '-%(range_year)s',
            'use_date_range': True,
            'company_id': self.company_id.id,
        })
        return sequence_sudo

    def _next_number(self, date):
        """Siguiente número correlativo del año de ``date``."""
        self.ensure_one()
        if not self.sequence_id:
            self.sequence_id = self._create_sequence()
        # sudo: el formulario público y los usuarios de atención no leen ir.sequence.
        sequence_sudo = self.sequence_id.sudo()
        return sequence_sudo.next_by_id(sequence_date=date)

    def action_view_complaints(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_l10n_pe_complaints_book.action_complaint')
        action['domain'] = [('book_id', '=', self.id)]
        action['context'] = {'default_book_id': self.id}
        return action

    def action_print_notice(self):
        return self.env.ref('al_l10n_pe_complaints_book.action_report_book_notice').report_action(self)

    def _get_public_url(self):
        self.ensure_one()
        return '/libro-reclamaciones?libro=%s' % self.id
