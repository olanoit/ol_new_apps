import base64
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.modules import module as module_registry
from odoo.tools import config

_logger = logging.getLogger(__name__)

# Un reporte que sigue en «Generando» pasado este tiempo quedó huérfano (el
# proceso murió a mitad): el cron lo vuelve a tomar.
STALE_GENERATING = timedelta(hours=2)


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
    _check_company_auto = True

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    report_type = fields.Selection(
        [('1301', 'Formato 13.1 — Valorizado'),
         ('1201', 'Formato 12.1 — Físico')], string='Tipo de informe',
        required=True, default='1301')
    group_by_warehouse = fields.Boolean(string='Por almacén')
    include_no_movement = fields.Boolean(string='Incluir sin movimientos', default=True)
    file_format = fields.Selection(
        [('xlsx', 'Excel'), ('pdf', 'PDF')], string='Formato', default='xlsx', required=True)
    warehouse_ids = fields.Many2many('stock.warehouse', string='Almacenes', check_company=True)
    product_ids = fields.Many2many('product.product', string='Productos')
    categ_ids = fields.Many2many('product.category', string='Categorías')

    state = fields.Selection(
        [('pending', 'Pendiente'), ('generating', 'Generando'),
         ('done', 'Listo'), ('empty', 'Sin datos'), ('error', 'Error')],
        default='pending', required=True, string='Estado')
    output_file = fields.Binary(string='Archivo', readonly=True, attachment=True)
    output_filename = fields.Char(readonly=True)
    error_message = fields.Text(string='Mensaje de error', readonly=True)
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user, readonly=True)

    # El cron genera como superusuario: el control es sobre quien lo pide.
    # No es un @api.constrains: el ORM ejecuta las restricciones en sudo y el
    # control debe hacerse con el usuario que crea o modifica el registro.
    def _check_company_allowed(self):
        if self.env.su:
            return
        for rec in self:
            if rec.company_id not in self.env.companies:
                raise ValidationError(self.env._(
                    'La compañía %s no está entre sus compañías activas.', rec.company_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_company_allowed()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'company_id' in vals:
            self._check_company_allowed()
        return res

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
                # Savepoint: si falla una consulta, la transacción queda
                # abortada y ni siquiera se podría guardar el estado «Error».
                with self.env.cr.savepoint():
                    wizard = rec.with_company(rec.company_id)._build_wizard()
                    empty_message = not wizard._has_data() and wizard._no_data_message()
                    if empty_message:
                        # Sin movimientos ni saldos: no se guarda un archivo vacío.
                        content = ext = None
                    elif rec.file_format == 'pdf':
                        content, _ = self.env['ir.actions.report'].with_company(
                            rec.company_id)._render_qweb_pdf(
                            'ol_stock_kardex_pe.report_kardex', wizard.ids)
                        ext = 'pdf'
                    else:
                        content = build_kardex_xlsx(wizard)
                        ext = 'xlsx'
                if empty_message:
                    rec.write({'state': 'empty', 'output_file': False,
                               'output_filename': False, 'error_message': empty_message})
                    if not _in_test_mode():
                        self.env.cr.commit()
                    continue
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
        domain = self._pending_domain()
        pending = self.search(domain, limit=limit)
        pending._generate()
        # Si quedan pendientes, re-despertar el cron.
        if len(pending) == limit and self.search_count(self._pending_domain()):
            cron = self.env.ref('ol_stock_kardex_pe.ir_cron_kardex_generate',
                                raise_if_not_found=False)
            if cron:
                cron._trigger()

    @api.model
    def _pending_domain(self):
        stale = fields.Datetime.now() - STALE_GENERATING
        return ['|', ('state', '=', 'pending'),
                '&', ('state', '=', 'generating'), ('write_date', '<', stale)]

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
