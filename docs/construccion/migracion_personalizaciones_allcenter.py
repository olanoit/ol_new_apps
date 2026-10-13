# -*- coding: utf-8 -*-
"""Migra las personalizaciones manuales de New Allcenter (campos x_, vistas,
acciones y automatizaciones creadas a mano en septiembre de 2026) a los
módulos de la suite. Se ejecuta con ``odoo shell`` en la base del cliente:

    FASE=migrar odoo shell -d <base> < migracion_personalizaciones_allcenter.py
    FASE=borrar odoo shell -d <base> < migracion_personalizaciones_allcenter.py

* ``migrar``: copia los datos a los campos de los módulos y quita las
  automatizaciones, sus acciones y las vistas manuales. Es idempotente.
* ``borrar``: borra los campos x_ (solo después de comprobar la migración).

Equivalencias:

=====================================  ==========================================
Personalización manual                 Módulo
=====================================  ==========================================
x_ubicacion_obra + «Alta de obra»      al_construction_material_request (código
                                       de obra, cuenta analítica y ubicación)
x_obra_nombre + vista de la venta      al_construction_planner (Nombre de la obra)
x_carga_historica + bloqueo de venta   al_sale_approval
«Tareo — foto obligatoria»             al_construction_planner (etapa que exige
                                       foto de evidencia)
x_obra_latitud/longitud/radio_m,       al_construction_attendance (sede con
x_distancia_m, x_obra_cercana,         ubicación y sede más cercana de la
x_fuera_de_rango                       marcación)
=====================================  ==========================================

Las columnas x_planN_id de la analítica y la hoja de trabajo de servicio de
campo las crea Odoo: no se tocan.
"""
import os

FASE = os.environ.get('FASE', 'migrar')
PROJECT_FIELDS = ['x_ubicacion_obra', 'x_obra_latitud', 'x_obra_longitud', 'x_obra_radio_m']
MANUAL_FIELDS = [
    ('project.project', 'x_ubicacion_obra'), ('project.project', 'x_obra_latitud'),
    ('project.project', 'x_obra_longitud'), ('project.project', 'x_obra_radio_m'),
    ('sale.order', 'x_obra_nombre'), ('sale.order', 'x_carga_historica'),
    ('hr.attendance', 'x_distancia_m'), ('hr.attendance', 'x_obra_cercana'),
    ('hr.attendance', 'x_fuera_de_rango'),
]
AUTOMATIONS = [
    'Allcenter · Alta de obra: código, cuenta analítica y ubicación',
    'Allcenter · Proyecto desde venta: código, nombre y ubicación',
    'Allcenter · Bloquear confirmación de venta sin aprobación',
    'Tareo de obra — foto obligatoria para marcar Hecha',
    'Tareo de obra — marcar asistencia fuera de rango',
    'Allcenter · Obra: ubicación Proyectos/<código> en el requerimiento',
]
VIEWS = ['sale.order.form.allcenter.obra', 'project.form.tareo.obra.coords',
         'hr.attendance.list.tareo.rango', 'hr.employee.form.pe.address.solo.rrhh']
SALE_APPROVAL_PRODUCT = 'Suministro e Instalación de Muebles de Melamina'
SALE_APPROVAL_CATEGORY = 'Aprobación de orden de venta'


def log(*args):
    print('MIG', *args)


def has_field(model, name):
    return name in env[model]._fields


