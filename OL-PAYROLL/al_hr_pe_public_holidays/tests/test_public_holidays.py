# -*- coding: utf-8 -*-
"""Feriados nacionales del Perú y su volcado a los calendarios laborales.

Dos frentes:

* **El dato**: los 16 feriados nacionales por año (Ley 31644 y sucesivas)
  para 2026-2035, con los móviles de Semana Santa cuadrados contra el
  cómputo de la Pascua.
* **La aplicación**: ``action_apply_to_calendars`` debe ser idempotente
  (re-aplicar actualiza el descanso existente, nunca lo duplica), respetar
  la zona horaria de cada calendario y no salirse de las compañías activas.
"""
from datetime import date, datetime, timedelta

from odoo.tests import TransactionCase, tagged

# Feriados de fecha fija del calendario laboral peruano.
FIXED_HOLIDAYS = [
    (1, 1, 'Año Nuevo'),
    (5, 1, 'Día del Trabajo'),
    (6, 7, 'Batalla de Arica'),
    (6, 29, 'San Pedro y San Pablo'),
    (7, 23, 'Día de la Fuerza Aérea'),
    (7, 28, 'Independencia'),
    (7, 29, 'Gran Parada Militar'),
    (8, 6, 'Batalla de Junín'),
    (8, 30, 'Santa Rosa de Lima'),
    (10, 8, 'Combate de Angamos'),
    (11, 1, 'Todos los Santos'),
    (12, 8, 'Inmaculada Concepción'),
    (12, 9, 'Batalla de Ayacucho'),
    (12, 25, 'Navidad'),
]


