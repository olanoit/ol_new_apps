# -*- coding: utf-8 -*-
"""Etapa del ambiente (P-15): las barras del cronograma con recursos.

Una por ambiente y etapa (Producción → Armado → Instalación → Acabado y
entrega), con sus fechas. No pertenece a una versión del plan sino al
ambiente: sobrevive a las versiones nuevas. Mover sus fechas desplaza la
fecha de necesidad de las líneas de esa etapa en el ambiente y sus módulos
(en el plan vigente) y avisa a Logística como «Cambiar fechas» (W-08).
Contrata, cuadrilla, monto y avance salen de esas líneas."""
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date

from .common import DRIVER_TYPES, STAGES

STAGE_ORDER = [stage for stage, _label in STAGES]
#: Días hábiles de una etapa por defecto (lunes a viernes de su semana).
DEFAULT_STAGE_DAYS = 5


class ConstructionSpaceStage(models.Model):
    _name = 'construction.space.stage'
    _description = 'Etapa del ambiente'
    _order = 'project_id, space_task_id, sequence, id'
    _check_company_auto = True

    space_task_id = fields.Many2one(
        'project.task', string='Ambiente', required=True, index=True, ondelete='cascade',
        check_company=True, domain="[('construction_level', '=', 'space')]")
    project_id = fields.Many2one(
        related='space_task_id.project_id', string='Obra', store=True, index=True)
    company_id = fields.Many2one(
        related='space_task_id.company_id', string='Compañía', store=True, index=True)
    apartment_task_id = fields.Many2one(
        related='space_task_id.construction_apartment_task_id', string='Departamento')
    floor_task_id = fields.Many2one(
        related='space_task_id.construction_floor_task_id', string='Piso')
    stage = fields.Selection(STAGES, string='Etapa', required=True)
    sequence = fields.Integer(
        string='Secuencia', compute='_compute_sequence', store=True,
        help='Orden de la etapa: Producción, Armado, Instalación, Acabado y entrega.')
    date_start = fields.Date(string='Inicio', required=True)
    date_end = fields.Date(string='Fin', required=True)
    predecessor_id = fields.Many2one(
        'construction.space.stage', string='Etapa anterior', compute='_compute_predecessor_id',
        check_company=True,
        help='La etapa anterior del mismo ambiente; son los vínculos del cronograma.')
    partner_id = fields.Many2one(
        'res.partner', string='Contrata', compute='_compute_resources',
        help='La contrata de las líneas de contrata de la etapa (la de mayor monto si hay '
             'varias).')
    role_id = fields.Many2one(
        'planning.role', string='Cuadrilla', compute='_compute_resources',
        help='El rol de las líneas de personal propio de la etapa.')
    amount_planned = fields.Monetary(
        string='Monto', compute='_compute_resources', currency_field='currency_id',
        help='Monto planificado de las líneas de la etapa en el ambiente y sus módulos.')
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    progress_pct = fields.Float(
        string='Avance', compute='_compute_progress_pct',
        help='Avance valorizado de las líneas de contrata y personal propio de la etapa en el '
             'ambiente y sus módulos.')

    _space_stage_unique = models.Constraint(
        'UNIQUE(space_task_id, stage)', 'Cada ambiente tiene una sola fila por etapa.')

    @api.depends('stage')
    def _compute_sequence(self):
        for record in self:
            record.sequence = STAGE_ORDER.index(record.stage) if record.stage in STAGE_ORDER else 0

    @api.depends('space_task_id.display_name', 'stage')
    def _compute_display_name(self):
        labels = dict(self._fields['stage']._description_selection(self.env))
        for record in self:
            record.display_name = ' · '.join(filter(None, [
                record.space_task_id.display_name, labels.get(record.stage)]))

    @api.depends('space_task_id.construction_stage_ids.stage', 'stage')
    def _compute_predecessor_id(self):
        for record in self:
            earlier = record.space_task_id.construction_stage_ids.filtered(
                lambda s: s.sequence < record.sequence)
            record.predecessor_id = earlier.sorted('sequence')[-1:]

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end and record.date_start > record.date_end:
                raise ValidationError(self.env._(
                    'El inicio de la etapa %s no puede ser posterior a su fin.',
                    record.display_name))

    @api.constrains('space_task_id')
    def _check_space(self):
        for record in self:
            if record.space_task_id.construction_level != 'space':
                raise ValidationError(self.env._(
                    'Las etapas del cronograma son de un ambiente: %s no lo es.',
                    record.space_task_id.display_name))

    # ------------------------------------------------------------------
    # Líneas del plan de la etapa
    # ------------------------------------------------------------------
    def _get_plan(self):
        self.ensure_one()
        return self.project_id._construction_current_plan()

    def _get_lines_domain(self):
        """Líneas de la etapa en el ambiente y sus módulos (plan vigente)."""
        self.ensure_one()
        return [('plan_id', '=', self._get_plan().id),
                ('space_task_id', '=', self.space_task_id.id), ('stage', '=', self.stage)]

    def _get_lines(self):
        self.ensure_one()
        return self.env['construction.resource.plan.line'].search(self._get_lines_domain())

    @api.model
    def _resources_by_stage(self, stages):
        """{(ambiente, etapa): {partner, role, amount}} de un lote de etapas
        con tres _read_group (sin una consulta por etapa)."""
        Line = self.env['construction.resource.plan.line']
        result = {}
        for project in stages.project_id:
            plan = project._construction_current_plan()
            spaces = stages.filtered(lambda s: s.project_id == project).space_task_id
            if not plan or not spaces:
                continue
            base = [('plan_id', '=', plan.id), ('space_task_id', 'in', spaces.ids)]
            for space, stage, amount in Line._read_group(
                    base, ['space_task_id', 'stage'], ['amount_planned:sum']):
                result.setdefault((space.id, stage), {})['amount'] = amount or 0.0
            # Etapas con contratas o personal propio: solo esas necesitan quien
            # las ejecute (la producción suele ser solo material).
            for space, stage in Line._read_group(
                    base + [('resource_type', 'in', DRIVER_TYPES)], ['space_task_id', 'stage']):
                result.setdefault((space.id, stage), {})['drivers'] = True
            for space, stage, partner, amount in Line._read_group(
                    base + [('resource_type', '=', 'contract'), ('partner_id', '!=', False)],
                    ['space_task_id', 'stage', 'partner_id'], ['amount_planned:sum']):
                item = result.setdefault((space.id, stage), {})
                if amount >= item.get('_partner_amount', -1):
                    item.update(partner=partner, _partner_amount=amount)
            for space, stage, role in Line._read_group(
                    base + [('resource_type', '=', 'labor'), ('role_id', '!=', False)],
                    ['space_task_id', 'stage', 'role_id']):
                result.setdefault((space.id, stage), {}).setdefault('role', role)
        return result

    @api.depends('space_task_id', 'stage')
    def _compute_resources(self):
        resources = self._resources_by_stage(self.filtered('id'))
        for record in self:
            item = resources.get((record.space_task_id.id, record.stage), {})
            record.partner_id = item.get('partner')
            record.role_id = item.get('role')
            record.amount_planned = item.get('amount', 0.0)

    @api.model
    def _progress_by_stage(self, stages):
        """{(ambiente, etapa): avance} valorizado, una consulta por etapa del
        catálogo (no por registro)."""
        Plan = self.env['construction.resource.plan']
        result = {}
        for project in stages.project_id:
            plan = project._construction_current_plan()
            group = stages.filtered(lambda s: s.project_id == project)
            if not plan:
                continue
            for stage in set(group.mapped('stage')):
                spaces = group.filtered(lambda s: s.stage == stage).space_task_id
                amounts = Plan._progress_amounts(
                    [('plan_id', '=', plan.id), ('stage', '=', stage),
                     ('space_task_id', 'in', spaces.ids)], 'space_task_id')
                for space in spaces:
                    result[(space.id, stage)] = Plan._progress_ratio(amounts, space.id)
        return result

    @api.depends('space_task_id', 'stage')
    def _compute_progress_pct(self):
        progress = self._progress_by_stage(self.filtered('id'))
        for record in self:
            record.progress_pct = progress.get((record.space_task_id.id, record.stage), 0.0)

    # ------------------------------------------------------------------
    # Mover fechas
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._rollup_task_dates()
        return records

    def write(self, vals):
        moving = 'date_start' in vals and not self.env.context.get('construction_stage_keep_lines')
        old = {record.id: record.date_start for record in self} if moving else {}
        res = super().write(vals)
        if moving:
            self._shift_lines(old)
        if {'date_start', 'date_end'} & set(vals):
            # Cambiar la etapa desde su formulario también empuja a las
            # siguientes del ambiente (el arrastre lo hace en una sola vez).
            if not self.env.context.get('construction_stage_no_chain'):
                for record in self:
                    record._chain_successors()
            if not self.env.context.get('construction_stage_no_rollup'):
                self._rollup_task_dates()
        return res

    def unlink(self):
        spaces = self.space_task_id
        res = super().unlink()
        self.browse()._rollup_task_dates(spaces)
        return res

    # ------------------------------------------------------------------
    # Días hábiles, cadena y fechas de las tareas (v1.5, M15-17 y M15-18)
    # ------------------------------------------------------------------
    def _company_for_days(self):
        return self.company_id or self.project_id.company_id or self.env.company

    def _chain_successors(self):
        """Empuja las etapas siguientes del ambiente que quedan solapadas:
        cada una empieza el día hábil siguiente al fin de la anterior y
        conserva sus días hábiles. Devuelve ``[(etapa, inicio, fin)]`` con
        las fechas anteriores de las movidas."""
        self.ensure_one()
        company = self._company_for_days()
        moved = []
        previous_end = self.date_end
        for successor in self.space_task_id.construction_stage_ids.filtered(
                lambda s: s.sequence > self.sequence).sorted('sequence'):
            if successor.date_start > previous_end:
                break
            days = company._construction_count_site_days(successor.date_start, successor.date_end)
            new_start = company._construction_next_site_day(previous_end + timedelta(days=1))
            new_end = company._construction_add_site_days(new_start, days)
            moved.append((successor, successor.date_start, successor.date_end))
            successor.with_context(construction_stage_no_chain=True,
                                   construction_stage_no_rollup=True).write(
                {'date_start': new_start, 'date_end': new_end})
            previous_end = new_end
        return moved

    @api.model
    def _task_date_fields(self):
        field_map = self.env['al.gantt.field.map'].get_map()
        return field_map.get('date_start'), field_map.get('date_end')

    def _rollup_task_dates(self, spaces=None):
        """Guarda en las tareas del árbol (ambiente, unidad, piso y
        agrupadores) el menor inicio y el mayor fin de lo que tienen debajo,
        para que Proyectos, listas, calendario e hitos vean las mismas fechas
        que el cronograma."""
        start_field, end_field = self._task_date_fields()
        if not start_field and not end_field:
            return
        Task = self.env['project.task'].with_context(
            tracking_disable=True, mail_notrack=True, construction_stage_no_rollup=True)
        nodes = (spaces or self.space_task_id)
        nodes = Task.browse(nodes.ids)

        def value(field, day):
            if not field or not day:
                return False
            return day if Task._fields[field].type == 'date' else \
                fields.Datetime.to_datetime(day)

        while nodes:
            for node in nodes:
                if node.construction_level == 'space':
                    stages = self.search([('space_task_id', '=', node.id)])
                    starts = stages.mapped('date_start')
                    ends = stages.mapped('date_end')
                else:
                    children = Task.search([('parent_id', '=', node.id),
                                            ('construction_level', '!=', False)])
                    starts = [fields.Date.to_date(c[start_field]) for c in children
                              if start_field and c[start_field]]
                    ends = [fields.Date.to_date(c[end_field]) for c in children
                            if end_field and c[end_field]]
                vals = {}
                if start_field:
                    vals[start_field] = value(start_field, min(starts) if starts else False)
                if end_field:
                    vals[end_field] = value(end_field, max(ends) if ends else False)
                vals = {k: v for k, v in vals.items() if node[k] != v}
                if vals:
                    node.write(vals)
            nodes = nodes.parent_id.filtered('construction_level')

    def _shift_lines(self, old_starts, notify=True):
        """Desplaza la fecha de necesidad de las líneas de cada etapa movida
        tantos días como su inicio y avisa a Logística. Devuelve
        ``{'lines': n, 'notified': [documentos]}``."""
        lines_count, notified = 0, []
        for record in self:
            old = old_starts.get(record.id)
            if not old or not record.date_start:
                continue
            delta = (record.date_start - old).days
            if not delta:
                continue
            lines = record._get_lines()
            shift = timedelta(days=delta)
            for line in lines:
                line.date_needed = line.date_needed + shift if line.date_needed \
                    else line._get_default_date_needed().get(line)
            lines_count += len(lines)
            plan = record._get_plan()
            if not plan or not lines or not notify:
                continue
            documents = plan._notify_logistics(lines, delta)
            notified += documents
            plan.message_post(body=self.env._(
                'Etapa %(stage)s movida %(delta)s días en el cronograma: %(lines)s líneas; '
                'avisos a Logística: %(docs)s.', stage=record.display_name, delta=delta,
                lines=len(lines), docs=', '.join(documents) or '—'))
        return {'lines': lines_count, 'notified': notified}

    def action_gantt_reschedule(self, date_start, date_end, chain=False):
        """Arrastre de la barra en el cronograma (P-15).

        Con ``chain`` empuja las etapas siguientes del ambiente que quedan
        solapadas, conservando su duración (fin-comienzo, como el Gantt de
        tareas). Devuelve las etapas movidas y los avisos para la interfaz."""
        self.ensure_one()
        self.check_access('write')
        start, end = fields.Date.to_date(date_start), fields.Date.to_date(date_end)
        if not start or not end:
            raise UserError(self.env._('Indique el inicio y el fin de la etapa.'))
        if start > end:
            raise UserError(self.env._('El inicio de la etapa no puede ser posterior a su fin.'))
        moves = [(self, start, end)]
        if chain:
            company = self._company_for_days()
            previous_end = end
            for successor in self.space_task_id.construction_stage_ids.filtered(
                    lambda s: s.sequence > self.sequence).sorted('sequence'):
                if successor.date_start > previous_end:
                    break
                # Empieza el día hábil siguiente y conserva sus días hábiles.
                days = company._construction_count_site_days(
                    successor.date_start, successor.date_end)
                new_start = company._construction_next_site_day(previous_end + timedelta(days=1))
                new_end = company._construction_add_site_days(new_start, days)
                moves.append((successor, new_start, new_end))
                previous_end = new_end
        old = {stage.id: stage.date_start for stage, _start, _end in moves}
        moved = self.browse()
        for stage, new_start, new_end in moves:
            if (stage.date_start, stage.date_end) != (new_start, new_end):
                stage.with_context(construction_stage_keep_lines=True,
                                   construction_stage_no_chain=True,
                                   construction_stage_no_rollup=True).write(
                    {'date_start': new_start, 'date_end': new_end})
                moved |= stage
        moved._rollup_task_dates()
        result = moved._shift_lines(old)
        result['stages'] = [{'id': stage.id, 'date_start': fields.Date.to_string(stage.date_start),
                             'date_end': fields.Date.to_string(stage.date_end)}
                            for stage in moved]
        return result

    # ------------------------------------------------------------------
    # Creación desde el plan
    # ------------------------------------------------------------------
    @api.model
    def _default_dates(self, space, stage, plan):
        """Fechas propuestas: desde el inicio del ambiente (o del plan), una
        semana por etapa en el orden Producción → Acabado, de lunes a
        viernes."""
        start_field = self.env['al.gantt.field.map'].get_map().get('date_start')
        base = fields.Date.to_date(space[start_field]) if start_field and space[start_field] \
            else plan.date_start or fields.Date.context_today(self)
        start = base + timedelta(days=7 * STAGE_ORDER.index(stage))
        return start, start + timedelta(days=DEFAULT_STAGE_DAYS - 1)

    @api.model
    def _sync_from_plan(self, plan):
        """Crea las etapas que faltan para las etapas con líneas en cada
        ambiente del plan. No toca las que ya existen (sus fechas son del
        cronograma). Devuelve las creadas."""
        Line = self.env['construction.resource.plan.line']
        existing = {(stage.space_task_id.id, stage.stage) for stage in self.search(
            [('project_id', '=', plan.project_id.id)])}
        values = []
        for space, stage in Line._read_group(
                [('plan_id', '=', plan.id), ('space_task_id', '!=', False),
                 ('stage', '!=', False)], ['space_task_id', 'stage']):
            if (space.id, stage) in existing:
                continue
            start, end = self._default_dates(space, stage, plan)
            values.append({'space_task_id': space.id, 'stage': stage,
                           'date_start': start, 'date_end': end})
        return self.create(values)


    @api.model
    def _schedule_by_pace(self, plan, spaces, date_start, mode, pace, order='asc', stage_days=None):
        """Ritmo de programación (v1.5, M15-17): fechas escalonadas por piso.

        ``mode`` ``floors_per_week`` (``pace`` pisos empiezan cada semana) o
        ``weeks_per_floor`` (cada piso empieza ``pace`` semanas después del
        anterior). Dentro de cada ambiente las etapas van una tras otra, con
        ``stage_days`` días hábiles cada una, desde el día hábil siguiente al
        fin de la anterior; los feriados no cuentan. Devuelve las etapas
        movidas."""
        if not spaces or not date_start or not pace or pace <= 0:
            return self.browse()
        company = plan.company_id or plan.project_id.company_id or self.env.company
        stage_days = stage_days or {}
        # En el orden del árbol: agrupadores (torre, etapa) y luego el piso.
        floors = spaces.mapped('construction_floor_task_id').sorted(
            lambda f: (f._construction_group_names(), f.sequence, f.name or '', f.id),
            reverse=(order == 'desc'))
        floor_start = {}
        for index, floor in enumerate(floors):
            weeks = index / pace if mode == 'floors_per_week' else index * pace
            floor_start[floor.id] = company._construction_next_site_day(
                date_start + timedelta(days=int(weeks * 7 + 0.5)))
        stages = self.search([('space_task_id', 'in', spaces.ids)])
        by_space = {}
        for stage in stages:
            by_space.setdefault(stage.space_task_id.id, []).append(stage)
        moved, old = self.browse(), {}
        for space in spaces:
            cursor = floor_start.get(space.construction_floor_task_id.id) or \
                company._construction_next_site_day(date_start)
            for stage in sorted(by_space.get(space.id, []), key=lambda s: s.sequence):
                start = company._construction_next_site_day(cursor)
                end = company._construction_add_site_days(
                    start, stage_days.get(stage.stage) or DEFAULT_STAGE_DAYS)
                if (stage.date_start, stage.date_end) != (start, end):
                    old[stage.id] = stage.date_start
                    stage.with_context(construction_stage_keep_lines=True,
                                       construction_stage_no_chain=True,
                                       construction_stage_no_rollup=True).write(
                        {'date_start': start, 'date_end': end})
                    moved |= stage
                cursor = end + timedelta(days=1)
        # Las fechas de necesidad se mueven con su etapa, sin un aviso por
        # etapa (al programar la obra todavía no hay documentos abiertos).
        moved._shift_lines(old, notify=False)
        moved._rollup_task_dates(spaces)
        return moved

