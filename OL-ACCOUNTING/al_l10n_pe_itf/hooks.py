"""Regla de conciliación «ITF» en las compañías que ya tienen el plan peruano."""


def post_init_hook(env):
    for company in env['res.company'].search([('chart_template', '=', 'pe'), ('parent_id', '=', False)]):
        company._l10n_pe_itf_reconcile_model()
