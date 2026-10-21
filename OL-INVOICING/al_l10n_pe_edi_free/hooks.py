"""Alta del grupo gratuito exonerado/inafecto en las compañías que ya tienen el
plan peruano (las nuevas lo reciben con la plantilla)."""
import logging

from .models.account_chart_template import FREE_EXEMPT_TAX_XMLID

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    companies = env['res.company'].search([('chart_template', '=', 'pe'), ('parent_id', '=', False)])
    for company in companies:
        ChartTemplate = env['account.chart.template'].with_company(company)
        if not ChartTemplate.ref(FREE_EXEMPT_TAX_XMLID, raise_if_not_found=False):
            data = {'account.tax': ChartTemplate._get_pe_free_account_tax()}
            ChartTemplate._deref_account_tags('pe', data['account.tax'])
            ChartTemplate._pre_reload_data(company, {}, data)
            ChartTemplate._load_data(data)
            _logger.info('al_l10n_pe_edi_free: grupo gratuito exonerado/inafecto creado en %s',
                         company.name)
        # _load_data no carga los name@es: sin esto el impuesto sale en inglés.
        ChartTemplate._load_translations(
            companies=company, template_data={'account.tax': ChartTemplate._get_pe_free_account_tax()})
