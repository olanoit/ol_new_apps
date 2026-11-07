# -*- coding: utf-8 -*-
"""Servicio del portal para el cambio pedido por el cliente (paquete 6,
CR-53)."""
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError


class ConstructionPortalService(models.AbstractModel):
    _inherit = 'construction.portal.service'

    def _resident_features(self):
        features = super()._resident_features()
        features['change_order'] = True
        return features

    @api.model
    def change_order(self, values):
        """El cambio que pide el cliente en obra: queda en «Borrador» con las
        fotos y la firma, y el contacto del cliente recibe la constancia en
        PDF. El residente no ve montos de venta: los pone el coordinador."""
        submission = self._submission('change_order', values.get('uuid'))
        if submission:
            return {'status': 'done', 'ids': submission.res_ids, 'duplicate': True}
        project, members = self._resident_project(values.get('project_id'))
        description = (values.get('description') or '').strip()
        if not description:
            raise UserError(self.env._('Describa el cambio que pide el cliente.'))
        kind = values.get('kind') or 'additional'
        if kind not in ('additional', 'deductive'):
            raise UserError(self.env._('El cambio es adicional o deductivo.'))
        rep_name = (values.get('rep_name') or '').strip()
        if not rep_name:
            raise UserError(self.env._('Indique quién lo pidió por el cliente.'))
        signature = (values.get('signature') or '').split(',', 1)[-1]
        if not signature:
            raise UserError(self.env._('Falta la firma de quien lo pidió.'))
        task_ids = {int(i) for i in values.get('task_ids') or []}
        tasks = self._lines(project, members).task_id.filtered(lambda t: t.id in task_ids)
        new_item = (values.get('new_item') or '').strip()
        if not tasks and not new_item:
            raise UserError(self.env._('Elija las partidas afectadas o describa la partida nueva.'))
        attachments = self._photos(values.get('photos'), 'construction.change.order',
                                   required=True)
        company = project.company_id or self.env.company
        reason = description
        if rep_name:
            reason = '%s\n%s' % (description, self.env._(
                'Lo pidió en obra: %(name)s%(role)s.', name=rep_name,
                role=(', %s' % values['rep_role'].strip()) if values.get('rep_role') else ''))
        # sudo: el cambio lo registra el residente en su obra; lo valoriza y
        # aprueba el coordinador en el escritorio.
        change = self.env['construction.change.order'].sudo().create({
            'project_id': project.id, 'kind': kind, 'requested_by': 'client',
            'date': self._portal_date(values.get('date'), company), 'reason': reason,
            'construction_portal_user_id': self.env.uid,
            'construction_client_rep_name': rep_name,
            'construction_client_rep_role': (values.get('rep_role') or '').strip() or False,
            'construction_client_signature': signature,
            'construction_portal_task_ids': [(6, 0, tasks.ids)],
            'construction_portal_new_item': new_item or False,
            'construction_portal_qty_estimate': (values.get('qty_estimate') or '').strip()
            or False,
            'construction_portal_attachment_ids': [(6, 0, attachments.ids)],
        })
        attachments.write({'res_id': change.id})
        author = self.env.user.partner_id
        change.message_post(body=self.env._('Registrado en obra por el residente desde el '
                                            'portal.'), author_id=author.id)
        contact = project.construction_client_contact_id
        if contact:
            pdf, _type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'al_construction_portal_sale.action_report_change_record', change.ids)
            change.message_post(
                body=Markup('<p>%s</p>') % self.env._(
                    'Constancia del cambio que pidió %s en obra.', rep_name),
                subject=self.env._('Constancia de cambio en obra · %(project)s · %(name)s',
                                   project=project.display_name, name=change.name),
                author_id=author.id, partner_ids=contact.ids,
                # Se crea con el mensaje: un usuario de portal no adjunta
                # archivos que no vengan del redactor.
                attachments=[(('Constancia %s.pdf' % change.name).replace('/', '-'), pdf)],
                message_type='comment', subtype_xmlid='mail.mt_comment')
            change.construction_record_sent_to_id = contact
        self._portal_register('change_order', values['uuid'], change)
        return {'status': 'done', 'ids': str(change.id), 'name': change.name,
                'sent_to': contact.display_name or ''}