def migrar():
    Project = env['project.project'].with_context(active_test=False)
    Location = env['stock.location'].with_context(active_test=False)
    # 1. Compañía: el código de obra es la primera palabra del nombre y las
    #    obras cuelgan de «Proyectos».
    root = env.ref('__allcenter__.loc_proyectos', raise_if_not_found=False) or Location.search(
        [('name', '=', 'Proyectos'), ('usage', '=', 'view'), ('location_id', '=', False)], limit=1)
    for company in env['res.company'].search([]):
        vals = {'construction_code_from_name': True}
        if root and (not root.company_id or root.company_id == company):
            vals['construction_sites_location_id'] = root.id
        category = env['approval.category'].search([('name', '=', SALE_APPROVAL_CATEGORY),
                                                     ('company_id', 'in', [company.id, False])], limit=1)
        if category:
            vals['sale_approval_category_id'] = category.id
        company.write(vals)
        log('compañía', company.name, vals)
    # Los proyectos sin compañía no siguen el cambio del ajuste: se recalcula
    # el código de todos.
    all_projects = Project.search([])
    all_projects._compute_construction_code()
    log('códigos de obra', len(all_projects.filtered('construction_code')))

    # 2. Obras: ubicación Proyectos/<código> y marca «Es obra».
    if has_field('project.project', 'x_ubicacion_obra'):
        projects = Project.search([('x_ubicacion_obra', '!=', False)])
        moved = 0
        for project in projects:
            previous = project.construction_location_id
            if previous != project.x_ubicacion_obra:
                project.construction_location_id = project.x_ubicacion_obra
                moved += 1
                if previous and not env['stock.move'].search_count(
                        ['|', ('location_id', '=', previous.id), ('location_dest_id', '=', previous.id)]) \
                        and not Project.search_count([('construction_location_id', '=', previous.id)]):
                    previous.unlink()
        projects.filtered(lambda p: not p.is_construction_site).write({'is_construction_site': True})
        log('obras', len(projects), 'ubicaciones corregidas', moved)

    # 3. Sedes de obra desde las coordenadas del proyecto.
    if has_field('project.project', 'x_obra_latitud'):
        Site = env['l10n_pe.hr.construction.site']
        created = 0
        for project in Project.search(['|', ('x_obra_latitud', '!=', 0), ('x_obra_longitud', '!=', 0)]):
            if not Site.search_count([('project_id', '=', project.id)]):
                Site.create({'name': project.name, 'project_id': project.id,
                             'latitude': project.x_obra_latitud, 'longitude': project.x_obra_longitud,
                             'radius_m': int(project.x_obra_radio_m or 300),
                             'analytic_account_id': project.account_id.id,
                             'company_id': (project.company_id or env.company).id})
                created += 1
        log('sedes creadas', created)
    if has_field('hr.attendance', 'x_obra_cercana'):
        attendances = env['hr.attendance'].search([('x_obra_cercana', '!=', False)])
        attendances._construction_assign_nearest_site()
        log('marcaciones con sede', len(attendances.filtered('l10n_pe_construction_site_id')),
            'de', len(attendances))

    # 4. Ventas: nombre de la obra, carga histórica y productos.
    if has_field('sale.order', 'x_obra_nombre'):
        Sale = env['sale.order'].with_context(active_test=False)
        named = Sale.search([('x_obra_nombre', '!=', False), ('construction_site_name', '=', False)])
        for order in named:
            order.construction_site_name = order.x_obra_nombre
        historic = Sale.search([('x_carga_historica', '=', True), ('sale_approval_exempt', '=', False)])
        historic.write({'sale_approval_exempt': True})
        log('ventas: nombre de obra', len(named), 'carga histórica', len(historic))
    Template = env['product.template'].with_context(active_test=False)
    creates_site = Template.search([('service_tracking', '=', 'project_only'),
                                    ('construction_creates_site', '=', False)])
    creates_site.write({'construction_creates_site': True})
    guarded = Template.search([('name', '=', SALE_APPROVAL_PRODUCT)])
    guarded.write({'sale_approval_required': True})
    log('productos que crean obra', creates_site.mapped('name'), 'con aprobación', guarded.mapped('name'))

    # 5. Etapas «Hecha»: exigen foto de evidencia.
    stages = env['project.task.type'].with_context(active_test=False).search([('name', '=', 'Hecha')])
    stages.write({'construction_requires_photo': True})
    log('etapas con foto', len(stages))

    # 6. Fuera lo manual: automatizaciones (y sus acciones) y vistas.
    automations = env['base.automation'].with_context(active_test=False).search(
        [('name', 'in', AUTOMATIONS)])
    actions = automations.action_server_ids
    automations.unlink()
    actions.exists().unlink()
    views = env['ir.ui.view'].with_context(active_test=False).search([('name', 'in', VIEWS)])
    views.unlink()
    log('automatizaciones borradas', len(automations), 'vistas borradas', len(views))


def borrar():
    Field = env['ir.model.fields']
    fields_ = Field.browse()
    for model, name in MANUAL_FIELDS:
        field = Field._get(model, name)
        if field and field.state == 'manual':
            fields_ |= field
    names = fields_.mapped(lambda f: '%s.%s' % (f.model, f.name))
    fields_.unlink()
    log('campos borrados', names)


if FASE == 'migrar':
    migrar()
elif FASE == 'borrar':
    borrar()
else:
    raise SystemExit('FASE debe ser migrar o borrar')
env.cr.commit()
log('fin', FASE)
