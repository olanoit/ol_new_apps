# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.tools.zeep.wsse.username import UsernameToken

FACTORY_HKA_DEMO_WSDL = 'https://demoose.thefactoryhka.com.pe/ol-ti-itcpfegem/billService?wsdl'


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_edi_provider = fields.Selection(
        selection_add=[('factory_hka', 'The Factory HKA')],
        ondelete={'factory_hka': 'set default'})
    l10n_pe_edi_factory_hka_username = fields.Char(
        string='Usuario de Factory HKA', groups='base.group_system',
        help='Usuario del servicio web que entrega The Factory HKA.')
    l10n_pe_edi_factory_hka_password = fields.Char(
        string='Contraseña de Factory HKA', groups='base.group_system',
        help='Contraseña del servicio web que entrega The Factory HKA.')
    l10n_pe_edi_factory_hka_wsdl_demo = fields.Char(
        string='WSDL de demostración', default=FACTORY_HKA_DEMO_WSDL,
        help='Servicio de pruebas de Factory HKA: se usa con «Entorno de prueba» activo.')
    l10n_pe_edi_factory_hka_wsdl_prod = fields.Char(
        string='WSDL de producción',
        help='Servicio de producción que indica Factory HKA al habilitar la cuenta.')

    # Funciones que se pueden activar o desactivar por compañía.
    l10n_pe_edi_factory_hka_retention = fields.Boolean(
        string='Comprobantes de retención (CRE) por Factory HKA', default=True,
        help='Envía los comprobantes de retención por Factory HKA. Desactivado, se '
             'envían directo a SUNAT con la clave SOL.')
    l10n_pe_edi_factory_hka_reversal = fields.Boolean(
        string='Reversión del CRE', default=True,
        help='Permite revertir en SUNAT un comprobante de retención aceptado '
             '(resumen de reversiones RR) desde el pago.')

    def _l10n_pe_edi_factory_hka_uses(self, function):
        """True si la compañía usa Factory HKA y tiene activa la función
        (``'retention'`` o ``'reversal'``; la reversión exige el CRE por HKA)."""
        self.ensure_one()
        if self.l10n_pe_edi_provider != 'factory_hka' or not self.l10n_pe_edi_factory_hka_retention:
            return False
        return function == 'retention' or (function == 'reversal' and self.l10n_pe_edi_factory_hka_reversal)

    def _l10n_pe_edi_factory_hka_wsdl(self):
        """WSDL según el modo de prueba de ``l10n_pe_edi``. Sin WSDL de
        producción no se envía: caer al de demostración daría por emitidos
        comprobantes que SUNAT nunca recibió."""
        self.ensure_one()
        if self.l10n_pe_edi_test_env:
            return self.l10n_pe_edi_factory_hka_wsdl_demo or FACTORY_HKA_DEMO_WSDL
        return self.l10n_pe_edi_factory_hka_wsdl_prod

    def _l10n_pe_edi_get_credentials(self, sunat_wsdl=None):
        """Credenciales de Factory HKA, o ``{'error', 'blocking_level'}`` si
        falta configuración (sin excepción, para no cortar el cron del EDI).
        Con el contexto ``l10n_pe_edi_direct_sunat`` (CRE con la función de
        HKA apagada) se usan las de SUNAT."""
        self.ensure_one()
        if self.l10n_pe_edi_provider != 'factory_hka' or self.env.context.get('l10n_pe_edi_direct_sunat'):
            return super()._l10n_pe_edi_get_credentials(sunat_wsdl=sunat_wsdl)
        company_sudo = self.sudo()  # credenciales con groups=base.group_system
        username = company_sudo.l10n_pe_edi_factory_hka_username
        password = company_sudo.l10n_pe_edi_factory_hka_password
        if not username or not password:
            return {'error': self.env._(
                'Faltan el usuario o la contraseña de Factory HKA de %(company)s. '
                'Configúrelos en Ajustes ▸ Contabilidad ▸ Facturación electrónica peruana.',
                company=self.display_name), 'blocking_level': 'error'}
        wsdl = self._l10n_pe_edi_factory_hka_wsdl()
        if not wsdl:
            return {'error': self.env._(
                'Falta el WSDL de producción de Factory HKA de %(company)s. '
                'Configúrelo en Ajustes o active «Entorno de prueba».',
                company=self.display_name), 'blocking_level': 'error'}
        return {'fault_ns': 'S', 'wsdl': wsdl, 'token': UsernameToken(username, password)}
