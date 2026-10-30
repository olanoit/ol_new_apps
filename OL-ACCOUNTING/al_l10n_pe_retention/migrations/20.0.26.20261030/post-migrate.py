from odoo import SUPERUSER_ID, api

from odoo.addons.al_l10n_pe_retention.hooks import _l10n_pe_retention_set_prefix


def migrate(cr, version):
    """Bases que instalaron el módulo con el impuesto nativo ya creado: la
    secuencia del CRE se quedó en RRR1-; pasa a R001- si aún no se usó."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env['res.company'].search([('chart_template', '=', 'pe'), ('parent_id', '=', False)]):
        _l10n_pe_retention_set_prefix(env['account.chart.template'].with_company(company))
