# -*- coding: utf-8 -*-
"""Paquete 1.22, M122-03: el motivo del re-trabajo pasa al catálogo.

* Los perfiles estándar (noupdate) reciben su lista de motivos si no tienen.
* Cada compañía con perfil recibe los motivos de su perfil si no tiene
  ninguno.
* Cada valor de la selección anterior (Cambio, Faltante, Mal armado) pasa al
  motivo del catálogo con el mismo nombre. Si la compañía no lo tiene, se
  crea: archivado cuando la compañía ya tiene su lista (el celular ofrece la
  del perfil y los registros conservan su motivo), activo si no tiene otra."""
from odoo import SUPERUSER_ID, api
from odoo.tools import SQL

REF = 'al_construction_planner.'
FURNITURE = 'Cambio pedido por el cliente\nFaltante de material o pieza\nMal armado\nDaño en obra'
WORKS = 'Defecto de ejecución\nCambio pedido por el cliente\nDaño de terceros\nFaltante de material'
PROFILES = {
    'profile_furniture': FURNITURE,
    'profile_construction': WORKS,
    'profile_construction_prof4': WORKS,
    'profile_construction_prof5': WORKS,
    'profile_construction_prof6': WORKS,
}
LEGACY = {'change': 'Cambio', 'missing': 'Faltante', 'bad_assembly': 'Mal armado'}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, names in PROFILES.items():
        profile = env.ref(REF + xmlid, raise_if_not_found=False)
        if profile and not profile.rework_reason_names:
            profile.rework_reason_names = names
    Reason = env['construction.portal.reason'].with_context(active_test=False)
    companies = env['res.company'].with_context(active_test=False).search(
        [('construction_profile_id', '!=', False)])
    for company in companies:
        Reason._seed_rework(
            company, (company.construction_profile_id.rework_reason_names or '').splitlines())
    for table in ('construction_task_progress', 'construction_exceed_log'):
        cr.execute(SQL(
            'SELECT DISTINCT company_id, rework_reason FROM %s '
            'WHERE rework_reason IS NOT NULL AND rework_reason_id IS NULL',
            SQL.identifier(table)))
        for company_id, code in cr.fetchall():
            name = LEGACY.get(code)
            if not name:
                continue
            reason = Reason.search(
                [('kind', '=', 'rework'), ('name', '=ilike', name),
                 ('company_id', 'in', (company_id, False))], order='company_id, id', limit=1)
            if not reason:
                has_list = bool(company_id) and Reason.search_count(
                    [('kind', '=', 'rework'), ('company_id', '=', company_id),
                     ('active', '=', True)], limit=1)
                reason = Reason.create({'name': name, 'kind': 'rework',
                                        'company_id': company_id or False,
                                        'sequence': 90, 'active': not has_list})
            cr.execute(SQL(
                'UPDATE %s SET rework_reason_id = %s WHERE rework_reason = %s '
                'AND rework_reason_id IS NULL AND company_id IS NOT DISTINCT FROM %s',
                SQL.identifier(table), reason.id, code, company_id))
    env.invalidate_all()