def easter_sunday(year):
    """Domingo de Pascua (algoritmo de Butcher, calendario gregoriano)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


@tagged('post_install', '-at_install')
class TestPeruPublicHolidays(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Holiday = cls.env['pe.public.holiday']
        cls.Calendar = cls.env['resource.calendar']
        cls.Leaves = cls.env['resource.calendar.leaves']
        cls.company = cls.env.company

    # ------------------------------------------------------------------
    # Contenido del calendario oficial
    # ------------------------------------------------------------------
    def test_ten_years_loaded(self):
        """Están cargados los 10 años del calendario (2026-2035)."""
        for year in range(2026, 2036):
            count = self.Holiday.search_count(
                [('year', '=', year), ('labor_regime', '=', False)])
            self.assertEqual(
                count, 16,
                'el año %s debe tener 16 feriados nacionales, tiene %s'
                % (year, count))

    def test_fixed_holidays_present_every_year(self):
        """Cada feriado de fecha fija existe en los diez años."""
        for year in range(2026, 2036):
            for month, day, label in FIXED_HOLIDAYS:
                self.assertTrue(
                    self.Holiday.search_count(
                        [('date', '=', date(year, month, day))]),
                    'falta %s (%02d/%02d) del año %s' % (label, day, month, year))

    def test_easter_holidays_match_computed_easter(self):
        """Jueves y Viernes Santo cuadran con el cómputo de la Pascua."""
        for year in range(2026, 2036):
            easter = easter_sunday(year)
            holidays = self.Holiday.search([('year', '=', year)])
            dates = holidays.mapped('date')
            thursday = easter - timedelta(days=3)
            friday = easter - timedelta(days=2)
            self.assertIn(thursday, dates,
                          'Jueves Santo %s ausente en %s' % (thursday, year))
            self.assertIn(friday, dates,
                          'Viernes Santo %s ausente en %s' % (friday, year))

    def test_easter_sunday_is_not_a_holiday(self):
        """El Domingo de Resurrección no es feriado legal en el Perú.

        Cargarlo como feriado marcaba como tal un domingo que no lo es: el
        tareaje le aplicaba la sobretasa del 100 % a quien trabajase ese día.
        """
        for year in range(2026, 2036):
            easter = easter_sunday(year)
            self.assertFalse(
                self.Holiday.search_count([('date', '=', easter)]),
                'el Domingo de Resurrección %s no es feriado' % easter)

    def test_no_duplicate_dates_within_year(self):
        """No hay dos feriados en la misma fecha (duplicaría el descanso)."""
        for year in range(2026, 2036):
            dates = self.Holiday.search([('year', '=', year)]).mapped('date')
            self.assertEqual(len(dates), len(set(dates)),
                             'fechas repetidas en %s' % year)

    def test_year_is_computed_and_stored(self):
        """``year`` se calcula desde la fecha y queda almacenado (se filtra por él)."""
        holiday = self.Holiday.create({'name': 'Prueba', 'date': date(2040, 5, 4)})
        self.assertEqual(holiday.year, 2040)
        self.assertIn(holiday, self.Holiday.search([('year', '=', 2040)]))

    def test_default_work_entry_type_is_rest_day(self):
        """El feriado no laborado se computa como día de descanso (D.Leg. 713)."""
        dom = self.env.ref('al_hr_pe.wd_DOM', raise_if_not_found=False)
        if not dom:
            self.skipTest('al_hr_pe no instalado: dependencia blanda')
        holiday = self.Holiday.create({'name': 'Prueba', 'date': date(2041, 5, 4)})
        self.assertEqual(holiday.work_entry_type_id, dom)

    # ------------------------------------------------------------------
    # Aplicación a los calendarios
    # ------------------------------------------------------------------
    def _calendar(self, tz='America/Lima'):
        return self.Calendar.create({
            'name': 'Calendario prueba feriados %s' % tz,
            'tz': tz,
            'company_id': self.company.id,
        })

    def _holiday(self, day=date(2042, 7, 28), **kw):
        vals = {'name': 'Feriado de prueba', 'date': day}
        vals.update(kw)
        return self.Holiday.create(vals)

    def test_apply_creates_global_leave(self):
        """Aplicar crea un descanso global (sin recurso) en el calendario."""
        calendar = self._calendar()
        holiday = self._holiday()
        holiday.action_apply_to_calendars()
        leave = self.Leaves.search([
            ('pe_public_holiday_id', '=', holiday.id),
            ('calendar_id', '=', calendar.id)])
        self.assertEqual(len(leave), 1)
        self.assertFalse(leave.resource_id,
                         'debe ser descanso global, no de un recurso')
        self.assertEqual(leave.name, holiday.name)

    def test_apply_is_idempotent(self):
        """Re-aplicar actualiza el descanso; no lo duplica."""
        calendar = self._calendar()
        holiday = self._holiday()
        holiday.action_apply_to_calendars()
        holiday.action_apply_to_calendars()
        holiday.action_apply_to_calendars()
        leaves = self.Leaves.search([
            ('pe_public_holiday_id', '=', holiday.id),
            ('calendar_id', '=', calendar.id)])
        self.assertEqual(len(leaves), 1,
                         'tres aplicaciones deben dejar un solo descanso')

    def test_apply_after_timezone_change_moves_the_leave(self):
        """Cambiar la zona del calendario corrige el descanso, no lo duplica.

        Es el caso que rompía la clave anterior (feriado+fechas): al mover
        la zona horaria, las fechas ya no coincidían y se creaba un segundo
        descanso solapado.
        """
        calendar = self._calendar()
        holiday = self._holiday()
        holiday.action_apply_to_calendars()
        original = self.Leaves.search([
            ('pe_public_holiday_id', '=', holiday.id),
            ('calendar_id', '=', calendar.id)]).date_from
        calendar.tz = 'UTC'
        holiday.action_apply_to_calendars()
        leaves = self.Leaves.search([
            ('pe_public_holiday_id', '=', holiday.id),
            ('calendar_id', '=', calendar.id)])
        self.assertEqual(len(leaves), 1)
        self.assertNotEqual(leaves.date_from, original,
                            'el descanso debe recolocarse en la nueva zona')

    def test_leave_range_is_timezone_aware(self):
        """00:00 en Lima (UTC-5) se guarda como 05:00 UTC.

        Regresión: ``hr_holidays`` reinterpreta las fechas del ``create``
        como si vinieran en el huso del usuario, y el descanso salía
        desplazado cinco horas —el feriado empezaba a media mañana—.
        """
        calendar = self._calendar()
        holiday = self._holiday(day=date(2042, 7, 28))
        holiday.action_apply_to_calendars()
        leave = self.Leaves.search([
            ('pe_public_holiday_id', '=', holiday.id),
            ('calendar_id', '=', calendar.id)])
        self.assertEqual(leave.date_from, datetime(2042, 7, 28, 5, 0, 0))
        self.assertEqual(leave.date_to, datetime(2042, 7, 29, 4, 59, 59))

    def test_half_day_leave_ends_at_configured_hour(self):
        """El medio día termina a la hora configurada, no a medianoche."""
        calendar = self._calendar()
        holiday = self._holiday(day=date(2042, 12, 24),
                                is_full_day=False, half_day_starts_at=13.5)
        holiday.action_apply_to_calendars()
        leave = self.Leaves.search([
            ('pe_public_holiday_id', '=', holiday.id),
            ('calendar_id', '=', calendar.id)])
        # 13:30 en Lima = 18:30 UTC
        self.assertEqual(leave.date_to, datetime(2042, 12, 24, 18, 30, 0))

    def test_work_entry_type_propagates_to_leave(self):
        """El concepto de nómina del feriado llega al descanso."""
        dom = self.env.ref('al_hr_pe.wd_DOM', raise_if_not_found=False)
        if not dom:
            self.skipTest('al_hr_pe no instalado: dependencia blanda')
        calendar = self._calendar()
        holiday = self._holiday(day=date(2042, 10, 8))
        holiday.action_apply_to_calendars()
        leave = self.Leaves.search([
            ('pe_public_holiday_id', '=', holiday.id),
            ('calendar_id', '=', calendar.id)])
        self.assertEqual(leave.work_entry_type_id, dom)

    def test_delete_holiday_removes_its_leaves(self):
        """Borrar el feriado arrastra sus descansos (ondelete cascade)."""
        calendar = self._calendar()
        holiday = self._holiday(day=date(2043, 1, 1))
        holiday.action_apply_to_calendars()
        leave_ids = self.Leaves.search(
            [('pe_public_holiday_id', '=', holiday.id)]).ids
        self.assertTrue(leave_ids)
        holiday.unlink()
        self.assertFalse(self.Leaves.browse(leave_ids).exists())

    def test_leave_count_reflects_applied_calendars(self):
        """El contador del feriado cuenta los calendarios donde se aplicó."""
        self._calendar()
        holiday = self._holiday(day=date(2043, 5, 1))
        holiday.action_apply_to_calendars()
        holiday.invalidate_recordset()
        self.assertEqual(holiday.leave_count, len(holiday.leave_ids))
        self.assertGreaterEqual(holiday.leave_count, 1)

    def test_other_company_calendars_untouched(self):
        """No se escriben feriados en calendarios de compañías no activas.

        Crear la compañía la añade a las permitidas del usuario, así que
        el caso multicompañía real se reproduce acotando
        ``allowed_company_ids`` a la compañía de la sesión.
        """
        other = self.env['res.company'].create({'name': 'AJENA SAC'})
        foreign = self.Calendar.create({
            'name': 'Calendario ajeno', 'tz': 'America/Lima',
            'company_id': other.id})
        holiday = self._holiday(day=date(2043, 7, 28))
        holiday.with_context(
            allowed_company_ids=[self.company.id]).action_apply_to_calendars()
        self.assertFalse(self.Leaves.search_count([
            ('pe_public_holiday_id', '=', holiday.id),
            ('calendar_id', '=', foreign.id)]),
            'el feriado no debe alcanzar compañías fuera de env.companies')
        self.assertTrue(self.Leaves.search_count([
            ('pe_public_holiday_id', '=', holiday.id),
            ('calendar_id.company_id', '=', self.company.id)]),
            'sí debe aplicarse en la compañía de la sesión')

    def test_cron_applies_current_and_next_year(self):
        """El cron cubre el año en curso y el siguiente (hueco de enero)."""
        calendar = self._calendar()
        this_year = date.today().year
        self.Holiday.cron_apply_yearly_holidays()
        for year in (this_year, this_year + 1):
            holidays = self.Holiday.search(
                [('year', '=', year), ('labor_regime', '=', False)])
            if not holidays:
                continue
            applied = self.Leaves.search_count([
                ('pe_public_holiday_id', 'in', holidays.ids),
                ('calendar_id', '=', calendar.id)])
            self.assertEqual(
                applied, len(holidays),
                'el cron debe aplicar todos los feriados de %s' % year)

    def test_cron_reaches_companies_outside_the_session(self):
        """El cron (superusuario) alcanza también a compañías que no están
        en sus compañías activas (auditoría 07/10/2026)."""
        other = self.env['res.company'].create({'name': 'Feriados otra SAC'})
        calendar = self.env['resource.calendar'].create({
            'name': 'Calendario otra', 'company_id': other.id})
        holiday = self.Holiday.search([
            ('year', '=', date.today().year), ('labor_regime', '=', False)],
            limit=1)
        if not holiday:
            self.skipTest('sin feriados del año en curso')
        self.Holiday.with_context(allowed_company_ids=[self.env.company.id]) \
            .cron_apply_yearly_holidays()
        self.assertTrue(self.Leaves.search_count([
            ('pe_public_holiday_id', '=', holiday.id), ('calendar_id', '=', calendar.id)]))

    def test_action_view_leaves_domain(self):
        """La acción de ver descansos filtra por el feriado."""
        holiday = self._holiday(day=date(2043, 12, 25))
        action = holiday.action_view_leaves()
        self.assertEqual(action['res_model'], 'resource.calendar.leaves')
        self.assertIn(('pe_public_holiday_id', '=', holiday.id), action['domain'])

    # ------------------------------------------------------------------
    # Feriados de régimen
    # ------------------------------------------------------------------
    def test_construction_day_loaded_every_year(self):
        """El 25 de octubre es feriado del régimen de construcción civil."""
        for year in range(2026, 2036):
            holiday = self.Holiday.search([('date', '=', date(year, 10, 25))])
            self.assertEqual(len(holiday), 1, year)
            self.assertEqual(holiday.labor_regime, 'construccion')

    def test_regime_holiday_only_reaches_regime_calendars(self):
        """Solo los calendarios de trabajadores del régimen lo reciben."""
        if 'l10n_pe_labor_regime' not in self.env['hr.version']._fields:
            self.skipTest('al_hr_pe no instalado: dependencia blanda')
        obra, oficina = self._calendar(), self._calendar(tz='America/Bogota')
        builder = self.env['hr.employee'].create({
            'name': 'Operario obra', 'company_id': self.company.id,
            'resource_calendar_id': obra.id})
        builder.version_id.l10n_pe_labor_regime = 'construccion'
        self.env['hr.employee'].create({
            'name': 'Asistente oficina', 'company_id': self.company.id,
            'resource_calendar_id': oficina.id})
        holiday = self._holiday(day=date(2044, 10, 25),
                                holiday_type='regime',
                                labor_regime='construccion')
        holiday.action_apply_to_calendars()
        self.assertEqual(holiday.leave_ids.calendar_id & (obra | oficina), obra)
