# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # PLAME exige el nombre descompuesto y en orden Apellidos + Nombres;
    # los reportes leen employee.name, así que se mantiene sincronizado.
    names = fields.Char(string='Nombres')
    last_name = fields.Char(string='Apellido paterno')
    m_last_name = fields.Char(string='Apellido materno')
    condition = fields.Selection(
        [('domiciled', 'Domiciliado'), ('not_domiciled', 'No domiciliado')],
        string='Condición', default='domiciled',
        help='Condición de domicilio fiscal (afecta la retención de 5ta).')
    # Tipo de documento: nativo latam (con códigos SUNAT/AFP añadidos por
    # este módulo); el número va en el campo nativo identification_id.
    l10n_latam_identification_type_id = fields.Many2one(
        'l10n_latam.identification.type', string='Tipo de documento',
        domain="[('country_id.code', '=', 'PE')]")
    cts_bank_account_id = fields.Many2one(
        'res.partner.bank', string='Cuenta CTS',
        domain="[('partner_id', '=', work_contact_id)]",
        help='Cuenta de depósito de CTS; en Perú suele ser un banco '
             'distinto al de haberes.')

    # identification_id vive en hr.version en v19 (en el empleado es
    # related sin columna), así que la unicidad no puede ser SQL.
    @api.constrains('identification_id',
                    'l10n_latam_identification_type_id', 'company_id')
    def _check_identification_uniq(self):
        for employee in self.filtered('identification_id'):
            duplicate = self.with_context(active_test=False).search_count([
                ('id', '!=', employee.id),
                ('company_id', '=', employee.company_id.id),
                ('l10n_latam_identification_type_id', '=',
                 employee.l10n_latam_identification_type_id.id),
                ('identification_id', '=', employee.identification_id),
            ], limit=1)
            if duplicate:
                raise ValidationError(self.env._(
                    'Ya existe un empleado con ese tipo y número de '
                    'documento en la compañía.'))

    def _l10n_pe_full_name(self):
        self.ensure_one()
        return ' '.join(part for part in (
            (self.last_name or '').strip(),
            (self.m_last_name or '').strip(),
            (self.names or '').strip()) if part)

    @api.onchange('names', 'last_name', 'm_last_name')
    def _onchange_l10n_pe_full_name(self):
        for employee in self:
            if employee.names or employee.last_name or employee.m_last_name:
                employee.name = employee._l10n_pe_full_name()

    @api.model_create_multi
    def create(self, vals_list):
        # Los importadores pasan solo los campos descompuestos: recomponer
        # también fuera de la UI (el onchange no corre en create/write).
        for vals in vals_list:
            if not vals.get('name') and (
                    vals.get('names') or vals.get('last_name')):
                vals['name'] = ' '.join(part for part in (
                    (vals.get('last_name') or '').strip(),
                    (vals.get('m_last_name') or '').strip(),
                    (vals.get('names') or '').strip()) if part)
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in ('names', 'last_name', 'm_last_name')) \
                and 'name' not in vals:
            for employee in self:
                full = employee._l10n_pe_full_name()
                if full:
                    super(HrEmployee, employee).write({'name': full})
        return res


class L10nLatamIdentificationType(models.Model):
    _inherit = 'l10n_latam.identification.type'

    # Cierra la migración diferida F2-2 del refactor v18: los códigos
    # SUNAT (PLAME) y AFP (AFPNet) del tipo de documento se cuelgan del
    # catálogo latam nativo en vez del modelo propio hr.type.document.
    l10n_pe_hr_sunat_code = fields.Char(
        string='Código SUNAT (planillas)',
        help='Código del tipo de documento en la planilla electrónica '
             'PLAME.')
    l10n_pe_hr_afp_code = fields.Char(
        string='Código AFP',
        help='Código del tipo de documento en AFPNet.')
