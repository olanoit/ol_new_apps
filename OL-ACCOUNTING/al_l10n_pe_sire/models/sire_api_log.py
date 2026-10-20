import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.modules import module

_logger = logging.getLogger(__name__)

#: Días que se conservan las llamadas; el historial de lo enviado está en
#: las operaciones y en el hilo del periodo, esto es para diagnosticar.
SIRE_LOG_RETENTION_DAYS = 90
#: Bastan para leer el error de SUNAT sin guardar el archivo descargado.
SIRE_LOG_RESPONSE_SIZE = 2000


class L10nPeSireApiLog(models.Model):
    """Bitácora de cada llamada a la API del SIRE.

    Se escribe en su propio cursor: si la llamada falla, la transacción del
    usuario se deshace, pero la respuesta de SUNAT queda para diagnosticar.
    """
    _name = 'l10n_pe.sire.api.log'
    _description = 'Llamada a la API SIRE'
    _order = 'id desc'
    _rec_name = 'endpoint'

    date = fields.Datetime(string='Fecha', readonly=True, default=fields.Datetime.now, index=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True, index=True)
    user_id = fields.Many2one('res.users', string='Usuario', readonly=True)
    res_model = fields.Char(string='Modelo', readonly=True)
    res_id = fields.Many2oneReference(string='Registro', model_field='res_model', readonly=True)
    method = fields.Char(string='Método', readonly=True)
    endpoint = fields.Char(string='Servicio', readonly=True)
    url = fields.Char(string='URL', readonly=True)
    status_code = fields.Integer(string='HTTP', readonly=True, aggregator=False)
    duration = fields.Float(string='Duración (s)', readonly=True, digits=(8, 2))
    is_error = fields.Boolean(string='Error', readonly=True, index=True)
    response = fields.Text(string='Respuesta', readonly=True)

    @api.model
    def _sire_log(self, values):
        """Guarda la llamada sin depender de que la transacción llegue al final."""
        values = dict(values, response=(values.get('response') or '')[:SIRE_LOG_RESPONSE_SIZE])
        if module.current_test:
            # En pruebas no hay un segundo cursor que vea los datos del test.
            self.sudo().create(values)
            return
        try:
            with self.env.registry.cursor() as cr:
                # sudo: la bitácora no la crea ni la edita ningún usuario.
                self.env(cr=cr, su=True)[self._name].create(values)
        except Exception:  # noqa: BLE001 — registrar nunca rompe la llamada
            _logger.warning('No se pudo registrar la llamada SIRE', exc_info=True)

    @api.autovacuum
    def _gc_sire_logs(self):
        limit = fields.Datetime.now() - timedelta(days=SIRE_LOG_RETENTION_DAYS)
        self.sudo().search([('date', '<', limit)]).unlink()
