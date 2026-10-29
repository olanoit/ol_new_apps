# -*- coding: utf-8 -*-
import copy
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AlPeDemo(models.AbstractModel):
    """Ayudas para los datos de demostración de la suite peruana.

    Cada módulo añade aquí su método ``_load_demo_<módulo>`` y lo llama desde
    su archivo de la clave ``demo`` del manifiesto, de modo que solo se carga en
    bases con datos de demostración. Los datos van a «PE Company»
    (``base.demo_company_pe``, de la demo de ``l10n_pe``), quedan con un xmlid
    del módulo en ``noupdate`` y cada carga es idempotente.
    """
    _name = 'al.pe.demo'
    _description = 'Datos de demostración de la localización peruana'

    @api.model
    def _demo_load(self, method):
        """Ejecuta ``method`` (un ``_load_demo_*``) en su propio punto de
        guardado. Si falla, se deshace solo ese ejemplo, se avisa en el log y
        la instalación sigue: un dato de demostración nunca debe impedir
        instalar o actualizar el módulo."""
        self.env.flush_all()
        cr = self.env.cr
        callbacks = [(queue, list(queue._funcs), {key: copy.copy(value) for key, value in queue.data.items()})
                     for queue in (cr.precommit, cr.postcommit)]
        try:
            with cr.savepoint():
                getattr(self, method)()
                self.env.flush_all()
        except Exception:  # noqa: BLE001 - se informa y se sigue sin la demo
            # Lo pendiente en la caché y en las tareas del commit (p. ej. el
            # rango de los contactos) es del ejemplo deshecho: se descarta
            # para que no apunte a registros que ya no existen.
            self.env.transaction.clear()
            for queue, funcs, data in callbacks:
                queue._funcs.clear()
                queue._funcs.extend(funcs)
                for key in list(queue.data):
                    if key not in data:
                        del queue.data[key]
                    elif isinstance(queue.data[key], (dict, set)):
                        # en el mismo objeto: las tareas lo tienen referenciado
                        queue.data[key].clear()
                        queue.data[key].update(data[key])
                    elif isinstance(queue.data[key], list):
                        queue.data[key][:] = data[key]
                    else:
                        queue.data[key] = data[key]
            _logger.warning('No se cargaron los datos de demostración %s.', method, exc_info=True)

    @api.model
    def _demo_company(self):
        """«PE Company» con el plan contable de Perú, o vacío si no existe."""
        company = self.env.ref('base.demo_company_pe', raise_if_not_found=False)
        if not company or company.chart_template != 'pe':
            _logger.info('Sin la compañía demo de Perú: no se cargan datos de demostración PE.')
            return self.env['res.company']
        return company

    @api.model
    def _demo_env(self, company):
        """Entorno sobre ``company`` (superusuario, como toda la carga de datos)."""
        return self.with_company(company).with_context(allowed_company_ids=company.ids).env

    @api.model
    def _demo_ref(self, xmlid):
        return self.env.ref(xmlid, raise_if_not_found=False)

    @api.model
    def _demo_record(self, xmlid, records, vals):
        """Registro con ``xmlid``; si no existe, lo crea con ``vals`` en el
        modelo de ``records`` y le asigna el xmlid (``noupdate``)."""
        record = self._demo_ref(xmlid)
        if record:
            return record
        record = records.create(vals)
        self._demo_xmlid(xmlid, record)
        return record

    @api.model
    def _demo_xmlid(self, xmlid, record):
        self.env['ir.model.data']._update_xmlids([{'xml_id': xmlid, 'record': record, 'noupdate': True}])

    @api.model
    def _demo_ruc(self, base10):
        """RUC con su dígito verificador (módulo 11 de SUNAT)."""
        total = sum(int(d) * w for d, w in zip(base10, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
        return base10 + str((11 - total % 11) % 10)

    @api.model
    def _demo_partner(self, env, xmlid, name, vat=False, **vals):
        """Contacto peruano (con RUC si ``vat`` tiene 11 dígitos, DNI si 8)."""
        values = {'name': name, 'country_id': env.ref('base.pe').id, 'is_company': bool(vat and len(vat) == 11)}
        if vat:
            values.update(env['res.partner']._l10n_pe_identification_vals(
                '6' if len(vat) == 11 else '1', vat))
        values.update(vals)
        return self._demo_record(xmlid, env['res.partner'], values)

    @api.model
    def _demo_journal(self, env, xmlid, name, code, journal_type, **vals):
        """Diario de la compañía demo. Los de venta y compra van sin documentos
        electrónicos: así ningún cron envía la demo a SUNAT ni al OSE."""
        values = {'name': name, 'code': code, 'type': journal_type, 'company_id': env.company.id}
        if journal_type in ('sale', 'purchase'):
            values['l10n_latam_use_documents'] = False
            Account = env['account.account']
            values['default_account_id'] = Account.search([
                *Account._check_company_domain(env.company),
                ('account_type', '=', 'income' if journal_type == 'sale' else 'expense')], limit=1).id
        values.update(vals)
        return self._demo_record(xmlid, env['account.journal'], values)

    @api.model
    def _demo_bank_journal(self, env):
        """Diario bancario de la compañía demo con las cuentas de cobros y
        pagos pendientes (1041003 y 1041004 del PCGE) en sus métodos manuales:
        sin ellas, en Odoo 19 un pago no genera asiento ni concilia la factura
        hasta conciliar el extracto."""
        company = env.company
        Journal = env['account.journal']
        journal = env.ref('account.%s_bank' % company.id, raise_if_not_found=False) \
            or Journal.search([*Journal._check_company_domain(company), ('type', '=', 'bank')], limit=1)
        Account = env['account.account']
        for lines, code in ((journal.inbound_payment_method_line_ids, '1041003'),
                            (journal.outbound_payment_method_line_ids, '1041004')):
            account = Account.search([*Account._check_company_domain(company), ('code', '=', code)], limit=1)
            lines.filtered(lambda l: l.code == 'manual' and not l.payment_account_id).payment_account_id = account
        return journal

    @api.model
    def _demo_account(self, env, xmlid, code, name, account_type, **vals):
        """Cuenta de la compañía demo: la existente con ``code`` o una nueva."""
        record = self._demo_ref(xmlid)
        if record:
            return record
        Account = env['account.account']
        record = Account.search([('code', '=', code), *Account._check_company_domain(env.company)], limit=1)
        if not record:
            record = Account.create(dict({'code': code, 'name': name, 'account_type': account_type,
                                          'company_ids': env.company.ids}, **vals))
            self._demo_xmlid(xmlid, record)
        return record

    @api.model
    def _demo_tax(self, env, type_tax_use, amount=18.0):
        """Impuesto de la compañía demo (IGV 18 % por defecto)."""
        domain = [*env['account.tax']._check_company_domain(env.company), ('type_tax_use', '=', type_tax_use),
                  ('amount', '=', amount), ('amount_type', '=', 'percent')]
        if amount == 18.0 and 'l10n_pe_edi_tax_code' in env['account.tax']._fields:  # de l10n_pe
            return env['account.tax'].search(domain + [('l10n_pe_edi_tax_code', '=', '1000')], limit=1) \
                or env['account.tax'].search(domain, limit=1)
        return env['account.tax'].search(domain, limit=1)
