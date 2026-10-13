# -*- coding: utf-8 -*-
"""Factura negociable (Ley 29623, modificada por el DU 013-2020): la
conformidad del adquirente, la anotación en cuenta en CAVALI y el historial de
eventos del título valor viven en la factura, con o sin operación de
factoring.

Orden de los eventos (como en el registro de CAVALI):

* Conformidad (expresa o presunta a los 8 días) o disconformidad.
* Anotación en cuenta: requiere factura al crédito y sin disconformidad.
* Transferencia al factor: requiere la anotación y la conformidad.
* Prórroga del vencimiento, pago, protesto o recompra: requieren la
  anotación; el pago y el protesto cierran el título.
"""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

#: DU 013-2020 (art. 7): el adquirente tiene 8 días calendario para dar su
#: conformidad; si no la objeta, se presume conforme sin prueba en contrario.
CONFORMITY_DAYS = 8
CONFORMITY_STATES = [
    ('pending', 'Pendiente'),
    ('accepted', 'Conforme (expresa)'),
    ('presumed', 'Conforme (presunta)'),
    ('rejected', 'Disconforme'),
]
NEGOTIABLE_STATES = [
    ('none', 'Sin anotar'),
    ('registered', 'Anotada en CAVALI'),
    ('transferred', 'Transferida'),
    ('paid', 'Pagada'),
    ('protested', 'Protestada'),
    ('repurchased', 'Recomprada'),
    ('cancelled', 'Anotación anulada'),
]
EVENT_TYPES = [
    ('accepted', 'Conformidad expresa'),
    ('presumed', 'Conformidad presunta'),
    ('rejected', 'Disconformidad'),
    ('registered', 'Anotación en cuenta'),
    ('transferred', 'Transferencia'),
    ('extended', 'Prórroga del vencimiento'),
    ('paid', 'Pago'),
    ('protested', 'Protesto'),
    ('repurchased', 'Recompra'),
    ('cancelled', 'Anulación de la anotación'),
    ('notified', 'Notificación al adquirente'),
    ('reverted', 'Reversión de la transferencia'),
]
#: Estado de la factura negociable que deja cada evento (los demás no lo cambian).
EVENT_STATE = {
    'registered': 'registered',
    'transferred': 'transferred',
    'paid': 'paid',
    'protested': 'protested',
    'repurchased': 'repurchased',
    'cancelled': 'cancelled',
    'reverted': 'registered',
}
#: Estados de la factura negociable desde los que se admite cada evento.
EVENT_ALLOWED_FROM = {
    'registered': ('none', 'cancelled'),
    'transferred': ('registered', 'transferred'),
    'extended': ('registered', 'transferred'),
    'paid': ('registered', 'transferred'),
    'protested': ('registered', 'transferred'),
    'repurchased': ('transferred', 'protested'),
    'cancelled': ('registered',),
    'reverted': ('transferred',),
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_conformity_state = fields.Selection(
        CONFORMITY_STATES, string='Conformidad', default='pending', copy=False, tracking=True,
        help='Conformidad del cliente con la factura (DU 013-2020, art. 7): expresa, presunta a '
             'los 8 días calendario sin objeción, o disconformidad (impide anotarla y cederla).')
    l10n_pe_conformity_date = fields.Date(string='Fecha de conformidad', copy=False)
    l10n_pe_presumed_conformity_date = fields.Date(
        string='Conformidad presunta', compute='_compute_l10n_pe_presumed_conformity_date', store=True,
        help='8 días calendario desde la emisión de la factura (la norma los cuenta desde que se '
             'pone a disposición del cliente y de SUNAT, hasta 2 días después).')
    l10n_pe_negotiable_state = fields.Selection(
        NEGOTIABLE_STATES, string='Factura negociable', default='none', copy=False, tracking=True,
        help='Situación del título valor en CAVALI según sus eventos.')
    l10n_pe_cavali_number = fields.Char(
        string='Anotación CAVALI', copy=False, tracking=True,
        help='Código de la anotación en cuenta de la factura negociable en CAVALI.')
    l10n_pe_cavali_date = fields.Date(
        string='Fecha de anotación', copy=False,
        help='Desde la anotación en cuenta la factura negociable se puede transferir.')
    l10n_pe_negotiable_holder_id = fields.Many2one(
        'res.partner', string='Tenedor', copy=False,
        help='Quien tiene hoy el derecho de cobro: la empresa o el factor al que se transfirió.')
    l10n_pe_negotiable_due_date = fields.Date(
        string='Fecha de pago', copy=False,
        help='Fecha de vencimiento de la factura negociable (cambia con las prórrogas).')
    l10n_pe_negotiable_event_ids = fields.One2many(
        'l10n_pe.negotiable.event', 'move_id', string='Eventos de la factura negociable', readonly=True)
    l10n_pe_is_credit = fields.Boolean(
        string='Al crédito', compute='_compute_l10n_pe_is_credit',
        help='La factura tiene plazo de pago: la factura negociable nace de una venta al crédito.')

    @api.depends('invoice_date')
    def _compute_l10n_pe_presumed_conformity_date(self):
        for move in self:
            move.l10n_pe_presumed_conformity_date = (
                move.invoice_date + timedelta(days=CONFORMITY_DAYS) if move.invoice_date else False)

    @api.depends('invoice_date', 'invoice_date_due')
    def _compute_l10n_pe_is_credit(self):
        for move in self:
            move.l10n_pe_is_credit = bool(move.invoice_date_due and move.invoice_date
                                          and move.invoice_date_due > move.invoice_date)

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------
    def _l10n_pe_check_negotiable_event(self, event_type):
        """Errores que impiden registrar el evento (todos juntos)."""
        self.ensure_one()
        errors = []
        if self.move_type != 'out_invoice' or self.state != 'posted':
            errors.append(self.env._('%s no es una factura de cliente publicada.', self.display_name))
            return errors
        state = self.l10n_pe_negotiable_state or 'none'
        allowed = EVENT_ALLOWED_FROM.get(event_type)
        if allowed and state not in allowed:
            errors.append(self.env._(
                '%(invoice)s está «%(state)s»: no admite «%(event)s».', invoice=self.name,
                state=dict(NEGOTIABLE_STATES)[state], event=dict(EVENT_TYPES)[event_type]))
        if event_type in ('accepted', 'presumed', 'rejected') and state not in ('none', 'registered'):
            errors.append(self.env._('La conformidad de %s ya no se puede cambiar.', self.name))
        if event_type == 'registered':
            if not self.l10n_pe_is_credit:
                errors.append(self.env._(
                    '%s es al contado: la factura negociable nace de una venta al crédito.', self.name))
            if self.l10n_pe_conformity_state == 'rejected':
                errors.append(self.env._('El cliente dio su disconformidad con %s.', self.name))
        if event_type == 'transferred' and self.l10n_pe_conformity_state not in ('accepted', 'presumed'):
            errors.append(self.env._(
                '%s no tiene la conformidad del cliente (expresa o presunta): no se puede transferir.',
                self.name))
        return errors

    def _l10n_pe_add_negotiable_event(self, event_type, date=None, reference=False, partner=False,
                                      note=False, source='manual', amount=0.0, due_date=False):
        """Registra el evento y actualiza la factura negociable. Valida el
        orden (``_l10n_pe_check_negotiable_event``)."""
        Event = self.env['l10n_pe.negotiable.event']
        events = Event
        for move in self:
            errors = move._l10n_pe_check_negotiable_event(event_type)
            if errors:
                raise UserError('\n'.join(errors))
            date = date or fields.Date.context_today(move)
            vals = {}
            if event_type in ('accepted', 'presumed', 'rejected'):
                vals.update(l10n_pe_conformity_state=event_type, l10n_pe_conformity_date=date)
            if event_type in EVENT_STATE:
                vals['l10n_pe_negotiable_state'] = EVENT_STATE[event_type]
            if event_type == 'registered':
                vals.update(l10n_pe_cavali_number=reference or move.l10n_pe_cavali_number,
                            l10n_pe_cavali_date=date,
                            l10n_pe_negotiable_holder_id=move.company_id.partner_id.id,
                            l10n_pe_negotiable_due_date=move.l10n_pe_negotiable_due_date
                            or move.invoice_date_due)
            if event_type == 'transferred' and partner:
                vals['l10n_pe_negotiable_holder_id'] = partner.id
            if event_type in ('repurchased', 'reverted'):
                vals['l10n_pe_negotiable_holder_id'] = move.company_id.partner_id.id
            if event_type == 'extended' and due_date:
                vals['l10n_pe_negotiable_due_date'] = due_date
            if vals:
                move.write(vals)
            events |= Event.create({
                'move_id': move.id, 'event_type': event_type, 'date': date, 'reference': reference,
                'partner_id': partner.id if partner else False, 'note': note, 'source': source,
                'amount': amount, 'due_date': due_date,
            })
        return events

    def action_l10n_pe_negotiable_event(self):
        """Asistente para registrar a mano un evento de la factura negociable."""
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Evento de la factura negociable'),
            'res_model': 'l10n_pe.negotiable.event.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_ids': self.ids},
        }

    @api.model
    def _cron_l10n_pe_presumed_conformity(self):
        """Pasa a conformidad presunta las facturas al crédito cuyo plazo de 8
        días venció sin objeción, y avisa (actividad) de las que vencen en los
        próximos 2 días."""
        today = fields.Date.context_today(self)
        domain = [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                  ('l10n_pe_conformity_state', '=', 'pending'),
                  ('invoice_date_due', '!=', False), ('company_id.account_fiscal_country_id.code', '=', 'PE')]
        due = self.search(domain + [('l10n_pe_presumed_conformity_date', '<=', today)])
        for move in due.filtered('l10n_pe_is_credit'):
            move._l10n_pe_add_negotiable_event(
                'presumed', date=move.l10n_pe_presumed_conformity_date, source='cron',
                note=self.env._('8 días calendario sin disconformidad del cliente.'))
        soon = self.search(domain + [('l10n_pe_presumed_conformity_date', '>', today),
                                     ('l10n_pe_presumed_conformity_date', '<=', today + timedelta(days=2))])
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for move in soon.filtered('l10n_pe_is_credit'):
            if activity_type and not move.activity_ids.filtered(
                    lambda a: a.activity_type_id == activity_type and 'conformidad' in (a.summary or '')):
                move.activity_schedule(
                    activity_type_id=activity_type.id,
                    date_deadline=move.l10n_pe_presumed_conformity_date,
                    summary=self.env._('Plazo de conformidad del cliente'),
                    note=self.env._('Si el cliente no objeta la factura hasta el %s, queda conforme '
                                    '(presunta) y se puede anotar en CAVALI y ceder.',
                                    move.l10n_pe_presumed_conformity_date),
                    user_id=move.invoice_user_id.id or self.env.uid)
        return len(due)


