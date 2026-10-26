# -*- coding: utf-8 -*-
"""Servicios del portal de obra (requerimiento CREVAL v1.0, 4.11).

Toda la lógica de las pantallas del portal está aquí, con el usuario del
portal como usuario del entorno: los controladores JSON (``/construction/api/v1``)
solo leen el pedido, llaman al servicio y devuelven su resultado, de modo que
una aplicación nativa futura usa los mismos servicios sin cambios en Odoo.

Los usuarios del portal no leen los modelos de Odoo: cada servicio comprueba
primero que la persona esté en el portal de la obra (y, la contrata, que sea
su partida u orden) y después lee o escribe con sudo solo eso. Al
sincronizar, Odoo vuelve a validar las reglas (saldo, fechas, permisos)."""
import base64
import re
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.al_construction_planner.models.common import DRIVER_TYPES

from .daily_report import WEATHER

MAX_PHOTO_BYTES = 8 * 1024 * 1024
API_VERSION = 1
#: Palabras que no cuentan para las iniciales del logo («Creamos Valor S.A.C.» → CV).
LEGAL_WORDS = {'SA', 'SAC', 'SAA', 'SRL', 'EIRL', 'DE', 'DEL', 'LA', 'LOS', 'Y'}


#: «3.04.01 Trabajo de pintura» → código y nombre de la partida (CR-17).
TASK_CODE = re.compile(r'^\s*(\d[\w.\-]*)\s+(.*)$', re.S)
#: Rol del recurso de la línea del plan en el portal.
KIND_LABELS = {'labor': 'personal propio', 'contract': 'contrata'}


def _split_task(task):
    """(código, nombre) de una partida cuyo nombre empieza con su código."""
    name = (task.name or '').strip()
    match = TASK_CODE.match(name)
    return (match.group(1), match.group(2).strip()) if match else ('', name)


def _task_labels(task, activity=None, kind=None):
    """Cómo se muestra una partida en el portal (CR-17): código, nombre, nivel
    superior y rol; nunca la ruta interna del árbol."""
    code, name = _split_task(task)
    parent = task.parent_id
    role = activity.name if activity else ''
    # Sin repetir el tipo si la actividad ya lo dice («Drywall (contrata)»).
    if role and kind in KIND_LABELS and KIND_LABELS[kind] not in role.lower():
        role = '%s (%s)' % (role, KIND_LABELS[kind])
    return {
        'task_code': code, 'task_name': name,
        'parent_label': ' '.join(_split_task(parent)).strip() if parent else '',
        'role_label': role,
    }


def _initials(name):
    words = [w for w in re.split(r'[^\w]+', name or '') if w and w.upper() not in LEGAL_WORDS]
    return ''.join(w[0] for w in words[:2]).upper() or 'OB'


