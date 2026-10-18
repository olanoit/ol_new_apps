# -*- coding: utf-8 -*-
{
    'name': 'PE - Farmacia: estupefacientes y psicotrópicos (AL)',
    'summary': 'Listas de fiscalización, receta especial con sus datos y vigencia de 3 días, '
               'retención con folio, libros de estupefacientes y psicotrópicos y balance '
               'trimestral en PDF y Excel.',
    'description': """
PE - Farmacia: estupefacientes y psicotrópicos
==============================================
Entrega E3 del plan (docs/farmacia/PLAN_FARMACIA.md), según el DS 023-2001-SA
y sus modificatorias (actualizado por el DS 020-2024-SA):

* Lista de fiscalización por producto (IIA, IIB, IIIA-C, IVA-B, VI, cannabis)
  que fija la condición de venta y el libro.
* Receta especial: documento, dirección y teléfono del paciente, diagnóstico
  y posología obligatorios; vigencia de 3 días; solo ella dispensa las listas
  de receta especial; nombre y documento del adquiriente.
* Retención con folio correlativo para las listas de receta especial y
  retenida.
* Libros de estupefacientes, psicotrópicos y cannabis desde los movimientos
  de inventario validados, con saldo y receta.
* Balance trimestral (declaración jurada) en PDF y Excel con las recetas del
  periodo; recordatorio el primer día de cada trimestre.
* Los controlados no se venden por internet ni delivery (BPOF 7.5.5.1).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_base/static/description/icon.png',
    'version': '2.20261018',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_prescription', 'al_pharmacy_stock', 'sale', 'l10n_pe', 'al_report_base'],
    'data': [
        'security/ir.model.access.csv',
        'data/controlled_data.xml',
        'views/controlled_views.xml',
        'report/controlled_reports.xml',
    ],
    'demo': ['demo/controlled_demo.xml'],
    'installable': True,
    'application': False,
}
