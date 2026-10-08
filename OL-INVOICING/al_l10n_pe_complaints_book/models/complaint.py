from datetime import datetime, time, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import email_normalize

#: Plazo de respuesta (Código, art. 24.1; Reglamento, arts. 6 y 6-B): 15 días
#: hábiles improrrogables, para reclamos y quejas.
RESPONSE_BUSINESS_DAYS = 15
#: Suspensión máxima por oferta de solución a distancia (art. 6-A.2.b).
MAX_SUSPENSION_DAYS = 5
#: Conservación mínima (art. 12).
RETENTION_YEARS = 2
#: Frase de aceptación de la solución (art. 6-A).
SETTLEMENT_PHRASE = 'ACUERDO ACEPTADO PARA SOLUCIONAR EL RECLAMO'

DOC_TYPES = [
    ('dni', 'DNI'),
    ('ce', 'Carné de extranjería'),
    ('passport', 'Pasaporte'),
    ('ruc', 'RUC'),
    ('other', 'Otro documento'),
]
CLOSED_STATES = ('answered', 'settled', 'closed')


class L10nPeComplaint(models.Model):
    """Hoja de reclamación (Anexo I del Reglamento, según el D.S. 101-2022-PCM)."""
    _name = 'l10n_pe.complaint'
    _description = 'Hoja de reclamación'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date_submitted desc, id desc'
    _rec_names_search = ['name', 'consumer_name', 'consumer_doc_number']
    _check_company_auto = True

    # ------------------------------------------------------------------
    # Cabecera
    # ------------------------------------------------------------------
    name = fields.Char(string='Número', readonly=True, copy=False, default='/', index=True,
                       help='Correlativo del libro y año (000000001-AAAA).')
    book_id = fields.Many2one('l10n_pe.complaint.book', string='Libro', required=True,
                              tracking=True, check_company=True, index=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, index=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.ref('base.PEN', raise_if_not_found=False)
                                  or self.env.company.currency_id)
    date_submitted = fields.Datetime(
        string='Fecha y hora de presentación', required=True, readonly=True, copy=False,
        default=fields.Datetime.now, tracking=True)
    channel = fields.Selection(
        selection=[('web', 'Libro virtual (web)'), ('physical', 'Libro físico'),
                   ('backup', 'Libro de respaldo'), ('phone', 'Teléfono u otro medio a distancia')],
        string='Canal', required=True, default='physical', tracking=True)
    backup_sheet_number = fields.Char(
        string='Número de la hoja de respaldo',
        help='Número impreso en la hoja del libro de respaldo (art. 4-A).')
    state = fields.Selection(
        selection=[('submitted', 'Registrada'), ('in_progress', 'En atención'),
                   ('suspended', 'Oferta de solución enviada'), ('answered', 'Respondida'),
                   ('settled', 'Solución aceptada'), ('closed', 'Cerrada')],
        string='Estado', default='submitted', required=True, tracking=True, copy=False,
        group_expand=True)
    responsible_user_id = fields.Many2one(
        'res.users', string='Responsable', tracking=True, domain=[('share', '=', False)])

    # ------------------------------------------------------------------
    # 1. Identificación del consumidor reclamante
    # ------------------------------------------------------------------
    partner_id = fields.Many2one('res.partner', string='Contacto', tracking=True,
                                 help='Opcional: el consumidor no necesita estar registrado.')
    consumer_name = fields.Char(string='Nombre', required=True, tracking=True)
    consumer_doc_type = fields.Selection(DOC_TYPES, string='Tipo de documento',
                                         required=True, default='dni')
    consumer_doc_number = fields.Char(string='Número de documento', required=True)
    consumer_address = fields.Char(string='Domicilio')
    consumer_phone = fields.Char(string='Teléfono')
    consumer_email = fields.Char(string='Correo electrónico', tracking=True)
    is_minor = fields.Boolean(string='Menor de edad')
    guardian_name = fields.Char(string='Padre, madre o representante')
    guardian_doc_number = fields.Char(string='Documento del representante')
    guardian_address = fields.Char(string='Domicilio del representante')
    guardian_phone = fields.Char(string='Teléfono del representante')
    guardian_email = fields.Char(string='Correo del representante')

    # ------------------------------------------------------------------
    # 2. Identificación del bien contratado
    # ------------------------------------------------------------------
    good_type = fields.Selection(
        selection=[('product', 'Producto'), ('service', 'Servicio'),
                   ('both', 'Producto y servicio')],
        string='Bien contratado', required=True, default='product')
    amount_claimed = fields.Monetary(string='Monto reclamado', currency_field='currency_id')
    good_description = fields.Text(string='Descripción del bien')
    order_reference = fields.Char(string='Comprobante o pedido',
                                  help='Número de comprobante, pedido o contrato, si lo indica.')

    # ------------------------------------------------------------------
    # 3. Detalle de la reclamación y pedido del consumidor
    # ------------------------------------------------------------------
    claim_type = fields.Selection(
        selection=[('claim', 'Reclamo'), ('complaint', 'Queja')],
        string='Tipo', required=True, default='claim', tracking=True,
        help='Reclamo: disconformidad relacionada a los productos o servicios. Queja: '
             'disconformidad no relacionada a los productos o servicios, o malestar respecto '
             'a la atención al público.')
    original_claim_type = fields.Selection(
        selection=[('claim', 'Reclamo'), ('complaint', 'Queja')],
        string='Tipo marcado por el consumidor', readonly=True, copy=False)
    detail = fields.Text(string='Detalle', required=True)
    consumer_request = fields.Text(string='Pedido del consumidor')
    preferred_response_channel = fields.Selection(
        selection=[('email', 'Correo electrónico'), ('letter', 'Carta')],
        string='Respuesta por', required=True, default='email',
        help='Medio por el que el consumidor pidió la respuesta (arts. 6 y 6-B).')
    consumer_confirmed = fields.Boolean(
        string='Envío confirmado por el consumidor', readonly=True, copy=False,
        help='Confirmación de voluntad en el libro virtual, en lugar de la firma.')
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Adjuntos del consumidor', copy=False)
    consumer_ip = fields.Char(string='IP de origen', readonly=True, copy=False,
                              groups='al_l10n_pe_complaints_book.group_complaint_manager')

    # ------------------------------------------------------------------
    # 4. Observaciones y acciones adoptadas por el proveedor
    # ------------------------------------------------------------------
    provider_observations = fields.Text(
        string='Observaciones y acciones adoptadas',
        help='Respuesta al consumidor. Si se rechaza el pedido, fundamente la posición.')
    response_date = fields.Date(string='Fecha de comunicación de la respuesta',
                                readonly=True, copy=False, tracking=True)
    response_user_id = fields.Many2one('res.users', string='Respondida por',
                                       readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Plazos
    # ------------------------------------------------------------------
    deadline_date = fields.Date(
        string='Vence', compute='_compute_deadline_date', store=True, tracking=True,
        help='Quince días hábiles desde el día siguiente a la presentación, más los días '
             'hábiles de suspensión por una oferta de solución a distancia.')
    suspension_start = fields.Date(string='Inicio de la suspensión', readonly=True, copy=False)
    suspension_end = fields.Date(string='Fin de la suspensión', readonly=True, copy=False)
    suspension_days = fields.Integer(string='Días hábiles suspendidos', readonly=True, copy=False)
    days_left = fields.Integer(string='Días hábiles restantes', compute='_compute_days_left')
    is_overdue = fields.Boolean(string='Vencida', compute='_compute_is_overdue',
                                search='_search_is_overdue')
    alert_sent = fields.Boolean(readonly=True, copy=False)
    overdue_alert_sent = fields.Boolean(readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Solución acordada (art. 6-A)
    # ------------------------------------------------------------------
    settlement_offer = fields.Text(string='Oferta de solución', readonly=True, copy=False)
    settlement_mode = fields.Selection(
        selection=[('in_person', 'Presencial'), ('remote', 'A distancia')],
        string='Modalidad de la oferta', readonly=True, copy=False)
    settlement_offer_date = fields.Date(string='Fecha de la oferta', readonly=True, copy=False)
    settlement_acceptance_date = fields.Date(string='Fecha de aceptación', readonly=True, copy=False)
    settlement_fulfilled = fields.Boolean(string='Solución cumplida', tracking=True, copy=False)

    # ------------------------------------------------------------------
    # Constancia, conservación y SIREC
    # ------------------------------------------------------------------
    ack_sent_date = fields.Datetime(string='Constancia enviada', readonly=True, copy=False)
    retention_until = fields.Date(string='Conservar hasta', compute='_compute_retention_until',
                                  store=True)
    sirec_state = fields.Selection(
        selection=[('pending', 'Pendiente'), ('reported', 'Reportada')],
        string='SIREC', default='pending', copy=False, tracking=True)
    sirec_report_date = fields.Date(string='Reportada al SIREC', readonly=True, copy=False)

    _name_book_uniq = models.Constraint(
        'unique (book_id, name)', 'El número de hoja ya existe en este libro.')

    # ------------------------------------------------------------------
    # Cómputos
    # ------------------------------------------------------------------
    @api.depends('date_submitted')
    def _compute_retention_until(self):
        for complaint in self:
            complaint.retention_until = complaint.date_submitted and (
                complaint.date_submitted.date() + relativedelta(years=RETENTION_YEARS))

    @api.depends('date_submitted', 'suspension_days', 'company_id')
    def _compute_deadline_date(self):
        for complaint in self:
            if not complaint.date_submitted:
                complaint.deadline_date = False
                continue
            start = complaint._local_date(complaint.date_submitted)
            complaint.deadline_date = complaint.company_id._l10n_pe_complaint_add_business_days(
                start, RESPONSE_BUSINESS_DAYS + complaint.suspension_days)

    @api.depends('deadline_date', 'state')
    def _compute_days_left(self):
        today = fields.Date.context_today(self)
        for complaint in self:
            if complaint.state in CLOSED_STATES or not complaint.deadline_date:
                complaint.days_left = 0
            elif complaint.deadline_date >= today:
                complaint.days_left = complaint.company_id._l10n_pe_complaint_business_days_between(
                    today, complaint.deadline_date)
            else:
                complaint.days_left = -complaint.company_id._l10n_pe_complaint_business_days_between(
                    complaint.deadline_date, today)

    @api.depends('deadline_date', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for complaint in self:
            complaint.is_overdue = bool(
                complaint.state not in CLOSED_STATES and complaint.state != 'suspended'
                and complaint.deadline_date and complaint.deadline_date < today)

    def _search_is_overdue(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise UserError(_('Búsqueda no admitida.'))
        domain = [('state', 'not in', CLOSED_STATES + ('suspended',)),
                  ('deadline_date', '<', fields.Date.context_today(self))]
        return domain if (operator == '=') == value else ['!', *domain]

    def _report_tz(self):
        """Zona horaria de la hoja: la de la compañía (Lima por defecto), no la del usuario."""
        return self.company_id.partner_id.tz or 'America/Lima'

    @api.model
    def _local_date_for(self, value, company):
        tz = pytz.timezone(company.partner_id.tz or 'America/Lima')
        return pytz.utc.localize(value).astimezone(tz).date()

    def _local_date(self, value):
        """Fecha local de un datetime UTC."""
        return self._local_date_for(value, self.company_id)

    def _local_datetime(self):
        """Fecha y hora local de presentación (constancia, art. 4-B)."""
        self.ensure_one()
        tz = pytz.timezone(self._report_tz())
        return pytz.utc.localize(self.date_submitted).astimezone(tz)

    def _compute_access_url(self):
        super()._compute_access_url()
        for complaint in self:
            complaint.access_url = '/libro-reclamaciones/hoja/%s' % complaint.id

    def _compute_display_name(self):
        for complaint in self:
            complaint.display_name = '%s - %s' % (complaint.name, complaint.consumer_name or '')

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------
    @api.constrains('consumer_name', 'consumer_doc_number', 'consumer_address',
                    'consumer_email', 'detail')
    def _check_minimum_data(self):
        """Sin nombre, documento, domicilio o correo, fecha y detalle, la hoja «se considera
        no presentada» (Reglamento, art. 5)."""
        for complaint in self:
            missing = []
            if not (complaint.consumer_name or '').strip():
                missing.append(_('nombre'))
            if not (complaint.consumer_doc_number or '').strip():
                missing.append(_('documento de identidad'))
            if not ((complaint.consumer_address or '').strip() or complaint.consumer_email):
                missing.append(_('domicilio o correo electrónico'))
            if not (complaint.detail or '').strip():
                missing.append(_('detalle'))
            if missing:
                raise ValidationError(_('Falta: %s.', ', '.join(missing)))

    @api.constrains('consumer_doc_type', 'consumer_doc_number')
    def _check_document(self):
        for complaint in self:
            number = (complaint.consumer_doc_number or '').strip()
            if complaint.consumer_doc_type == 'dni' and not (len(number) == 8 and number.isdigit()):
                raise ValidationError(_('El DNI debe tener 8 dígitos.'))
            if complaint.consumer_doc_type == 'ruc' and not (len(number) == 11 and number.isdigit()):
                raise ValidationError(_('El RUC debe tener 11 dígitos.'))

    @api.constrains('consumer_email', 'guardian_email')
    def _check_emails(self):
        for complaint in self:
            for email in (complaint.consumer_email, complaint.guardian_email):
                if email and not email_normalize(email):
                    raise ValidationError(_('El correo %s no es válido.', email))

    @api.constrains('is_minor', 'guardian_name')
    def _check_guardian(self):
        for complaint in self:
            if complaint.is_minor and not (complaint.guardian_name or '').strip():
                raise ValidationError(_('Indique el padre, la madre o el representante del menor.'))

    @api.constrains('preferred_response_channel', 'consumer_email', 'consumer_address')
    def _check_response_channel(self):
        for complaint in self:
            if complaint.preferred_response_channel == 'email' and not complaint.consumer_email:
                raise ValidationError(_('Para responder por correo, indique el correo del consumidor.'))
            if complaint.preferred_response_channel == 'letter' and not complaint.consumer_address:
                raise ValidationError(_('Para responder por carta, indique el domicilio.'))

    # ------------------------------------------------------------------
    # Creación: número correlativo y constancia
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('original_claim_type', vals.get('claim_type', 'claim'))
            book = self.env['l10n_pe.complaint.book'].browse(vals.get('book_id'))
            if book:
                vals['company_id'] = book.company_id.id
                if vals.get('name', '/') == '/':
                    # Antes de insertar: con la secuencia «no_gap», si la hoja no
                    # pasa las validaciones la transacción revierte también el número.
                    submitted = fields.Datetime.to_datetime(vals.get('date_submitted')) \
                        or fields.Datetime.now()
                    vals['name'] = book._next_number(self._local_date_for(submitted, book.company_id))
        complaints = super().create(vals_list)
        for complaint in complaints:
            if not complaint.responsible_user_id and complaint.book_id.user_ids:
                complaint.responsible_user_id = complaint.book_id.user_ids[:1]
        complaints._notify_registration()
        return complaints

    def write(self, vals):
        protected = {'name', 'book_id', 'date_submitted', 'consumer_name', 'consumer_doc_type',
                     'consumer_doc_number', 'detail', 'consumer_request', 'good_type',
                     'amount_claimed', 'good_description'}
        if protected & set(vals) and not self.env.context.get('l10n_pe_complaint_force') \
                and not self.env.su and any(c.state != 'submitted' for c in self):
            raise UserError(_('Lo que el consumidor registró no se modifica una vez en atención: '
                              'deje constancia en las observaciones.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_retention(self):
        """Conservación mínima de 2 años (art. 12)."""
        today = fields.Date.context_today(self)
        for complaint in self:
            if complaint.retention_until and complaint.retention_until > today:
                raise UserError(_(
                    'La hoja %(name)s debe conservarse hasta el %(date)s (Reglamento, art. 12).',
                    name=complaint.name, date=complaint.retention_until))

    def _notify_registration(self):
        """Constancia al consumidor (art. 4-B) y aviso al equipo de atención."""
        ack = self.env.ref('al_l10n_pe_complaints_book.mail_template_complaint_ack',
                           raise_if_not_found=False)
        internal = self.env.ref('al_l10n_pe_complaints_book.mail_template_complaint_internal',
                                raise_if_not_found=False)
        for complaint in self:
            partners = complaint.book_id.user_ids.partner_id
            if partners:
                complaint.message_subscribe(partner_ids=partners.ids)
            if complaint.consumer_email and ack:
                complaint._send_with_sheet(ack)
                complaint.ack_sent_date = fields.Datetime.now()
            if internal and (partners or complaint.book_id.notify_email):
                internal.send_mail(complaint.id, email_values={
                    'recipient_ids': [(6, 0, partners.ids)],
                    'email_to': complaint.book_id.notify_email or False,
                })

    def _send_with_sheet(self, template):
        """Envía ``template`` con la hoja de reclamación en PDF adjunta."""
        self.ensure_one()
        report = self.env.ref('al_l10n_pe_complaints_book.action_report_complaint')
        # sudo: el formulario público genera la constancia sin permisos internos.
        pdf, dummy = self.env['ir.actions.report'].sudo().with_context(
            tz=self._report_tz())._render_qweb_pdf(report, self.ids)
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'Hoja de reclamación %s.pdf' % self.name,
            'raw': pdf,
            'mimetype': 'application/pdf',
            'res_model': self._name,
            'res_id': self.id,
        })
        template.send_mail(self.id, force_send=False, email_values={
            'attachment_ids': [(4, attachment.id)],
        })
        return attachment

    # ------------------------------------------------------------------
    # Atención y respuesta
    # ------------------------------------------------------------------
    def action_start(self):
        self.filtered(lambda c: c.state == 'submitted').write({'state': 'in_progress'})
        for complaint in self.filtered(lambda c: not c.responsible_user_id):
            complaint.responsible_user_id = self.env.user
        return True

    def action_reclassify_as_claim(self):
        """Una queja cuyo detalle es un reclamo se tramita como reclamo (art. 6)."""
        for complaint in self:
            if complaint.claim_type != 'complaint':
                raise UserError(_('La hoja %s ya es un reclamo.', complaint.name))
            complaint.with_context(l10n_pe_complaint_force=True).claim_type = 'claim'
            complaint.message_post(body=_(
                'Recalificada de queja a reclamo: el detalle se refiere a los productos o servicios.'))
        return True

    def action_send_response(self):
        """Comunica la respuesta por el medio que pidió el consumidor."""
        template = self.env.ref('al_l10n_pe_complaints_book.mail_template_complaint_response')
        for complaint in self:
            if complaint.state in CLOSED_STATES:
                raise UserError(_('La hoja %s ya está respondida o cerrada.', complaint.name))
            if not (complaint.provider_observations or '').strip():
                raise UserError(_('Escriba las observaciones y acciones adoptadas antes de responder.'))
            complaint.write({
                'state': 'answered',
                'response_date': fields.Date.context_today(complaint),
                'response_user_id': self.env.user.id,
            })
            if complaint.preferred_response_channel == 'email':
                complaint._send_with_sheet(template)
            else:
                complaint.message_post(body=_(
                    'Respuesta por carta: imprima la hoja y deje constancia de la entrega.'))
        return True

    def action_close(self):
        for complaint in self:
            if complaint.state not in ('answered', 'settled'):
                raise UserError(_('Solo se cierra una hoja respondida o con solución aceptada.'))
        self.write({'state': 'closed'})
        return True

    def action_reopen(self):
        self.filtered(lambda c: c.state == 'closed').write({'state': 'in_progress'})
        return True

    def action_print(self):
        return self.env.ref('al_l10n_pe_complaints_book.action_report_complaint').report_action(self)

    def action_open_settlement(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Oferta de solución'),
            'res_model': 'l10n_pe.complaint.settlement.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_complaint_id': self.id},
        }

    # ------------------------------------------------------------------
    # Solución acordada (art. 6-A)
    # ------------------------------------------------------------------
    def _register_settlement_offer(self, offer, mode, accepted=False):
        self.ensure_one()
        if self.state in CLOSED_STATES:
            raise UserError(_('La hoja %s ya está respondida o cerrada.', self.name))
        today = fields.Date.context_today(self)
        vals = {'settlement_offer': offer, 'settlement_mode': mode, 'settlement_offer_date': today}
        if mode == 'in_person':
            # La oferta presencial se anota en la sección 4 y el consumidor la firma.
            if not accepted:
                raise UserError(_('Una oferta presencial se registra cuando el consumidor la acepta '
                                  'firmando la hoja.'))
            vals.update(state='settled', settlement_acceptance_date=today)
        else:
            vals.update(state='suspended', suspension_start=today, suspension_end=False)
        self.write(vals)
        self.message_post(body=_('Oferta de solución (%(mode)s): %(offer)s',
                                 mode=dict(self._fields['settlement_mode'].selection)[mode],
                                 offer=offer))

    def action_settlement_accepted(self):
        """El consumidor aceptó la oferta a distancia: el reclamo concluye (art. 6-A.3)."""
        for complaint in self.filtered(lambda c: c.state == 'suspended'):
            complaint.write({'state': 'settled',
                             'settlement_acceptance_date': fields.Date.context_today(complaint),
                             'suspension_end': fields.Date.context_today(complaint)})
            complaint.message_post(body=_('Solución aceptada: «%s».', SETTLEMENT_PHRASE))
        return True

    def action_settlement_rejected(self):
        """Oferta rechazada o sin aceptación expresa: se reanuda el plazo (art. 6-A.2.b)."""
        for complaint in self.filtered(lambda c: c.state == 'suspended'):
            complaint._end_suspension()
            complaint.message_post(body=_('Oferta no aceptada: se reanuda el plazo de respuesta.'))
        return True

    def _end_suspension(self, end_date=None):
        """Cierra la suspensión: cuenta como mucho 5 días hábiles."""
        self.ensure_one()
        end_date = end_date or fields.Date.context_today(self)
        days = self.company_id._l10n_pe_complaint_business_days_between(
            self.suspension_start, end_date)
        self.write({'state': 'in_progress', 'suspension_end': end_date,
                    'suspension_days': min(days, MAX_SUSPENSION_DAYS)})

    # ------------------------------------------------------------------
    # Alertas de plazo
    # ------------------------------------------------------------------
    @api.model
    def _cron_deadline_alerts(self):
        """Reanuda suspensiones vencidas y avisa de plazos por vencer y vencidos."""
        today = fields.Date.context_today(self)
        for complaint in self.search([('state', '=', 'suspended')]):
            limit = complaint.company_id._l10n_pe_complaint_add_business_days(
                complaint.suspension_start, MAX_SUSPENSION_DAYS)
            if limit < today:
                complaint._end_suspension(limit)
                complaint.message_post(body=_(
                    'Pasaron 5 días hábiles sin aceptación expresa: la oferta se entiende '
                    'rechazada y se reanuda el plazo.'))
        open_complaints = self.search([('state', 'in', ('submitted', 'in_progress'))])
        for complaint in open_complaints:
            user = complaint.responsible_user_id or complaint.book_id.user_ids[:1]
            alert_days = complaint.company_id.l10n_pe_complaint_alert_days
            if complaint.is_overdue and not complaint.overdue_alert_sent:
                complaint.activity_schedule(
                    'mail.mail_activity_data_warning', user_id=(user or self.env.user).id,
                    summary=_('Hoja de reclamación vencida'),
                    note=_('Venció el %s: responda cuanto antes.', complaint.deadline_date))
                complaint.overdue_alert_sent = True
            elif not complaint.alert_sent and 0 <= complaint.days_left <= alert_days:
                complaint.activity_schedule(
                    'mail.mail_activity_data_todo', date_deadline=complaint.deadline_date,
                    user_id=(user or self.env.user).id,
                    summary=_('Responder la hoja de reclamación'),
                    note=_('Quedan %s días hábiles.', complaint.days_left))
                complaint.alert_sent = True

    # ------------------------------------------------------------------
    # SIREC
    # ------------------------------------------------------------------
    @staticmethod
    def _sirec_text(value, size):
        text = ' '.join(str(value or '').replace('|', ' ').split())
        return text[:size]

    def _sirec_row(self):
        """Registro del archivo de carga masiva del SIREC (manual, sección H)."""
        self.ensure_one()
        number, dummy, year = (self.name or '').partition('-')
        address = self.consumer_address or self.consumer_email or ''
        response = self.provider_observations or self.settlement_offer or ''
        return [
            self._sirec_text(self.book_id.sirec_site_code, 6),
            number[-9:],
            year or str(self.date_submitted.year),
            self._local_date(self.date_submitted).strftime('%Y-%m-%d'),
            self._sirec_text(self.consumer_name, 150),
            self._sirec_text(address, 150),
            self._sirec_text(self.consumer_doc_number, 11),
            self._sirec_text(self.consumer_phone, 50),
            self._sirec_text(self.consumer_email, 80),
            self._sirec_text(self.guardian_name if self.is_minor else '', 150),
            {'product': 'P', 'service': 'S', 'both': 'PS'}[self.good_type],
            self._sirec_text('%.2f %s' % (self.amount_claimed, self.currency_id.name)
                             if self.amount_claimed else '', 100),
            self._sirec_text(self.good_description, 4000),
            'R' if self.claim_type == 'claim' else 'Q',
            self._sirec_text(self.detail, 4000),
            self._sirec_text(self.consumer_request, 4000),
            self.response_date.strftime('%Y-%m-%d') if self.response_date else '',
            self._sirec_text(response if self.response_date or self.state == 'settled' else '', 4000),
        ]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_complaint_calendar_id = fields.Many2one(
        'resource.calendar', string='Calendario de feriados (reclamos)',
        help='Días hábiles son de lunes a viernes; de este calendario se toman los feriados '
             '(ausencias globales) para contar los 15 días hábiles de respuesta.')
    l10n_pe_complaint_alert_days = fields.Integer(
        string='Avisar cuando queden (días hábiles)', default=5)
    l10n_pe_complaint_sirec = fields.Boolean(
        string='Obligada al SIREC',
        help='Ingresos anuales de 3 000 UIT o más (Reglamento, art. 16).')

    def _get_company_root_delegated_field_names(self):
        # La obligación se mide por los ingresos del RUC: las sucursales usan
        # la de su raíz.
        return super()._get_company_root_delegated_field_names() + [
            'l10n_pe_complaint_sirec',
        ]

    def _l10n_pe_complaint_calendar(self):
        self.ensure_one()
        return self.l10n_pe_complaint_calendar_id or self.resource_calendar_id

    def _l10n_pe_complaint_is_business_day(self, day):
        """Lunes a viernes que no son feriado.

        El horario del calendario no cuenta (en Perú suele incluir el sábado):
        los días hábiles del plazo son de lunes a viernes, y del calendario
        solo se toman las ausencias globales, es decir, los feriados.
        """
        if day.weekday() >= 5:
            return False
        calendar = self._l10n_pe_complaint_calendar()
        if not calendar:
            return True
        tz = pytz.timezone(calendar.tz or 'America/Lima')
        start = tz.localize(datetime.combine(day, time(12))).astimezone(pytz.utc).replace(tzinfo=None)
        return not self.env['resource.calendar.leaves'].sudo().search_count([
            ('calendar_id', 'in', (calendar.id, False)),
            ('resource_id', '=', False),
            ('company_id', 'in', (self.id, False)),
            ('date_from', '<=', start),
            ('date_to', '>=', start),
        ], limit=1)

    def _l10n_pe_complaint_add_business_days(self, start_date, days):
        """Fecha del ``days``-ésimo día hábil contado desde el día siguiente a ``start_date``."""
        self.ensure_one()
        day, found = start_date, 0
        while found < days:
            day += timedelta(days=1)
            if self._l10n_pe_complaint_is_business_day(day):
                found += 1
        return day

    def _l10n_pe_complaint_business_days_between(self, start_date, end_date):
        """Días hábiles en el intervalo (start_date, end_date]."""
        self.ensure_one()
        count, day = 0, start_date
        while day < end_date:
            day += timedelta(days=1)
            if self._l10n_pe_complaint_is_business_day(day):
                count += 1
        return count


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_complaint_calendar_id = fields.Many2one(
        related='company_id.l10n_pe_complaint_calendar_id', readonly=False)
    l10n_pe_complaint_alert_days = fields.Integer(
        related='company_id.l10n_pe_complaint_alert_days', readonly=False)
    l10n_pe_complaint_sirec = fields.Boolean(
        related='company_id.l10n_pe_complaint_sirec', readonly=False)
