"""Configura la facturación electrónica de una base de farmacia con los módulos
del proyecto (l10n_pe_edi, al_account_move_name_sequence, al_l10n_pe_edi_pos)
en el entorno de prueba de SUNAT (beta, usuario MODDATOS, certificado de
prueba de l10n_pe_edi). Se usó en farmacia-dev el 18/10/2026.

Uso (dentro del contenedor): odoo shell ... -d <base> < configurar_cpe_beta.py

Para producción: cambie la razón social, el RUC y la dirección por los del
cliente, cargue SU certificado digital y su usuario SOL u operador (OSE), y
desmarque «Entorno de prueba». Nunca deje el certificado de prueba.
"""
import base64

company = env.company
partner = company.partner_id
district = env['l10n_pe.res.city.district'].search([('code', '=', '150122')], limit=1)  # Miraflores, Lima
company.write({'name': 'Botica Santa Rosa S.A.C.', 'vat': '20557912879'})
partner.write({
    'l10n_latam_identification_type_id': env.ref('l10n_pe.it_RUC').id,
    'street': 'Av. José Larco 1234', 'country_id': env.ref('base.pe').id,
    'l10n_pe_district': district.id, 'city_id': district.city_id.id,
    'state_id': district.city_id.state_id.id, 'city': district.city_id.name, 'zip': '15074',
})
Certificate = env['certificate.certificate']
certificate = Certificate.search([('company_id', '=', company.id), ('name', '=', 'Certificado de prueba SUNAT beta')], limit=1)
if not certificate:
    with open('/mnt/enterprise/l10n_pe_edi/demo/certificates/certificate.pfx', 'rb') as pfx:
        certificate = Certificate.create({
            'name': 'Certificado de prueba SUNAT beta', 'company_id': company.id,
            'content': base64.b64encode(pfx.read()), 'pkcs12_password': '12345678a'})
company.write({'l10n_pe_edi_provider': 'sunat', 'l10n_pe_edi_test_env': True,
               'l10n_pe_edi_certificate_id': certificate.id})

Series = env['edi.invoice.series']
def series(name, doc_xmlid, nc, nd):
    record = Series.search([('company_id', '=', company.id), ('name', '=', name)], limit=1)
    if not record:
        record = Series.create({'name': name, 'name_nc': nc, 'name_nd': nd, 'company_id': company.id,
                                'l10n_latam_document_type_id': env.ref(doc_xmlid).id})
    if record.state != 'publish':
        record.action_publish()
    return record
f001 = series('F001', 'l10n_pe.document_type01', 'FC01', 'FD01')
b001 = series('B001', 'l10n_pe.document_type02', 'BC01', 'BD01')

Journal = env['account.journal']
base_journal = Journal.search([('company_id', '=', company.id), ('type', '=', 'sale'), ('code', '=', 'INV')], limit=1)
def journal(code, name, serie):
    record = Journal.search([('company_id', '=', company.id), ('code', '=', code)], limit=1)
    if not record:
        record = base_journal.copy({'name': name, 'code': code})
    record.write({'l10n_latam_use_documents': True, 'use_name_sequence': True,
                  'edi_series_ids': [(6, 0, serie.ids)]})
    return record
factura_journal = journal('FAC', 'Facturas electrónicas', f001)
boleta_journal = journal('BOL', 'Boletas electrónicas', b001)

config = env['pos.config'].search([('name', '=', 'Botica Principal')], limit=1)
config.write({'l10n_pe_boleta_journal_id': boleta_journal.id,
              'l10n_pe_factura_journal_id': factura_journal.id})

Partner = env['res.partner']
def customer(name, vat, id_type):
    record = Partner.search([('vat', '=', vat)], limit=1)
    if not record:
        record = Partner.create({'name': name, 'vat': vat, 'country_id': env.ref('base.pe').id,
                                 'l10n_latam_identification_type_id': env.ref(id_type).id,
                                 'street': 'Av. Benavides 455', 'l10n_pe_district': district.id,
                                 'city_id': district.city_id.id, 'state_id': district.city_id.state_id.id})
    return record
customer('Lucía Fernández Ríos', '44556677', 'l10n_pe.it_DNI')
customer('Distribuidora Médica Lima S.A.C.', '20512528458', 'l10n_pe.it_RUC')
env.cr.commit()
print('RESULT', company.name, company.vat, company.l10n_pe_edi_provider, company.l10n_pe_edi_test_env,
      certificate.is_valid, [s.name + ':' + s.state for s in (f001 | b001)],
      factura_journal.code, boleta_journal.code, config.l10n_pe_cpe_enabled,
      [s.name for s in config.l10n_pe_boleta_series_ids], [s.name for s in config.l10n_pe_factura_series_ids])
