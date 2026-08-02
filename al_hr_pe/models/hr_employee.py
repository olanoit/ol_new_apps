# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
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
    l10n_pe_dependent_ids = fields.One2many(
        'l10n_pe.hr.dependent', 'employee_id', string='Derechohabientes')
    l10n_pe_dependent_count = fields.Integer(
        string='N° de derechohabientes',
        compute='_compute_l10n_pe_dependent_count')

    @api.depends('l10n_pe_dependent_ids.date_end')
    def _compute_l10n_pe_dependent_count(self):
        today = fields.Date.context_today(self)
        for employee in self:
            employee.l10n_pe_dependent_count = len(
                employee.l10n_pe_dependent_ids.filtered(
                    lambda d: not d.date_end or d.date_end >= today))

    def _l10n_pe_has_family_allowance(self, on_date=None):
        """¿Corresponde asignación familiar (Ley 25129) en esa fecha?

        Si el trabajador tiene derechohabientes cargados, manda el dato
        real: hijos menores de 18, o de hasta 24 que cursen estudios
        superiores. Si todavía no se han cargado, se conserva el criterio
        anterior (el campo nativo ``children``) para no dejar sin
        asignación a quien la venía cobrando.
        """
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        dependents = self.sudo().l10n_pe_dependent_ids
        if dependents:
            return any(dependent._is_family_allowance_source(on_date)
                       for dependent in dependents)
        return bool(self.children)

    def action_open_l10n_pe_dependents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Derechohabientes de %s', self.display_name),
            'res_model': 'l10n_pe.hr.dependent',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

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
