# -*- coding: utf-8 -*-
{
    'name': 'Requerimiento de materiales de obra (AL)',
    'summary': 'El personal de obra pide materiales, se aprueba por niveles y '
               'lo disponible sale del almacén central; el faltante va a '
               'requerimiento de compra (OCA purchase_request).',
    'description': """
Requerimiento de materiales de obra
===================================
Plan: ``docs/construccion/PLAN_MODULO_al_construction_material_request.md``.

* Requerimiento por obra (proyecto) con líneas, analítica por línea
  (proyecto / disciplina / partida) y tarea opcional.
* Aprobación multinivel con ``base_tier_validation`` (OCA).
* Procesamiento por logística: lo disponible en el almacén central sale
  por transferencia interna a ``OBRAS/<obra>``; el faltante se envía a
  ``purchase.request`` (OCA), ya aprobado.
* Trazabilidad requerimiento → transferencias → requerimientos de compra
  → OC → recepción en obra.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECT/Apps',
    'version': '2.20260930',
    # LGPL-3 y no OPL-1: base_tier_validation es AGPL-3 (plan, F0.4).
    'license': 'LGPL-3',
    'depends': [
        'analytic',
        # stock.picking.project_id
        'project_stock',
        # purchase_stock incluido
        'purchase_request',
        'base_tier_validation',
    ],
    'data': [
        'security/construction_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/ir_sequence_data.xml',
        'data/mail_templates.xml',
        'report/construction_material_request_report.xml',
        'views/construction_material_request_views.xml',
        'views/project_views.xml',
        'views/stock_picking_views.xml',
        'views/purchase_request_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'al_construction_material_request/static/src/css/report_material_request.css',
        ],
    },
    'demo': [
        'demo/construction_demo.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
}
