# -*- coding: utf-8 -*-
"""Servicios del residente en el portal de obra (paquete 6).

* CR-48: «Mi día» (contadores y agenda de hoy ordenada por urgencia).
* CR-49: bandeja «Por validar»: avances reportados de la obra con sus avisos
  y su evidencia; validar (con corrección a la baja), rechazar y re-trabajo.
* CR-50: bandeja «Por aprobar»: requerimientos de la obra donde el residente
  es revisor del nivel actual; aprobar (con la cantidad por línea) o rechazar.

El portal no tiene lógica de negocio propia: llama a los mismos métodos del
escritorio (``action_validate``, ``_action_reject``, ``_validate_tier``,
``_rejected_tier`` o la solicitud de Aprobaciones). Validar y aprobar entran a
la cola sin señal: cada decisión lleva lo que vio el residente y Odoo la
vuelve a comprobar al recibirla; si el registro cambió, la rechaza con el
motivo y no la aplica."""
import base64
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext
from odoo.tools.image import image_process

from .portal_service import _split_task, _task_labels

#: Tolerancia al comparar la cantidad que vio el residente.
QTY_EPSILON = 1e-6


class ConstructionPortalService(models.AbstractModel):
    _inherit = 'construction.portal.service'

    # ------------------------------------------------------------------
    # Alcance
    # ------------------------------------------------------------------
    def _resident_project(self, project_id):
        """La obra si la persona es su residente en esta sesión (con usuario
        y clave). El servicio lo comprueba en cada llamada (CR-48)."""
        project, members = self._project(project_id)
        if 'resident' not in self._roles(members):
            raise AccessError(self.env._(
                'Esto lo hace el residente de la obra, con su usuario y clave.'))
        return project, members

    # ------------------------------------------------------------------
    # Sincronización
    # ------------------------------------------------------------------
    @api.model
    def sync(self, project_id):
        data = super().sync(project_id)
        project, members = self._project(project_id)
        if 'resident' not in self._roles(members):
            return data
        company = project.company_id or self.env.company
        today = fields.Date.context_today(self)
        progress = self._resident_progress_rows(project)
        requests = self._resident_request_rows(project)
        daily = self._resident_daily_count(project, today)
        data['resident'] = {
            'progress': progress,
            'requests': requests,
            'reasons': self.env['construction.portal.reason']._portal_list(company),
            'agenda': self._resident_agenda(project, data, progress, requests, today),
        }
        data['counters'].update({
            'inbox_progress': len(progress),
            'inbox_requests': len(requests),
            'daily_to_review': daily,
        })
        return data

    def _resident_daily_count(self, project, today):
        """Partes del día enviados al residente (CR-56 los revisa)."""
        # sudo: los partes diarios de la obra del residente.
        return self.env['construction.daily.report'].sudo().search_count([
            ('project_id', '=', project.id), ('date', '=', today), ('state', '=', 'sent')])

    # ------------------------------------------------------------------
    # Bandeja «Por validar» (CR-49)
    # ------------------------------------------------------------------
    def _resident_progress_records(self, project):
        # sudo: los avances reportados de la obra del residente.
        return self.env['construction.task.progress'].sudo().search([
            ('project_id', '=', project.id), ('state', '=', 'draft')],
            order='date, id')

    def _closed_weeks(self, project, progresses):
        """(contrata, fecha) de los avances cuya semana ya tiene una
        valorización presentada o más adelante: la semana está cerrada."""
        if 'construction.contract.settlement' not in self.env:
            return set()
        partners = progresses.partner_id.commercial_partner_id
        if not partners:
            return set()
        # sudo: las valorizaciones de las contratas de la obra.
        settlements = self.env['construction.contract.settlement'].sudo().search([
            ('project_id', '=', project.id), ('partner_id', 'in', partners.ids),
            ('state', 'not in', ('draft', 'cancel'))])
        closed = set()
        for progress in progresses.filtered('partner_id'):
            partner = progress.partner_id.commercial_partner_id
            if any(s.partner_id.commercial_partner_id == partner
                   and s.period_start <= progress.date <= (s.period_end or s.period_start)
                   for s in settlements):
                closed.add(progress.id)
        return closed

    def _last_validated_photos(self, lines):
        """Última foto validada de cada partida (U7)."""
        if not lines:
            return {}
        # sudo: los avances validados de las partidas de la obra.
        validated = self.env['construction.task.progress'].sudo().search([
            ('plan_line_id', 'in', lines.ids), ('state', '=', 'validated'),
            ('attachment_ids', '!=', False)], order='validation_date desc, id desc')
        result = {}
        for progress in validated:
            if progress.plan_line_id.id not in result:
                attachment = progress.attachment_ids.sorted('id')[-1:]
                result[progress.plan_line_id.id] = {
                    'id': attachment.id, 'date': fields.Date.to_string(progress.date),
                    'progress': progress.name}
        return result

    def _progress_warnings(self, progress, line, site, closed):
        """Avisos de la tarjeta (CR-49, punto 5). Con aviso no se valida en
        lote (U9)."""
        warnings = []
        uom = progress.uom_id.name or ''
        if not progress.is_rework:
            pending_others = line._get_reported_qty() - progress.qty
            balance = line.qty_planned - line.qty_executed - pending_others
            if progress.qty > balance + QTY_EPSILON:
                warnings.append({'code': 'over', 'text': self.env._(
                    'Supera el saldo del plan en %(qty)s %(uom)s.',
                    qty=round(progress.qty - max(balance, 0.0), 2), uom=uom)})
        if progress.exceed_state == 'exceeded' \
                and progress._construction_exceed_policy() == 'approval':
            warnings.append({'code': 'exceed', 'blocking': True, 'text': self.env._(
                'Excede el plan: espera la aprobación de la jefatura antes de validarse.')})
        if not (progress.latitude or progress.longitude):
            warnings.append({'code': 'gps', 'text': self.env._('Foto sin ubicación GPS.')})
        elif site and site.radius_m and progress.distance_m > site.radius_m:
            warnings.append({'code': 'gps', 'text': self.env._(
                'Reportado a %(m)s m de la obra (radio %(r)s m).',
                m=round(progress.distance_m), r=site.radius_m)})
        if progress.id in closed:
            warnings.append({'code': 'closed', 'text': self.env._(
                'La fecha cae en una semana con la valorización ya presentada.')})
        return warnings

    def _resident_progress_rows(self, project):
        progresses = self._resident_progress_records(project)
        site = project._construction_site() if hasattr(project, '_construction_site') else False
        closed = self._closed_weeks(project, progresses)
        last_photos = self._last_validated_photos(progresses.plan_line_id)
        reasons = dict(progresses._fields['rework_reason']._description_selection(self.env))
        periods = {}
        rows = []
        for progress in progresses:
            line = progress.plan_line_id
            if progress.date not in periods:
                periods[progress.date] = project._construction_period(progress.date)[1]
            labels = _task_labels(progress.task_id, progress.activity_id, line.resource_type)
            pending_others = line._get_reported_qty() - progress.qty
            rows.append(dict(labels, **{
                'id': progress.id, 'name': progress.name,
                'plan_line_id': line.id, 'kind': line.resource_type,
                'date': fields.Date.to_string(progress.date),
                'reported_at': fields.Datetime.to_string(progress.create_date),
                'reported_by': progress.reported_by_id.name or '',
                'reported_by_id': progress.reported_by_id.id,
                'partner': progress.partner_id.commercial_partner_id.name or '',
                'qty': progress.qty, 'uom': progress.uom_id.name or '',
                'planned': line.qty_planned, 'validated': line.qty_executed,
                'balance': line.qty_planned - line.qty_executed - pending_others,
                # Corte de valorización de la semana del avance (U5).
                'cutoff': fields.Date.to_string(periods[progress.date])
                if progress.partner_id else '',
                'is_rework': progress.is_rework,
                'rework_reason': reasons.get(progress.rework_reason, '')
                if progress.is_rework else '',
                'distance_m': round(progress.distance_m or 0.0),
                'has_gps': bool(progress.latitude or progress.longitude),
                'photos': [{'id': a.id, 'taken': fields.Datetime.to_string(a.create_date)}
                           for a in progress.attachment_ids.sorted('id')],
                'last_photo': last_photos.get(line.id) or False,
                'warnings': self._progress_warnings(progress, line, site, closed),
            }))
        # «Por corte» (U5): primero los de contrata con el corte más cercano.
        rows.sort(key=lambda r: (not r['cutoff'], r['cutoff'] or '', r['date'], r['id']))
        return rows

    def _check_seen_progress(self, progress, seen_qty):
        """Lo que vio el residente sigue igual: reportado y con la misma
        cantidad. Si no, la decisión no se aplica (regla «Sin señal»)."""
        if not progress:
            raise UserError(self.env._('El avance ya no existe.'))
        if progress.state != 'draft':
            label = dict(progress._fields['state']._description_selection(self.env)).get(
                progress.state, progress.state).lower()
            raise UserError(self.env._('El avance %(name)s ya fue %(state)s.',
                                       name=progress.name, state=label))
        if seen_qty is not None and abs(progress.qty - float(seen_qty)) > QTY_EPSILON:
            raise UserError(self.env._(
                'El avance %(name)s cambió de cantidad (%(old)s → %(new)s): revíselo de nuevo.',
                name=progress.name, old=seen_qty, new=progress.qty))

    def _reason(self, reason_id, kind, required=True):
        reason = self.env['construction.portal.reason'].sudo().search([
            ('id', '=', int(reason_id or 0)), ('kind', '=', kind)], limit=1)
        if required and not reason:
            raise UserError(self.env._('Elija el motivo.'))
        return reason

    @api.model
    def resident_progress(self, values):
        """Validar, rechazar o marcar re-trabajo de avances reportados. La
        cola manda ``items``: [{id, seen_qty}] (validar en lote: varios)."""
        submission = self._submission('resident_progress', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, _members = self._resident_project(values.get('project_id'))
        action = values.get('action')
        if action not in ('validate', 'reject', 'rework'):
            raise UserError(self.env._('Acción desconocida.'))
        items = values.get('items') or []
        if not items:
            raise UserError(self.env._('Elija los avances.'))
        if len(items) > 1 and action != 'validate':
            raise UserError(self.env._('El rechazo y el re-trabajo van de uno en uno.'))
        Progress = self.env['construction.task.progress'].sudo().with_context(
            construction_portal_resident_projects=[project.id])
        progresses = Progress
        for item in items:
            progress = Progress.search([('id', '=', int(item.get('id') or 0)),
                                        ('project_id', '=', project.id)], limit=1)
            if not progress and Progress.browse(int(item.get('id') or 0)).exists():
                raise AccessError(self.env._('Ese avance no es de su obra.'))
            self._check_seen_progress(progress, item.get('seen_qty'))
            progresses |= progress
        comment = (values.get('comment') or '').strip()
        partner = self.env.user.partner_id
        if action == 'validate' and len(progresses) > 1:
            # En lote solo lo que no tiene aviso (U9).
            site = project._construction_site() if hasattr(project, '_construction_site') \
                else False
            closed = self._closed_weeks(project, progresses)
            flagged = progresses.filtered(lambda p: self._progress_warnings(
                p, p.plan_line_id, site, closed))
            if flagged:
                raise UserError(self.env._(
                    'Estos avances tienen aviso y se validan de uno en uno: %s.',
                    ', '.join(flagged.mapped('name'))))
        if action == 'validate':
            if len(progresses) == 1 and values.get('qty') not in (None, ''):
                self._correct_qty(progresses, float(values['qty']), values, comment)
            progresses.action_validate()
            text = self.env._('Validado por el residente desde el portal.')
        elif action == 'reject':
            reason = self._reason(values.get('reason_id'), 'progress_reject')
            progresses._action_reject(
                '%s%s' % (reason.name, (' — %s' % comment) if comment else ''))
            text = self.env._('Rechazado por el residente desde el portal: %s', reason.name)
        else:
            code = values.get('rework_reason')
            codes = dict(progresses._fields['rework_reason']._description_selection(self.env))
            if code not in codes:
                raise UserError(self.env._('Elija el motivo del re-trabajo.'))
            # La regla de re-trabajo vigente: entra con 0 a liquidar salvo que
            # se marque pagado en la valorización.
            progresses.write({'is_rework': True, 'rework_reason': code})
            progresses.action_validate()
            text = self.env._('Validado como re-trabajo (%s) por el residente desde el portal.',
                              codes[code])
        for progress in progresses:
            # Quien reportó recibe el aviso (CR-49, punto 8), en el celular si
            # su papel lo recibe (CR-57); si no, queda en el historial.
            reporter = self._notice_users(project, 'progress_decision',
                                          progress.reported_by_id).partner_id
            progress.message_post(
                body='%s%s' % (text, (' %s' % comment) if comment and action != 'reject' else ''),
                author_id=partner.id, message_type='comment',
                subtype_xmlid='mail.mt_comment',
                partner_ids=(reporter - partner).ids)
        self._portal_register('resident_progress', values['uuid'], progresses)
        return {'status': 'done', 'ids': ','.join(str(i) for i in progresses.ids),
                'name': ', '.join(progresses.mapped('name')),
                'states': progresses.mapped('state')}

    def _correct_qty(self, progress, qty, values, comment):
        """Validar con la cantidad corregida a la baja (CR-49, punto 3)."""
        if qty <= 0:
            raise UserError(self.env._('La cantidad validada debe ser mayor que cero.'))
        if qty > progress.qty + QTY_EPSILON:
            raise UserError(self.env._(
                'Solo se corrige a la baja: para más, quien reporta registra otro avance.'))
        if abs(qty - progress.qty) <= QTY_EPSILON:
            return
        reason = self._reason(values.get('reason_id'), 'progress_correct')
        old = progress.qty
        progress.write({'qty': qty})
        progress.message_post(body=self.env._(
            'Cantidad corregida por el residente: %(old)s → %(new)s %(uom)s. Motivo: '
            '%(reason)s%(comment)s',
            old=round(old, 4), new=round(qty, 4), uom=progress.uom_id.name or '',
            reason=reason.name, comment=('. %s' % comment) if comment else ''),
            author_id=self.env.user.partner_id.id)

    @api.model
    def progress_photo(self, project_id, attachment_id, size=None):
        """Foto de un avance de la obra, para la evidencia (U7)."""
        project, members = self._project(project_id)
        if not self._roles(members) & {'resident', 'office'}:
            raise AccessError(self.env._('Las fotos de los avances las revisa el residente.'))
        # sudo: solo un adjunto de un avance de esta obra.
        attachment = self.env['ir.attachment'].sudo().browse(int(attachment_id or 0)).exists()
        progress = self.env['construction.task.progress'].sudo().search([
            ('project_id', '=', project.id), ('attachment_ids', 'in', attachment.ids)], limit=1) \
            if attachment else False
        # También las fotos de los partes del día de la obra (CR-56).
        report = self.env['construction.daily.report'].sudo().search([
            ('project_id', '=', project.id), ('attachment_ids', 'in', attachment.ids)], limit=1) \
            if attachment and not progress else False
        if not progress and not report:
            raise AccessError(self.env._('Esa foto no es de un avance ni de un parte de su obra.'))
        data = attachment.raw or b''
        mimetype = attachment.mimetype or 'image/jpeg'
        if size == 'thumb' and data and mimetype.startswith('image/'):
            data = image_process(data, size=(360, 360), output_format='JPEG')
            mimetype = 'image/jpeg'
        return data, mimetype

    # ------------------------------------------------------------------
    # Bandeja «Por aprobar» (CR-50)
    # ------------------------------------------------------------------
    def _resident_review_state(self, request):
        """(revisa, marca) del requerimiento para el usuario: si le toca
        revisarlo ahora y qué nivel vio (para la nueva comprobación)."""
        if request.state != 'to_approve':
            return False, ''
        if 'construction_approval_engine' in request._fields \
                and request.construction_approval_engine == 'approvals':
            approval = request.construction_approval_id
            can = bool(approval) and request.construction_approval_can_review
            return can, 'approval:%s' % approval.id if can else ''
        sequences = request._get_sequences_to_approve(self.env.user)
        reviews = request.review_ids.filtered(
            lambda r: r.sequence in sequences and r.status in ('waiting', 'pending'))
        if not reviews:
            return False, ''
        return True, 'tier:%s' % ','.join(str(i) for i in sorted(reviews.ids))

    def _resident_request_records(self, project):
        # sudo: los requerimientos de la obra en aprobación; luego se filtran
        # los que le toca revisar al residente.
        requests = self.env['construction.material.request'].sudo().search([
            ('project_id', '=', project.id), ('state', '=', 'to_approve')],
            order='priority desc, date_required, id')
        return requests.filtered(lambda r: self._resident_review_state(r)[0])

    def _resident_request_rows(self, project):
        requests = self._resident_request_records(project)
        types = dict(requests._fields['request_type']._description_selection(self.env))
        rows = []
        for request in requests:
            lines = []
            for line in request.line_ids.filtered(lambda l: not l.cancelled):
                task = line.task_id or request.task_id
                code, name = _split_task(task) if task else ('', '')
                remaining = line.construction_plan_remaining \
                    if 'construction_plan_remaining' in line._fields else None
                exceeded = line.construction_plan_exceeded \
                    if 'construction_plan_exceeded' in line._fields else False
                out_of_plan = line.construction_out_of_plan \
                    if 'construction_out_of_plan' in line._fields else False
                lines.append({
                    'id': line.id, 'name': line.product_id.display_name or '',
                    'qty': line.product_qty, 'uom': line.product_uom_id.name or '',
                    'task_code': code, 'task_name': name,
                    # Saldo del plan y exceso por línea (U14).
                    'plan_remaining': remaining,
                    'excess': max((line.product_qty - remaining), 0.0)
                    if remaining is not None and exceeded else 0.0,
                    'out_of_plan': out_of_plan,
                })
            rows.append({
                'id': request.id, 'name': request.name,
                'type': request.request_type, 'type_label': types.get(request.request_type, ''),
                'kind': self._request_kind(request),
                'requested_by': request.requested_by.name or '',
                'urgent': request.priority == '1',
                'date_request': fields.Date.to_string(request.date_request),
                'date_required': fields.Date.to_string(request.date_required)
                if request.date_required else '',
                'note': html2plaintext(request.note or '').strip(),
                'seen': self._resident_review_state(request)[1],
                'lines': lines,
            })
        return rows

    def _request_kind(self, request):
        """De partida, EPP, útiles y aseo o fuera de catálogo (CR-50, punto 2)."""
        if request.request_type == 'site':
            note = request.note and str(request.note) or ''
            return 'text' if not request.line_ids and note else 'partida'
        categories = set(request.line_ids.product_id.categ_id.mapped(
            'construction_portal_catalog')) - {False}
        if categories == {'epp'}:
            return 'epp'
        if categories == {'office'}:
            return 'office'
        return 'internal'

    @api.model
    def resident_request(self, values):
        """Aprobar (con la cantidad de cada línea) o rechazar un
        requerimiento de la obra. ``seen`` es el nivel que vio el residente."""
        submission = self._submission('resident_request', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, _members = self._resident_project(values.get('project_id'))
        action = values.get('action')
        if action not in ('approve', 'reject'):
            raise UserError(self.env._('Acción desconocida.'))
        Request = self.env['construction.material.request'].sudo()
        request = Request.search([('id', '=', int(values.get('request_id') or 0)),
                                  ('project_id', '=', project.id)], limit=1)
        if not request:
            if Request.browse(int(values.get('request_id') or 0)).exists():
                raise AccessError(self.env._('Ese requerimiento no es de su obra.'))
            raise UserError(self.env._('El requerimiento ya no existe.'))
        can, seen = self._resident_review_state(request)
        if not can:
            label = dict(request._fields['state']._description_selection(self.env)).get(
                request.state, request.state)
            raise UserError(self.env._(
                'El requerimiento %(name)s ya no espera su aprobación (está «%(state)s»).',
                name=request.name, state=label))
        if values.get('seen') and values['seen'] != seen:
            raise UserError(self.env._(
                'El requerimiento %s cambió de nivel de aprobación: revíselo de nuevo.',
                request.name))
        comment = (values.get('comment') or '').strip()
        author = self.env.user.partner_id
        if action == 'approve':
            self._apply_request_quantities(request, values.get('lines') or [], comment)
            if seen.startswith('approval:'):
                request.action_construction_approve()
            else:
                reviews = request.review_ids.filtered(
                    lambda r: str(r.id) in seen.split(':', 1)[1].split(','))
                if comment:
                    reviews.write({'comment': comment})
                request._validate_tier(reviews)
                request._update_counter({'review_deleted': True})
            text = self.env._('Aprobado por el residente desde el portal.')
        else:
            reason = self._reason(values.get('reason_id'), 'request_reject')
            full = '%s%s' % (reason.name, (' — %s' % comment) if comment else '')
            if seen.startswith('approval:'):
                wizard = self.env['construction.approval.refuse.wizard'].sudo().create({
                    'approval_ids': [fields.Command.set(request.construction_approval_id.ids)],
                    'reason': full})
                wizard.action_refuse()
            else:
                reviews = request.review_ids.filtered(
                    lambda r: str(r.id) in seen.split(':', 1)[1].split(','))
                reviews.write({'comment': full})
                request._rejected_tier(reviews)
                request._update_counter({'review_deleted': True})
            text = self.env._('Rechazado por el residente desde el portal: %s', full)
        request.message_post(body=text, author_id=author.id, message_type='comment',
                             subtype_xmlid='mail.mt_comment',
                             partner_ids=(request.requested_by.partner_id - author).ids)
        self._portal_register('resident_request', values['uuid'], request)
        return {'status': 'done', 'ids': str(request.id), 'name': request.name,
                'state': request.state}

    def _apply_request_quantities(self, request, rows, comment):
        """La cantidad que aprueba el residente en cada línea (U14): lo pedido,
        el saldo del plan u otra menor."""
        changes = []
        lines = request.line_ids.filtered(lambda l: not l.cancelled)
        for row in rows:
            line = lines.filtered(lambda l: l.id == int(row.get('id') or 0))
            if not line or row.get('qty') in (None, ''):
                continue
            qty = float(row['qty'])
            if qty <= 0:
                raise UserError(self.env._(
                    'La cantidad aprobada de %s debe ser mayor que cero: si no va, rechace el '
                    'requerimiento.', line.product_id.display_name))
            if qty > line.product_qty + QTY_EPSILON:
                raise UserError(self.env._(
                    'Solo se aprueba hasta lo pedido de %s.', line.product_id.display_name))
            if abs(qty - line.product_qty) > QTY_EPSILON:
                changes.append((line, line.product_qty, qty))
        for line, old, qty in changes:
            # El revisor ajusta la cantidad del documento en revisión: se omite
            # ese control de OCA solo para esta escritura.
            line.with_context(skip_validation_check=True).write({'product_qty': qty})
        if changes:
            request.message_post(body=self.env._(
                'El residente aprobó otra cantidad: %s', '; '.join(
                    '%s %s → %s %s' % (line.product_id.display_name, round(old, 4),
                                       round(qty, 4), line.product_uom_id.name or '')
                    for line, old, qty in changes)), author_id=self.env.user.partner_id.id)

    # ------------------------------------------------------------------
    # «Mi día» (CR-48, punto 3; U1)
    # ------------------------------------------------------------------
    def _resident_agenda(self, project, data, progress_rows, request_rows, today):
        """Agenda de hoy ordenada por urgencia: pedidos urgentes, cortes de
        valorización de la semana con avances por validar, entregas del día y
        partidas que empiezan hoy."""
        items = []
        for row in request_rows:
            if row['urgent']:
                items.append({'rank': 0, 'kind': 'urgent', 'id': row['id'],
                              'title': self.env._('Pedido urgente %s', row['name']),
                              'sub': row['requested_by']})
        week_end = today + timedelta(days=6)
        cutoffs = defaultdict(int)
        for row in progress_rows:
            if row['cutoff'] and row['cutoff'] <= fields.Date.to_string(week_end):
                cutoffs[(row['cutoff'], row['partner'])] += 1
        for (cutoff, partner), count in sorted(cutoffs.items()):
            items.append({'rank': 1, 'kind': 'cutoff', 'date': cutoff, 'partner': partner,
                          'title': self.env._('Corte de %s', partner),
                          'sub': self.env._('%(n)s por validar · corte el %(d)s', n=count,
                                            d=cutoff)})
        today_str = fields.Date.to_string(today)
        for delivery in data.get('deliveries') or []:
            if (delivery.get('date_local') or '')[:10] <= today_str:
                items.append({'rank': 2, 'kind': 'delivery', 'id': delivery['id'],
                              'title': self.env._('Entrega %s', delivery['name']),
                              'sub': delivery.get('partner') or delivery.get('origin') or ''})
        for task in self._tasks_starting(project, today):
            code, name = _split_task(task)
            items.append({'rank': 3, 'kind': 'start', 'id': task.id,
                          'title': self.env._('Empieza %s', name),
                          'sub': code})
        items.sort(key=lambda item: (item['rank'], item.get('date') or ''))
        return items

    def _tasks_starting(self, project, today):
        """Partidas de la obra que empiezan hoy según el cronograma."""
        Task = self.env['project.task'].sudo()
        if 'planned_date_begin' not in Task._fields:
            return Task
        tz_start = fields.Datetime.to_datetime(today)
        # sudo: las partidas de la obra del residente.
        return Task.search([
            ('project_id', '=', project.id), ('planned_date_begin', '>=', tz_start),
            ('planned_date_begin', '<', tz_start + timedelta(days=1)),
            ('child_ids', '=', False)], limit=20)
