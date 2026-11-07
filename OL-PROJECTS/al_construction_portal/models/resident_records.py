# -*- coding: utf-8 -*-
"""Registros del residente en el portal de obra (paquete 6, entrega 2).

* CR-56: partes del día (los que envían capataces, contratas y oficina
  técnica, y quién no envió) y «Cerrar el día»: el parte diario de obra en PDF
  al contacto del cliente; los partes quedan «Revisado por el residente».
* CR-51: deductivo de contrata con foto (``construction.contract.deduction``
  en «Pendiente», como desde el escritorio).
* CR-52: solicitud de contrata o de cuadrilla adicional: una actividad en la
  tarea de la partida para el planificador de la obra, sin modelo nuevo. Su
  estado («Pedida», «Asignada», «Cancelada») se lee de la actividad y de la
  asignación de la partida.

El cambio pedido por el cliente (CR-53) está en el puente con Ventas,
``al_construction_portal_sale``: el cambio de obra vive en ese módulo."""
from datetime import datetime, time, timedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .daily_report import RESTRICTIONS
from .portal_service import _split_task, _task_labels

#: Tipo de solicitud del residente (CR-52).
REQUEST_KINDS = {'contract': 'contrata', 'crew': 'cuadrilla adicional'}


class ConstructionPortalService(models.AbstractModel):
    _inherit = 'construction.portal.service'

    # ------------------------------------------------------------------
    # Sincronización
    # ------------------------------------------------------------------
    @api.model
    def sync(self, project_id):
        data = super().sync(project_id)
        if 'resident' not in data:
            return data
        project, _members = self._project(project_id)
        today = fields.Date.context_today(self)
        resident = data['resident']
        resident['parts'] = self._resident_parts(project, today)
        resident['orders'] = self._resident_orders(project)
        resident['deduction_types'] = self._deduction_types()
        resident['crew_requests'] = self._resident_crew_requests(project)
        resident['features'] = self._resident_features()
        data['counters']['daily_to_review'] = len(
            [p for p in resident['parts']['reports'] if p['state'] == 'sent'])
        return data

    def _resident_features(self):
        """Lo que el residente puede registrar en esta base (los puentes
        instalados agregan lo suyo)."""
        return {'deduction': 'construction.contract.deduction' in self.env,
                'crew_request': True, 'change_order': False, 'expense': False}

    # ------------------------------------------------------------------
    # CR-56: partes del día y «Cerrar el día»
    # ------------------------------------------------------------------
    def _resident_parts(self, project, day):
        # sudo: los partes del día de la obra del residente.
        Report = self.env['construction.daily.report'].sudo()
        reports = Report.search([('project_id', '=', project.id), ('date', '=', day),
                                 ('kind', '=', 'member')], order='write_date')
        site = Report.search([('project_id', '=', project.id), ('date', '=', day),
                              ('kind', '=', 'site')], limit=1)
        # sudo: el personal del portal de la obra (quién debe enviar parte).
        members = self.env['construction.portal.member'].sudo().search([
            ('project_id', '=', project.id), ('active', '=', True),
            ('role', 'in', ('foreman', 'contractor', 'office'))])
        roles = dict(members._fields['role']._description_selection(self.env))
        senders = reports.user_id
        restrictions = dict(RESTRICTIONS)
        weather = dict(Report._fields['weather']._description_selection(self.env))
        rows = []
        for report in reports:
            member = members.filtered(lambda m: m.user_id == report.user_id)[:1]
            rows.append({
                'id': report.id, 'name': report.user_id.name,
                'role': roles.get(member.role, '') if member else '',
                'partner': member.partner_id.commercial_partner_id.name or '' if member else '',
                'sent_at': fields.Datetime.to_string(report.write_date),
                'state': report.state, 'staff_total': report.staff_total,
                'staff': [{'name': s.name, 'count': s.count} for s in report.staff_line_ids],
                'weather': weather.get(report.weather, ''),
                'restrictions': [restrictions[code] for code in restrictions
                                 if report['restriction_%s' % code]],
                'occurrences': report.occurrences or '',
                'photos': [{'id': a.id} for a in report.attachment_ids],
            })
        missing = [{'name': m.name, 'role': roles.get(m.role, ''),
                    'partner': m.partner_id.commercial_partner_id.name or ''}
                   for m in members if m.user_id not in senders]
        # Lo que el parte de obra trae del día (U10).
        progress = self.env['construction.task.progress'].sudo().search([
            ('project_id', '=', project.id), ('date', '=', day), ('state', '!=', 'rejected')])
        daily = self._daily_data(project, project._construction_site()
                                 if hasattr(project, '_construction_site') else False, day)
        return {
            'date': fields.Date.to_string(day), 'reports': rows, 'missing': missing,
            'site': {'id': site.id, 'state': site.state,
                     'comment': site.resident_comment or ''} if site else False,
            'own_today': daily['own_today'],
            'validated': len(progress.filtered(lambda p: p.state == 'validated')),
            'pending': len(progress.filtered(lambda p: p.state == 'draft')),
            'client_contact': project.construction_client_contact_id.display_name or '',
        }

    @api.model
    def close_day(self, values):
        """«Cerrar el día» (CR-56, U16): arma el parte diario de obra con los
        partes recibidos, lo envía en PDF al contacto del cliente de la obra
        (o lo deja en la obra si no tiene contacto) y marca los partes como
        revisados."""
        submission = self._submission('close_day', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, _members = self._resident_project(values.get('project_id'))
        company = project.company_id or self.env.company
        day = self._portal_date(values.get('date'), company,
                                company.construction_portal_progress_days)
        Report = self.env['construction.daily.report'].sudo()
        site = Report.search([('project_id', '=', project.id), ('date', '=', day),
                              ('kind', '=', 'site')], limit=1)
        if site.state == 'closed':
            raise UserError(self.env._('El día %s ya se cerró y se envió al cliente.', day))
        members = Report.search([('project_id', '=', project.id), ('date', '=', day),
                                 ('kind', '=', 'member'), ('state', 'in', ('sent', 'reviewed'))])
        seen = {int(i) for i in values.get('seen_report_ids') or []}
        if seen and not seen <= set(members.ids):
            raise UserError(self.env._(
                'Los partes del día cambiaron desde que los revisó: vuelva a revisarlos.'))
        staff = {}
        for line in members.staff_line_ids:
            key = (line.name, line.source)
            staff[key] = staff.get(key, 0) + line.count
        site_vals = {
            'project_id': project.id, 'date': day, 'kind': 'site', 'user_id': self.env.uid,
            'resident_comment': (values.get('comment') or '').strip() or False,
            'restriction_material': any(members.mapped('restriction_material')),
            'restriction_front': any(members.mapped('restriction_front')),
            'restriction_weather': any(members.mapped('restriction_weather')),
            'occurrences': '\n'.join('%s: %s' % (m.user_id.name, m.occurrences)
                                     for m in members if m.occurrences) or False,
            'staff_line_ids': [(5, 0, 0)] + [(0, 0, {'name': name, 'source': source,
                                                     'count': count})
                                             for (name, source), count in staff.items()],
        }
        # sudo: el parte de obra lo arma el residente de la obra.
        if site:
            site.write(site_vals)
        else:
            site = Report.create(site_vals)
        members.write({'site_report_id': site.id, 'state': 'reviewed'})
        pdf, _type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'al_construction_portal.action_report_site_day', site.ids)
        # El PDF se crea con el mensaje: un usuario de portal no puede
        # adjuntar a un mensaje archivos que no vengan del redactor.
        pdf_file = [(('Parte diario %s %s.pdf' % (project.display_name, day)).replace('/', '-'),
                     pdf)]
        contact = project.construction_client_contact_id
        author = self.env.user.partner_id
        if contact:
            site.message_post(
                body=self.env._('Parte diario de obra del %(day)s.%(comment)s',
                                day=day, comment=Markup('<br/>%s') % site.resident_comment
                                if site.resident_comment else ''),
                subject=self.env._('Parte diario de obra · %(project)s · %(day)s',
                                   project=project.display_name, day=day),
                author_id=author.id, partner_ids=contact.ids, attachments=pdf_file,
                message_type='comment', subtype_xmlid='mail.mt_comment')
        else:
            # Sin contacto del cliente, el PDF queda en la obra.
            project.sudo().message_post(
                body=self.env._('Parte diario de obra del %s (la obra no tiene contacto del '
                                'cliente: no se envió).', day),
                author_id=author.id, attachments=pdf_file)
        site.write({'state': 'closed', 'closed_by_id': self.env.uid,
                    'closed_at': fields.Datetime.now(), 'sent_to_id': contact.id})
        self._portal_register('close_day', values['uuid'], site)
        return {'status': 'done', 'ids': str(site.id), 'name': site.name,
                'sent_to': contact.display_name or '', 'reviewed': len(members)}

    # ------------------------------------------------------------------
    # CR-51: deductivo de contrata con foto
    # ------------------------------------------------------------------
    def _resident_orders(self, project):
        """Órdenes de contrata de la obra con sus partidas (para el
        deductivo)."""
        if 'construction.contract.deduction' not in self.env:
            return []
        # sudo: las órdenes de contrata de la obra del residente.
        orders = self.env['purchase.order'].sudo().search([
            ('construction_project_id', '=', project.id),
            ('construction_is_service_order', '=', True), ('state', 'in', ('purchase', 'done'))],
            order='partner_id, id')
        result = []
        for order in orders:
            lines = []
            for line in order.order_line.filtered(lambda l: not l.display_type):
                task = line.construction_task_id if 'construction_task_id' in line._fields \
                    else self.env['project.task']
                code, name = _split_task(task) if task else ('', line.name or '')
                lines.append({'id': line.id, 'task_id': task.id, 'task_code': code,
                              'task_name': name, 'uom': line.product_uom_id.name or '',
                              'price_unit': line.price_unit})
            result.append({'id': order.id, 'name': order.name,
                           'partner': order.partner_id.commercial_partner_id.name,
                           'lines': lines})
        return result

    def _deduction_types(self):
        if 'construction.contract.deduction.type' not in self.env:
            return []
        types = self.env['construction.contract.deduction.type'].sudo().search([])
        return [[t.id, t.name] for t in types]

    @api.model
    def deduction(self, values):
        """Deductivo de una contrata con foto (CR-51): queda «Pendiente» y
        entra en la siguiente valorización como el del escritorio."""
        submission = self._submission('deduction', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, _members = self._resident_project(values.get('project_id'))
        if 'construction.contract.deduction' not in self.env:
            raise UserError(self.env._('Los deductivos piden el módulo de contratas.'))
        orders = {row['id']: row for row in self._resident_orders(project)}
        order_id = int(values.get('purchase_order_id') or 0)
        if order_id not in orders:
            raise AccessError(self.env._('Esa orden no es de una contrata de su obra.'))
        order = self.env['purchase.order'].sudo().browse(order_id)
        line = next((l for l in orders[order_id]['lines']
                     if l['id'] == int(values.get('order_line_id') or 0)), None)
        type_id = int(values.get('type_id') or 0)
        if type_id not in {t[0] for t in self._deduction_types()}:
            raise UserError(self.env._('Elija el motivo del deductivo.'))
        description = (values.get('description') or '').strip()
        if not description:
            raise UserError(self.env._('Describa el deductivo.'))
        qty = float(values.get('qty') or 0.0)
        if qty and line:
            # Por cantidad: al precio de la partida en la orden.
            amount = order.currency_id.round(qty * line['price_unit'])
            description = '%s (%s %s × %s)' % (description, qty, line['uom'],
                                               line['price_unit'])
        else:
            amount = float(values.get('amount') or 0.0)
        if amount <= 0:
            raise UserError(self.env._('Indique el monto o la cantidad del deductivo.'))
        attachments = self._photos(values.get('photos'), 'construction.contract.deduction',
                                   required=True)
        # sudo: el deductivo lo registra el residente sobre una orden de su
        # obra (comprobada arriba); queda «Pendiente» como desde el escritorio.
        deduction = self.env['construction.contract.deduction'].sudo().create({
            'purchase_order_id': order.id, 'type_id': type_id, 'description': description,
            'amount': amount, 'task_id': line['task_id'] if line and line['task_id'] else False,
            'date': self._portal_date(values.get('date'), project.company_id or self.env.company),
            'attachment_ids': [(6, 0, attachments.ids)],
        })
        deduction.message_post(body=self.env._('Registrado por el residente desde el portal.'),
                               author_id=self.env.user.partner_id.id)
        self._portal_register('deduction', values['uuid'], deduction)
        return {'status': 'done', 'ids': str(deduction.id), 'name': deduction.name}

    # ------------------------------------------------------------------
    # CR-52: solicitudes de contrata y de cuadrilla adicional
    # ------------------------------------------------------------------
    def _planner_user(self, project):
        """Quien recibe las solicitudes: el jefe (planificador) de la obra."""
        return project.user_id

    @api.model
    def crew_request(self, values):
        """Solicitud de contrata o de cuadrilla adicional (CR-52): una
        actividad en cada partida pedida, asignada al planificador de la obra,
        con los datos en el resumen y en la nota. La asignación sigue en el
        escritorio."""
        submission = self._submission('crew_request', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._resident_project(values.get('project_id'))
        kind = values.get('kind')
        if kind not in REQUEST_KINDS:
            raise UserError(self.env._('Elija si pide contrata o cuadrilla.'))
        lines = self._lines(project, members)
        task_ids = {int(i) for i in values.get('task_ids') or []}
        tasks = lines.task_id.filtered(lambda t: t.id in task_ids)
        if not tasks:
            raise UserError(self.env._('Elija las partidas.'))
        need = fields.Date.to_date(values.get('date_needed')) if values.get('date_needed') \
            else False
        if not need:
            raise UserError(self.env._('Indique la fecha en que se necesita.'))
        planner = self._planner_user(project)
        if not planner:
            raise UserError(self.env._('La obra %s no tiene jefe (planificador) que reciba la '
                                       'solicitud.', project.display_name))
        if kind == 'crew':
            people = [(row.get('role') or '-', int(row.get('count') or 0))
                      for row in values.get('people') or [] if int(row.get('count') or 0) > 0]
            if not people:
                raise UserError(self.env._('Indique cuántas personas y de qué rol.'))
            detail = ', '.join('%s %s' % (count, role) for role, count in people)
        else:
            detail = (values.get('scope') or '').strip()
            if not detail:
                raise UserError(self.env._('Indique el metrado que hará la contrata.'))
        comment = (values.get('comment') or '').strip()
        summary = self.env._('Pide %(kind)s para el %(day)s: %(detail)s',
                             kind=REQUEST_KINDS[kind], day=need, detail=detail)[:250]
        note = Markup('<p>%s</p><p>%s</p><p>%s</p>') % (
            self.env._('Solicitud del residente %s desde el portal de obra.', self.env.user.name),
            self.env._('Partidas: %s', ', '.join(tasks.mapped('display_name'))),
            comment or '')
        activities = self.env['mail.activity']
        for task in tasks:
            # sudo: la actividad la deja el residente en la partida de su obra
            # para el planificador (la asignación sigue en el escritorio).
            activities |= task.sudo().activity_schedule(
                'mail.mail_activity_data_todo', date_deadline=need, summary=summary,
                note=note, user_id=planner.id)
        self.env['construction.portal.submission'].sudo().create({
            'uuid': values['uuid'], 'user_id': self.env.uid, 'kind': 'crew_request',
            'res_model': 'project.task', 'res_ids': ','.join(str(i) for i in tasks.ids),
            'state': 'done', 'message': '%s|%s|%s|%s' % (
                kind, fields.Date.to_string(need), detail,
                ','.join(str(a.id) for a in activities))})
        return {'status': 'done', 'ids': ','.join(str(i) for i in tasks.ids), 'name': summary}

    def _request_assigned(self, kind, tasks, need):
        """La partida ya tiene contrata o cuadrilla para esa fecha."""
        if kind == 'contract':
            plan = tasks.project_id[:1]._construction_current_plan()
            if not plan:
                return False
            return bool(self.env['construction.resource.plan.line'].sudo().search_count([
                ('plan_id', '=', plan.id), ('task_id', 'in', tasks.ids),
                ('resource_type', '=', 'contract'), ('partner_id', '!=', False)]))
        if 'planning.slot' not in self.env \
                or 'construction_task_id' not in self.env['planning.slot']._fields:
            return False
        start = datetime.combine(need, time.min)
        return bool(self.env['planning.slot'].sudo().search_count([
            ('construction_task_id', 'in', tasks.ids),
            ('start_datetime', '<', start + timedelta(days=1)),
            ('end_datetime', '>', start)]))

    def _resident_crew_requests(self, project):
        """Las solicitudes del residente con su estado (CR-52, punto 4)."""
        submissions = self.env['construction.portal.submission'].sudo().search([
            ('user_id', '=', self.env.uid), ('kind', '=', 'crew_request'),
            ('state', '=', 'done')], order='create_date desc, id desc', limit=30)
        Task = self.env['project.task'].sudo()
        result = []
        for submission in submissions:
            tasks = Task.browse([int(i) for i in (submission.res_ids or '').split(',') if i]
                                ).exists().filtered(lambda t: t.project_id == project)
            if not tasks:
                continue
            kind, need, detail, activity_ids = ((submission.message or '').split('|') + [''] * 4)[:4]
            need = fields.Date.to_date(need) if need else False
            activities = self.env['mail.activity'].sudo().browse(
                [int(i) for i in activity_ids.split(',') if i]).exists()
            if need and self._request_assigned(kind, tasks, need):
                state = 'assigned'
            elif activities:
                state = 'requested'
            else:
                state = 'cancelled'
            labels = [_task_labels(task) for task in tasks]
            result.append({
                'id': submission.id, 'kind': kind, 'kind_label': REQUEST_KINDS.get(kind, ''),
                'date_needed': fields.Date.to_string(need) if need else '', 'detail': detail,
                'tasks': [' · '.join(filter(None, [l['task_name'], l['task_code']]))
                          for l in labels],
                'state': state, 'state_label': {
                    'assigned': self.env._('Asignada'), 'requested': self.env._('Pedida'),
                    'cancelled': self.env._('Cancelada')}[state],
                'created': fields.Datetime.to_string(submission.create_date),
            })
        return result
