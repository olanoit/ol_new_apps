# -*- coding: utf-8 -*-
"""Funciones de campo de mobiliario del portal de obra (paquete 1.22, etapa
2, M122-05 a M122-09).

Como el resto del portal: la persona es un usuario de portal sin permisos
internos; cada servicio comprueba que está en el portal de la obra con el
papel que corresponde y que la obra usa la función, y después lee o escribe
con sudo solo eso. Nada se pregunta por el código de una etapa ni por el
nombre de un nivel: se pregunta por la función del nivel (unidad de entrega,
ambiente, módulo) y por el tipo de la etapa en el catálogo."""
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.al_construction_planner.models.construction_space_current_stage import (
    SPACE_STATE_CODES,
)

from .project_task import PORTAL_MEASURE

#: {función del portal: campo del perfil de vertical}.
FURNITURE_FEATURES = {
    'module_reception': 'portal_module_reception',
    'replacement': 'portal_replacement',
    'measure': 'portal_measure',
    'stage_progress': 'portal_stage_progress',
    'contractor_units': 'portal_contractor_units',
}
#: Quienes reciben, miden y piden reposición: el capataz y la oficina técnica
#: (el residente trabaja también con esos dos papeles).
FIELD_ROLES = {'foreman', 'office'}
#: Cómo llegó cada módulo de un despacho.
MODULE_STATUS = ('ok', 'missing', 'damaged')
#: Estados del módulo que un despacho ya no mueve.
PLACED_STATES = ('installed', 'delivered')


