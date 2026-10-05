# -*- coding: utf-8 -*-


def post_init_hook(env):
    """Deja cada compañía con almacén lista: ubicación padre ``OBRAS`` y tipo
    de operación «Despacho a obra». Las compañías nuevas lo obtienen de forma
    perezosa al procesar su primer requerimiento."""
    companies = env['stock.warehouse'].search([]).company_id
    companies._al_construction_ensure_setup()
