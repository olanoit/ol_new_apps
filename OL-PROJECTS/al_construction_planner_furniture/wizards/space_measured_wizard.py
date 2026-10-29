# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import fields, models


class ConstructionSpaceMeasuredWizard(models.TransientModel):
    _name = 'construction.space.measured.wizard'
    _description = 'Marcar ambientes como medidos'

    task_ids = fields.Many2many(
        'project.task', string='Ambientes', required=True,
        domain=[('construction_level', '=', 'space')])
    date = fields.Date(
        string='Fecha de medición', required=True, default=fields.Date.context_today)
    file = fields.Binary(string='Archivo', required=True, attachment=False)
    file_name = fields.Char(string='Nombre del archivo')
    note = fields.Char(string='Nota')

    def action_confirm(self):
        self.ensure_one()
        tasks = self.task_ids.filtered(lambda t: t.construction_level == 'space')
        tasks._construction_check_supervisor()
        tasks.check_access('read')
        # El supervisor ve el ambiente pero puede no editar la tarea (la
        # regla de Proyectos): solo se escriben la marca, la fecha y el
        # archivo de la medición.
        for task in tasks.sudo():
            attachment = self.env['ir.attachment'].create({
                'name': self.file_name or self.env._('Medición %s', task.display_name),
                'raw': self.file,
                'res_model': 'project.task',
                'res_id': task.id,
            })
            task.write({
                'construction_measured': True,
                'construction_measured_date': self.date,
                'construction_measured_user_id': self.env.user.id,
                'construction_measured_attachment_ids': [fields.Command.link(attachment.id)],
            })
            body = self.env._('Medido el %s.', fields.Date.to_string(self.date))
            if self.note:
                body = Markup('%s<br/>%s') % (body, self.note)
            task.message_post(body=body, attachment_ids=attachment.ids)
        return {'type': 'ir.actions.act_window_close'}
