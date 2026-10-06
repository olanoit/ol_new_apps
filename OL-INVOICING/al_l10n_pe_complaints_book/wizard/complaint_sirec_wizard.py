import base64

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nPeComplaintSirecWizard(models.TransientModel):
    """Archivo de carga masiva del SIREC (Directiva 004-2014/DIR-COD-INDECOPI).

    Un registro por línea separado por «|»; los opcionales vacíos conservan
    su separador. Cada reclamo y su respuesta se reportan en 30 días
    calendario desde su presentación.
    """
    _name = 'l10n_pe.complaint.sirec.wizard'
    _description = 'Exportación al SIREC'

    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    date_from = fields.Date(string='Desde', required=True,
                            default=lambda self: fields.Date.context_today(self).replace(day=1)
                            - relativedelta(months=1))
    date_to = fields.Date(string='Hasta', required=True,
                          default=lambda self: fields.Date.context_today(self).replace(day=1)
                          - relativedelta(days=1))
    book_ids = fields.Many2many('l10n_pe.complaint.book', string='Libros',
                                domain="[('company_id', '=', company_id)]",
                                help='Vacío: todos los libros de la compañía.')
    only_pending = fields.Boolean(string='Solo las no reportadas', default=True)
    mark_reported = fields.Boolean(string='Marcar como reportadas', default=True)
    file = fields.Binary(string='Archivo', readonly=True)
    filename = fields.Char(readonly=True)
    count = fields.Integer(string='Hojas exportadas', readonly=True)

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.book_ids = False

    def _complaints(self):
        domain = [('company_id', '=', self.company_id.id),
                  ('date_submitted', '>=', fields.Datetime.to_datetime(self.date_from)),
                  ('date_submitted', '<', fields.Datetime.to_datetime(self.date_to + relativedelta(days=1)))]
        if self.book_ids:
            domain.append(('book_id', 'in', self.book_ids.ids))
        if self.only_pending:
            domain.append(('sirec_state', '=', 'pending'))
        return self.env['l10n_pe.complaint'].search(domain, order='book_id, name')

    def action_export(self):
        self.ensure_one()
        complaints = self._complaints()
        if not complaints:
            raise UserError(_('No hay hojas de reclamación en el periodo.'))
        without_code = complaints.book_id.filtered(lambda b: not b.sirec_site_code)
        if without_code:
            raise UserError(_('Indique el código de sede SIREC de: %s.',
                              ', '.join(without_code.mapped('name'))))
        content = '\r\n'.join('|'.join(c._sirec_row()) for c in complaints)
        self.write({
            'file': base64.b64encode(content.encode('utf-8')),
            'filename': 'SIREC_%s_%s_%s.txt' % (self.company_id.vat or '', self.date_from.strftime('%Y%m%d'),
                                                self.date_to.strftime('%Y%m%d')),
            'count': len(complaints),
        })
        if self.mark_reported:
            complaints.write({'sirec_state': 'reported',
                              'sirec_report_date': fields.Date.context_today(self)})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
