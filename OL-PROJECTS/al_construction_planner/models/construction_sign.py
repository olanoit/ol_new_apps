# -*- coding: utf-8 -*-
"""Casillas de firma de los documentos impresos de la vertical (requerimiento
CREVAL v1.0, 3.12): Elaboró, una casilla por cada nivel de aprobación del
documento y, en los que van al contratista, su conformidad. Las casillas de
aprobación salen del registro de aprobación que el documento ya tiene (las
revisiones de la validación por niveles); el cargo, del puesto del empleado
vinculado al usuario. Un paso que aún no ocurre deja la casilla con el rol y
sin nombre."""
from odoo import api, models
from odoo.tools.misc import format_datetime


class ConstructionSignMixin(models.AbstractModel):
    _name = 'construction.sign.mixin'
    _description = 'Casillas de firma de los documentos de obra'

    @api.model
    def _construction_user_job(self, user):
        """Cargo del usuario: el puesto de su empleado en la compañía del
        documento (vacío sin Empleados o sin empleado)."""
        if not user or 'employee_ids' not in user._fields:
            return ''
        # sudo: el puesto del empleado es público en el documento impreso;
        # quien imprime no siempre lee Empleados.
        employees = user.sudo().employee_ids
        company = self.company_id if 'company_id' in self._fields and len(self) == 1 else None
        employee = employees.filtered(lambda e: e.company_id == company)[:1] if company \
            else employees[:1]
        employee = employee or employees[:1]
        return employee.job_title or employee.job_id.name or ''

    def _construction_sign_box(self, role, user=None, date=None, name=None, job=None):
        return {
            'role': role,
            'name': name if name is not None else (user.name if user else ''),
            'job': job if job is not None else self._construction_user_job(user),
            'date': format_datetime(self.env, date, tz=(user or self.env.user).tz,
                                    dt_format='dd/MM/yyyy HH:mm') if date else '',
        }

    def _construction_review_boxes(self, role=None):
        """Una casilla por nivel de la validación por niveles, en su
        secuencia, con quien aprobó y la fecha."""
        self.ensure_one()
        if 'review_ids' not in self._fields:
            return []
        reviews = self.review_ids.sorted(lambda r: (r.sequence, r.id))
        role = role or self.env._('Aprobó')
        boxes = []
        for index, review in enumerate(reviews, 1):
            label = role if len(reviews) == 1 else '%s · %s' % (role, index)
            if review.status == 'approved':
                boxes.append(self._construction_sign_box(label, review.done_by,
                                                         review.reviewed_date))
            else:
                boxes.append(self._construction_sign_box(label, name='', job=''))
        return boxes

    def _construction_sign_boxes(self):
        """Casillas del documento (gancho de cada modelo)."""
        self.ensure_one()
        return []
