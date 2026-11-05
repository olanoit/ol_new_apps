# -*- coding: utf-8 -*-
"""Búsqueda periódica de la tabla salarial y alerta cuando falta.

Cada corrida deja su registro: qué revisó, qué encontró y qué falló, para no
tener que entrar a los logs del servidor. La tabla importada sigue entrando
archivada: la activa una persona.
"""
import logging
from datetime import date

from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..tools import wage_table_links
from .hr_construction_wage_import import WageTablePageNotFound, same_url

_logger = logging.getLogger(__name__)

# Del 1-dic al 31-ene, semanal; el resto del año, mensual. El convenio 2026 se
# firmó el 5-dic y rigió desde el 1-ene.
WEEKLY_MONTHS = (12, 1)
WEEKLY_DAYS = 7
# Tope por página: un PDF pesa hasta 30 MB y una página con muchos enlaces sin año
# no debe descargarse entera.
MAX_PDFS_PER_PAGE = 5
MAX_PAGES_PER_PAGE = 3


class L10nPeHrConstructionWageCheck(models.Model):
    _name = 'l10n_pe.hr.construction.wage.check'
    _description = 'Búsqueda de la tabla salarial'
    _order = 'date desc, id desc'

    date = fields.Datetime(string='Fecha', required=True, readonly=True,
                           default=fields.Datetime.now)
    trigger = fields.Selection(
        [('cron', 'Automática'), ('manual', 'Manual')], string='Origen',
        required=True, default='cron', readonly=True)
    target_year = fields.Integer(string='Año buscado', readonly=True)
    line_ids = fields.One2many('l10n_pe.hr.construction.wage.check.line', 'check_id',
                               string='Direcciones revisadas', readonly=True)
    state = fields.Selection(
        [('imported', 'Tabla nueva importada'), ('nothing', 'Sin novedad'),
         ('partial', 'Con errores'), ('failed', 'Falló')],
        string='Resultado', compute='_compute_result', store=True)
    summary = fields.Char(string='Resumen', compute='_compute_result', store=True)

    @api.depends('line_ids.result')
    def _compute_result(self):
        for check in self:
            results = check.line_ids.mapped('result')
            errors = results.count('error')
            imported = results.count('imported')
            if imported:
                check.state = 'imported'
            elif errors and errors == len(results):
                check.state = 'failed'
            elif errors:
                check.state = 'partial'
            else:
                check.state = 'nothing'
            check.summary = _(
                '%(total)s direcciones revisadas, %(imported)s importadas, %(errors)s con error',
                total=len(results), imported=imported, errors=errors)

    def _compute_display_name(self):
        for check in self:
            check.display_name = _('Búsqueda del %s', fields.Datetime.to_string(check.date))

    def action_search_now(self):
        """«Buscar ahora»: sin esperar a la siguiente fecha."""
        check = self._l10n_pe_run('manual')
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': check.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Cuándo toca
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_is_due(self, today=None):
        """¿Toca buscar hoy? La acción corre a diario y decide aquí, para que la
        alerta salga el 1-dic y el 1-ene aunque no toque descargar nada. Una corrida
        que falló entera no cuenta: se reintenta al día siguiente."""
        today = today or fields.Date.context_today(self)
        last = self.search([('state', '!=', 'failed')], limit=1)
        if not last:
            return True
        last_day = last.date.date()
        if today.month in WEEKLY_MONTHS:
            year = today.year if today.month == 12 else today.year - 1
            return last_day < date(year, 12, 1) or (today - last_day).days >= WEEKLY_DAYS
        return (last_day.year, last_day.month) != (today.year, today.month)

    # ------------------------------------------------------------------
    # Corrida
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_run(self, trigger='cron'):
        """Revisa las páginas y, como respaldo, las direcciones fijas."""
        Table = self.env['l10n_pe.hr.construction.wage.table']
        target = Table._l10n_pe_target_year()
        check = self.create({'trigger': trigger, 'target_year': target})
        tried = []
        for page in Table._l10n_pe_watched_pages(target):
            check._l10n_pe_check_page(page, target, tried, follow=True)
        for url in Table._l10n_pe_watched_urls():
            if not any(same_url(url, seen) for seen in tried):
                check._l10n_pe_check_pdf(url, 'backup', tried)
        check.line_ids.filtered(lambda line: line.result == 'imported').table_id \
            ._l10n_pe_schedule_review()
        return check

    def _l10n_pe_log(self, url, kind, result, message=False, table=None):
        self.ensure_one()
        return self.env['l10n_pe.hr.construction.wage.check.line'].create({
            'check_id': self.id, 'url': url, 'kind': kind, 'result': result,
            'message': message, 'table_id': table.id if table else False})

    def _l10n_pe_check_page(self, url, target, tried, follow):
        self.ensure_one()
        Table = self.env['l10n_pe.hr.construction.wage.table']
        tried.append(url)
        try:
            with self.env.cr.savepoint():
                content = Table._l10n_pe_download_page(url)
                pdfs, pages = wage_table_links.find_links(content, url, target)
        except WageTablePageNotFound as error:
            self._l10n_pe_log(url, 'page', 'not_found', str(error))
            return
        except Exception as error:  # noqa: BLE001
            # Una página con otro formato no debe tumbar las demás: queda anotada.
            _logger.warning('Tabla salarial de construcción civil: %s', error)
            self._l10n_pe_log(url, 'page', 'error', _message(error))
            return
        self._l10n_pe_log(url, 'page', 'no_news', _(
            '%(pdfs)s PDF y %(pages)s páginas que pueden ser del convenio %(year)s.',
            pdfs=len(pdfs), pages=len(pages), year=target))
        for pdf in pdfs[:MAX_PDFS_PER_PAGE]:
            if not any(same_url(pdf, seen) for seen in tried):
                self._l10n_pe_check_pdf(pdf, 'pdf', tried)
        if follow:
            for page in pages[:MAX_PAGES_PER_PAGE]:
                if not any(same_url(page, seen) for seen in tried):
                    self._l10n_pe_check_page(page, target, tried, follow=False)

    def _l10n_pe_check_pdf(self, url, kind, tried):
        self.ensure_one()
        Table = self.env['l10n_pe.hr.construction.wage.table']
        tried.append(url)
        try:
            with self.env.cr.savepoint():
                content = Table._l10n_pe_download_pdf(url)
                table, created = Table._l10n_pe_create_from_pdf(content, url)
        except Exception as error:  # noqa: BLE001
            _logger.warning('Tabla salarial de construcción civil: %s', error)
            self._l10n_pe_log(url, kind, 'error', _message(error))
            return
        self._l10n_pe_log(url, kind, 'imported' if created else 'existing', table=table)

    # ------------------------------------------------------------------
    # Alerta por falta de tabla
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_construction_companies(self, today):
        """Compañías con trabajadores de construcción civil: una base que no tiene
        ninguno no recibe alertas de este régimen."""
        groups = self.env['hr.version'].sudo()._read_group([
            ('l10n_pe_is_construction', '=', True),
            ('employee_id.active', '=', True),
            '|', ('contract_date_end', '=', False), ('contract_date_end', '>=', today),
        ], ['company_id'])
        return self.env['res.company'].browse(
            [company.id for (company,) in groups if company])

    @api.model
    def _l10n_pe_check_coverage(self, today=None):
        """Crea o cierra las actividades según la tabla que falte.

        Desde el 1-dic avisa si nada, ni archivado, cubre el 1-ene siguiente. Si hoy
        no hay tabla activa, la actividad es urgente. Cuando el problema se resuelve,
        la actividad se cierra sola.
        """
        today = today or fields.Date.context_today(self)
        Table = self.env['l10n_pe.hr.construction.wage.table']
        AnyTable = Table.with_context(active_test=False)
        next_year = date(today.year + 1, 1, 1)
        wanted = {}
        managers = self.env['res.users'].search([
            ('all_group_ids', 'in', self.env.ref('hr_payroll.group_hr_payroll_manager').id),
            ('share', '=', False)])
        for company in self._l10n_pe_construction_companies(today):
            users = managers.filtered(lambda user: company in user.company_ids)
            if not Table._get_table_for_date(today, company):
                archived = AnyTable._get_table_for_date(today, company)
                kind = 'urgent'
                note = _(
                    'Hay una tabla archivada para hoy (%(table)s): revísela y actívela.',
                    table=archived.name,
                ) if archived else _(
                    'Ninguna tabla cubre la fecha de hoy. Impórtela desde Tablas salariales.')
            elif today.month == 12 and not AnyTable._get_table_for_date(next_year, company):
                kind = 'missing'
                note = _('Ninguna tabla, activa o archivada, cubre el %(date)s. '
                         'Revise si ya se publicó el convenio e impórtelo.',
                         date=next_year.strftime('%d/%m/%Y'))
            else:
                continue
            for user in users:
                wanted.setdefault((kind, user), note)
        self._l10n_pe_sync_activities(wanted, today)

    @api.model
    def _l10n_pe_sync_activities(self, wanted, today):
        Table = self.env['l10n_pe.hr.construction.wage.table']
        types = {
            'missing': self.env.ref('al_hr_pe_construction.activity_wage_table_missing'),
            'urgent': self.env.ref('al_hr_pe_construction.activity_wage_table_urgent'),
        }
        open_activities = self.env['mail.activity'].search([
            ('res_model', '=', Table._name),
            ('activity_type_id', 'in', [kind.id for kind in types.values()])])
        kept = open_activities.browse()
        for activity in open_activities:
            kind = next(key for key, value in types.items()
                        if value == activity.activity_type_id)
            if (kind, activity.user_id) in wanted:
                kept |= activity
        (open_activities - kept).action_feedback(
            feedback=_('Resuelto: ya hay tabla salarial para esa fecha.'))
        # La actividad necesita un registro donde colgarse: la tabla más reciente.
        holder = Table.with_context(active_test=False).search([], order='date_to desc', limit=1)
        if not holder:
            if wanted:
                _logger.warning('Construcción civil: falta tabla salarial y no hay ninguna '
                                'donde dejar la actividad.')
            return
        summaries = {'missing': _('Falta la tabla salarial del año siguiente'),
                     'urgent': _('Urgente: no hay tabla salarial vigente')}
        existing = {(activity.activity_type_id, activity.user_id) for activity in kept}
        for (kind, user), note in wanted.items():
            if (types[kind], user) not in existing:
                holder.activity_schedule(
                    activity_type_id=types[kind].id, user_id=user.id,
                    date_deadline=today, summary=summaries[kind], note=escape(note))


class L10nPeHrConstructionWageCheckLine(models.Model):
    _name = 'l10n_pe.hr.construction.wage.check.line'
    _description = 'Dirección revisada en la búsqueda de la tabla salarial'
    _order = 'id'

    check_id = fields.Many2one('l10n_pe.hr.construction.wage.check', required=True,
                               ondelete='cascade', index=True)
    url = fields.Char(string='Dirección', required=True)
    kind = fields.Selection(
        [('page', 'Página vigilada'), ('pdf', 'PDF encontrado'),
         ('backup', 'Dirección de respaldo')], string='Tipo', required=True)
    result = fields.Selection(
        [('no_news', 'Revisada'), ('existing', 'Ya estaba cargada'),
         ('imported', 'Importada'), ('not_found', 'Aún no publicada'), ('error', 'Error')],
        string='Resultado', required=True)
    message = fields.Char(string='Detalle')
    table_id = fields.Many2one('l10n_pe.hr.construction.wage.table', string='Tabla',
                               ondelete='set null',
                               context={'active_test': False})


def _message(error):
    """El texto para el registro, sin el traceback."""
    if isinstance(error, UserError):
        return error.args[0]
    return '%s: %s' % (type(error).__name__, error)


