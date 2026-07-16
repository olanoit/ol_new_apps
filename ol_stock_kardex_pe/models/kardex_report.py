import base64
import logging

from odoo import api, fields, models
from odoo.modules import module as module_registry
from odoo.tools import config

_logger = logging.getLogger(__name__)


def _in_test_mode():
    return bool(config['test_enable']) or module_registry.current_test


class L10nPeKardexReport(models.Model):
    """Archivo de Kardex generado (en segundo plano o a demanda).

    Guarda el resultado de una corrida del kardex para volúmenes grandes:
    el wizard crea el registro, el cron lo procesa reutilizando el mismo motor
    de la vista SQL, y el usuario descarga el archivo cuando el estado es
    'done'. Evita bloquear la interfaz con reportes de miles de movimientos.
    """
    _name = 'l10n_pe.kardex.report'
    _description = 'Kardex SUNAT generado'
    _order = 'create_date desc'

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    report_type = fields.Selection(
        [('1301', 'Formato 13.1 — Valorizado'),
         ('1201', 'Formato 12.1 — Físico')],
        required=True, default='1301')
    group_by_warehouse = fields.Boolean(string='Por almacén')
    include_no_movement = fields.Boolean(string='Incluir sin movimientos', default=True)
    file_format = fields.Selection(
        [('xlsx', 'Excel'), ('pdf', 'PDF')], default='xlsx', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', string='Almacenes')
    product_ids = fields.Many2many('product.product', string='Productos')
    categ_ids = fields.Many2many('product.category', string='Categorías')

    state = fields.Selection(
        [('pending', 'Pendiente'), ('generating', 'Generando'),
         ('done', 'Listo'), ('error', 'Error')],
        default='pending', required=True, string='Estado')
    output_file = fields.Binary(string='Archivo', readonly=True, attachment=True)
    output_filename = fields.Char(readonly=True)
    error_message = fields.Text(readonly=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)

    @api.depends('report_type', 'date_from', 'date_to')
    def _compute_name(self):
        for rec in self:
            rec.name = 'Kardex %s · %s a %s' % (
                '13.1' if rec.report_type == '1301' else '12.1',
                rec.date_from or '?', rec.date_to or '?')

    def _enqueue(self):
        """Despierta el cron para procesar los pendientes cuanto antes."""
        self.write({'state': 'pending'})
        cron = self.env.ref('ol_stock_kardex_pe.ir_cron_kardex_generate',
                            raise_if_not_found=False)
        if cron:
            cron._trigger()

    def _build_wizard(self):
        self.ensure_one()
        return self.env['l10n_pe.kardex.report.wizard'].create({
            'company_id': self.company_id.id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'report_type': self.report_type,
            'group_by_warehouse': self.group_by_warehouse,
            'include_no_movement': self.include_no_movement,
            'warehouse_ids': [(6, 0, self.warehouse_ids.ids)],
            'product_ids': [(6, 0, self.product_ids.ids)],
            'categ_ids': [(6, 0, self.categ_ids.ids)],
        })

    def _generate(self):
        from ..reports.kardex_xlsx import build_kardex_xlsx
        for rec in self:
            rec.state = 'generating'
            # Commit del estado para que el usuario vea el progreso aunque la
            # generación sea larga.
            if not _in_test_mode():
                self.env.cr.commit()
            try:
                wizard = rec.with_company(rec.company_id)._build_wizard()
                if rec.file_format == 'pdf':
                    content, _ = self.env['ir.actions.report'].with_company(
                        rec.company_id)._render_qweb_pdf(
                        'ol_stock_kardex_pe.report_kardex', wizard.ids)
                    ext, mimetype = 'pdf', 'application/pdf'
                else:
                    content = build_kardex_xlsx(wizard)
                    ext = 'xlsx'
                rec.write({
                    'state': 'done',
                    'output_file': base64.b64encode(content),
                    'output_filename': 'KARDEX_%s_%s%02d.%s' % (
                        rec.report_type, rec.date_from.year, rec.date_from.month, ext),
                    'error_message': False,
                })
            except Exception as e:  # noqa: BLE001
                _logger.exception('Error generando kardex %s', rec.id)
                rec.state = 'error'
                rec.error_message = str(e)
            if not _in_test_mode():
                self.env.cr.commit()

    @api.model
    def _cron_generate(self, limit=20):
        pending = self.search([('state', '=', 'pending')], limit=limit)
        pending._generate()
        # Si quedan pendientes, re-despertar el cron.
        if len(pending) == limit and self.search_count([('state', '=', 'pending')]):
            cron = self.env.ref('ol_stock_kardex_pe.ir_cron_kardex_generate',
                                raise_if_not_found=False)
            if cron:
                cron._trigger()

    def action_download(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?' + '&'.join([
                'model=l10n_pe.kardex.report', 'id=%s' % self.id,
                'filename_field=output_filename', 'field=output_file',
                'download=true']),
            'target': 'new',
        }