class L10nPeNegotiableEvent(models.Model):
    _name = 'l10n_pe.negotiable.event'
    _description = 'Evento de la factura negociable'
    _order = 'date desc, id desc'
    _check_company_auto = True

    move_id = fields.Many2one('account.move', string='Factura', required=True, ondelete='cascade',
                              index=True, check_company=True)
    company_id = fields.Many2one(related='move_id.company_id', store=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Contraparte',
                                 help='Factor al que se transfiere o quien paga.')
    event_type = fields.Selection(EVENT_TYPES, string='Evento', required=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    reference = fields.Char(string='Referencia', help='Código de CAVALI o número de la constancia.')
    amount = fields.Monetary(string='Importe', currency_field='currency_id')
    currency_id = fields.Many2one(related='move_id.currency_id')
    due_date = fields.Date(string='Nueva fecha de pago')
    source = fields.Selection(
        [('manual', 'Manual'), ('cavali', 'CAVALI'), ('factoring', 'Operación de factoring'),
         ('cron', 'Automático')], string='Origen', required=True, default='manual')
    note = fields.Text(string='Nota')
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user,
                              readonly=True)


class L10nPeNegotiableEventWizard(models.TransientModel):
    _name = 'l10n_pe.negotiable.event.wizard'
    _description = 'Registrar un evento de la factura negociable'

    move_ids = fields.Many2many('account.move', string='Facturas', required=True)
    event_type = fields.Selection(
        [t for t in EVENT_TYPES if t[0] not in ('notified', 'reverted')], string='Evento', required=True,
        default='accepted')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    reference = fields.Char(string='Referencia')
    partner_id = fields.Many2one('res.partner', string='Factor')
    due_date = fields.Date(string='Nueva fecha de pago')
    note = fields.Text(string='Nota')

    def action_apply(self):
        self.ensure_one()
        if self.event_type == 'extended' and not self.due_date:
            raise UserError(self.env._('Indique la nueva fecha de pago.'))
        errors = [error for move in self.move_ids
                  for error in move._l10n_pe_check_negotiable_event(self.event_type)]
        if errors:
            raise UserError('\n'.join(errors))
        self.move_ids._l10n_pe_add_negotiable_event(
            self.event_type, date=self.date, reference=self.reference, partner=self.partner_id,
            note=self.note, due_date=self.due_date)
        return {'type': 'ir.actions.act_window_close'}
