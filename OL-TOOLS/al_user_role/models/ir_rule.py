# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import AccessError
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval


class IrRule(models.Model):
    _inherit = 'ir.rule'

    def _compute_domain(self, model_name, mode='read'):
        """Aplica a los registros las restricciones de los roles del usuario.

        - Solo lectura (del modelo o "Todo en solo lectura"): ningún registro
          para crear, modificar o borrar. Es real: vale también para botones,
          importación y API, no solo para las vistas.
        - Dominio de registros: se agrega (AND) a las reglas. Aplica solo si
          todos los roles vigentes del usuario tienen dominio para el modelo; los
          dominios de los roles se unen con OR (los roles suman acceso).

        Las restricciones van en caché por grupos, y la caché de
        ``_compute_domain`` se limpia al cambiar grupos o restricciones.
        """
        domain = super()._compute_domain(model_name, mode=mode)
        Role = self.env['al.user.role']
        if mode != 'read' and Role._al_is_readonly_model(model_name):
            return Domain.FALSE
        restrictions = Role._al_ui_restrictions()
        role_domains = restrictions.get('domains', {}).get(model_name) if restrictions else None
        if not role_domains:
            return domain
        eval_context = self._eval_context()
        role_domain = Domain.OR(Domain(safe_eval(d, eval_context)) for d in role_domains)
        return (domain & role_domain).optimize(self.env[model_name])

    def _make_access_error(self, operation, records):
        """Mensaje claro cuando lo que bloquea es la solo lectura del rol."""
        if operation != 'read' and self.env['al.user.role']._al_is_readonly_model(records._name):
            description = self.env['ir.model']._get(records._name).name or records._name
            return AccessError(self.env._(
                'Su rol solo permite consultar "%(model)s": no puede crear, modificar ni '
                'borrar estos registros.', model=description,
            ))
        return super()._make_access_error(operation, records)