class ConstructionPortalService(models.AbstractModel):
    _name = 'construction.portal.service'
    _description = 'Servicios del portal de obra'

    # ------------------------------------------------------------------
    # Alcance
    # ------------------------------------------------------------------
    def _members(self, project=None):
        # sudo: el usuario del portal no lee el personal del portal; solo
        # sus propias filas.
        domain = [('user_id', '=', self.env.uid), ('active', '=', True)]
        if project:
            domain.append(('project_id', '=', project.id))
        return self.env['construction.portal.member'].sudo().search(domain)

    def _project(self, project_id):
        """La obra del pedido si la persona está en su portal."""
        try:
            project_id = int(project_id or 0)
        except (TypeError, ValueError):
            project_id = 0
        project = self.env['project.project'].sudo().browse(project_id).exists()
        members = self._members(project) if project else self.env['construction.portal.member']
        if not members:
            raise AccessError(self.env._('No está en el portal de esa obra.'))
        return project, members

    def _roles(self, members):
        return set(members.mapped('role'))

    def _partners(self, members):
        return members.filtered(lambda m: m.role == 'contractor').partner_id.commercial_partner_id

    def _lines(self, project, members):
        """Partidas de la persona en el plan vigente: la contrata, las suyas;
        el capataz, las de personal propio; la oficina técnica, todas."""
        plan = project._construction_current_plan()
        if not plan:
            return self.env['construction.resource.plan.line'].sudo()
        roles = self._roles(members)
        domain = [('plan_id', '=', plan.id), ('resource_type', 'in', DRIVER_TYPES),
                  ('activity_id', '!=', False), ('task_id', '!=', False),
                  ('line_state', '!=', 'cancel')]
        if 'office' not in roles:
            parts = []
            partners = self._partners(members)
            if partners:
                parts.append([('resource_type', '=', 'contract'),
                              ('partner_id', 'child_of', partners.ids)])
            if 'foreman' in roles:
                parts.append([('resource_type', '=', 'labor')])
            if not parts:
                return self.env['construction.resource.plan.line'].sudo()
            domain += ['|'] * (len(parts) - 1) + [term for part in parts for term in part]
        # sudo: el dominio de arriba limita las líneas a las de la persona.
        return self.env['construction.resource.plan.line'].sudo().search(domain)

    def _submission(self, kind, uuid):
        """El envío ya registrado con ese identificador (o vacío)."""
        if not uuid:
            raise UserError(self.env._('Falta el identificador del registro.'))
        return self.env['construction.portal.submission'].sudo().search([
            ('uuid', '=', uuid), ('user_id', '=', self.env.uid), ('kind', '=', kind),
            ('state', '=', 'done')], limit=1)

    def _portal_register(self, kind, uuid, records):
        self.env['construction.portal.submission'].sudo().create({
            'uuid': uuid, 'user_id': self.env.uid, 'kind': kind, 'res_model': records._name,
            'res_ids': ','.join(str(i) for i in records.ids), 'state': 'done'})

    def _photos(self, photos, res_model, required=False):
        """Adjuntos de las fotos del celular ({name, data base64, mimetype})."""
        photos = [photo for photo in photos or [] if photo and photo.get('data')]
        if required and not photos:
            raise UserError(self.env._('Tome al menos una foto.'))
        values = []
        for index, photo in enumerate(photos, start=1):
            data = photo['data'].split(',', 1)[-1]
            if len(data) * 3 / 4 > MAX_PHOTO_BYTES:
                raise UserError(self.env._('La foto %s pesa más de 8 MB.', index))
            values.append({'name': photo.get('name') or 'foto-%s.jpg' % index, 'datas': data,
                           'mimetype': photo.get('mimetype') or 'image/jpeg',
                           'res_model': res_model, 'res_id': 0})
        # sudo: las fotos del portal las adjunta el sistema al registro.
        return self.env['ir.attachment'].sudo().create(values)

    def _portal_date(self, value, company, past_days=None):
        day = fields.Date.to_date(value) if value else fields.Date.context_today(self)
        today = fields.Date.context_today(self)
        if day > today:
            raise UserError(self.env._('La fecha no puede ser futura.'))
        if past_days is not None and day < today - timedelta(days=past_days):
            raise UserError(self.env._(
                'La fecha no puede ser anterior a %s días.', past_days))
        return day

    # ------------------------------------------------------------------
    # Inicio y sincronización (pantallas 2 y 3)
    # ------------------------------------------------------------------
    @api.model
    def me(self):
        user = self.env.user
        projects = defaultdict(set)
        for member in self._members():
            projects[member.project_id].add(member.role)
        company = user.company_id
        return {
            'api': API_VERSION,
            'user': {'id': user.id, 'name': user.name, 'initials': _initials(user.name)},
            'company': {'name': company.name, 'initials': _initials(company.name),
                        'color': company.primary_color or '#714B67'},
            'projects': [{'id': project.id, 'name': project.display_name,
                          'roles': sorted(roles)} for project, roles in projects.items()],
            'params': {'progress_days': company.construction_portal_progress_days,
                       'photo_max_px': company.construction_portal_photo_max_px or 1600},
        }

    @api.model
    def sync(self, project_id):
        """Lo que el celular guarda para trabajar sin señal."""
        project, members = self._project(project_id)
        roles = self._roles(members)
        site = project._construction_site() if hasattr(project, '_construction_site') else False
        lines = self._lines(project, members)
        today = fields.Date.context_today(self)
        week_start, week_end = project._construction_period(today)
        last_validation = self._last_validation(lines)
        data = {
            'project': {'id': project.id, 'name': project.display_name,
                        'week_start': fields.Date.to_string(week_start),
                        'week_end': fields.Date.to_string(week_end),
                        'location': project.construction_location_id.complete_name or '',
                        'latitude': site.latitude if site else 0.0,
                        'longitude': site.longitude if site else 0.0,
                        'radius_m': site.radius_m if site else 0},
            'roles': sorted(roles),
            'members': [{'role': member.role, 'name': member.name,
                         'partner': member.partner_id.commercial_partner_id.name or ''}
                        for member in members],
            'partidas': [self._line_data(line, last_validation.get(line.id)) for line in
                         lines.sorted(lambda l: (l.task_id.construction_path or '', l.id))],
            'rework_reasons': [[code, label] for code, label in self.env[
                'construction.task.progress']._fields['rework_reason']._description_selection(
                self.env)],
            'weather': [[code, label] for code, label in WEATHER],
            'synced_at': fields.Datetime.to_string(fields.Datetime.now()),
        }
        if roles & {'foreman', 'office'}:
            data['catalog'] = self._catalog(project, lines, roles)
            data['deliveries'] = self._deliveries(project)
            data['returnables'] = self._returnables(project)
            data['daily'] = self._daily_data(project, site, today)
        if 'foreman' in roles:
            data['crew'] = self._crew(project, members)
        if 'contractor' in roles:
            contract = self.valuations(project.id)
            data['valuations'] = contract['valuations']
            data['orders'] = contract['orders']
            data['contract_partner'] = contract['partner']
        data['counters'] = self._counters(project, members, lines, data, today)
        return data

    def _line_data(self, line, last_validation=None):
        validated = line.qty_executed
        pending = line._get_reported_qty()
        labels = _task_labels(line.task_id, line.activity_id, line.resource_type)
        return dict(labels, **{
            # «item» y «path» siguen para la aplicación ya instalada, sin la
            # ruta interna (CR-17): el código de la partida y su nivel superior.
            'id': line.id, 'item': labels['task_code'],
            'name': line.task_id.name, 'path': labels['parent_label'],
            'activity': line.activity_id.display_name, 'uom': line.activity_id.uom_id.name,
            'kind': line.resource_type, 'planned': line.qty_planned, 'validated': validated,
            'pending': pending, 'balance': line.qty_planned - validated - pending,
            # Lo que admite el plan sobre lo presupuestado (tolerancia).
            'tolerance': line._get_tolerance_qty(),
            # Qué pasa más allá: bloquear, solo alerta o aprobación de la jefatura.
            'exceed_policy': line.plan_id._exceed_policy_for(line.resource_type),
            'last_validated': fields.Date.to_string(last_validation) if last_validation else '',
            'partner': line.partner_id.name or '',
        })

    def _last_validation(self, lines):
        """Fecha de la última validación de cada partida."""
        if not lines:
            return {}
        # sudo: el avance de las partidas de la persona (comprobadas al leerlas).
        groups = self.env['construction.task.progress'].sudo()._read_group(
            [('plan_line_id', 'in', lines.ids), ('state', '=', 'validated')],
            ['plan_line_id'], ['validation_date:max'])
        return {line.id: fields.Datetime.context_timestamp(self, last).date()
                for line, last in groups if last}

    def _counters(self, project, members, lines, data, today):
        """Los tres números del inicio: avances por validar, pedidos en
        aprobación y entregas por recibir hoy."""
        Progress = self.env['construction.task.progress'].sudo()
        to_validate = Progress.search_count([
            ('plan_line_id', 'in', lines.ids), ('state', '=', 'draft')]) if lines else 0
        requests = 0
        if self._roles(members) & {'foreman', 'office'}:
            domain = [('project_id', '=', project.id), ('state', '=', 'to_approve')]
            if 'office' not in self._roles(members):
                domain.append(('requested_by', '=', self.env.uid))
            # sudo: solo se cuentan los requerimientos de la obra (o los suyos).
            requests = self.env['construction.material.request'].sudo().search_count(domain)
        today_str = fields.Date.to_string(today)
        deliveries = [row for row in data.get('deliveries') or []
                      if (row.get('date_local') or '')[:10] <= today_str]
        return {'progress_to_validate': to_validate, 'requests_to_approve': requests,
                'deliveries_today': len(deliveries)}

    def _daily_data(self, project, site, today):
        """Lo que el parte diario trae ya llenado: el personal propio que
        marcó hoy en la sede, cada contrata de la obra y los avances del día."""
        own = 0
        if site:
            tz = site._tz()
            start = tz.localize(datetime.combine(today, time.min)).astimezone(pytz.utc)
            # sudo: solo se cuentan las marcaciones de hoy en la sede de la obra.
            own = len(self.env['hr.attendance'].sudo().search([
                ('l10n_pe_construction_site_id', '=', site.id),
                ('check_in', '>=', start.replace(tzinfo=None)),
                ('check_in', '<', (start + timedelta(days=1)).replace(tzinfo=None))
            ]).employee_id)
        plan = project._construction_current_plan()
        contractors = []
        if plan:
            # sudo: las contratas de la obra y lo que hacen (sin montos).
            contract_lines = self.env['construction.resource.plan.line'].sudo().search([
                ('plan_id', '=', plan.id), ('resource_type', '=', 'contract'),
                ('partner_id', '!=', False), ('line_state', '!=', 'cancel')])
            scopes = defaultdict(list)
            for line in contract_lines:
                partner = line.partner_id.commercial_partner_id
                name = line.activity_id.name
                if name and name not in scopes[partner]:
                    scopes[partner].append(name)
            contractors = [{'name': partner.name, 'scope': ', '.join(names[:2])}
                           for partner, names in sorted(scopes.items(), key=lambda kv: kv[0].name)]
        # sudo: los avances de hoy en la obra, para «Trabajos del día».
        progress = self.env['construction.task.progress'].sudo().search([
            ('task_id.project_id', '=', project.id), ('date', '=', today),
            ('state', '!=', 'rejected')], order='id')
        states = dict(progress._fields['state']._description_selection(self.env))
        # Reportados y validados, con su estado (7.1).
        work = [dict(_task_labels(p.task_id, p.activity_id), **{
            'item': _split_task(p.task_id)[0], 'name': _split_task(p.task_id)[1],
            'partner': p.partner_id.commercial_partner_id.name or '',
            'qty': p.qty, 'uom': p.activity_id.uom_id.name or '',
            'state': p.state, 'state_label': states.get(p.state, '')}) for p in progress]
        return {'own_today': own, 'contractors': contractors, 'work': work}

    # ------------------------------------------------------------------
    # Avance (pantalla 4)
    # ------------------------------------------------------------------
    @api.model
    def progress(self, values):
        """Avance de una partida con fotos, ubicación y re-trabajo; entra
        «Por validar» con origen Portal."""
        submission = self._submission('progress', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._project(values.get('project_id'))
        line = self._lines(project, members).filtered(
            lambda l: l.id == int(values.get('plan_line_id') or 0))
        if not line:
            raise AccessError(self.env._('Esa partida no es suya.'))
        company = project.company_id or self.env.company
        day = self._portal_date(values.get('date'), company, company.construction_portal_progress_days)
        qty = float(values.get('qty') or 0.0)
        if values.get('mode') == 'pct':
            target = line.qty_planned * float(values.get('pct') or 0.0) / 100.0
            qty = target - line.qty_executed - line._get_reported_qty()
        if qty <= 0:
            raise UserError(self.env._('El avance debe ser mayor que lo ya registrado.'))
        is_rework = bool(values.get('is_rework'))
        if is_rework and not values.get('rework_reason'):
            raise UserError(self.env._('Un re-trabajo pide su motivo.'))
        attachments = self._photos(values.get('photos'), 'construction.task.progress',
                                   required=True)
        # sudo: el avance lo crea la persona del portal sobre su partida
        # (comprobada arriba); queda «Por validar» con origen Portal.
        progress = self.env['construction.task.progress'].sudo().create({
            'task_id': line.task_id.id, 'activity_id': line.activity_id.id,
            'plan_line_id': line.id, 'date': day, 'qty': qty,
            'reported_by_id': self.env.uid, 'source': 'portal',
            'latitude': float(values.get('latitude') or 0.0),
            'longitude': float(values.get('longitude') or 0.0),
            'is_rework': is_rework, 'rework_reason': values.get('rework_reason') or False,
            'attachment_ids': [(6, 0, attachments.ids)],
        })
        attachments.write({'res_id': progress.id})
        if values.get('note'):
            progress.message_post(body=values['note'], author_id=self.env.user.partner_id.id)
        self._portal_register('progress', values['uuid'], progress)
        return {'status': 'done', 'ids': str(progress.id), 'name': progress.name,
                'over_balance': line.qty_planned < line.qty_executed + line._get_reported_qty(),
                'exceed_state': progress.exceed_state}

    # ------------------------------------------------------------------
    # Parte diario (pantalla 6)
    # ------------------------------------------------------------------
    @api.model
    def daily_report(self, values):
        submission = self._submission('daily_report', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._project(values.get('project_id'))
        if not self._roles(members) & {'foreman', 'office'}:
            raise AccessError(self.env._('El parte diario lo envía el maestro de obra.'))
        company = project.company_id or self.env.company
        day = self._portal_date(values.get('date'), company)
        Report = self.env['construction.daily.report'].sudo()
        report = Report.search([('project_id', '=', project.id), ('date', '=', day)], limit=1)
        restrictions = set(values.get('restrictions') or [])
        attachments = self._photos(values.get('photos'), 'construction.daily.report')
        vals = {
            'project_id': project.id, 'date': day, 'user_id': self.env.uid,
            'weather': values.get('weather') or False,
            'restriction_material': 'material' in restrictions,
            'restriction_front': 'front' in restrictions,
            'restriction_weather': 'weather' in restrictions,
            'occurrences': values.get('occurrences') or False,
            'staff_line_ids': [(5, 0, 0)] + [(0, 0, {
                'name': row.get('name') or '-', 'source': row.get('source') or 'own',
                'count': int(row.get('count') or 0)}) for row in values.get('staff') or []],
            'state': 'sent',
        }
        if values.get('signature'):
            vals['signature'] = values['signature'].split(',', 1)[-1]
        # sudo: el parte lo crea el maestro de obra del portal de su obra.
        if report:
            report.write(vals)
        else:
            report = Report.create(vals)
        if attachments:
            attachments.write({'res_id': report.id})
            report.attachment_ids = [(4, a.id) for a in attachments]
        if project.user_id:
            report.message_post(body=self.env._('Parte diario enviado al residente.'),
                                partner_ids=project.user_id.partner_id.ids)
        self._portal_register('daily_report', values['uuid'], report)
        return {'status': 'done', 'ids': str(report.id), 'name': report.name}

    # ------------------------------------------------------------------
    # Cuadrilla y tareo (pantalla 7)
    # ------------------------------------------------------------------
    def _crew(self, project, members):
        """Cuadrilla del capataz: las personas con turno en la obra en los
        últimos días y las que marcan en su sede."""
        Employee = self.env['hr.employee'].sudo()
        employees = Employee
        if 'planning.slot' in self.env:
            today = fields.Date.context_today(self)
            slots = self.env['planning.slot'].sudo().search([
                ('project_id', '=', project.id),
                ('start_datetime', '<=', datetime.combine(today + timedelta(days=1), time.min)),
                ('end_datetime', '>=', datetime.combine(today - timedelta(days=7), time.min))])
            employees |= slots.resource_id.employee_id
        employees |= members.employee_id
        return [{'id': employee.id, 'name': employee.name,
                 'category': employee.version_id.l10n_pe_construction_category_id.name or ''
                 if 'l10n_pe_construction_category_id' in employee.version_id._fields else ''}
                for employee in employees.sorted('name')]

    @api.model
    def crew_day(self, values):
        """Asistencia (marcación en la sede de la obra) y horas por partida
        (tareo) del día."""
        submission = self._submission('crew_day', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._project(values.get('project_id'))
        if 'foreman' not in self._roles(members):
            raise AccessError(self.env._('El tareo lo registra el capataz.'))
        company = project.company_id or self.env.company
        day = self._portal_date(values.get('date'), company, company.construction_portal_progress_days)
        crew = {row['id'] for row in self._crew(project, members)}
        lines = self._lines(project, members)
        site = project._construction_site() if hasattr(project, '_construction_site') else False
        if not site:
            raise UserError(self.env._('La obra %s no tiene sede de marcación.',
                                       project.display_name))
        hours_day = company.construction_crew_hours_per_day or 8.0 \
            if 'construction_crew_hours_per_day' in company._fields else 8.0
        tz = site._tz()
        Attendance = self.env['hr.attendance'].sudo()
        Tareo = self.env['construction.portal.tareo'].sudo()
        attendances = Attendance
        tareos = Tareo
        hours_by_employee = defaultdict(float)
        for row in values.get('hours') or []:
            employee_id = int(row.get('employee_id') or 0)
            line = lines.filtered(lambda l: l.id == int(row.get('plan_line_id') or 0))
            hours = float(row.get('hours') or 0.0)
            if employee_id not in crew or not line or hours <= 0:
                continue
            hours_by_employee[employee_id] += hours
        for employee_id, total in hours_by_employee.items():
            if total > hours_day + 4:
                raise UserError(self.env._(
                    'Una persona no puede pasar de %s horas en el día.', hours_day + 4))
        # Se rehace el tareo del día de esta cuadrilla.
        Tareo.search([('project_id', '=', project.id), ('date', '=', day),
                      ('employee_id', 'in', list(crew))]).unlink()
        for row in values.get('hours') or []:
            employee_id = int(row.get('employee_id') or 0)
            line = lines.filtered(lambda l: l.id == int(row.get('plan_line_id') or 0))
            hours = float(row.get('hours') or 0.0)
            if employee_id in crew and line and hours > 0:
                tareos |= Tareo.create({'project_id': project.id, 'date': day,
                                        'employee_id': employee_id, 'plan_line_id': line.id,
                                        'hours': hours})
        for row in values.get('attendance') or []:
            employee_id = int(row.get('employee_id') or 0)
            if employee_id not in crew or not row.get('present'):
                continue
            hour, minute = (str(row.get('time') or '07:30').split(':') + ['0'])[:2]
            local = tz.localize(datetime.combine(day, time(int(hour), int(minute))))
            check_in = local.astimezone(pytz.utc).replace(tzinfo=None)
            worked = hours_by_employee.get(employee_id) or hours_day
            existing = Attendance.search([
                ('employee_id', '=', employee_id), ('l10n_pe_construction_site_id', '=', site.id),
                ('check_in', '>=', check_in - timedelta(hours=12)),
                ('check_in', '<=', check_in + timedelta(hours=12))], limit=1)
            vals = {'check_in': check_in, 'check_out': check_in + timedelta(hours=worked)}
            # sudo: la marcación de la cuadrilla la registra el capataz desde
            # el portal (RR. HH. la ve como marcación de la sede).
            if existing:
                existing.write(vals)
                attendance = existing
            else:
                attendance = Attendance.create(dict(
                    vals, employee_id=employee_id, l10n_pe_construction_site_id=site.id))
            # Las horas trabajadas descuentan el almuerzo del horario del
            # empleado: la salida se corre lo que dura el descanso.
            gap = worked - attendance.worked_hours
            if gap > 0.01:
                attendance.check_out += timedelta(hours=gap)
            attendances |= attendance
        if tareos and not attendances:
            self.env['construction.crew.day']._refresh_executed(project, day, day)
        records = attendances or tareos
        self._portal_register('crew_day', values['uuid'], records)
        return {'status': 'done', 'ids': ','.join(str(i) for i in records.ids),
                'present': len(attendances), 'tareo': len(tareos)}

    # ------------------------------------------------------------------
    # Requerimientos (pantallas 8 y 9)
    # ------------------------------------------------------------------
    def _catalog(self, project, lines, roles=None):
        """Materiales de las partidas con el saldo del plan; EPP y útiles y
        aseo con sus kits. El capataz ve los materiales de las recetas de su
        cuadrilla (las partidas que ejecuta); la oficina técnica, todos."""
        plan = project._construction_current_plan()
        Product = self.env['product.product'].sudo()
        material_lines = self.env['construction.resource.plan.line'].sudo()
        if plan:
            domain = [('plan_id', '=', plan.id), ('resource_type', '=', 'material'),
                      ('product_id', '!=', False), ('is_client_supply', '=', False),
                      ('line_state', '!=', 'cancel')]
            # Sin partidas propias (capataz sin cuadrilla asignada), el catálogo
            # de toda la obra.
            if roles is not None and 'office' not in roles and lines:
                domain.append(('task_id', 'in', lines.task_id.ids))
            material_lines = material_lines.search(domain)
        partida = []
        for line in material_lines:
            labels = _task_labels(line.task_id)
            partida.append(dict(labels, **{
                'product_id': line.product_id.id, 'name': line.product_id.display_name,
                'uom': line.product_uom_id.name, 'task_id': line.task_id.id,
                'item': labels['task_code'], 'task': labels['task_name'],
                'balance': line.qty_planned - line.qty_requested}))
        company = project.company_id or self.env.company
        result = {'partida': partida}
        for catalog in ('epp', 'office'):
            products = Product.search([
                ('product_tmpl_id.categ_id.construction_portal_catalog', '=', catalog),
                ('company_id', 'in', (company.id, False))], limit=500)
            kits = self.env['construction.portal.kit'].sudo().search([
                ('catalog', '=', catalog), ('company_id', 'in', (company.id, False))])
            result[catalog] = {
                'products': [{'product_id': p.id, 'name': p.display_name,
                              'uom': p.uom_id.name,
                              'note': p.description_picking or ''} for p in products],
                'kits': [{'id': kit.id, 'name': kit.name, 'lines': [
                    {'product_id': kl.product_id.id, 'name': kl.product_id.display_name,
                     'uom': kl.product_id.uom_id.name, 'qty': kl.qty}
                    for kl in kit.line_ids]} for kit in kits],
            }
        return result

    @api.model
    def material_request(self, values):
        """Un requerimiento de obra con los materiales de partida y otro
        interno con la analítica de gastos generales de la obra para EPP,
        útiles y aseo; cada uno va a su aprobación."""
        submission = self._submission('material_request', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._project(values.get('project_id'))
        if not self._roles(members) & {'foreman', 'office'}:
            raise AccessError(self.env._('Los requerimientos los piden el capataz y la oficina '
                                         'técnica.'))
        catalog = self._catalog(project, self._lines(project, members), self._roles(members))
        allowed = {
            'partida': {(row['product_id'], row['task_id']) for row in catalog['partida']},
            'epp': {row['product_id'] for row in catalog['epp']['products']} |
            {line['product_id'] for kit in catalog['epp']['kits'] for line in kit['lines']},
            'office': {row['product_id'] for row in catalog['office']['products']} |
            {line['product_id'] for kit in catalog['office']['kits'] for line in kit['lines']},
        }
        site_lines, internal_lines, texts = [], [], []
        Product = self.env['product.product'].sudo()
        for row in values.get('lines') or []:
            qty = float(row.get('qty') or 0.0)
            if qty <= 0:
                continue
            kind = row.get('catalog') or 'partida'
            product_id = int(row.get('product_id') or 0)
            if not product_id:
                if row.get('text'):
                    texts.append('%s × %s' % (row['text'], qty))
                continue
            product = Product.browse(product_id)
            if kind == 'partida':
                task_id = int(row.get('task_id') or 0)
                if (product_id, task_id) not in allowed['partida']:
                    raise AccessError(self.env._('%s no es material de esa partida.',
                                                 product.display_name))
                site_lines.append({'product_id': product_id, 'product_qty': qty,
                                   'product_uom_id': product.uom_id.id, 'task_id': task_id})
            elif product_id in allowed.get(kind, set()):
                internal_lines.append({'product_id': product_id, 'product_qty': qty,
                                       'product_uom_id': product.uom_id.id})
            else:
                raise AccessError(self.env._('%s no está en el catálogo.', product.display_name))
        if not site_lines and not internal_lines and not texts:
            raise UserError(self.env._('El requerimiento no tiene materiales.'))
        note = values.get('note') or ''
        if texts:
            note = '%s\n%s: %s' % (note, self.env._('Fuera de catálogo'), '; '.join(texts))
        common = {'date_required': values.get('date_required') or False,
                  'priority': '1' if values.get('priority') == 'urgent' else '0',
                  'note': note.strip() or False, 'requested_by': self.env.uid}
        Request = self.env['construction.material.request'].sudo()
        requests = Request
        if site_lines or (texts and not internal_lines):
            tasks = {line['task_id'] for line in site_lines}
            # sudo: el requerimiento lo pide la persona del portal de su obra;
            # va a la aprobación por niveles como cualquier otro.
            requests |= Request.create(dict(
                common, request_type='site', project_id=project.id,
                task_id=list(tasks)[0] if len(tasks) == 1 else False,
                line_ids=[(0, 0, line) for line in site_lines]))
        if internal_lines:
            area = project.construction_portal_overhead_area_id
            if not area:
                raise UserError(self.env._(
                    'La obra %s no tiene la analítica de gastos generales para EPP, útiles y '
                    'aseo.', project.display_name))
            # Con la obra (7.3): se carga a gastos generales, pero aparece en
            # la obra y en sus reportes.
            requests |= Request.create(dict(
                common, request_type='internal', area_id=area.id, project_id=project.id,
                line_ids=[(0, 0, line) for line in internal_lines]))
        for request in requests.filtered('line_ids'):
            request.action_request_approval()
        self._portal_register('material_request', values['uuid'], requests)
        return {'status': 'done', 'ids': ','.join(str(i) for i in requests.ids),
                'names': requests.mapped('name'),
                'states': requests.mapped('state')}

    # ------------------------------------------------------------------
    # Recepción y devolución (pantallas 10 y 11)
    # ------------------------------------------------------------------
    def _deliveries(self, project):
        location = project.construction_location_id
        if not location:
            return []
        # sudo: las entregas por recibir en la ubicación de la obra.
        pickings = self.env['stock.picking'].sudo().search([
            ('location_dest_id', 'child_of', location.id), ('state', '=', 'assigned')]).filtered(
            lambda p: not p.location_id._child_of(location))
        return [{'id': picking.id, 'name': picking.name, 'origin': picking.origin or '',
                 'date': fields.Datetime.to_string(picking.scheduled_date),
                 'date_local': fields.Date.to_string(fields.Datetime.context_timestamp(
                     self, picking.scheduled_date).date()) if picking.scheduled_date else '',
                 # Compra directa a obra o despacho del almacén, con su proveedor.
                 'kind': 'purchase' if picking.picking_type_id.code == 'incoming' else 'dispatch',
                 'partner': picking.partner_id.commercial_partner_id.name or '',
                 'lines': [{'move_id': move.id, 'name': move.product_id.display_name,
                            'uom': move.product_uom.name, 'sent': move.product_uom_qty}
                           for move in picking.move_ids.filtered(
                               lambda m: m.state not in ('done', 'cancel'))]}
                for picking in pickings]

    @api.model
    def reception(self, values):
        """Valida lo recibido en la obra; el faltante queda pendiente
        (entrega parcial)."""
        submission = self._submission('reception', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._project(values.get('project_id'))
        if not self._roles(members) & {'foreman', 'office'}:
            raise AccessError(self.env._('La recepción la registra el capataz.'))
        picking_id = int(values.get('picking_id') or 0)
        allowed = {row['id'] for row in self._deliveries(project)}
        if picking_id not in allowed:
            raise AccessError(self.env._('Esa entrega no es de su obra o ya se recibió.'))
        picking = self.env['stock.picking'].sudo().browse(picking_id)
        attachments = self._photos(values.get('photos'), 'stock.picking', required=True)
        received = {int(row.get('move_id') or 0): float(row.get('qty') or 0.0)
                    for row in values.get('lines') or []}
        for move in picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
            qty = max(received.get(move.id, 0.0), 0.0)
            move.quantity = qty
            move.picked = True
        if not any(picking.move_ids.mapped('quantity')):
            raise UserError(self.env._('No recibió nada de esta entrega.'))
        # sudo: la persona de la obra confirma lo que llegó; el despacho
        # (M16-10) se valida con lo recibido.
        result = picking.with_context(skip_sms=True).button_validate()
        if isinstance(result, dict) and result.get('res_model') == 'stock.backorder.confirmation':
            wizard = self.env['stock.backorder.confirmation'].sudo().with_context(
                result.get('context', {})).create({'pick_ids': [(6, 0, picking.ids)]})
            wizard.process()
        attachments.write({'res_id': picking.id})
        note = values.get('note')
        picking.message_post(body=self.env._('Recibido en obra desde el portal.%s',
                                             (' %s' % note) if note else ''),
                             attachment_ids=attachments.ids)
        backorder = self.env['stock.picking'].sudo().search(
            [('backorder_id', '=', picking.id)], limit=1)
        self._portal_register('reception', values['uuid'], picking)
        return {'status': 'done', 'ids': str(picking.id), 'name': picking.name,
                'backorder': backorder.name or False}

    def _returnables(self, project):
        location = project.construction_location_id
        if not location:
            return []
        # sudo: el stock de la ubicación de la obra.
        quants = self.env['stock.quant'].sudo().search([
            ('location_id', 'child_of', location.id), ('quantity', '>', 0)])
        totals = defaultdict(float)
        for quant in quants:
            totals[quant.product_id] += quant.quantity
        return [{'product_id': product.id, 'name': product.display_name,
                 'uom': product.uom_id.name, 'qty': qty}
                for product, qty in sorted(totals.items(), key=lambda kv: kv[0].display_name)]

    @api.model
    def return_material(self, values):
        """Lo que vuelve al almacén central (transferencia) y lo dañado a
        merma (desecho)."""
        submission = self._submission('return', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._project(values.get('project_id'))
        if not self._roles(members) & {'foreman', 'office'}:
            raise AccessError(self.env._('La devolución la registra el capataz.'))
        location = project.construction_location_id
        stock = {row['product_id']: row['qty'] for row in self._returnables(project)}
        attachments = self._photos(values.get('photos'), 'stock.picking', required=True)
        good, damaged = [], []
        for row in values.get('lines') or []:
            product_id, qty = int(row.get('product_id') or 0), float(row.get('qty') or 0.0)
            if qty <= 0:
                continue
            if product_id not in stock or qty > stock[product_id] + 1e-6:
                raise UserError(self.env._('No hay tanto en la obra para devolver.'))
            (damaged if row.get('state') == 'damaged' else good).append((product_id, qty))
        if not good and not damaged:
            raise UserError(self.env._('Indique lo que devuelve.'))
        company = project.company_id or self.env.company
        warehouse = self.env['stock.warehouse'].sudo().search(
            [('company_id', '=', company.id)], limit=1)
        Product = self.env['product.product'].sudo()
        records = self.env['stock.picking'].sudo()
        if good:
            # sudo: la devolución la registra la obra; el almacén la recibe.
            picking = records.create({
                'picking_type_id': warehouse.int_type_id.id, 'location_id': location.id,
                'location_dest_id': warehouse.lot_stock_id.id, 'origin': self.env._(
                    'Devolución de %s', project.display_name),
                'move_ids': [(0, 0, {
                    'product_id': product_id, 'product_uom_qty': qty,
                    'product_uom': Product.browse(product_id).uom_id.id,
                    'location_id': location.id, 'location_dest_id': warehouse.lot_stock_id.id,
                }) for product_id, qty in good]})
            picking.action_confirm()
            note = self.env._('Traslado: %s', dict(
                own=self.env._('unidad propia (guía de remisión)'),
                supplier=self.env._('flete de proveedor')).get(values.get('transport'), '-'))
            attachments.write({'res_id': picking.id})
            picking.message_post(body=note, attachment_ids=attachments.ids)
            records |= picking
        scraps = self.env['stock.scrap'].sudo()
        for product_id, qty in damaged:
            scrap = scraps.create({'product_id': product_id, 'scrap_qty': qty,
                                   'product_uom_id': Product.browse(product_id).uom_id.id,
                                   'location_id': location.id,
                                   'origin': self.env._('Dañado en %s', project.display_name),
                                   'company_id': company.id})
            scrap.action_validate()
            scraps |= scrap
        self._portal_register('return', values['uuid'], records or scraps)
        return {'status': 'done', 'pickings': records.mapped('name'), 'scraps': len(scraps)}

    # ------------------------------------------------------------------
    # Valorizaciones de la contrata (pantallas 12 y 13)
    # ------------------------------------------------------------------
    def _contract_scope(self, project_id):
        project, members = self._project(project_id)
        partners = self._partners(members)
        if not partners:
            raise AccessError(self.env._('Las valorizaciones las ve la contrata.'))
        return project, partners

    @api.model
    def valuations(self, project_id):
        project, partners = self._contract_scope(project_id)
        # sudo: solo las órdenes y valorizaciones de la empresa de la persona.
        orders = self.env['purchase.order'].sudo().search([
            ('construction_project_id', '=', project.id),
            ('partner_id', 'child_of', partners.ids),
            ('construction_is_service_order', '=', True), ('state', '=', 'purchase')])
        settlements = self.env['construction.contract.settlement'].sudo().search([
            ('project_id', '=', project.id), ('partner_id', 'child_of', partners.ids),
            ('state', '!=', 'cancel')], order='period_end desc, id desc')
        states = dict(settlements._fields['state']._description_selection(self.env))
        Order = self.env['purchase.order']
        frequencies = dict(Order._fields['construction_frequency']._description_selection(
            self.env)) if 'construction_frequency' in Order._fields else {}
        weekdays = dict(Order._fields['construction_cutoff_weekday']._description_selection(
            self.env)) if 'construction_cutoff_weekday' in Order._fields else {}
        Deduction = self.env['construction.contract.deduction'].sudo() \
            if 'construction.contract.deduction' in self.env else None
        Progress = self.env['construction.task.progress'].sudo()

        def order_data(order):
            valued = sum(order._construction_valued_settlements().mapped('amount_direct')) \
                if hasattr(order, '_construction_valued_settlements') else 0.0
            deductions = sum(Deduction.search([
                ('purchase_order_id', '=', order.id), ('state', '=', 'applied')]).mapped(
                'signed_amount')) if Deduction is not None else 0.0
            frequency = getattr(order, 'construction_frequency', False) or ''
            weekday = getattr(order, 'construction_cutoff_weekday', False) or ''
            return {
                'id': order.id, 'name': order.name, 'amount_untaxed': order.amount_untaxed,
                'valued': valued,
                'valued_pct': round(100.0 * valued / order.amount_untaxed)
                if order.amount_untaxed else 0,
                'guarantee': getattr(order, 'construction_guarantee_retained', 0.0),
                'deductions': deductions,
                'frequency': frequency, 'frequency_label': frequencies.get(frequency, ''),
                'cutoff_label': weekdays.get(weekday, '') if frequency == 'weekly' else '',
            }

        def settlement_data(settlement):
            pending = 0
            if settlement.state == 'draft':
                # Avances de la contrata aún por validar hasta el corte.
                pending = Progress.search_count([
                    ('task_id.project_id', '=', project.id),
                    ('partner_id', 'child_of', partners.ids), ('state', '=', 'draft'),
                    ('date', '<=', settlement.period_end)])
            return {
                'id': settlement.id, 'name': settlement.display_name,
                'title': settlement.title if 'title' in settlement._fields else '',
                'period_start': fields.Date.to_string(settlement.period_start),
                'period_end': fields.Date.to_string(settlement.period_end),
                'state': settlement.state, 'state_label': states.get(settlement.state),
                'amount': settlement.amount_net if 'amount_net' in settlement._fields else 0.0,
                'amount_total': settlement.amount_total
                if 'amount_total' in settlement._fields else 0.0,
                'invoice': settlement.invoice_id.name or '',
                'pending_progress': pending,
            }

        return {'partner': partners[:1].name or '',
                'orders': [order_data(order) for order in orders],
                'valuations': [settlement_data(settlement) for settlement in settlements]}

    def _settlement(self, project_id, settlement_id):
        project, partners = self._contract_scope(project_id)
        settlement = self.env['construction.contract.settlement'].sudo().search([
            ('id', '=', int(settlement_id or 0)), ('project_id', '=', project.id),
            ('partner_id', 'child_of', partners.ids)], limit=1)
        if not settlement:
            raise AccessError(self.env._('Esa valorización no es suya.'))
        return settlement

    @api.model
    def valuation(self, project_id, settlement_id):
        settlement = self._settlement(project_id, settlement_id)
        invoice = settlement.invoice_id
        detraction = detraction_pct = 0.0
        if invoice and 'l10n_pe_detraction_amount' in invoice._fields:
            detraction = invoice.l10n_pe_detraction_amount
            if 'l10n_pe_detraction_type_id' in invoice._fields:
                detraction_pct = invoice.l10n_pe_detraction_type_id.percentage or 0.0
        payment_labels = dict(invoice._fields['payment_state']._description_selection(
            self.env)) if invoice else {}
        reasons = dict(settlement.line_ids._fields['rework_reason']._description_selection(
            self.env)) if 'rework_reason' in settlement.line_ids._fields else {}
        lines = [{'name': line.purchase_line_id.name or line.activity_id.display_name,
                  'qty': line.qty_settle, 'uom': line.uom_id.name or '',
                  'amount': line.amount, 'rework': line.is_rework,
                  'rework_reason': reasons.get(line.rework_reason, '') if line.is_rework else '',
                  'paid_rework': getattr(line, 'rework_paid', False)}
                 for line in settlement.line_ids]
        deductions = [{'name': d.description or d.name, 'amount': -d.amount}
                      for d in settlement.deduction_ids] \
            if 'deduction_ids' in settlement._fields else []
        amount = lambda name: settlement[name] if name in settlement._fields else 0.0
        subtotal = amount('amount_subtotal') or sum(line['amount'] for line in lines)
        tax = amount('amount_tax')
        total = invoice.amount_total if invoice else amount('amount_total')
        guarantee = amount('amount_retention')
        advance = amount('amount_advance')
        # El neto ya descuenta la amortización del adelanto y el fondo; con
        # factura, también la detracción que va al Banco de la Nación.
        to_pay = amount('amount_to_pay') or (total - guarantee - advance)
        payments = []
        if invoice:
            for payment in invoice.sudo()._get_reconciled_payments():
                payments.append({'date': fields.Date.to_string(payment.date),
                                 'amount': payment.amount, 'name': payment.name})
        return {
            'id': settlement.id, 'name': settlement.display_name,
            'title': settlement.title if 'title' in settlement._fields else '',
            'period_start': fields.Date.to_string(settlement.period_start),
            'period_end': fields.Date.to_string(settlement.period_end),
            'lines': lines, 'deductions': deductions,
            'progress_total': amount('amount_direct') + amount('amount_additional')
            + amount('amount_adjustments') or sum(
                line['amount'] for line in lines if not line['rework'] or line['paid_rework']),
            'subtotal': subtotal, 'tax': tax,
            'tax_pct': round(100.0 * tax / subtotal) if subtotal else 0,
            'total': total, 'guarantee': guarantee,
            'guarantee_pct': round(100.0 * guarantee / total, 1) if total else 0,
            'advance': advance, 'detraction': detraction, 'detraction_pct': detraction_pct,
            'net': to_pay - detraction,
            'invoice': invoice.name or '',
            'payment_state': payment_labels.get(invoice.payment_state, '') if invoice else '',
            'payment_code': invoice.payment_state if invoice else '',
            'amount_paid': (invoice.amount_total - invoice.amount_residual) if invoice else 0.0,
            'payments': payments,
            'has_invoice_pdf': bool(invoice),
        }

    def valuation_pdf(self, project_id, settlement_id, document):
        """PDF del valorizado o de su factura, si son de la contrata."""
        settlement = self._settlement(project_id, settlement_id)
        if document == 'invoice':
            record, report = settlement.invoice_id, 'account.account_invoices'
            if not record:
                raise UserError(self.env._('La valorización aún no tiene factura.'))
        else:
            record = settlement
            report = 'al_construction_planner_subcontract.action_report_contract_valuation'
        # sudo: la contrata solo descarga su valorización o su factura
        # (comprobadas arriba).
        pdf, _type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report, record.ids)
        filename = '%s.pdf' % (record.name or record.display_name).replace('/', '-')
        return pdf, filename
