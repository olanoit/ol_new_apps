# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.fields import Domain


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def _load_pos_data_domain(self, data, config):
        """Empleados cargados en el TPV.

        Con pos_hr activo: los de pos_hr (quienes pueden iniciar sesión) más
        los vendedores autorizados. Sin pos_hr: SOLO los vendedores
        autorizados (el dominio de pos_hr traería a todos los empleados de
        la compañía)."""
        domain = super()._load_pos_data_domain(data, config)
        sellers = config.seller_ids if config.authorized_seller else self.browse()
        seller_domain = Domain.AND([
            Domain('id', 'in', sellers.ids),
            self._check_company_domain(config.company_id),
        ])
        if not config.module_pos_hr:
            return seller_domain
        if sellers:
            return Domain.OR([domain, seller_domain])
        return domain

    @api.model
    def _load_pos_data_read(self, records, config):
        """Los vendedores que no pueden iniciar sesión en la caja llegan al
        frontend sin PIN ni código de barras (su hash SHA1 es reversible) y
        con rol mínimo; el frontend les impide iniciar sesión."""
        if config.module_pos_hr:
            login_domain = config._employee_domain(config.current_user_id.id)
            login_employees = records.filtered_domain(login_domain)
        else:
            login_employees = self.browse()
        seller_only = records - login_employees
        result = super()._load_pos_data_read(login_employees, config) if login_employees else []
        if seller_only:
            fields = self._load_pos_data_fields(config)
            for vals in seller_only.read(fields, load=False):
                vals.update({'_role': 'minimal', '_al_seller_only': True})
                result.append(vals)
        return result
