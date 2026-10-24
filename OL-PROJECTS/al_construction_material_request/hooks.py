# -*- coding: utf-8 -*-


def post_init_hook(env):
    """Deja cada compañía con almacén lista: ubicación padre ``OBRAS`` y tipo
    de operación «Despacho a obra». Las compañías nuevas lo obtienen de forma
    perezosa al procesar su primer requerimiento."""
    companies = env['stock.warehouse'].search([]).company_id
    companies._al_construction_ensure_setup()
    setup_package_111_options(env)


def setup_package_111_options(env):
    """Valores iniciales de las opciones del paquete 1.11 (M111-19 C y
    M111-20 A): Logística aprueba el interno sin jefe y todos los usuarios
    internos pueden hacer requerimientos internos."""
    logistics = env.ref('al_construction_material_request.group_construction_logistics')
    companies = env['res.company'].search([])
    companies.filtered(lambda c: not c.construction_internal_fallback_group_id).write(
        {'construction_internal_fallback_group_id': logistics.id})
    companies._construction_sync_internal_fallback_rule()
    internal = env.ref('al_construction_material_request.group_construction_internal_requester')
    user_group = env.ref('base.group_user')
    if internal not in user_group.implied_ids:
        user_group.write({'implied_ids': [(4, internal.id)]})
