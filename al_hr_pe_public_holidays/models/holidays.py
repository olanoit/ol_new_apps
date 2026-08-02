# -*- coding: utf-8 -*-
"""Feriados nacionales del Perú y su aplicación a los calendarios laborales.

Los feriados se materializan como **descansos globales** del calendario
(``resource.calendar.leaves`` sin recurso). De ahí los leen las dos capas
que los necesitan:

* el motor nativo de *work entries*, que genera la entrada del día con el
  ``work_entry_type_id`` que lleve el descanso, y
* el tareaje de ``al_hr_pe_attendance`` (``_get_public_holidays``), que
  clasifica el día como feriado y aplica la sobretasa del 100 % si se
  trabajó (D.Leg. 713, arts. 5-9).

Por eso el tipo de entrada del descanso importa: un feriado **no**
laborado es día de descanso remunerado (D.Leg. 713, arts. 1 y 5), así que
por defecto se marca con el concepto PE «DÍAS DE DESCANSO».
"""
from datetime import date, datetime, time

from pytz import UTC, timezone

from odoo import _, api, fields, models


class PeruPublicHoliday(models.Model):
    _name = "pe.public.holiday"
    _description = "Peru Public Holiday"
    _order = "date"

    name = fields.Char(string="Holiday Name", required=True, translate=True)
    date = fields.Date(string="Date", required=True, index=True)
    year = fields.Integer(string="Year", compute="_compute_year", store=True, index=True)
    holiday_type = fields.Selection(
        [
            ("national", "National"),
            ("religious", "Religious"),
            ("memorial", "Memorial"),
        ],
        string="Type",
        default="national",
        required=True,
    )
    is_full_day = fields.Boolean(string="Full Day", default=True)
    half_day_starts_at = fields.Float(string="Half Day Starts At", default=13.0)
    description = fields.Text(string="Description", translate=True)
    work_entry_type_id = fields.Many2one(
        "hr.work.entry.type",
        string="Tipo de entrada de trabajo",
        default=lambda self: self._default_work_entry_type_id(),
        help="Concepto con el que la nómina computa el día. Los descansos "
             "que se creen en los calendarios lo heredan, y de ahí lo toma "
             "el motor de work entries. Vacío = el día simplemente no "
             "genera jornada.",
    )
    leave_ids = fields.One2many(
        "resource.calendar.leaves",
        "pe_public_holiday_id",
        string="Descansos aplicados",
        readonly=True,
    )
    leave_count = fields.Integer(
        string="Calendarios aplicados", compute="_compute_leave_count")

    @api.model
    def _default_work_entry_type_id(self):
        """Concepto PE de descanso, si la nómina peruana está instalada.

        Dependencia blanda a propósito: el módulo se puede usar solo con
        ``hr_holidays`` y sin ``al_hr_pe``.
        """
        return self.env.ref("al_hr_pe.wd_DOM", raise_if_not_found=False)

    @api.depends("date")
    def _compute_year(self):
        for r in self:
            r.year = r.date.year if r.date else 0

    @api.depends("leave_ids")
    def _compute_leave_count(self):
        for holiday in self:
            holiday.leave_count = len(holiday.leave_ids)

    def _holiday_datetime_range(self, calendar):
        tz_name = calendar.tz or "UTC"
        tz = timezone(tz_name)
        local_start = tz.localize(datetime.combine(self.date, time(0, 0, 0)))
        if self.is_full_day:
            local_end = tz.localize(datetime.combine(self.date, time(23, 59, 59)))
        else:
            hour = int(self.half_day_starts_at)
            minute = int(round((self.half_day_starts_at - hour) * 60))
            local_end = tz.localize(datetime.combine(self.date, time(hour, minute, 0)))
        return (
            local_start.astimezone(UTC).replace(tzinfo=None),
            local_end.astimezone(UTC).replace(tzinfo=None),
        )

    def _target_calendars(self):
        """Calendarios de las compañías activas.

        Antes se escribía en **todos** los calendarios de la base: en
        multicompañía eso metía feriados en compañías ajenas a la sesión.
        """
        return self.env["resource.calendar"].search([
            ("company_id", "in", list(self.env.companies.ids) + [False]),
        ])

    def action_apply_to_calendars(self):
        Leaves = self.env["resource.calendar.leaves"]
        calendars = self._target_calendars()
        created = updated = 0
        for holiday in self:
            for cal in calendars:
                date_from, date_to = holiday._holiday_datetime_range(cal)
                vals = {
                    "name": holiday.name,
                    "calendar_id": cal.id,
                    "company_id": cal.company_id.id or self.env.company.id,
                    "date_from": date_from,
                    "date_to": date_to,
                    "work_entry_type_id": holiday.work_entry_type_id.id or False,
                    "pe_public_holiday_id": holiday.id,
                }
                # La clave es feriado+calendario, no las fechas exactas:
                # con la clave anterior, cambiar la zona horaria del
                # calendario duplicaba el descanso en vez de corregirlo.
                existing = Leaves.search([
                    ("pe_public_holiday_id", "=", holiday.id),
                    ("calendar_id", "=", cal.id),
                ], limit=1)
                if existing:
                    existing.write(vals)
                    updated += 1
                else:
                    Leaves.create(vals)
                    created += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Holidays Applied"),
                "message": _(
                    "%(created)d descansos creados y %(updated)d actualizados "
                    "en %(calendars)d calendario(s).",
                    created=created, updated=updated, calendars=len(calendars)),
                "type": "success",
            },
        }

    def action_view_leaves(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Descansos de %s", self.name),
            "res_model": "resource.calendar.leaves",
            "view_mode": "list,form",
            "domain": [("pe_public_holiday_id", "=", self.id)],
        }

    @api.model
    def cron_apply_yearly_holidays(self):
        """Aplica los feriados del año en curso y del siguiente.

        Incluir el año siguiente evita el hueco de enero cuando el cron
        se salta o la planificación se hace en diciembre.
        """
        this_year = date.today().year
        holidays = self.search([("year", "in", (this_year, this_year + 1))])
        if holidays:
            holidays.action_apply_to_calendars()


class ResourceCalendarLeaves(models.Model):
    _inherit = "resource.calendar.leaves"

    pe_public_holiday_id = fields.Many2one(
        "pe.public.holiday",
        string="Feriado (PE)",
        index="btree_not_null",
        ondelete="cascade",
        help="Feriado peruano que generó este descanso. Permite volver a "
             "aplicarlo sin duplicarlo y quitarlo al borrar el feriado.",
    )