class ConstructionPortalService(models.AbstractModel):
    _inherit = 'construction.portal.service'

    # ------------------------------------------------------------------
    # Funciones del perfil
    # ------------------------------------------------------------------
    @api.model
    def _portal_feature_fields(self):
        return dict(super()._portal_feature_fields(), **FURNITURE_FEATURES)

    @api.model
    def _portal_feature_messages(self):
        return dict(super()._portal_feature_messages(), **{
            'module_reception': self.env._('La obra no recibe módulos por departamento.'),
            'replacement': self.env._('La obra no pide reposiciones desde el portal.'),
            'measure': self.env._('La obra no marca ambientes medidos desde el portal.'),
            'stage_progress': self.env._('La obra no usa el avance por sub etapa.'),
            'contractor_units': self.env._('La obra no usa el avance de la contrata por '
                                           'departamento.'),
        })

    # ------------------------------------------------------------------
    # Ayudas
    # ------------------------------------------------------------------
    def _furniture_install_stages(self, project):
        """Sub etapas de instalación de la obra, en el orden del catálogo:
        las etapas de campo de su perfil cuyos materiales no salen con la
        orden de fabricación (el armado de planta queda fuera)."""
        # sudo: la persona del portal no lee el catálogo de etapas.
        Stage = self.env['construction.stage'].sudo()
        produced = set(Stage._production_codes(project))
        codes = [code for code in Stage._field_codes(project) if code not in produced]
        return Stage._tree_sorted(Stage._by_code(codes)) if codes else Stage

    def _furniture_module_label(self, task):
        """Cómo se nombra un módulo en el portal: su rótulo del ETO; sin él,
        su código en la tipología o su nombre. Nunca el código del producto."""
        return task.construction_eto_label or task.construction_module_code or task.name or ''

    def _furniture_module_data(self, task):
        space = task.construction_space_task_id
        label = self._furniture_module_label(task)
        return {
            'id': task.id, 'label': label,
            'name': task.name if task.name and task.name != label else '',
            'space_id': space.id or False, 'space': space.name or '',
            'typology': space.construction_typology_id.code or '',
        }

    def _furniture_module_product(self, task):
        """Producto fabricado del módulo: el de su módulo de tipología (se
        crea al aprobar el plan)."""
        typology = task.construction_space_task_id.construction_typology_id
        return typology.module_line_ids.filtered(
            lambda module: module.code == task.construction_module_code)[:1].product_id

    def _furniture_reasons(self, company):
        # sudo: la persona del portal no lee el catálogo de motivos de fabricación.
        return self.env['construction.production.reason'].sudo().search(
            [('company_id', 'in', (company.id, False))])

    def _furniture_reason(self, raw, company, default=False):
        """El motivo que envía el celular, entre los de la compañía de la
        obra. Con ``default``, sin motivo vale el primero del catálogo."""
        reasons = self._furniture_reasons(company)
        if raw:
            reason = reasons.filtered(lambda r: r.id == int(raw))
            if not reason:
                raise UserError(self.env._(
                    'Ese motivo de reposición no es de la compañía de la obra.'))
            return reason
        if not default:
            raise UserError(self.env._('Elija el motivo de la reposición.'))
        if not reasons:
            raise UserError(self.env._('La compañía no tiene motivos de reposición: pida que los '
                                       'configuren en Fabricación.'))
        return reasons[:1]

    def _furniture_replacement_create(self, project, task, qty, reason, note, attachments):
        """Reposición a planta en borrador, pedida por la persona del portal,
        con sus fotos. Sigue en Odoo su flujo de siempre."""
        product = self._furniture_module_product(task)
        if not product:
            raise UserError(self.env._(
                '%s aún no tiene producto de módulo (se crea al aprobar el plan): pida la '
                'reposición a la oficina.', self._furniture_module_label(task)))
        company = project.company_id or self.env.company
        # sudo: la reposición la pide la persona del portal de su obra
        # (comprobada por quien llama); queda en borrador para la oficina.
        replacement_sudo = self.env['construction.replacement.request'].sudo().with_company(
            company).create({
                'company_id': company.id, 'project_id': project.id, 'task_id': task.id,
                'product_id': product.id, 'product_qty': qty, 'reason_id': reason.id,
                'reason_note': note or False, 'requested_by': self.env.uid})
        attachments.write({'res_id': replacement_sudo.id})
        replacement_sudo.message_post(
            body=self.env._('Pedida desde el portal de obra: %(module)s de %(space)s.',
                            module=self._furniture_module_label(task),
                            space=task.construction_space_task_id.display_name or '-'),
            author_id=self.env.user.partner_id.id, attachment_ids=attachments.ids)
        return replacement_sudo

    # ------------------------------------------------------------------
    # Sincronización: ficha del departamento
    # ------------------------------------------------------------------
    @api.model
    def sync(self, project_id):
        data = super().sync(project_id)
        features = set(data.get('features') or [])
        if features & set(FURNITURE_FEATURES):
            project, members = self._project(project_id)
            data['furniture'] = self._furniture_data(project, members, features)
        return data

    def _furniture_data(self, project, members, features):
        """Lo que el celular guarda para la ficha del departamento y las
        funciones de mobiliario, para trabajar sin señal."""
        roles = self._roles(members)
        field = bool(roles & FIELD_ROLES)
        company = project.company_id or self.env.company
        lines = self._lines(project, members)
        # sudo: los departamentos de la obra (o de las líneas de la contrata),
        # sus ambientes y módulos; la persona ya está en el portal de la obra.
        Task = self.env['project.task'].sudo()
        if field:
            apartments = Task.search([('project_id', '=', project.id),
                                      ('construction_level', '=', 'apartment')])
        else:
            apartments = lines.apartment_task_id
        result = {
            'stages': [{'code': stage.code, 'label': stage._label(),
                        'number': stage.number or ''}
                       for stage in self._furniture_install_stages(project)],
            'apartments': {}, 'reasons': [], 'settled': {}, 'week': False,
        }
        with_modules = field and bool(features & {'replacement', 'module_reception'})
        children = Task.search([
            ('construction_apartment_task_id', 'in', apartments.ids),
            ('construction_level', 'in', ('space', 'module') if with_modules else ('space',)),
        ], order='sequence, id') if apartments else Task
        stage_labels = dict(Task._fields['construction_current_stage']._description_selection(
            self.env))
        stage_labels.update(project._construction_space_state_labels())
        for apartment in apartments:
            result['apartments'][apartment.id] = {
                'id': apartment.id, 'name': apartment.name or '',
                'parent': apartment.parent_id.name or '', 'spaces': [], 'modules': [],
                'replacements': []}
        for task in children:
            entry = result['apartments'][task.construction_apartment_task_id.id]
            if task.construction_level == 'space':
                code = task.construction_current_stage or ''
                measured = bool(task.construction_measured)
                entry['spaces'].append({
                    'id': task.id, 'name': task.name or '', 'stage': code,
                    'stage_label': stage_labels.get(code) or '',
                    # Pendiente, Medido y Entregado no son etapas del catálogo.
                    'kind': code if code in SPACE_STATE_CODES else 'stage' if code else '',
                    'measured': measured,
                    'can_measure': not measured and code in ('', 'pending'),
                    'typology': task.construction_typology_id.code or ''})
            elif with_modules:
                entry['modules'].append(self._furniture_module_data(task))
        if field and 'replacement' in features:
            self._furniture_open_replacements(project, result['apartments'])
        if field and features & {'replacement', 'module_reception'}:
            result['reasons'] = [[reason.id, reason.name]
                                 for reason in self._furniture_reasons(company)]
        if 'contractor_units' in features and 'contractor' in roles:
            partners = self._partners(members)
            own = lines.filtered(lambda l: l.resource_type == 'contract'
                                 and l.partner_id.commercial_partner_id in partners)
            result['settled'] = {line.id: line.qty_settled for line in own if line.qty_settled}
            result['week'] = self._furniture_contract_week(project, own, partners)
        return result

    def _furniture_open_replacements(self, project, apartments):
        """Reposiciones abiertas de la obra, en la ficha de su departamento."""
        # sudo: la persona del portal no lee las reposiciones; solo se
        # muestran las de su obra, con su estado.
        replacements_sudo = self.env['construction.replacement.request'].sudo().search([
            ('project_id', '=', project.id), ('state', 'not in', ('done', 'cancel')),
            ('task_id', '!=', False)])
        states = dict(replacements_sudo._fields['state']._description_selection(self.env))
        for replacement in replacements_sudo:
            task = replacement.task_id
            entry = apartments.get(task.construction_apartment_task_id.id)
            if not entry:
                continue
            entry['replacements'].append({
                'id': replacement.id, 'name': replacement.name,
                'module': self._furniture_module_label(task)
                if task.construction_level == 'module' else task.name or '',
                'space': task.construction_space_task_id.name or '',
                'qty': replacement.product_qty,
                'state': replacement.state, 'state_label': states.get(replacement.state, ''),
                'reason': replacement.reason_id.name or ''})

    def _furniture_contract_week(self, project, lines, partners):
        """«Esta semana» de la contrata (M122-09): lo reportado y lo validado
        de la semana de la obra por actividad, en la unidad de su driver. Es
        lo que toma la liquidación semanal; aquí solo se lee."""
        today = fields.Date.context_today(self)
        week_start, week_end = project._construction_period(today)
        totals = {}
        if lines:
            # sudo: los avances de las líneas de la contrata (limitadas por
            # quien llama a las de su empresa).
            groups = self.env['construction.task.progress'].sudo()._read_group(
                [('plan_line_id', 'in', lines.ids), ('date', '>=', week_start),
                 ('date', '<=', week_end), ('state', '!=', 'rejected'),
                 ('is_rework', '=', False)],
                ['activity_id', 'state'], ['qty_weighted:sum'])
            for activity, state, qty in groups:
                row = totals.setdefault(activity, {'reported': 0.0, 'validated': 0.0})
                row['reported'] += qty or 0.0
                if state == 'validated':
                    row['validated'] += qty or 0.0
        return {
            'start': fields.Date.to_string(week_start), 'end': fields.Date.to_string(week_end),
            'partner': partners[:1].name or '',
            'rows': [{'activity': activity.display_name, 'uom': activity.uom_id.name or '',
                      'reported': row['reported'], 'validated': row['validated']}
                     for activity, row in sorted(
                         totals.items(), key=lambda kv: (kv[0].sequence, kv[0].id))],
        }

    # ------------------------------------------------------------------
    # M122-05 · Recepción de módulos por departamento
    # ------------------------------------------------------------------
    def _furniture_delivery_modules(self, picking, project):
        """{movimiento: módulos de la obra que trae} de una entrega por
        recibir. Los módulos salen del propio movimiento (envío de planta a
        obra) o, en el despacho por unidad, de los del departamento de la
        transferencia con ese producto. Un movimiento cuyos módulos no
        cuadran con su cantidad se sigue recibiendo por producto."""
        # sudo: los módulos de la entrega de la obra de la persona.
        Task = self.env['project.task'].sudo()
        moves = picking.move_ids.filtered(
            lambda m: m.state not in ('done', 'cancel')
            and m.product_id.product_tmpl_id.construction_project_id == project)
        result = {}
        if not moves:
            return result
        chain = picking | picking.move_ids.move_orig_ids.picking_id
        department = None
        taken = Task
        for move in moves:
            qty = move.product_uom._compute_quantity(move.product_uom_qty, move.product_id.uom_id)
            tasks = move.construction_module_task_ids.filtered(
                lambda t: t.construction_level == 'module')
            if not tasks and picking.construction_apartment_task_id:
                if department is None:
                    department = picking._construction_department_modules()
                candidates = (department.get(move.product_id) or Task).filtered(
                    lambda t: t not in taken and t.construction_unit_state not in PLACED_STATES
                    and not (t.construction_shipment_picking_id.state == 'done'
                             and t.construction_shipment_picking_id not in chain))
                tasks = candidates.sorted(
                    lambda t: (t.construction_shipment_picking_id not in chain, t.id)
                )[:max(int(round(qty)), 0)]
            if tasks and move.product_id.uom_id.compare(qty, len(tasks)) == 0:
                result[move] = tasks
                taken |= tasks
        return result

    def _deliveries(self, project):
        """Con la función activa, la entrega que trae módulos de la obra se
        muestra por departamento (``departments``); sus líneas por producto
        quedan solo para lo demás. La recepción de materiales no cambia."""
        rows = super()._deliveries(project)
        if not rows or 'module_reception' not in self._portal_features(project):
            return rows
        # sudo: las mismas entregas que ya listó el portal para la obra.
        pickings = {picking.id: picking for picking in self.env['stock.picking'].sudo().browse(
            [row['id'] for row in rows])}
        for row in rows:
            modules = self._furniture_delivery_modules(pickings[row['id']], project)
            if not modules:
                continue
            departments = {}
            for move, tasks in modules.items():
                lot = move.construction_lot_id.name or ', '.join(
                    move.move_line_ids.lot_id.mapped('name'))
                for task in tasks:
                    apartment = task.construction_apartment_task_id
                    entry = departments.setdefault(apartment.id, {
                        'id': apartment.id, 'name': apartment.name or '', 'modules': []})
                    entry['modules'].append(dict(
                        self._furniture_module_data(task), move_id=move.id, lot=lot or ''))
            row['departments'] = sorted(departments.values(), key=lambda d: (d['name'], d['id']))
            module_moves = {move.id for move in modules}
            row['lines'] = [line for line in row['lines'] if line['move_id'] not in module_moves]
        return rows

    @api.model
    def module_reception(self, values):
        """Recepción de un despacho de módulos por departamento: cada módulo
        llegó, no llegó o llegó dañado. Se valida con lo que llegó, como la
        recepción de siempre (``reception``: hasta lo enviado, foto de la
        guía, entrega parcial); lo que no llegó queda en la entrega parcial
        y lo dañado entra a la obra y abre su reposición en borrador."""
        submission = self._submission('reception', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._project(values.get('project_id'))
        self._portal_require(project, 'module_reception')
        if not self._roles(members) & FIELD_ROLES:
            raise AccessError(self.env._('La recepción la registra el capataz.'))
        picking_id = int(values.get('picking_id') or 0)
        if picking_id not in {row['id'] for row in super()._deliveries(project)}:
            raise AccessError(self.env._('Esa entrega no es de su obra o ya se recibió.'))
        # sudo: la entrega es de la obra de la persona (comprobada arriba).
        picking = self.env['stock.picking'].sudo().browse(picking_id)
        modules = self._furniture_delivery_modules(picking, project)
        if not modules:
            raise UserError(self.env._(
                'Esa entrega no trae módulos de la obra: recíbala por producto.'))
        company = project.company_id or self.env.company
        Task = self.env['project.task'].sudo()
        expected = {(move.id, task.id): task for move, tasks in modules.items() for task in tasks}
        arrived, damaged = Task, []
        seen = set()
        for row in values.get('modules') or []:
            key = (int(row.get('move_id') or 0), int(row.get('task_id') or 0))
            status = row.get('status') or 'missing'
            if key not in expected or key in seen:
                raise UserError(self.env._('Un módulo marcado no es de esta entrega: actualice '
                                           'los datos de la obra y vuelva a recibirla.'))
            if status not in MODULE_STATUS:
                raise UserError(self.env._('Cada módulo llegó, no llegó o llegó dañado.'))
            seen.add(key)
            if status == 'missing':
                continue
            arrived |= expected[key]
            if status == 'damaged':
                damaged.append((expected[key], row))
        # Lo dañado se comprueba antes de validar la entrega: foto y motivo.
        replacements_todo = []
        for task, row in damaged:
            label = self._furniture_module_label(task)
            photos = [photo for photo in row.get('photos') or [] if photo and photo.get('data')]
            if not photos:
                raise UserError(self.env._('Tome la foto del daño de %s.', label))
            reason = self._furniture_reason(row.get('reason_id'), company, default=True)
            if not self._furniture_module_product(task):
                raise UserError(self.env._('%s no tiene producto de módulo.', label))
            replacements_todo.append((task, reason, (row.get('note') or '').strip(), photos))
        # Lo que llegó de cada movimiento de módulos, en su unidad; lo demás,
        # como lo cuenta la recepción por producto.
        lines = [row for row in values.get('lines') or []
                 if int(row.get('move_id') or 0) not in {move.id for move in modules}]
        for move, tasks in modules.items():
            count = len(tasks & arrived)
            lines.append({'move_id': move.id, 'qty': move.product_id.uom_id._compute_quantity(
                count, move.product_uom)})
        before = {task.id: task.construction_unit_state for task in expected.values()}
        result = self.reception({
            'uuid': values.get('uuid'), 'project_id': project.id, 'picking_id': picking.id,
            'photos': values.get('photos'), 'note': values.get('note'), 'lines': lines})
        self._furniture_settle_modules(picking, modules, arrived, before)
        replacements = self.env['construction.replacement.request'].sudo()
        for task, reason, note, photos in replacements_todo:
            attachments = self._photos(photos, 'construction.replacement.request', required=True)
            replacements |= self._furniture_replacement_create(
                project, task, 1.0, reason,
                note or self.env._('Llegó dañado en %s.', picking.name), attachments)
        if replacements:
            picking.message_post(body=self.env._(
                'Módulos que llegaron dañados, con reposición en borrador: %s.',
                ', '.join(replacements.mapped('name'))))
        return dict(result, replacements=replacements.mapped('name'),
                    received=len(arrived), missing=len(expected) - len(arrived))

    def _furniture_settle_modules(self, picking, modules, arrived, before):
        """Tras validar: los módulos que llegaron quedan «En obra» con esta
        transferencia y los que no, con la entrega parcial («En tránsito»).
        La validación nativa marca por producto y cantidad; aquí se deja lo
        que la persona marcó módulo por módulo. No crea movimientos."""
        Task = self.env['project.task'].sudo()
        expected = Task.union(*modules.values())
        missing = expected - arrived
        backorder = self.env['stock.picking'].sudo().search(
            [('backorder_id', '=', picking.id)], order='id desc', limit=1)
        # El enlace del movimiento con sus módulos (envío de planta a obra):
        # el movimiento hecho conserva los que llegaron; el resto queda en el
        # movimiento de la entrega parcial.
        for move, tasks in modules.items():
            gone = tasks & missing
            if not gone or not move.construction_module_task_ids:
                continue
            if move.picking_id != picking:
                # No llegó ninguno: el movimiento pasó entero a la entrega parcial.
                move.construction_module_task_ids = [(6, 0, gone.ids)]
                continue
            move.construction_module_task_ids = [(3, task.id) for task in gone]
            rest = backorder.move_ids.filtered(
                lambda m, move=move: m.product_id == move.product_id
                and m.construction_lot_id == move.construction_lot_id
                and m.state != 'cancel')[:1]
            if rest:
                rest.construction_module_task_ids = [(6, 0, gone.ids)]
        here = arrived.filtered(lambda t: t.construction_shipment_picking_id != picking)
        here.write({'construction_shipment_picking_id': picking.id})
        arrived.filtered(
            lambda t: t.construction_unit_state not in PLACED_STATES + ('on_site',)
        ).write({'construction_unit_state': 'on_site'})
        for task in missing:
            vals = {}
            if task.construction_shipment_picking_id != backorder:
                vals['construction_shipment_picking_id'] = backorder.id
            if task.construction_unit_state == 'on_site':
                # No llegó: vuelve al estado que tenía; si ya figuraba en obra
                # desde la salida al tránsito, a «Producido».
                previous = before.get(task.id)
                vals['construction_unit_state'] = previous \
                    if previous and previous != 'on_site' else 'produced'
            if vals:
                task.write(vals)

    # ------------------------------------------------------------------
    # M122-06 · Pedir reposición
    # ------------------------------------------------------------------
    @api.model
    def replacement(self, values):
        """Reposición a planta de un módulo de la obra, en borrador, con su
        motivo, «Qué pasó» y foto obligatoria."""
        submission = self._submission('replacement', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._project(values.get('project_id'))
        self._portal_require(project, 'replacement')
        if not self._roles(members) & FIELD_ROLES:
            raise AccessError(self.env._('La reposición la pide el capataz o el residente.'))
        # sudo: el módulo se busca solo en la obra de la persona.
        task = self.env['project.task'].sudo().search([
            ('id', '=', int(values.get('task_id') or 0)), ('project_id', '=', project.id),
            ('construction_level', '=', 'module')], limit=1)
        if not task:
            raise AccessError(self.env._('Ese módulo no es de su obra.'))
        qty = float(values.get('qty') or 0.0)
        if qty <= 0:
            raise UserError(self.env._('Indique la cantidad.'))
        company = project.company_id or self.env.company
        reason = self._furniture_reason(values.get('reason_id'), company)
        attachments = self._photos(values.get('photos'), 'construction.replacement.request',
                                   required=True)
        replacement = self._furniture_replacement_create(
            project, task, qty, reason, (values.get('note') or '').strip(), attachments)
        self._portal_register('replacement', values['uuid'], replacement)
        return {'status': 'done', 'ids': str(replacement.id), 'name': replacement.name,
                'state': replacement.state}

    # ------------------------------------------------------------------
    # M122-07 · Marcar medido
    # ------------------------------------------------------------------
    @api.model
    def measure(self, values):
        """Marca uno o varios ambientes como medidos, con fotos o croquis,
        con el asistente del escritorio: la marca, la fecha, «Medido por» (la
        persona del portal) y los archivos. Desmarcar sigue en Odoo."""
        submission = self._submission('measure', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._project(values.get('project_id'))
        self._portal_require(project, 'measure')
        if not self._roles(members) & FIELD_ROLES:
            raise AccessError(self.env._(
                'La medición la marca el capataz o la oficina técnica.'))
        space_ids = {int(space_id) for space_id in values.get('space_ids') or []}
        if not space_ids:
            raise UserError(self.env._('Elija al menos un ambiente.'))
        # sudo: los ambientes se buscan solo en la obra de la persona.
        spaces = self.env['project.task'].sudo().search([
            ('id', 'in', list(space_ids)), ('project_id', '=', project.id),
            ('construction_level', '=', 'space')])
        if len(spaces) != len(space_ids):
            raise AccessError(self.env._('Ese ambiente no es de su obra.'))
        spaces = spaces.filtered(lambda t: not t.construction_measured)
        if not spaces:
            raise UserError(self.env._('Esos ambientes ya están medidos.'))
        company = project.company_id or self.env.company
        day = self._portal_date(values.get('date'), company)
        attachments = self._photos(values.get('photos'), 'project.task', required=True)
        first, extra = attachments[:1], attachments[1:]
        # sudo: el asistente del escritorio con la marca del servidor; el
        # control de «personal de obra» acepta a la persona del portal de la
        # obra de cada ambiente (project_task.py). El autor sigue siendo ella.
        wizard_sudo = self.env['construction.space.measured.wizard'].sudo().with_context(
            construction_portal_measure=PORTAL_MEASURE).create({
                'task_ids': [(6, 0, spaces.ids)], 'date': day, 'file': first.datas,
                'file_name': first.name, 'note': (values.get('note') or '').strip() or False})
        wizard_sudo.action_confirm()
        # El asistente guarda su copia del primer archivo en cada ambiente.
        first.unlink()
        for index, space in enumerate(spaces):
            if not extra:
                break
            photos = extra if not index else extra.copy()
            photos.write({'res_id': space.id})
            space.construction_measured_attachment_ids = [(4, photo.id) for photo in photos]
            space.message_post(body=self.env._('Más archivos de la medición.'),
                               author_id=self.env.user.partner_id.id,
                               attachment_ids=photos.ids)
        self._portal_register('measure', values['uuid'], spaces)
        return {'status': 'done', 'ids': ','.join(str(i) for i in spaces.ids),
                'name': ', '.join(spaces.mapped('name')), 'count': len(spaces)}

    # ------------------------------------------------------------------
    # M122-08 y M122-09 · Avance por sub etapa
    # ------------------------------------------------------------------
    @api.model
    def stage_progress(self, values):
        """Un envío con una foto registra un avance por cada línea del plan
        de los ambientes y sub etapas marcados, con el saldo que le falta
        para llegar al porcentaje pedido. Las reglas son las del avance de
        una línea (``progress``): fecha, saldo, tolerancia y exceso las
        aplica el propio avance al crearse y lo valida el residente. Una
        línea que ya llegó a ese porcentaje no registra nada. La contrata
        solo alcanza sus líneas (``_lines``)."""
        submission = self._submission('stage_progress', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._project(values.get('project_id'))
        self._portal_require(project, 'progress')
        self._portal_require(project, 'stage_progress')
        company = project.company_id or self.env.company
        day = self._portal_date(values.get('date'), company,
                                company.construction_portal_progress_days)
        stages = set(self._furniture_install_stages(project).mapped('code'))
        targets = {}
        for cell in values.get('cells') or []:
            key = (int(cell.get('space_id') or 0), cell.get('stage') or '')
            pct = float(cell.get('pct') or 0.0)
            if key[1] not in stages:
                raise UserError(self.env._('Esa sub etapa no es de instalación en la obra.'))
            if pct > 0:
                targets[key] = max(pct, targets.get(key, 0.0))
        if not targets:
            raise UserError(self.env._('Marque al menos un ambiente y una sub etapa.'))
        lines = self._lines(project, members).filtered(
            lambda l: (l.space_task_id.id, l.stage) in targets)
        if not lines:
            raise AccessError(self.env._(
                'No tiene líneas del plan en esos ambientes y sub etapas.'))
        reported = self._reported_qty_map(lines)
        todo = []
        for line in lines.sorted(lambda l: (l.task_id.construction_path or '', l.id)):
            target = line.qty_planned * targets[(line.space_task_id.id, line.stage)] / 100.0
            qty = target - line.qty_executed - reported.get(line.id, 0.0)
            if line.product_uom_id.compare(qty, 0.0) > 0:
                todo.append((line, qty))
        if not todo:
            raise UserError(self.env._(
                'Esas líneas ya tienen registrado ese avance: no queda saldo por reportar.'))
        attachments = self._photos(values.get('photos'), 'construction.task.progress',
                                   required=True)
        latitude = float(values.get('latitude') or 0.0)
        longitude = float(values.get('longitude') or 0.0)
        vals_list, photo_sets = [], []
        for index, (line, qty) in enumerate(todo):
            # La misma foto en cada avance (el archivo se guarda una vez).
            photos = attachments if not index else attachments.copy()
            photo_sets.append(photos)
            vals_list.append({
                'task_id': line.task_id.id, 'activity_id': line.activity_id.id,
                'plan_line_id': line.id, 'date': day, 'qty': qty,
                'reported_by_id': self.env.uid, 'source': 'portal',
                'latitude': latitude, 'longitude': longitude,
                'attachment_ids': [(6, 0, photos.ids)]})
        # sudo: los avances los crea la persona del portal sobre sus líneas
        # (limitadas arriba); quedan «Por validar» con origen Portal.
        progresses = self.env['construction.task.progress'].sudo().create(vals_list)
        for progress, photos in zip(progresses, photo_sets):
            photos.write({'res_id': progress.id})
        note = (values.get('note') or '').strip()
        if note:
            for progress in progresses:
                progress.message_post(body=note, author_id=self.env.user.partner_id.id)
        # Fuera del radio de la obra: un solo aviso por el envío.
        site = project._construction_site() if hasattr(project, '_construction_site') else False
        first = progresses[:1]
        if site and site.radius_m and first.distance_m > site.radius_m:
            self._portal_notice(first, project, 'out_of_radius', self.env._(
                '%(count)s avances por sub etapa reportados a %(m)s m de la obra (radio '
                '%(r)s m), desde %(name)s.', count=len(progresses),
                m=round(first.distance_m), r=site.radius_m, name=first.name))
        self._portal_register('stage_progress', values['uuid'], progresses)
        return {'status': 'done', 'ids': ','.join(str(i) for i in progresses.ids),
                'name': self.env._('%s avances', len(progresses)),
                'count': len(progresses), 'skipped': len(lines) - len(todo),
                'exceeded': len(progresses.filtered(lambda p: p.exceed_state == 'exceeded'))}
