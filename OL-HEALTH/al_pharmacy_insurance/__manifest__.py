# -*- coding: utf-8 -*-
{
    'name': 'Farmacia: convenios con EPS y empresas (AL)',
    'summary': 'Convenios con aseguradoras y empresas: cobertura por producto o categoría, copago, '
               'topes por venta y por mes, afiliados, cobro de la parte cubierta en la caja y '
               'liquidación mensual a la aseguradora.',
    'description': """
Farmacia: convenios con EPS y empresas
======================================
Entrega E10 de las mejoras (docs/farmacia/MEJORAS_PROCESOS.md).

* Convenio con la aseguradora o empresa: cobertura (% por defecto y por
  categoría o producto), copago fijo por venta, tope por venta y tope mensual
  por afiliado, vigencia y exigencia de receta. Modalidad «convenio»
  (factura a la aseguradora) o «reembolso» (el paciente paga el total).
* Afiliados: paciente, convenio, número de afiliado y vigencia.
* En la caja: cada convenio tiene su método de pago «cuenta de cliente». Al
  elegirlo, el servidor calcula la parte cubierta y la reparte por línea
  (base e IGV); el paciente paga el resto.
* Dos comprobantes por la venta (Informe SUNAT 029-2013): la boleta o
  factura del paciente lleva solo su parte, con su IGV (sin comprobante, el
  cierre de caja registra solo esa parte), y la liquidación mensual emite
  la factura a la aseguradora por la parte cubierta, con la referencia de
  cada venta, el DNI del paciente y el número de afiliado. Los dos suman la
  venta: ingreso, IGV y total.
* PDF de la liquidación como sustento para la aseguradora.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_insurance/static/description/icon.png',
    'version': '3.20261027',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_pos', 'account', 'al_report_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/pharmacy_insurance_security.xml',
        'data/pharmacy_insurance_data.xml',
        'report/liquidation_report.xml',
        'views/pharmacy_insurance_views.xml',
    ],
    'demo': ['demo/pharmacy_insurance_demo.xml'],
    'assets': {
        'point_of_sale._assets_pos': [
            'al_pharmacy_insurance/static/src/app/**/*',
        ],
        'web.assets_tests': [
            'al_pharmacy_insurance/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