class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_stage_ids = fields.One2many(
        'construction.space.stage', 'space_task_id', string='Etapas del ambiente')


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def action_sync_space_stages(self):
        """«Crear etapas del cronograma»: las etapas que faltan en el plan."""
        self.ensure_one()
        created = self.env['construction.space.stage']._sync_from_plan(self)
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'type': 'success' if created else 'info',
                'message': self.env._('%s etapas creadas en el cronograma.', len(created))
                if created else self.env._('El cronograma ya tiene todas las etapas del plan.'),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_open_schedule(self):
        """Abre el cronograma con recursos (P-15) de este plan."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'al_construction_planner.schedule',
            'name': self.env._('Cronograma · %s', self.display_name),
            'context': {'construction_plan_id': self.id,
                        'gantt_project_ids': self.project_id.ids},
        }

    # ------------------------------------------------------------------
    # Avisos a Logística
    # ------------------------------------------------------------------
    def _get_logistics_user(self, company):
        group = self.env.ref(
            'al_construction_material_request.group_construction_logistics',
            raise_if_not_found=False)
        users = group.sudo().all_user_ids.filtered(
            lambda u: not u.share and company in u.company_ids) if group else False
        return users[:1] or self.env.user

    def _get_open_documents(self, lines):
        """{documento: (fecha del documento, fecha de necesidad más temprana de
        sus líneas)} de los requerimientos de obra, compras masivas y OC
        abiertos de las líneas."""
        documents = {}

        def add(document, doc_date, need):
            if not document or not doc_date or not need:
                return
            doc_date = fields.Date.to_date(doc_date)
            prev = documents.get(document)
            documents[document] = (doc_date, min(need, prev[1]) if prev else need)

        # sudo: los documentos son de compras y almacén; solo se leen sus
        # fechas para avisar a Logística.
        for allocation in lines.sudo().allocation_ids.filtered(lambda a: a.state == 'open'):
            need = allocation.plan_line_id.date_needed
            if allocation.kind == 'material_request':
                request = allocation.material_request_line_id.request_id
                add(request, request.date_required, need)
            elif allocation.kind == 'purchase_request':
                pr_line = allocation.purchase_request_line_id
                add(pr_line.request_id, pr_line.date_required, need)
                for po_line in pr_line.purchase_lines.filtered(
                        lambda l: l.state not in ('cancel', 'done')):
                    add(po_line.order_id, po_line.date_planned, need)
            elif allocation.kind == 'service_order':
                po_line = allocation.purchase_line_id
                add(po_line.order_id, po_line.date_planned, need)
        return documents

    def _notify_logistics(self, lines, delta):
        """Avisos de «Cambiar fechas» (W-08) y del cronograma (P-15).

        Actividad para Logística en cada documento cuya fecha queda antes
        de la nueva necesidad (al postergar: llegaría antes de tiempo) o
        después (al adelantar: llegaría tarde)."""
        notified = []
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for document, (doc_date, need) in self._get_open_documents(lines).items():
            if delta > 0 and doc_date >= need or delta < 0 and doc_date <= need:
                continue
            if delta > 0:
                note = self.env._(
                    'El plan %(plan)s se postergó %(days)s días: la nueva necesidad es el '
                    '%(need)s y este documento tiene fecha %(date)s. Revise si conviene '
                    'postergarlo.', plan=self.display_name, days=delta,
                    need=format_date(self.env, need), date=format_date(self.env, doc_date))
            else:
                note = self.env._(
                    'El plan %(plan)s se adelantó %(days)s días: la nueva necesidad es el '
                    '%(need)s y este documento tiene fecha %(date)s. Revise si se puede '
                    'adelantar.', plan=self.display_name, days=-delta,
                    need=format_date(self.env, need), date=format_date(self.env, doc_date))
            user = document.user_id if document._name == 'purchase.order' and \
                document.user_id else self._get_logistics_user(document.company_id)
            summary = self.env._('Fechas del plan cambiadas')
            # sudo: quien cambia las fechas (Proyectos) no suele tener acceso
            # a compras ni almacén; la actividad es el aviso a Logística.
            document_sudo = document.sudo()
            # Arrastrar varias etapas seguidas no apila avisos: se suma la nota
            # a la actividad pendiente del mismo aviso.
            pending_sudo = document_sudo.activity_ids.filtered(
                lambda a: a.summary == summary and a.user_id == user)[:1]
            if pending_sudo:
                pending_sudo.note = Markup('%s<p>%s</p>') % (pending_sudo.note or '', note)
            else:
                document_sudo.activity_schedule(
                    activity_type_id=activity_type.id if activity_type else False,
                    summary=summary, note=note, user_id=user.id,
                    date_deadline=fields.Date.context_today(self))
            notified.append(document.display_name)
        return notified
