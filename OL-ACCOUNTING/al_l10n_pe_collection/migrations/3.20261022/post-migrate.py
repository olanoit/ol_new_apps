from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """El resultado «Reclamo o disconformidad» (datos noupdate) pasa a abrir reclamos."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    result = env.ref('al_l10n_pe_collection.result_claim', raise_if_not_found=False)
    if result:
        result.is_dispute = True
