# -*- coding: utf-8 -*-
"""Paquetes de industria.

Cada módulo ``al_industry_<rubro>`` instala las aplicaciones del rubro (sus
dependencias) y deja un registro ``al.industry`` con lo que se configura por
compañía: la actividad económica principal (CIIU) del RUC y, si el rubro usa
el planificador de obra, su perfil de vertical. Al instalarse lo aplica a la
compañía activa; las demás compañías se configuran con el botón «Aplicar a la
compañía activa». Aplicar solo completa lo que falta: no pisa lo que la
compañía ya tiene.
"""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class AlIndustry(models.Model):
    _name = 'al.industry'
    _description = 'Paquete de industria'
    _order = 'sequence, name'

    # Catálogo global (como los perfiles de vertical): sin company_id, lo que
    # es de cada compañía queda en company_ids y en la propia compañía.
    name = fields.Char(string='Industria', required=True, translate=True)
    code = fields.Char(string='Código', required=True)
    sequence = fields.Integer(default=10)
    module_id = fields.Many2one('ir.module.module', string='Módulo', readonly=True,
                                ondelete='cascade')
    description = fields.Text(string='Para quién es', translate=True)
    ciiu_code = fields.Char(
        string='CIIU', help='Clase CIIU Rev. 4 (4 dígitos) que se pone como actividad '
                            'económica principal de la compañía si no tiene una.')
    planner_profile_xmlid = fields.Char(
        string='Perfil del planificador',
        help='Identificador externo del perfil de vertical del planificador de obra que se '
             'aplica a la compañía (vacío: el rubro no usa el planificador).')
    company_ids = fields.Many2many(
        'res.company', 'al_industry_company_rel', 'industry_id', 'company_id',
        string='Aplicada en', readonly=True)

    _code_unique = models.Constraint('UNIQUE(code)', 'Ya hay una industria con ese código.')

    def _apply(self, company):
        """Configura ``company`` para el rubro, sin pisar lo que ya tiene."""
        for industry in self:
            if industry.ciiu_code:
                industry._apply_main_activity(company)
            if industry.planner_profile_xmlid:
                industry._apply_planner_profile(company)
            industry.company_ids = [Command.link(company.id)]

    def _apply_main_activity(self, company):
        self.ensure_one()
        Line = self.env['l10n_pe.partner.economic.activity']
        partner = company.partner_id
        if Line.search_count([('partner_id', '=', partner.id), ('kind', '=', 'principal')], limit=1):
            return
        activity = self.env['l10n_pe.economic.activity'].search(
            [('code', '=', self.ciiu_code)], limit=1)
        if activity:
            Line.create({'partner_id': partner.id, 'kind': 'principal', 'activity_id': activity.id})

    def _apply_planner_profile(self, company):
        self.ensure_one()
        profile = self.env.ref(self.planner_profile_xmlid, raise_if_not_found=False)
        if not profile or company.construction_profile_id:
            return
        # La parte del perfil que no instala módulos (los puentes ya son
        # dependencias del paquete): etapas, parámetros, planes analíticos y
        # plantilla de niveles de la compañía.
        profile._apply_configuration(company)

    @api.model
    def _apply_on_install(self, xmlid):
        """Llamado desde los datos (noupdate) de cada paquete al instalarse."""
        self.env.ref(xmlid)._apply(self.env.company)

    def action_apply_current_company(self):
        if not self.env.user.has_group('base.group_system'):
            raise UserError(self.env._('Solo un administrador aplica paquetes de industria.'))
        self._apply(self.env.company)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._('Configurado para %(company)s.', company=self.env.company.name),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
